#!/usr/bin/env python3
"""Test real Foot/ble.sh editing and fixture layouts using QMP keyboard events."""
import argparse
import json
from pathlib import Path
import time

from gui import experiment, key, type_text, capture
from qmp import Monitor
from session import ssh, graphical

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
monitor = Monitor(directory / 'qmp.sock')
report = {'cases': []}
try:
    if ssh(directory, 'pgrep -x swaylock || true').strip():
        raise ValueError('Unlock the graphical session before testing editor input')
    fixture = Path(__file__).with_name('fixtures') / 'shell-test.bash'
    ssh(directory, 'cat > ~/mini-os-shell-test.bash', fixture.read_text())
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] kill" || true')
    ssh(directory, 'rm -f ~/mini-os-shell-startup.txt')
    graphical(directory, 'swaymsg exec "foot --app-id=mini-os-edit bash --rcfile /home/vmuser/mini-os-shell-test.bash -i"')
    for _ in range(30):
        if ssh(directory, 'test ! -f ~/mini-os-shell-startup.txt || cat ~/mini-os-shell-startup.txt').strip():
            break
        time.sleep(.5)
    else:
        raise ValueError('Fresh Foot test shell did not start')
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] focus"; swaymsg "[app_id=mini-os-edit] fullscreen enable"; swaymsg "input type:keyboard xkb_switch_layout 0"')
    # Focus the fresh fixture shell with US selected.
    startup = ssh(directory, 'cat ~/mini-os-shell-startup.txt').splitlines()
    if len(startup) != 2 or not startup[0].startswith('0.4') or startup[1] != 'true':
        raise ValueError('Fresh interactive shell did not load both integrations')
    report['startup'] = startup
    cases = [
        ('one character', 'echo alpha', ['backspace'], 'echo alph'),
        ('path and underscore', 'cat /tmp/foo_bar', ['ctrl', 'backspace'], 'cat '),
        ('underscore', 'echo foo_bar', ['ctrl', 'backspace'], 'echo '),
        ('single quoted word', "echo 'hello'", ['ctrl', 'backspace'], 'echo '),
        ('quoted word with spaces', "echo 'two words'", ['ctrl', 'backspace'], "echo 'two "),
    ]
    for name, text, keys, expected in cases:
        time.sleep(1)
        key(monitor, ['ctrl', 'a'])
        key(monitor, ['ctrl', 'k'])
        time.sleep(0.5)
        type_text(monitor, text)
        key(monitor, keys)
        time.sleep(0.5)
        ssh(directory, 'rm -f ~/mini-os-edit-result.txt')
        key(monitor, ['ctrl', 'f12'])
        time.sleep(1)
        actual = ssh(directory, 'cat ~/mini-os-edit-result.txt')
        report['cases'].append({'name': name, 'input': text, 'expected': expected, 'actual': actual, 'passed': actual == expected})
        if actual != expected: raise ValueError('Unexpected editing result: ' + name)
    key(monitor, ['ctrl', 'a'])
    key(monitor, ['ctrl', 'k'])
    time.sleep(1)
    key(monitor, ['alt', 'shift'])
    type_text(monitor, 'ghbdtn')
    key(monitor, ['backspace'])
    ssh(directory, 'rm -f ~/mini-os-edit-result.txt')
    key(monitor, ['ctrl', 'f12'])
    time.sleep(1)
    actual = ssh(directory, 'cat ~/mini-os-edit-result.txt')
    report['russian_backspace'] = actual
    if actual != 'приве': raise ValueError('Russian input/backspace did not change actual text')
    time.sleep(1)
    key(monitor, ['ctrl', 'backspace'])
    ssh(directory, 'rm -f ~/mini-os-edit-result.txt')
    key(monitor, ['ctrl', 'f12'])
    time.sleep(1)
    actual = ssh(directory, 'cat ~/mini-os-edit-result.txt')
    if actual != '': raise ValueError('Russian Ctrl+Backspace did not delete the word')
    report['russian_ctrl_backspace'] = True
    key(monitor, ['alt', 'shift'])
    capture(monitor, directory, 'shell-editing')
    report['passed'] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    monitor.close()
    (directory / 'shell-editing-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))
