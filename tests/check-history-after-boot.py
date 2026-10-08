#!/usr/bin/env python3
"""Accept a pre-reboot history suggestion in a fresh authenticated Foot shell."""
import argparse
import json
from pathlib import Path
import time

from gui import experiment, key, type_text, capture
from qmp import Monitor
from session import ssh, graphical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    args = parser.parse_args()
    directory = experiment.select_directory(args.directory)
    history = json.loads((directory / 'history-report.json').read_text())
    if not history.get('passed'):
        raise ValueError('A passing offline history test is required before reboot')
    expected = 'echo ' + history['marker']
    fixture = Path(__file__).with_name('fixtures') / 'shell-test.bash'
    ssh(directory, 'cat > ~/mini-os-shell-test.bash', fixture.read_text())
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] kill" || true')
    ssh(directory, 'rm -f ~/mini-os-shell-startup.txt ~/mini-os-edit-result.txt')
    graphical(directory, 'swaymsg exec "foot --app-id=mini-os-edit bash --rcfile /home/vmuser/mini-os-shell-test.bash -i"')
    for _ in range(30):
        startup = ssh(directory, 'test ! -f ~/mini-os-shell-startup.txt || cat ~/mini-os-shell-startup.txt').splitlines()
        if len(startup) == 2:
            break
        time.sleep(.5)
    else:
        raise TimeoutError('Fresh Foot shell did not load')
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] focus"; swaymsg "[app_id=mini-os-edit] fullscreen enable"; swaymsg "input type:keyboard xkb_switch_layout 0"')
    monitor = Monitor(directory / 'qmp.sock')
    try:
        type_text(monitor, expected[:-3])
        time.sleep(3)
        key(monitor, ['right'])
        key(monitor, ['ctrl', 'f12'])
        time.sleep(1)
        actual = ssh(directory, 'cat ~/mini-os-edit-result.txt')
        capture(monitor, directory, 'history-after-maintenance-boot')
        key(monitor, ['ctrl', 'a'])
        key(monitor, ['ctrl', 'k'])
    finally:
        monitor.close()
    report = {'startup': startup, 'expected': expected, 'accepted_suggestion': actual,
              'after_upgrade_and_cold_boot': True,
              'passed': actual == expected and startup[0].startswith('0.4') and startup[1] == 'true'}
    (directory / 'fresh-history-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit('Fresh history suggestion did not match the pre-reboot command')


if __name__ == '__main__':
    main()
