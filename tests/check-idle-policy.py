#!/usr/bin/env python3
"""Check charger detection and idle-process transitions without host changes."""
import ast
import configparser
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
from unittest.mock import Mock, patch


project = Path(__file__).resolve().parents[1]
policy = runpy.run_path(str(project / 'setup/desktop/minion-idle'))
supervise = policy['supervise']

# AC disables inactivity timers; it must never disable lid-close suspend.
tree = ast.parse((project / 'setup/desktop/provision.py').read_text())
lid_policy = [ast.literal_eval(node.args[1]) for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == 'write' and node.args
              and isinstance(node.args[0], ast.Constant)
              and node.args[0].value == '/etc/systemd/logind.conf.d/60-minion-power.conf']
assert len(lid_policy) == 1
config = configparser.ConfigParser()
config.read_string(lid_policy[0])
for setting in ('HandleLidSwitch', 'HandleLidSwitchExternalPower', 'HandleLidSwitchDocked'):
    assert config['Login'][setting] == 'suspend'

with tempfile.TemporaryDirectory() as temporary:
    supplies = Path(temporary)

    def supply(name, **attributes):
        directory = supplies / name
        directory.mkdir(exist_ok=True)
        for key, value in attributes.items():
            (directory / key).write_text(value)
        return directory

    supply('BAT0', type='Battery', online='1', status='Full')
    assert not policy['external_power'](supplies)
    ac = supply('AC', type='Mains', online='0')
    assert not policy['external_power'](supplies)
    (ac / 'online').write_text('1')
    assert policy['external_power'](supplies)
    (ac / 'online').write_text('0')
    usb = supply('USB', type='USB', online='1', scope='Device')
    assert not policy['external_power'](supplies)
    (usb / 'scope').write_text('System')
    assert policy['external_power'](supplies)
    (usb / 'online').unlink()
    supply('incomplete', online='1')
    assert not policy['external_power'](supplies)

ac_command = policy['idle_command'](True)
battery_command = policy['idle_command'](False)
assert ac_command == ['/usr/bin/swayidle', '-w', 'before-sleep', 'minion-lock']
assert policy['idle_command'](False, True) == ac_command
assert policy['idle_command'](True, True) == ac_command
assert battery_command == ['/usr/bin/swayidle', '-w',
                           'timeout', '300', 'minion-lock',
                           'timeout', '600', 'swaymsg "output * power off"',
                           'resume', 'swaymsg "output * power on"',
                           'before-sleep', 'minion-lock']

# swayidle executes commands through /bin/sh. Preserve the output wildcard
# even when its working directory contains filenames (as a real home does).
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    (directory / 'Documents').mkdir()
    (directory / 'Downloads').mkdir()
    stub = directory / 'swaymsg'
    stub.write_text('#!/usr/bin/python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
    stub.chmod(0o755)
    environment = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ.get('PATH', ''))
    for command, expected in ((battery_command[7], 'output * power off'),
                              (battery_command[9], 'output * power on')):
        result = subprocess.run(['/bin/sh', '-c', command], cwd=directory,
                                env=environment, capture_output=True, text=True, check=True)
        assert json.loads(result.stdout) == [expected]


class StopAfter:
    def __init__(self, count):
        self.remaining = count

    def is_set(self):
        return self.remaining == 0

    def wait(self, seconds):
        assert seconds == 2
        self.remaining -= 1


children = [Mock(), Mock(), Mock()]
for child in children:
    child.poll.return_value = None
with patch.dict(supervise.__globals__, external_power=Mock(side_effect=[False, False, True, True, False]), keep_awake=Mock(return_value=False)), \
        patch.object(subprocess, 'Popen', side_effect=children) as popen, \
        patch.object(subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
    supervise(StopAfter(5))
assert [call.args[0] for call in popen.call_args_list] == [battery_command, ac_command, battery_command]
run.assert_called_once_with(['swaymsg', 'output', '*', 'power', 'on'], check=True, timeout=5)
for child in children:
    child.terminate.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=3)

# Keep awake survives charger changes, retains before-sleep locking and
# restores fresh battery timers when disabled. Toggling alone never wakes a panel.
children = [Mock() for _ in range(5)]
for child in children:
    child.poll.return_value = None
