#!/usr/bin/env python3
"""Exercise the session's idle service with a temporary ten-second VM timeout."""
import argparse
import json
import time

from gui import experiment, type_text, key, capture
from qmp import Monitor
from session import ssh, graphical

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
credentials = json.loads(directory.joinpath('credentials.json').read_text())
override = '~/.config/systemd/user/mini-os-idle.service.d/vm-test.conf'
if ssh(directory, 'pgrep -x swaylock || true').strip():
    raise SystemExit('Unlock before testing idle locking')
ssh(directory, 'mkdir -p ~/.config/systemd/user/mini-os-idle.service.d; cat > ' + override,
    '[Service]\nExecStart=\nExecStart=/usr/bin/swayidle -w timeout 10 /usr/local/bin/mini-os-lock\n')
graphical(directory, 'swaymsg "input type:keyboard xkb_switch_layout 0"; systemctl --user daemon-reload; systemctl --user restart mini-os-idle.service')
monitor = Monitor(directory / 'qmp.sock')
report = {'vm_timeout_seconds': 10, 'normal_timeout_seconds': 300}
try:
    for _ in range(30):
        if ssh(directory, 'pgrep -x swaylock || true').strip():
            break
        time.sleep(.5)
    else:
        raise ValueError('Idle service did not create a locker')
    report['idle_created_locker'] = True
    capture(monitor, directory, 'idle-locked')
    type_text(monitor, 'wrong-idle-password\n')
    time.sleep(5)
    report['wrong_password_refused'] = bool(ssh(directory, 'pgrep -x swaylock || true').strip())
    if not report['wrong_password_refused']:
        raise ValueError('Wrong password unlocked the idle lock')
    key(monitor, ['ctrl', 'u'])
    type_text(monitor, credentials['login_password'] + '\n')
    for _ in range(10):
        if not ssh(directory, 'pgrep -x swaylock || true').strip():
            break
        time.sleep(.2)
    else:
        raise ValueError('Correct password did not unlock')
    report['correct_password_unlocked'] = True
    report['passed'] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    monitor.close()
    # Stopping a service while its forked locker is alive abandons the lock.
    if not ssh(directory, 'pgrep -x swaylock || true').strip():
        graphical(directory, 'systemctl --user stop mini-os-idle.service; rm -f ' + override +
                  '; systemctl --user daemon-reload; systemctl --user start mini-os-idle.service')
        report['normal_policy_restored'] = True
    else:
        report['normal_policy_restored'] = False
        report['passed'] = False
    directory.joinpath('idle-lock-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
