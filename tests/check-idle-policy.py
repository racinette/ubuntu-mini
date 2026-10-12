#!/usr/bin/env python3
"""Check charger detection and idle-process transitions without host changes."""
import ast
import configparser
import contextlib
import io
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
assert battery_command == ['/usr/bin/swayidle', '-w',
                           'timeout', '300', 'minion-lock',
                           'timeout', '600', 'swaymsg output * power off',
                           'resume', 'swaymsg output * power on',
                           'before-sleep', 'minion-lock']


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
with patch.dict(supervise.__globals__, external_power=Mock(side_effect=[False, False, True, True, False])), \
        patch.object(subprocess, 'Popen', side_effect=children) as popen, \
        patch.object(subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
    supervise(StopAfter(5))
assert [call.args[0] for call in popen.call_args_list] == [battery_command, ac_command, battery_command]
run.assert_called_once_with(['swaymsg', 'output', '*', 'power', 'on'], check=True, timeout=5)
for child in children:
    child.terminate.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=3)

# An unexpected swayidle exit must reach systemd's Restart=on-failure path.
child = Mock()
child.poll.return_value = 1
with patch.dict(supervise.__globals__, external_power=Mock(return_value=False)), \
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