with patch.dict(supervise.__globals__,
                external_power=Mock(side_effect=[False, False, True, False, False]),
                keep_awake=Mock(side_effect=[False, True, True, True, False])), \
        patch.object(subprocess, 'Popen', side_effect=children) as popen, \
        patch.object(subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
    supervise(StopAfter(5))
assert [call.args[0] for call in popen.call_args_list] == [battery_command, ac_command, ac_command, ac_command, battery_command]
run.assert_called_once_with(['swaymsg', 'output', '*', 'power', 'on'], check=True, timeout=5)
for child in children:
    child.terminate.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=3)

# CLI controls use runtime state only; they never lock, suspend or modify logind.
controls = runpy.run_path(str(project / 'setup/desktop/minion-idle-controls'))
with tempfile.TemporaryDirectory() as temporary, \
        patch.dict(os.environ, XDG_RUNTIME_DIR=temporary), \
        patch.object(subprocess, 'check_output', return_value='[{"power":true}]'), \
        patch.object(subprocess, 'run') as run:
    assert not policy['keep_awake']()
    assert controls['toggle_awake']() is True
    assert policy['keep_awake']()
    assert controls['toggle_awake']() is False
    assert not policy['keep_awake']()
    assert (Path(temporary) / 'minion-idle/keep-awake').stat().st_mode & 0o777 == 0o600
    assert all(call.args[0][0] == 'notify-send' for call in run.call_args_list)
    run.reset_mock()
    controls['display_power'](False)
    assert run.call_args_list[0].args[0] == ['systemctl', '--user', 'kill', '--kill-who=main',
                                           '--signal=SIGUSR1', 'minion-display-wake.service']
    assert run.call_args_list[1].args[0] == ['swaymsg', 'output', '*', 'power', 'off']
    run.reset_mock()
    controls['display_power'](True)
    assert run.call_count == 1 and run.call_args.args[0] == ['swaymsg', 'output', '*', 'power', 'on']
    # Fail before powering off if no independent input-wake listener is running.
    run.reset_mock()
    run.side_effect = subprocess.CalledProcessError(1, 'systemctl')
    try:
        controls['display_power'](False)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Display-off ignored a missing wake listener')
    assert run.call_count == 1

# Scope both press and release to the rear keyboard so Print on the physical
# keyboard keeps its screenshot binding. No power-button policy is introduced.
sway_config = (project / 'setup/desktop/sway.conf').read_text()
assert 'bindsym --to-code $mod+l exec minion-lock' in sway_config
for key, command in [('Print', 'off'), ('Pause', 'toggle-awake')]:
    matches = [line for line in sway_config.splitlines()
               if line.startswith('bindsym --input-device=12068:309:Mouse_for_Windows') and f' {key} ' in line]
    assert len(matches) == 2
    assert all('--no-repeat' in line for line in matches)
    assert any(line.endswith(f'{key} nop') for line in matches)
    assert all(line.endswith(f'{key} nop') for line in matches)
    assert any('--release' in line for line in matches)
assert 'XF86PowerOff' not in sway_config
assert not config.has_option('Login', 'HandlePowerKey')
physical = 'bindsym --input-device=1:1:AT_Translated_Set_2_keyboard'
fn_bindings = [line for line in sway_config.splitlines() if line.startswith(physical)]
assert any('XF86AudioStop exec minion-idle-controls display-press' in line and '--locked' in line for line in fn_bindings)
assert any('XF86AudioStop exec minion-idle-controls display-release' in line and '--release' in line for line in fn_bindings)
assert any('XF86AudioPrev exec minion-idle-controls toggle-awake' in line and '--locked' not in line for line in fn_bindings)
for key in ('XF86AudioPlay', 'XF86AudioPause', 'XF86AudioNext'):
    assert any(line.endswith(key + ' nop') for line in fn_bindings)
assert all('--no-repeat' in line for line in fn_bindings)

# Fn+F3 snapshots state on press and acts on release, including a long hold
# after input has already woken a dark screen. A wake marker is consumed once.
toggle_display = controls['display_toggle']
with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_RUNTIME_DIR=temporary), \
        patch.object(subprocess, 'check_output', return_value='[{"power":true}]'), \
        patch.dict(toggle_display.__globals__, display_power=Mock()) as scope:
    power = toggle_display.__globals__['display_power']
    toggle_display('press')
    toggle_display('release')
    power.assert_called_once_with(False)
    power.reset_mock()
    directory = Path(temporary) / 'minion-idle'
    with patch.object(controls['time'], 'monotonic', return_value=50):
        (directory / 'last-display-wake').write_text('49.9')
        toggle_display('press')
    with patch.object(controls['time'], 'monotonic', return_value=55):
        toggle_display('release')
    power.assert_called_once_with(True)
    assert not (directory / 'last-display-wake').exists()
    power.reset_mock()
    toggle_display('press'); toggle_display('release')
    power.assert_called_once_with(False)
    power.reset_mock()
    with patch.object(subprocess, 'check_output', return_value='[{"power":false}]'):
        toggle_display('press'); toggle_display('release')
    power.assert_called_once_with(True)

