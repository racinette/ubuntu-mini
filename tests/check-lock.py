#!/usr/bin/env python3
"""Verify a real Sway lock rejects a wrong password and accepts the user password."""
import argparse
import json
import time

from gui import experiment, key, type_text, capture
from qmp import Monitor
from session import graphical, ssh

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
credentials = json.loads(directory.joinpath('credentials.json').read_text())
monitor = Monitor(directory / 'qmp.sock')
report = {}
try:
    if ssh(directory, 'pgrep -x swaylock || true').strip():
        raise ValueError('Begin this test with the session unlocked')
    # Pause the timer BEFORE locking; stopping its cgroup while locked kills the locker.
    ssh(directory, 'systemctl --user stop mini-os-idle.service')
    graphical(directory, 'swaymsg "input type:keyboard xkb_switch_layout 0"; swaymsg "exec mini-os-lock"')
    time.sleep(1)
    if not ssh(directory, 'pgrep -x swaylock || true').strip(): raise ValueError('Locker did not start')
    report['locker_started'] = True
    capture(monitor, directory, 'screen-lock')
    type_text(monitor, 'incorrect-lock-password\n')
    time.sleep(5)  # PAM's failure delay must finish before the next input attempt.
    if not ssh(directory, 'pgrep -x swaylock || true').strip(): raise ValueError('Incorrect password unlocked')
    report['wrong_password_refused'] = True
    capture(monitor, directory, 'screen-lock-wrong-password')
    key(monitor, ['ctrl', 'u'])
    type_text(monitor, credentials['login_password'] + '\n')
    time.sleep(3)
    if ssh(directory, 'pgrep -x swaylock || true').strip(): raise ValueError('Correct password did not unlock')
    report['correct_password_unlocked'] = True
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] focus"')
    capture(monitor, directory, 'screen-unlocked')
    report['passed'] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    monitor.close()
    (directory / 'screen-lock-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
