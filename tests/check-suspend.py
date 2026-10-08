#!/usr/bin/env python3
"""Exercise guest suspend/wake and authentication without stopping its locker."""
import argparse
import json
import subprocess
import time

from gui import experiment, type_text, key, capture
from qmp import Monitor
from session import ssh, graphical

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
state = json.loads(directory.joinpath('state.json').read_text())
credentials = json.loads(directory.joinpath('credentials.json').read_text())
monitor = Monitor(directory / 'qmp.sock')
report = {}
try:
    if ssh(directory, 'pgrep -x swaylock || true').strip():
        raise ValueError('Unlock before the suspend check')
    graphical(directory, 'swaymsg "input type:keyboard xkb_switch_layout 0"')
    result = subprocess.run(['ssh', '-i', str(directory / 'ssh-key'), '-p', str(state['ssh_port']),
        '-o', 'BatchMode=yes', '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'),
        'vmuser@127.0.0.1', 'sudo -k -S -p "" systemctl --no-block suspend'],
        input=credentials['login_password'] + '\n', text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr)
    for _ in range(40):
        if monitor.execute('query-status')['status'] == 'suspended':
            break
        time.sleep(.5)
    else:
        raise ValueError('QEMU did not reach suspended state')
    report['qemu_suspended'] = True
    capture(monitor, directory, 'suspended')
    monitor.execute('system_wakeup')
    time.sleep(3)
    report['locker_present_after_wake'] = bool(ssh(directory, 'pgrep -x swaylock || true').strip())
    if not report['locker_present_after_wake']:
        raise ValueError('No locker after wake')
    capture(monitor, directory, 'resume-locked')
    type_text(monitor, 'wrong-resume-password\n')
    time.sleep(5)
    report['wrong_password_refused'] = bool(ssh(directory, 'pgrep -x swaylock || true').strip())
    if not report['wrong_password_refused']:
        raise ValueError('Wrong password unlocked after wake')
    key(monitor, ['ctrl', 'u'])
    type_text(monitor, credentials['login_password'] + '\n')
    time.sleep(3)
    report['correct_password_unlocked'] = not ssh(directory, 'pgrep -x swaylock || true').strip()
    if not report['correct_password_unlocked']:
        raise ValueError('Correct password did not unlock after wake')
    capture(monitor, directory, 'resume-unlocked')
    report['passed'] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    monitor.close()
    directory.joinpath('suspend-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
