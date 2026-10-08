#!/usr/bin/env python3
"""Launch Firefox, type both VM fixture languages, and open its real chooser."""
import argparse
import json
import time

from gui import experiment, key, type_text, capture
from qmp import Monitor
from session import graphical

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
mirror = json.loads((experiment.PROJECT / '.local/mirror/server.json').read_text())['guest_url']
monitor = Monitor(directory / 'qmp.sock')
report = {}
def windows(node):
    result = [node] if node.get('pid') else []
    for child in node.get('nodes', []) + node.get('floating_nodes', []):
        result.extend(windows(child))
    return result
try:
    graphical(directory, 'swaymsg "[app_id=mini-os-edit] fullscreen disable"; swaymsg "input type:keyboard xkb_switch_layout 0"')
    tree = json.loads(graphical(directory, 'swaymsg -t get_tree'))
    if not any(n.get('app_id') == 'firefox_firefox' for n in windows(tree)):
        key(monitor, ['meta_l', 'b'])
    for _ in range(30):
        tree = json.loads(graphical(directory, 'swaymsg -t get_tree'))
        if any(n.get('app_id') == 'firefox_firefox' for n in windows(tree)):
            break
        time.sleep(.5)
    else:
        raise ValueError('Firefox did not open')
    browser = next(n for n in windows(tree) if n.get('app_id') == 'firefox_firefox')
    browser_id = browser['id']
    for _ in range(3):
        graphical(directory, f'swaymsg "[con_id={browser_id}] focus"; swaymsg "[con_id={browser_id}] fullscreen enable"')
        key(monitor, ['ctrl', 'l'])
        type_text(monitor, mirror + '/assets/desktop-test.html\n')
        time.sleep(3)
        tree = json.loads(graphical(directory, 'swaymsg -t get_tree'))
        if any(n['id'] == browser_id and 'Mini OS desktop test' in (n.get('name') or '') for n in windows(tree)):
            break
    else:
        raise ValueError('Firefox startup did not reach the local fixture page')
    type_text(monitor, 'Fresh hello ')
    key(monitor, ['alt', 'shift'])
    type_text(monitor, 'ghbdtn')
    key(monitor, ['alt', 'shift'])
    key(monitor, ['ctrl', 'a'])
    key(monitor, ['ctrl', 'c'])
    time.sleep(2)
    text = graphical(directory, 'wl-paste --no-newline')
    if text != 'Fresh hello привет':
        raise ValueError('Browser actual input mismatch: ' + repr(text))
    report['actual_us_ru_input_and_clipboard'] = text
    capture(monitor, directory, 'fresh-browser')
    key(monitor, ['tab'])
    key(monitor, ['spc'])
    for _ in range(20):
        tree = json.loads(graphical(directory, 'swaymsg -t get_tree'))
        if any(n.get('app_id') == 'xdg-desktop-portal-gtk' for n in windows(tree)):
            break
        time.sleep(.5)
    else:
        raise ValueError('GTK portal chooser did not open')
    report['portal_chooser_window_present'] = True
    capture(monitor, directory, 'fresh-browser-chooser')
    graphical(directory, 'swaymsg "[app_id=xdg-desktop-portal-gtk] focus"')
    key(monitor, ['esc'])
    report['passed'] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    monitor.close()
    directory.joinpath('browser-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))
