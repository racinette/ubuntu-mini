#!/usr/bin/env python3
"""Record and search history in actual Foot with the VM network disconnected."""
import argparse
import json
import time

from gui import experiment, key, type_text, capture
from qmp import Monitor
from session import ssh, graphical

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
report = {}
monitor = Monitor(directory / 'qmp.sock')
marker = 'MINI_OS_OFFLINE_HISTORY_' + str(int(time.time()))
try:
    tree = json.loads(graphical(directory, 'swaymsg -t get_tree'))
    def contains_fixture(node):
        return node.get('app_id') == 'mini-os-edit' or any(contains_fixture(n)
            for n in node.get('nodes', []) + node.get('floating_nodes', []))
    if not contains_fixture(tree):
        raise ValueError('Run check-shell-editing.py first to open the interactive Foot fixture')
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] focus"; swaymsg "input type:keyboard xkb_switch_layout 0"')
    if ssh(directory, 'pgrep -x swaylock || true').strip(): raise ValueError('Unlock before testing')
    monitor.execute('set_link', {'name': 'net0', 'up': False})
    report['network_disconnected'] = True
    key(monitor, ['ctrl', 'a'])
    key(monitor, ['ctrl', 'k'])
    type_text(monitor, 'echo ' + marker + '\n')
    time.sleep(2)
    type_text(monitor, "atuin search --cmd-only --search-mode prefix 'echo " + marker + "' > /home/vmuser/mini-os-offline-search.txt\n")
    time.sleep(2)
    type_text(monitor, 'atuin doctor > /home/vmuser/mini-os-doctor-interactive.txt 2>&1\n')
    time.sleep(2)
    capture(monitor, directory, 'offline-history')
finally:
    monitor.execute('set_link', {'name': 'net0', 'up': True})
    monitor.close()
for _ in range(30):
    try:
        ssh(directory, 'true')
        break
    except Exception:
        time.sleep(1)
else:
    raise TimeoutError('SSH did not recover after restoring the VM link')
result = ssh(directory, 'cat ~/mini-os-offline-search.txt')
report['marker'] = marker
report['search_result'] = result.strip()
report['offline_record_and_search_passed'] = result.strip() == 'echo ' + marker
doctor = ssh(directory, 'cat ~/mini-os-doctor-interactive.txt')
(directory / 'atuin-doctor-interactive.txt').write_text(doctor)
report['interactive_doctor_detected_blesh'] = '"blesh"' in doctor and '"atuin"' in doctor
report['doctor_sqlite_diagnostic_warning'] = 'database schema is locked' in doctor
report['passed'] = report['offline_record_and_search_passed'] and report['interactive_doctor_detected_blesh']
(directory / 'history-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if not report['passed']: raise SystemExit(1)
