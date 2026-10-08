#!/usr/bin/env python3
"""Test greetd password refusal and a fresh authenticated graphical session."""
import argparse
import json
from pathlib import Path
import time

from gui import experiment, key, type_text, capture
from qmp import Monitor
from session import ssh

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
if ssh(directory, 'pgrep -x sway || true').strip():
    raise SystemExit('Log out before testing a fresh login')
monitor = Monitor(directory / 'qmp.sock')
report = {}
try:
    key(monitor, ['ctrl', 'u'])
    type_text(monitor, 'vmuser\n')
    time.sleep(1)
    type_text(monitor, 'intentionally-wrong-login-password\n')
    time.sleep(5)
    report['wrong_password_refused'] = not ssh(directory, 'pgrep -x sway || true').strip()
    if not report['wrong_password_refused']:
        raise ValueError('A compositor started after the wrong password')
    capture(monitor, directory, 'greeter-wrong-password')
    type_text(monitor, 'vmuser\n')
    time.sleep(1)
    credentials = json.loads(directory.joinpath('credentials.json').read_text())
    type_text(monitor, credentials['login_password'] + '\n')
    for _ in range(20):
        if ssh(directory, 'pgrep -x sway || true').strip():
            break
        time.sleep(.5)
    else:
        raise ValueError('Correct password did not start Sway')
    time.sleep(2)
    report['correct_password_started_sway'] = True
    capture(monitor, directory, 'fresh-desktop-login')
    report['passed'] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    monitor.close()
    directory.joinpath('graphical-login-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
