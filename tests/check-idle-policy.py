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

# logind remains a safe fallback outside the desktop session.
# The running idle service owns lid handling so Awake can suppress lid sleep.
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
                           'timeout', '600', 'minion-idle-controls idle-off',
                           'resume', 'minion-idle-controls wake',
                           'before-sleep', 'minion-lock']

# Every automatic display-on path must use the guarded control, not raw IPC.
wake_service = (project / 'setup/desktop/minion-display-wake.service').read_text()
assert 'resume "minion-idle-controls wake"' in wake_service
assert 'after-resume "minion-idle-controls wake"' in wake_service
assert '--what=handle-lid-switch --mode=block' in (project / 'setup/desktop/provision.py').read_text()


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
run.assert_called_once_with(['minion-idle-controls', 'wake'], check=True, timeout=5)
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
run.assert_called_once_with(['minion-idle-controls', 'wake'], check=True, timeout=5)
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
    assert run.call_count == 1
    assert run.call_args.args[0] == ['swaymsg', 'output', '*', 'power', 'off']
    directory = Path(temporary) / 'minion-idle'
    assert (directory / 'manual-display-off').exists()
    run.reset_mock()
    controls['display_power'](True, automatic=True)
    run.assert_not_called()  # Activity, AC, resume cannot undo manual blanking.
    controls['display_power'](True)
    assert run.call_args.args[0] == ['swaymsg', 'output', '*', 'power', 'on']
    assert not (directory / 'manual-display-off').exists()
    run.reset_mock()
    controls['display_power'](False, automatic=True)
    assert not (directory / 'manual-display-off').exists()
    controls['display_power'](True, automatic=True)
    assert run.call_count == 2  # Ordinary idle blanking still wakes on activity.

# Lid blanking is independent of manual blanking; no wake path defeats it.
with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_RUNTIME_DIR=temporary), \
        patch.object(subprocess, 'check_output', return_value='[{"power":false}]'), \
        patch.object(subprocess, 'run') as run, \
        patch.dict(controls['lid_changed'].__globals__, lid_keyboard=Mock()) as scope:
    keyboard = controls['lid_changed'].__globals__['lid_keyboard']
    directory = controls['state_directory']()
    (directory / 'keep-awake').write_text('1')
    controls['lid_changed'](True)
    keyboard.assert_called_once_with(True)
    assert [c.args[0] for c in run.call_args_list] == [['swaymsg', 'output', '*', 'power', 'off']]
    run.reset_mock()
    controls['display_power'](True, automatic=True)
    controls['display_power'](True)
    run.assert_not_called()
    controls['lid_changed'](False)
    keyboard.assert_called_with(False)
    assert run.call_args.args[0] == ['swaymsg', 'output', '*', 'power', 'on']
    controls['display_power'](False)
    controls['lid_changed'](True)
    run.reset_mock()
    controls['lid_changed'](False)
    controls['display_power'](True, automatic=True)
    run.assert_not_called()  # Opening the lid preserves explicit Fn+F3 blanking.
    controls['display_power'](True)
    assert not (directory / 'manual-display-off').exists()
    (directory / 'keep-awake').write_text('0')
    run.reset_mock()
    controls['lid_changed'](True)
    assert [c.args[0] for c in run.call_args_list] == [
        ['swaymsg', 'output', '*', 'power', 'off'], ['minion-lock'], ['systemctl', 'suspend']]
    # A quick reopening while lock starts must not cause a delayed suspend.
    run.reset_mock()
    def reopen_during_lock(command, **_):
        if command == ['minion-lock']:
            (directory / 'lid-closed').unlink()
    run.side_effect = reopen_during_lock
    controls['lid_changed'](True)
    assert all(c.args[0] != ['systemctl', 'suspend'] for c in run.call_args_list)
    # Refuse to suspend if authentication lock fails.
    run.reset_mock()
    run.side_effect = [None, subprocess.CalledProcessError(1, 'minion-lock')]
    try:
        controls['lid_changed'](True)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Lid suspend ignored failed lock')
    assert run.call_count == 2

# Disable only the built-in keyboard. Repeated close events preserve the
# original setting, and an unsuccessful restore keeps it for a later retry.
with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_RUNTIME_DIR=temporary):
    identifier = controls['BUILTIN_KEYBOARD']
    for original in ('enabled', 'disabled'):
        inputs = [dict(identifier=identifier, libinput=dict(send_events=original)),
                  dict(identifier='external-keyboard', libinput=dict(send_events='enabled'))]
        def keyboard_ipc(command, **_):
            return json.dumps(inputs) if command[-1] == 'get_inputs' else '[{"success":true}]'
        with patch.object(subprocess, 'check_output', side_effect=keyboard_ipc) as ipc:
            controls['lid_keyboard'](True)
            saved = controls['state_directory']() / 'lid-keyboard-events'
            assert saved.read_text() == original and saved.stat().st_mode & 0o777 == 0o600
            controls['lid_keyboard'](True)
            assert saved.read_text() == original
            assert sum(c.args[0][-1] == 'get_inputs' for c in ipc.call_args_list) == 1
            with patch.object(subprocess, 'check_output', return_value='[{"success":false}]'):
                try:
                    controls['lid_keyboard'](False)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('Failed keyboard restore was accepted')
            assert saved.exists()
            controls['lid_keyboard'](False)
            assert not saved.exists()
            assert ipc.call_args.args[0][-1] == f'input "{identifier}" events {original}'
            assert all('external-keyboard' not in c.args[0][-1] for c in ipc.call_args_list)
            ipc.reset_mock()
            controls['lid_keyboard'](False)
            ipc.assert_not_called()
    with patch.object(subprocess, 'check_output', return_value='[]') as ipc:
        controls['lid_keyboard'](True)
        ipc.assert_called_once()

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
assert 'bindswitch --locked lid:on exec minion-idle-controls lid-close' in sway_config
assert 'bindswitch --locked lid:off exec minion-idle-controls lid-open' in sway_config
assert 'XF86PowerOff' not in sway_config
assert not config.has_option('Login', 'HandlePowerKey')
physical = 'bindsym --input-device=1:1:AT_Translated_Set_2_keyboard'
fn_bindings = [line for line in sway_config.splitlines() if line.startswith(physical)]
assert any('XF86AudioStop exec minion-idle-controls display-press' in line and '--locked' in line for line in fn_bindings)
assert any('XF86AudioStop exec minion-idle-controls display-release' in line and '--release' in line for line in fn_bindings)
assert any('XF86AudioPrev exec minion-idle-controls toggle-awake' in line and '--locked' not in line for line in fn_bindings)
for key in ('XF86AudioPlay', 'XF86AudioPause'):
    assert any(line.endswith(key + ' exec minion-idle-controls toggle-refresh') for line in fn_bindings)