# Firmware can repeat both Linux value=2 events and entire press/release
# macros. All repetitions form one hold; genuine subsequent taps still work.
rear = runpy.run_path(str(project / 'setup/desktop/minion-rear-buttons'))
for key in (99, 119):
    for repeats in (0, 1, 10, 100):
        actions = []
        buttons = rear['Buttons'](actions.append)
        now = 0.
        buttons.event(key, 1, now)
        for _ in range(repeats):
            now += .3
            buttons.event(key, 2, now)
            buttons.event(key, 0, now)
            buttons.tick(now + .02)
            buttons.event(key, 1, now + .02)
            buttons.tick(now + .15)
            assert actions == (['cancel'] if key == 119 and now + .15 >= .75 else []), actions
        buttons.event(key, 0, now + .3)
        buttons.tick(now + .4)
        expected = [] if key == 99 else ['cancel'] if now + .3 >= .75 else ['toggle']
        assert actions == expected, actions
        buttons.tick(now + 2)
        assert actions == expected
        buttons.event(key, 1, now + 3)
        buttons.event(key, 0, now + 3.3)
        buttons.tick(now + 3.4)
        assert actions == expected + ([] if key == 99 else ['toggle'])

# A true continuous hold cancels before release, once only. Grace time alone
# cannot turn a sub-threshold tap into cancellation.
for duration, expected in [(.74, 'toggle'), (.75, 'cancel'), (3., 'cancel')]:
    actions = []
    buttons = rear['Buttons'](actions.append)
    buttons.event(119, 1, 0)
    buttons.tick(duration)
    assert actions == ([] if duration < .75 else ['cancel'])
    buttons.event(119, 0, duration)
    buttons.tick(duration + .08)
    buttons.tick(duration + 10)
    assert actions == [expected]
actions = []
buttons = rear['Buttons'](actions.append)
buttons.event(119, 1, 0); buttons.event(119, 0, .1)
buttons.event(119, 1, .2); buttons.event(119, 0, .3); buttons.tick(.4)
assert actions == ['toggle', 'toggle']  # Even when a new press precedes the next poll.

with patch.dict(rear['action'].__globals__, active_session=Mock(return_value=False)), \
        patch.object(subprocess, 'Popen') as popen:
    rear['action']('toggle')
    popen.assert_not_called()
with patch.dict(rear['action'].__globals__, active_session=Mock(return_value=True)), \
        patch.object(subprocess, 'run', return_value=Mock(returncode=0)), \
        patch.object(subprocess, 'Popen') as popen:
    rear['action']('toggle')
    popen.assert_not_called()
with patch.dict(rear['action'].__globals__, active_session=Mock(return_value=True)), \
        patch.object(subprocess, 'run', return_value=Mock(returncode=3)), \
        patch.object(subprocess, 'Popen') as popen:
    rear['action']('cancel')
    assert popen.call_args.args[0] == ['minion-voice', 'cancel']

# An unexpected swayidle exit must reach systemd's Restart=on-failure path.
child = Mock()
child.poll.return_value = 1
with patch.dict(supervise.__globals__, external_power=Mock(return_value=False), keep_awake=Mock(return_value=False)), \
        patch.object(subprocess, 'Popen', return_value=child), contextlib.redirect_stdout(io.StringIO()):
    try:
        supervise(StopAfter(2))
    except RuntimeError as error:
        assert str(error) == 'swayidle exited unexpectedly'
    else:
        raise AssertionError('Unexpected child exit was ignored')
child.wait.assert_called_once_with(timeout=3)

# A stuck child cannot prevent a power-source transition indefinitely.
child = Mock()
child.poll.return_value = None
child.wait.side_effect = [subprocess.TimeoutExpired('swayidle', 3), 0]
policy['stop_child'](child)
child.terminate.assert_called_once_with()
child.kill.assert_called_once_with()
assert child.wait.call_count == 2

print('Idle policy checks passed: lid suspend on every power source, charger detection, AC/battery transitions, cleanup and failure handling.')