assert any(line.endswith('XF86AudioNext nop') for line in fn_bindings)
assert all('--no-repeat' in line for line in fn_bindings)
assert sway_config.index('include ~/.config/sway/minion-refresh.conf') < sway_config.index('include ~/.config/sway/minion.conf')

# Select only advertised modes at the current native resolution, persist only
# successful readback, and restore the old mode after a switch/write failure.
with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_RUNTIME_DIR=temporary):
    directory = Path(temporary)
    preference = directory / 'config/sway/minion-refresh.conf'
    low = dict(width=1080, height=1920, refresh=60012)
    high = dict(width=1080, height=1920, refresh=120007)
    panel = dict(name='eDP-1', active=True, current_mode=dict(low), scale=2, transform='90',
                 modes=[dict(width=1920, height=1080, refresh=120000), low, high])
    commands = []
    behavior = {'reject': False, 'wrong_readback': False}

    def display_command(command, **kwargs):
        if command[-1] == 'get_outputs':
            return json.dumps([dict(name='HDMI-A-1', active=True, current_mode=high), panel])
        commands.append(command[-1])
        if behavior['reject'] and '@120.007Hz' in command[-1]:
            return '[{"success":false}]'
        if not behavior['wrong_readback']:
            panel['current_mode'] = dict(high if '@120.007Hz' in command[-1] else low)
        return '[{"success":true}]'

    with patch.object(subprocess, 'check_output', side_effect=display_command), \
            patch.object(subprocess, 'run') as notify:
        assert controls['toggle_refresh'](preference) == 120
        assert panel['current_mode'] == high and panel['scale'] == 2 and panel['transform'] == '90'
        assert preference.read_text().endswith('output eDP-1 mode 1080x1920@120.007Hz transform 90 scale 2\n')
        assert preference.stat().st_mode & 0o777 == 0o600
        assert controls['toggle_refresh'](preference) == 60
        original = preference.read_bytes()
        assert preference.read_text().endswith('output eDP-1 mode 1080x1920@60.012Hz transform 90 scale 2\n')
        for failure in ('reject', 'wrong_readback', 'write'):
            behavior.update(reject=failure == 'reject', wrong_readback=failure == 'wrong_readback')
            with patch.object(Path, 'replace', side_effect=OSError('fixture disk failure')) if failure == 'write' else contextlib.nullcontext():
                try:
                    controls['toggle_refresh'](preference)
                except (RuntimeError, OSError):
                    pass
                else:
                    raise AssertionError('Failed refresh switch was accepted')
            assert preference.read_bytes() == original and panel['current_mode'] == low
            assert commands[-1].endswith('@60.012Hz')
        behavior.update(reject=False, wrong_readback=False)
        for invalid in ('unsupported', 'inactive', 'personal', 'symlink'):
            commands.clear()
            panel['modes'] = [low] if invalid == 'unsupported' else [low, high]
            panel['active'] = invalid != 'inactive'
            preference.write_bytes(original if invalid != 'personal' else b'# Personal configuration\n')
            link = directory / 'link'
            link.symlink_to(preference)
            candidate = link if invalid == 'symlink' else preference
            before = preference.read_bytes()
            try:
                controls['toggle_refresh'](candidate)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Invalid refresh preference or display accepted')
            assert preference.read_bytes() == before and not commands
            link.unlink()

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

with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_RUNTIME_DIR=temporary):
    marker = Path(temporary) / 'minion-idle/lid-closed'
    marker.parent.mkdir()
    assert not rear['lid_closed']()
    marker.touch()
    assert rear['lid_closed']()
    with patch.dict(rear['action'].__globals__, active_session=Mock(return_value=True)), \
            patch.object(subprocess, 'run') as run, patch.object(subprocess, 'Popen') as popen:
        rear['action']('toggle')
        rear['action']('cancel')
        run.assert_not_called()
        popen.assert_not_called()

with patch.dict(rear['action'].__globals__, lid_closed=Mock(return_value=False), active_session=Mock(return_value=False)), \
        patch.object(subprocess, 'Popen') as popen:
    rear['action']('toggle')
    popen.assert_not_called()
with patch.dict(rear['action'].__globals__, lid_closed=Mock(return_value=False), active_session=Mock(return_value=True)), \
        patch.object(subprocess, 'run', return_value=Mock(returncode=0)), \
        patch.object(subprocess, 'Popen') as popen:
    rear['action']('toggle')
    popen.assert_not_called()
with patch.dict(rear['action'].__globals__, lid_closed=Mock(return_value=False), active_session=Mock(return_value=True)), \
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

print('Idle policy checks passed: Awake-aware lid handling, persistent manual blanking, charger detection, AC/battery transitions, cleanup and failure handling.')
