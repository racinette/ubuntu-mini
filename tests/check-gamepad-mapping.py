#!/usr/bin/env python3
"""Install and exercise the approved navigation profile on a disposable desktop branch."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time

from gui import capture, experiment, key, type_text
from qmp import Monitor
from session import graphical, ssh, stage_setup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('--prepare', action='store_true', help='Stage source-only setup and apply it through the fixture local mirror before graphical login')
    args = parser.parse_args()
    directory = experiment.select_directory(args.directory)
    parent = experiment.select_directory(json.loads((directory / 'baseline.json').read_text())['directory'])
    if not any(p.exists() and json.loads(p.read_text()).get('passed') for p in
               (parent / 'source-setup-report.json', parent / 'post-install-setup-report.json')):
        raise ValueError('Use a disposable branch of a passed desktop setup fixture')
    state = json.loads((directory / 'state.json').read_text())
    credentials = json.loads((directory / 'credentials.json').read_text())

    def root(command):
        return ssh(directory, 'sudo -k -S -p "" sh -ec ' + shlex.quote(command),
                   credentials['login_password'] + '\n')

    def copy(source, target):
        subprocess.run(['scp', '-i', str(directory / 'ssh-key'), '-P', str(state['ssh_port']),
                        '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                        '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'), str(source),
                        'vmuser@127.0.0.1:' + target], check=True, capture_output=True)

    if args.prepare:
        target = '/home/vmuser/minion-controller-setup'
        stage_setup(directory, target)
        snapshot_command = "sha256sum /home/vmuser/.bashrc /home/vmuser/.config/foot/foot.ini /home/vmuser/.config/atuin/config.toml; if test ! -f /home/vmuser/.config/minion/gamepad.json; then true; else sha256sum /home/vmuser/.config/minion/gamepad.json; fi; sfdisk --json /dev/vda"
        before = root(snapshot_command)
        mirror = json.loads((experiment.PROJECT / '.local/mirror/server.json').read_text())['guest_url']
        output = root(target + '/setup.sh --asset-url ' + shlex.quote(mirror + '/assets'))
        (directory / 'gamepad-setup-console.log').write_text(output)
        after = root(snapshot_command)
        result = json.loads(root('python3 -c ' + shlex.quote('''
import json
from pathlib import Path
run=Path(json.loads(Path('/var/lib/minion/setup/last-success.json').read_text())['run'])
print((run/'result.json').read_text())
''')))
        source_matches = all(experiment.digest(experiment.PROJECT / name) == checksum for name, checksum in result['source_sha256'].items())
        report = {'passed': result['passed'] and before == after and source_matches,
                  'settings_and_gpt_preserved': before == after, 'sources_match': source_matches, 'setup_result': result}
        (directory / 'gamepad-setup-report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['passed']:
            raise ValueError('Controller setup preparation failed')
        print('Controller setup passed: source revision, user settings and GPT preservation.', flush=True)
        return

    def control(operation, events=None, release=None, delay=.12):
        request = {'operation': operation}
        if events is not None:
            request['events'] = events
        if release is not None:
            request.update(release=release, delay=delay)
        code = '''import json,socket
s=socket.socket(socket.AF_UNIX);s.connect('/run/minion-gamepad-test/control.sock')
s.sendall((%r+'\\n').encode());print(s.makefile().readline())
''' % json.dumps(request)
        result = json.loads(root('python3 -c ' + shlex.quote(code)))
        if 'error' in result:
            raise ValueError(result['error'])
        return result

    def pulse(kind, code, value=1, delay=.12):
        return control('pulse', [[kind, code, value]], [[kind, code, 0]], delay)

    def status():
        return json.loads(graphical(directory, 'minion-gamepad --status'))

    def wait(function, predicate, label, seconds=10):
        deadline = time.monotonic() + seconds
        while True:
            value = function()
            if predicate(value):
                return value
            if time.monotonic() > deadline:
                raise ValueError(label + ': ' + json.dumps(value))
            time.sleep(.1)

    def browser():
        return json.loads(ssh(directory, "python3 -c 'import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8765/state\").read().decode())'"))

    def browser_set(**command):
        code = '''import urllib.request
print(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765/command',data=%r.encode(),method='POST')).read().decode())
''' % json.dumps(command)
        result = json.loads(ssh(directory, 'python3 -c ' + shlex.quote(code)))
        return wait(browser, lambda s: s.get('command') == result['id'], 'Browser did not apply fixture command')

    def keyboard_keys():
        return json.loads(root('python3 -c ' + shlex.quote('''
import evdev,json
for path in evdev.list_devices():
 d=evdev.InputDevice(path)
 if d.name=='Minion gamepad keyboard':
  print(json.dumps(d.active_keys()));break
else:raise ValueError('Mapped keyboard is missing')
''')))

    def tree():
        value = json.loads(graphical(directory, 'swaymsg -t get_tree'))

        def walk(node, workspace=None, floating=False):
            if node.get('type') == 'workspace':
                workspace = node['name']
            result = [dict(node, workspace=workspace, is_floating=floating)] if node.get('app_id') else []
            for child in node.get('nodes', []):
                result.extend(walk(child, workspace, floating))
            for child in node.get('floating_nodes', []):
                result.extend(walk(child, workspace, True))
            return result

        return walk(value)

    def focused_workspace():
        return next(w['num'] for w in json.loads(graphical(directory, 'swaymsg -t get_workspaces')) if w['focused'])

    report = {'passed': False, 'started_at': time.time(), 'checks': {}}
    monitor = Monitor(directory / 'qmp.sock')
    daemon_started = False
    try:
        if not json.loads((directory / 'gamepad-setup-report.json').read_text())['passed']:
            raise ValueError('Run --prepare and authenticate into Sway first')
        wait(status, lambda s: s['session_active'], 'Mapper has no active local session')
        ssh(directory, 'mkdir -p ~/minion-gamepad-fixture')
        for name in ('virtual-gamepad.py', 'gamepad-mapping-http.py', 'gamepad-mapping-test.html'):
            copy(experiment.PROJECT / 'tests/fixtures' / name, '/home/vmuser/minion-gamepad-fixture/' + name)
        root('modprobe joydev; systemd-run --quiet --unit=minion-virtual-gamepad python3 /home/vmuser/minion-gamepad-fixture/virtual-gamepad.py /run/minion-gamepad-test')
        daemon_started = True
        root('for attempt in $(seq 1 30); do test ! -S /run/minion-gamepad-test/control.sock || exit 0; sleep .1; done; exit 1')
        control('create')
        root('udevadm settle')
        attached = wait(status, lambda s: s['device'] and s['grabbed'] and s['ready'], 'Mapper did not acquire controller')
        report['initial_status'] = attached
        report['checks']['session_user_and_device_access'] = True
        graphical(directory, 'systemctl --user stop minion-gamepad-http.service 2>/dev/null || true; systemd-run --user --quiet --unit=minion-gamepad-http python3 /home/vmuser/minion-gamepad-fixture/gamepad-mapping-http.py')
        graphical(directory, 'swaymsg "workspace number 1; exec firefox --new-window http://127.0.0.1:8765/"')
        wait(tree, lambda nodes: any(n['app_id'] == 'firefox_firefox' for n in nodes), 'Firefox window missing', 30)
        graphical(directory, 'swaymsg "[app_id=firefox_firefox] focus; [app_id=firefox_firefox] fullscreen enable"')
        time.sleep(3)
        graphical(directory, 'swaymsg "input type:keyboard xkb_switch_layout 0"')
        for attempt in range(3):
            key(monitor, ['ctrl', 'l'])
            key(monitor, ['ctrl', 'a'])
            type_text(monitor, 'http://127.0.0.1:8765/\n')
            time.sleep(2)
            if browser().get('focused'):
                break
        wait(browser, lambda s: s.get('focused') and s.get('target') == 'editor', 'Browser keyboard fixture missing')

        face_results = []
        # Xbox/xpad A/B/X/Y event codes, independent of mapper configuration.
        for button, expected in ((304, 'Enter'), (305, 'Escape'), (307, 'Backspace'), (308, 'Space')):
            browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
            pulse(1, button)
            result = wait(browser, lambda s: any(e['type'] == 'keyup' and e['code'] == expected for e in s['events']), expected + ' was not delivered')
            face_results.append({'button': button, 'events': result['events'], 'text': result['text'], 'target': result['target']})
            if expected == 'Backspace' and result['text'] != 'hello worl':
                raise ValueError('Backspace did not edit browser text')
            if expected == 'Space' and result['text'] != 'hello world ':
                raise ValueError('Space did not insert a character')
        report['face_buttons'] = face_results
        report['checks']['face_keys_in_browser'] = True
        browser_set(text='x' * 100, selection=[100, 100], focus='editor', clear=True)
        control('emit', [[1, 307, 1]])
        immediate = wait(browser, lambda s: len(s['text']) < 100, 'Backspace did not act on press')
        time.sleep(1)
        repeated = browser()
        if len(repeated['text']) >= len(immediate['text']) or not any(e['repeat'] for e in repeated['events']):
            raise ValueError('Held Backspace did not repeat')
        control('emit', [[1, 307, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Backspace remained held')
        time.sleep(.2)
        frozen = browser()['text']; time.sleep(.4)
        if browser()['text'] != frozen:
            raise ValueError('Backspace repeated after release')
        report['checks']['immediate_backspace_hold_repeat_and_release'] = True
        browser_set(text='', selection=[0, 0], focus='editor', clear=True)
        control('emit', [[1, 308, 1]])
        immediate = wait(browser, lambda s: len(s['text']) > 0, 'Space did not act on press')
        time.sleep(1)
        repeated = browser()
        if len(repeated['text']) <= len(immediate['text']) or not any(e['repeat'] for e in repeated['events']):
            raise ValueError('Held Space did not repeat')
        control('emit', [[1, 308, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Space remained held')
        time.sleep(.2)
        frozen = browser()['text']; time.sleep(.4)
        if browser()['text'] != frozen:
            raise ValueError('Space repeated after release')
        report['checks']['immediate_space_hold_repeat_and_release'] = True
        arrow_results = []
        for axis, value, expected in ((16, -1, 'ArrowLeft'), (16, 1, 'ArrowRight'), (17, -1, 'ArrowUp'), (17, 1, 'ArrowDown')):
            browser_set(text='hello world', selection=[6, 6], focus='editor', clear=True)
            pulse(3, axis, value)
            result = wait(browser, lambda s: any(e['type'] == 'keyup' and e['code'] == expected for e in s['events']), expected + ' was not delivered')
            arrow_results.append({'direction': expected, 'events': result['events']})
        report['arrows'] = arrow_results
        browser_set(text='x' * 500, selection=[500, 500], focus='editor', clear=True)
        control('emit', [[3, 16, -1]])
        immediate = wait(browser, lambda s: s['selection'] == [499, 499], 'D-pad did not act on press')
        time.sleep(.9)
        early = browser()['selection'][0]
        time.sleep(1)
        middle = browser()['selection'][0]
        time.sleep(1)
        late = browser()['selection'][0]
        if not 0 < 499 - early < middle - late or middle - late < 20:
            raise ValueError('D-pad hold did not accelerate')
        control('emit', [[3, 16, 0]])
        time.sleep(.2)
        frozen = browser()['selection']; time.sleep(.5)
        if browser()['selection'] != frozen or keyboard_keys():
            raise ValueError('D-pad repeated or remained held after release')
        report['dpad_acceleration'] = {'initial': immediate['selection'], 'early': early, 'middle': middle, 'late': late}
        report['checks']['dpad_immediate_accelerating_hold_and_release'] = True

        inputs = {'UP': [3, 17, -1], 'DOWN': [3, 17, 1], 'LEFT': [3, 16, -1], 'RIGHT': [3, 16, 1],
                  'A': [1, 304, 1], 'B': [1, 305, 1], 'Y': [1, 308, 1], 'X': [1, 307, 1], 'SELECT': [1, 314, 1]}
        def chord(name):
            events = [inputs[token] for token in name.split('+')]
            faces = [event for event in events if event[0] == 1]
            directions = [event for event in events if event[0] == 3]
            if 'SELECT' in name.split('+'):
                control('emit', [inputs['SELECT']])
                faces = [event for event in faces if event[1] != 314]
            control('emit', faces)
            return control('pulse', directions, [[kind, code, 0] for kind, code, value in reversed(events)])
        for tokens in (['SELECT', 'A'], ['SELECT', 'X', 'Y'], ['A', 'B']):
            browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
            events = [inputs[token] for token in tokens]
            control('emit', events); control('emit', [[e[0], e[1], 0] for e in events])
            time.sleep(.15)
            if browser()['text'] != 'preserved' or browser()['events']:
                raise ValueError('Invalid or reserved shortcut leaked single actions')
        browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
        control('emit', [inputs['A']]); control('emit', [inputs['UP']]); control('emit', [[3, 17, 0]])
        control('emit', [inputs['B']]); control('emit', [[1, 304, 0], [1, 305, 0]])
        time.sleep(.15)
        if browser()['events']:
            raise ValueError('Rolling shortcut leaked single actions')
        report['checks']['invalid_reserved_and_rolling_shortcuts_consumed'] = True

        browser_set(text='preserved', selection=[0, 9], focus='editor', clear=True)
        control('emit', [inputs['A']]); time.sleep(1)
        if browser()['events']:
            raise ValueError('Held face prefix acted before a direction')
        control('emit', [inputs['UP']]); time.sleep(.7)
        if browser()['events']:
            raise ValueError('Held combo leaked arrows or Enter')
        control('emit', [[3, 17, 0], [1, 304, 0]])
        wait(lambda: graphical(directory, 'wl-paste --no-newline'), lambda text: text == 'preserved', 'Delayed prefix Copy failed')
        browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
        control('emit', [inputs['LEFT']])
        wait(browser, lambda s: s['selection'] == [8, 8], 'Wrong-order navigation did not act')
        control('emit', [inputs['A']]); time.sleep(.7)
        control('emit', [[3, 16, 0]]); control('emit', [[1, 304, 0]])
        wrong_order = browser()
        if wrong_order['selection'] != [8, 8] or any(e['code'] == 'Enter' for e in wrong_order['events']):
            raise ValueError('Wrong-order gesture leaked a combo or face action')
        report['checks']['face_prefix_wait_and_wrong_order_navigation'] = True

        trigger_cases = []
        for axis, key_code in ((2, 42), (5, 29)):
            for value, desired in ((95, []), (160, [key_code]), (130, [key_code]), (80, [])):
                control('emit', [[3, axis, value]])
                observed = wait(keyboard_keys, lambda keys: keys == desired, 'Trigger hysteresis mismatch')
                trigger_cases.append({'axis': axis, 'value': value, 'keyboard_keys': observed})
            control('emit', [[3, axis, 0]])
        report['trigger_hysteresis'] = trigger_cases
        report['checks']['trigger_thresholds_and_hysteresis'] = True

        browser_set(text='controller clipboard', selection=[0, 20], focus='editor', clear=True)
        chord('UP+A')
        wait(lambda: graphical(directory, 'wl-paste --no-newline'), lambda text: text == 'controller clipboard', 'Copy failed')
        browser_set(text='', selection=[0, 0], focus='editor', clear=True)
        chord('DOWN+A'); wait(browser, lambda s: s['text'] == 'controller clipboard', 'Paste failed')
        chord('UP+RIGHT+A'); wait(browser, lambda s: s['selection'] == [0, 20], 'Select all failed')
        chord('UP+LEFT+A'); wait(browser, lambda s: not s['text'], 'Cut failed')
        browser_set(text='', selection=[0, 0], focus='editor', clear=True)
        type_text(monitor, 'undo-redo'); wait(browser, lambda s: s['text'] == 'undo-redo', 'Undo fixture missing')
        chord('LEFT+A'); wait(browser, lambda s: s['text'] != 'undo-redo', 'Undo failed')
        chord('RIGHT+A'); wait(browser, lambda s: s['text'] == 'undo-redo', 'Redo failed')
        report['checks']['copy_paste_cut_select_all_undo_redo'] = True
        browser_set(text='hello world', selection=[6, 6], focus='editor', clear=True)
        chord('UP+LEFT+B'); wait(browser, lambda s: s['selection'] == [0, 0], 'Document Home failed')
        control('emit', [[3, 2, 255]])
        chord('UP+RIGHT+B'); wait(browser, lambda s: s['selection'] == [0, 11], 'Shift+document End selection failed')
        control('emit', [[3, 2, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Navigation retained Shift')
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        wait(status, lambda s: s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Default Scroll/Windows mode missing')
        pulse(1, 317)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'windows'}, 'L3 did not enable text navigation')
        control('emit', [[3, 0, -32768]])
        wait(browser, lambda s: s['selection'][0] == s['selection'][1] < 11, 'Left stick did not move the caret')
        control('emit', [[3, 0, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Caret movement left a key held')
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        control('emit', [[3, 2, 255]])
        control('emit', [[3, 0, -32768]])
        wait(browser, lambda s: s['selection'][0] < s['selection'][1], 'Left stick did not select text')
        time.sleep(.8)
        if browser()['selection'][0] >= 10:
            raise ValueError('Held left stick did not extend selection')
        control('emit', [[3, 0, 0]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Selection did not preserve the held trigger')
        control('emit', [[3, 2, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Selection left a key held')
        for shift in (False, True):
            browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
            control('emit', [[3, 2, 255 if shift else 0], [3, 5, 255], [3, 0, -32768]])
            wait(browser, lambda s: s['selection'][0] < 11 and any(
                e['type'] == 'keydown' and e['code'] == 'ArrowLeft' and e['ctrl'] and e['shift'] == shift
                for e in s['events']), 'Word navigation/selection modifiers were not delivered')
            control('emit', [[3, 0, 0], [3, 2, 0], [3, 5, 0]])
            wait(keyboard_keys, lambda keys: not keys, 'Word movement left a modifier held')
        pulse(1, 317)
        wait(status, lambda s: s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'L3 did not restore scrolling')
        # Place the pointer over the fixture: the mapper leaves it in place.
        rect = next(n['rect'] for n in tree() if n['app_id'] == 'firefox_firefox')
        graphical(directory, f"swaymsg 'seat seat0 cursor set {rect['x'] + rect['width'] // 2} {rect['y'] + rect['height'] // 2}'")
        scroll_results = []
        for modifiers in (False, True):
            for axis, value, coordinate, sign in ((1, 32767, 1, 1), (1, -32768, 1, -1),
                                                  (0, 32767, 0, 1), (0, -32768, 0, -1)):
                browser_set(scroll=[200, 200], clear=True)
                time.sleep(.4)
                before_scroll = browser()['scroll']
                control('emit', [[3, 2, 255 if modifiers else 0], [3, 5, 255 if modifiers else 0]])
                pulse(3, axis, value)
                result = wait(browser, lambda s: (s['scroll'][coordinate] - before_scroll[coordinate]) * sign >= 20,
                              'Left stick did not scroll in the expected direction')
                wheels = [event for event in result['events'] if event['type'] == 'wheel']
                if (not wheels or any(event['ctrl'] or event['shift'] for event in wheels)
                        or abs(wheels[-1]['deltaY' if coordinate else 'deltaX']) < 20):
                    raise ValueError('Wheel movement was too small or trigger modifiers changed scrolling')
                control('emit', [[3, 2, 0], [3, 5, 0]])
                wait(keyboard_keys, lambda keys: not keys, 'Scrolling left a modifier held')
                scroll_results.append({'axis': axis, 'value': value, 'triggers': modifiers, 'events': wheels})
        browser_set(scroll=[0, 0], focus='editor', clear=True)
        report['scrolling'] = scroll_results
        report['checks']['window_scrolling_both_axes_and_trigger_suppression'] = True
        pulse(1, 317)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'windows'}, 'L3 changed the right stick')
        pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'R3 changed the left stick')
        report['checks']['navigation_selection_left_stick_and_repeat'] = True
        print('Application keys passed: shortcut editing, text navigation, holdable Backspace and left-stick selection.', flush=True)
        capture(monitor, directory, 'mapped-controller-editing')
        pulse(1, 317); pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Default layout not restored before window tests')

        graphical(directory, 'swaymsg "[app_id=firefox_firefox] fullscreen disable; workspace number 2; layout splith; exec foot --app-id=minion-map-left --title=Controller-left /bin/sleep infinity"')
        wait(tree, lambda nodes: any(n['app_id'] == 'minion-map-left' for n in nodes), 'First Foot window missing')
        graphical(directory, 'swaymsg "exec foot --app-id=minion-map-right --title=Controller-right /bin/sleep infinity"')
        wait(tree, lambda nodes: any(n['app_id'] == 'minion-map-right' for n in nodes), 'Second Foot window missing')
        pulse(3, 3, -32768)
        focus = wait(tree, lambda nodes: any(n['app_id'] == 'minion-map-left' and n['focused'] for n in nodes), 'Right stick did not change window focus')
        report['focus_windows'] = [{'app_id': n['app_id'], 'focused': n['focused'], 'rect': n['rect']} for n in focus]
        action_count = len(status()['actions'])
        pulse(3, 3, 32767, 1.1)
        repeated_actions = status()['actions'][action_count:]
        if not 2 <= len(repeated_actions) <= 6 or any(a['command'] != 'focus right' for a in repeated_actions):
            raise ValueError('Stick repeat was absent or unbounded')
        frozen = status()['actions']
        control('emit', [[3, 3, 1000], [3, 4, -500]])
        time.sleep(.4)
        if status()['actions'] != frozen:
            raise ValueError('Neutral stick jitter caused a window action')
        control('emit', [[3, 3, 0], [3, 4, 0]])
        report['checks']['stick_repeat_and_deadzone'] = True
        report['stick_repeat_actions'] = repeated_actions
        graphical(directory, 'swaymsg "[app_id=minion-map-right] focus"')
        before_move = next(n for n in tree() if n['app_id'] == 'minion-map-right')['rect']
        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Shift hold missing before window move')
        pulse(3, 3, -32768)
        after_move = wait(tree, lambda nodes: next(n for n in nodes if n['app_id'] == 'minion-map-right')['rect']['x'] < before_move['x'], 'Shift+stick did not move the window')
        control('emit', [[3, 2, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Shift remained held after move')
        pulse(1, 317); pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'Resize mode missing')
        before_resize = next(n for n in after_move if n['app_id'] == 'minion-map-right')['rect']
        pulse(3, 3, 32767)
        resized = wait(tree, lambda nodes: next(n for n in nodes if n['app_id'] == 'minion-map-right')['rect']['width'] > before_resize['width'], 'Right stick did not resize the window')
        report['window_move_and_resize'] = {'before_move': before_move, 'after_move': before_resize,
                                         'after_resize': next(n for n in resized if n['app_id'] == 'minion-map-right')['rect']}
        control('emit', [[1, 310, 1]])
        time.sleep(1.1)
        if focused_workspace() != 2:
            raise ValueError('L1 acted before release')
        control('emit', [[1, 310, 0]])
        if focused_workspace() != 1:
            raise ValueError('Held L1 must switch exactly one workspace')
        pulse(1, 311)
        if focused_workspace() != 2:
            raise ValueError('R1 did not select the next workspace')
        control('emit', [[1, 311, 1]])
        if focused_workspace() != 2:
            raise ValueError('R1 acted before late Shift combination')
        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Shift hold missing before workspace move')
        control('emit', [[1, 311, 0]])
        sent = wait(tree, lambda nodes: any(n['app_id'] == 'minion-map-right' and n['workspace'] == '3' for n in nodes), 'Shift+bumper did not send the window to a workspace')
        control('emit', [[3, 2, 0]])
        report['checks']['focus_move_resize_and_workspace_clicks'] = True
        report['checks']['bumper_release_and_late_modifier'] = True
        capture(monitor, directory, 'mapped-controller-windows')
        print('Sway actions passed: focus, Shift+move, resize, bumper clicks and Shift+workspace move.', flush=True)

        def picker_processes():
            return ssh(directory, 'pgrep -x fuzzel || true').splitlines()

        before_terminal = {node['id'] for node in tree()}
        control('emit', [[1, 315, 1]])
        time.sleep(.4)
        if {node['id'] for node in tree()} != before_terminal:
            raise ValueError('Start opened a terminal before release')
        control('emit', [[1, 315, 0]])
        terminal_tree = wait(tree, lambda nodes: any(n['id'] not in before_terminal and n['app_id'] == 'foot' for n in nodes), 'Start did not open a terminal')
        terminal_id = next(n['id'] for n in terminal_tree if n['id'] not in before_terminal and n['app_id'] == 'foot')
        time.sleep(.4)
        if len({n['id'] for n in tree()} - before_terminal) != 1:
            raise ValueError('One Start release opened multiple terminals')
        report['start_terminal_id'] = terminal_id
        report['checks']['start_terminal_on_release'] = True

        before_explorer = {node['id'] for node in tree()}
        control('emit', [[1, 315, 1]])
        time.sleep(1)
        if {node['id'] for node in tree()} != before_explorer:
            raise ValueError('Start hold opened a window before release')
        control('emit', [[1, 315, 0]])
        explorer_tree = wait(tree, lambda nodes: any(n['id'] not in before_explorer and n['app_id'] == 'thunar' for n in nodes), 'Start hold did not open Thunar')
        explorer_id = next(n['id'] for n in explorer_tree if n['id'] not in before_explorer and n['app_id'] == 'thunar')
        time.sleep(.4)
        if len({n['id'] for n in tree()} - before_explorer) != 1:
            raise ValueError('One Start hold opened multiple windows')
        report['checks']['start_hold_file_manager_on_release'] = True
        graphical(directory, f'swaymsg "[con_id={explorer_id}] kill"')

        control('emit', [[1, 316, 1]])
        time.sleep(.3)
        if status()['legend_open'] or picker_processes() or keyboard_keys():
            raise ValueError('Menu hold acted before its threshold')
        wait(status, lambda s: s['legend_open'], 'Menu hold did not open legend')
        control('emit', [[1, 316, 0]])
        wait(picker_processes, bool, 'Legend overlay missing')
        time.sleep(3)
        if not status()['legend_open']:
            raise ValueError('Legend disappeared before dismissal')
        windows_before = {n['id'] for n in tree()}
        chord('UP+B')
        if {n['id'] for n in tree()} != windows_before:
            raise ValueError('Legend allowed Close to reach the underlying window')
        capture(monitor, directory, 'mapped-shortcut-legend')
        pulse(1, 305); wait(status, lambda s: not s['legend_open'], 'B did not dismiss legend')
        pulse(1, 316, 1, 1.0); wait(status, lambda s: s['legend_open'], 'Second legend missing')
        pulse(1, 316); wait(status, lambda s: not s['legend_open'], 'Menu tap did not dismiss legend')
        report['checks']['persistent_legend_toggle_and_shortcut_capture'] = True
        before = {n['id'] for n in tree()}
        pulse(1, 315)
        nodes = wait(tree, lambda ns: any(n['id'] not in before for n in ns), 'Temporary terminal missing')
        temporary = next(n['id'] for n in nodes if n['id'] not in before)
        graphical(directory, f'swaymsg "[con_id={temporary}] focus"')
        chord('UP+B')
        wait(tree, lambda ns: all(n['id'] != temporary for n in ns), 'Close window shortcut failed')
        graphical(directory, f'swaymsg "[con_id={terminal_id}] focus"')
        for expected in (1, 0):
            chord('SELECT+A')
            wait(tree, lambda ns: next(n for n in ns if n['id'] == terminal_id)['fullscreen_mode'] == expected, 'Fullscreen shortcut failed')
        for expected in (True, False):
            chord('SELECT+B')
            wait(tree, lambda ns: next(n for n in ns if n['id'] == terminal_id)['is_floating'] == expected, 'Floating shortcut failed')
        report['checks']['close_fullscreen_and_floating_shortcuts'] = True
        chord('SELECT+A')
        wait(tree, lambda ns: next(n for n in ns if n['id'] == terminal_id)['fullscreen_mode'] == 1, 'Fullscreen missing before launcher')
        control('emit', [[1, 316, 1]])
        time.sleep(.4)
        if picker_processes():
            raise ValueError('Menu opened a launcher before release')
        control('emit', [[1, 316, 0]])
        wait(picker_processes, lambda values: len(values) == 1, 'Menu did not open the launcher')
        time.sleep(.4)
        capture(monitor, directory, 'mapped-app-launcher')
        pulse(1, 305)
        wait(picker_processes, lambda values: not values, 'B did not cancel the launcher')
        pulse(1, 316); wait(picker_processes, bool, 'Second launcher missing')
        pulse(1, 316); wait(picker_processes, lambda values: not values, 'Menu did not dismiss launcher')
        report['checks']['menu_launcher_on_release_and_toggle'] = True

        control('emit', [[1, 314, 1]])
        time.sleep(.4)
        if picker_processes():
            raise ValueError('Select opened a window picker before release')
        control('emit', [[1, 314, 0]])
        wait(picker_processes, lambda values: len(values) == 1, 'Select did not open the window picker')
        type_text(monitor, 'Controller-')
        time.sleep(.4)
        pulse(3, 17, 1)
        capture(monitor, directory, 'mapped-window-picker')
        pulse(1, 304)
        wait(picker_processes, lambda values: not values, 'A did not accept the selected window')
        chosen = wait(tree, lambda nodes: any(n['app_id'] == 'minion-map-right' and n['focused'] for n in nodes), 'Picker did not focus the selected window across workspaces')
        if focused_workspace() != 3:
            raise ValueError('Picker did not switch to the selected window workspace')
        selected_id = next(n['id'] for n in chosen if n['focused'])
        pulse(1, 314)
        wait(picker_processes, lambda values: len(values) == 1, 'Second Select did not open the picker')
        pulse(1, 305)
        wait(picker_processes, lambda values: not values, 'B did not cancel the picker')
        if not any(n['id'] == selected_id and n['focused'] for n in tree()):
            raise ValueError('Cancelling the picker changed the selected window')
        graphical(directory, 'swaymsg "[con_id=' + str(terminal_id) + '] fullscreen disable"')
        report['picker_selected_window_id'] = selected_id
        report['checks']['select_picker_navigation_accept_and_cancel'] = True
        print('Desktop passed: named window shortcuts, persistent legend, terminal, launcher and window picker.', flush=True)

        graphical(directory, 'swaymsg "workspace number 1; [app_id=firefox_firefox] focus"')
        browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
        control('emit', [inputs['UP'], inputs['A']])
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before disconnect')
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'Workspace mode missing before disconnect')
        control('destroy')
        wait(status, lambda s: s['device'] is None and not s['keys'] and s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Disconnect left mapped keys or Workspace mode armed')
        wait(keyboard_keys, lambda keys: not keys, 'Kernel keyboard retained Ctrl after disconnect')
        control('create')
        root('udevadm settle')
        wait(status, lambda s: s['device'] and s['grabbed'] and s['ready'], 'Reconnect failed')
        if browser()['text'] != 'preserved' or any(e['code'] != 'ControlLeft' for e in browser()['events']):
            raise ValueError('Disconnect committed an unfinished shortcut')
        report['checks']['disconnect_discards_unfinished_shortcut'] = True
        report['checks']['disconnect_reconnect_releases_modifiers'] = True

        graphical(directory, 'swaymsg "workspace number 1; [app_id=firefox_firefox] focus; [app_id=firefox_firefox] fullscreen enable"')
        browser_set(text='hello', selection=[5, 5], focus='editor', clear=True)
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before passthrough')
        pulse(1, 317); pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'Workspace mode missing before passthrough')
        graphical(directory, 'minion-gamepad --toggle')
        wait(status, lambda s: s['mode'] == 'reaper' and not s['keys'] and
             s['stick_modes'] == {'left': 'scroll', 'right': 'zoom'}, 'REAPER profile did not clear modifiers or reset sticks')
        graphical(directory, 'minion-gamepad --toggle')
        wait(status, lambda s: s['mode'] == 'passthrough' and not s['grabbed'] and not s['keys'] and s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Passthrough did not clear modifiers or release source grab')
        wait(keyboard_keys, lambda keys: not keys, 'Ctrl remained held in passthrough')
        control('emit', [[3, 5, 0]])
        control('emit', [[1, 304, 1]])
        raw = wait(browser, lambda s: any(p['buttons'][0]['pressed'] for p in s['pads']), 'Firefox did not receive raw controller in passthrough')
        control('emit', [[1, 304, 0]])
        if raw['text'] != 'hello' or any(e['code'] == 'Enter' for e in raw['events']):
            raise ValueError('Passthrough still produced keyboard Enter')
        report['passthrough_browser'] = raw
        control('emit', [[1,315,1]])
        control('emit', [[3,16,-1]])
        control('emit', [[1,315,0]])
        control('emit', [[3,16,0]])
        wait(status, lambda s: s['mode'] == 'desktop' and s['ready'] and s['grabbed'], 'Controller chord did not restore desktop mode')
        report['checks']['passthrough_and_direct_mode_selection'] = True

        frozen_windows = {n['id'] for n in tree()}
        frozen_actions = status()['actions']
        control('emit', [[1,315,1]])
        control('emit', [[3,17,-1]])
        time.sleep(1)
        if status()['mode'] != 'desktop' or {n['id'] for n in tree()} != frozen_windows or picker_processes():
            raise ValueError('Held mode chord acted before release')
        control('emit', [[1,315,0]])
        if status()['mode'] != 'desktop' or picker_processes():
            raise ValueError('Partial chord release triggered an action')
        control('emit', [[3,17,0]])
        wait(status, lambda s: s['mode'] == 'reaper' and s['ready'], 'Full chord release did not select REAPER')
        if status()['actions'] != frozen_actions or {n['id'] for n in tree()} != frozen_windows or picker_processes():
            raise ValueError('Mode chord also dispatched an individual action')
        for value,target in ((1,'passthrough'),(-1,'desktop')):
            control('emit', [[1,315,1]])
            control('emit', [[3,16,value]])
            control('emit', [[3,16,0]])
            control('emit', [[1,315,0]])
            wait(status, lambda s: s['mode']==target and s['ready'], 'Direct mode selection failed: '+target)
        control('pulse', [[1,314,1],[1,315,1]], [[1,315,0],[1,314,0]], 1)
        time.sleep(.3)
        if status()['mode'] != 'desktop' or status()['actions'] != frozen_actions or picker_processes():
            raise ValueError('Removed Start+Select gesture dispatched an action')
        report['checks']['chord_release_consumes_individual_actions'] = True

        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Shift missing before lock')
        pulse(1, 317); pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'Workspace mode missing before lock')
        graphical(directory, 'minion-lock')
        wait(status, lambda s: s['paused'] and not s['grabbed'] and not s['keys'] and s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Lock did not pause and clear modifiers')
        wait(keyboard_keys, lambda keys: not keys, 'Shift remained held behind lock')
        pulse(1, 304)
        if not ssh(directory, 'pgrep -x swaylock || true').strip():
            raise ValueError('Controller unexpectedly dismissed the lock')
        control('emit', [[3, 2, 0]])
        key(monitor, ['ctrl', 'u'])
        type_text(monitor, credentials['login_password'] + '\n')
        wait(lambda: ssh(directory, 'pgrep -x swaylock || true').strip(), lambda s: not s, 'Password did not unlock')
        wait(status, lambda s: not s['paused'] and s['ready'] and s['grabbed'], 'Mapping did not resume after unlock')
        report['checks']['lock_pause_and_authenticated_resume'] = True

        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before switching consoles')
        pulse(1, 317); pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'Workspace mode missing before switching consoles')
        key(monitor, ['ctrl', 'alt', 'f2'])
        wait(status, lambda s: not s['session_active'] and not s['grabbed'] and not s['keys'] and s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Inactive graphical session kept modifiers')
        wait(keyboard_keys, lambda keys: not keys, 'Ctrl remained held on another console')
        control('emit', [[3, 5, 0]])
        key(monitor, ['ctrl', 'alt', 'f1'])
        wait(status, lambda s: s['session_active'] and s['ready'] and s['grabbed'], 'Mapping did not resume on the graphical console')
        report['checks']['inactive_console_releases_modifiers'] = True

        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before service restart')
        pulse(1, 317); pulse(1, 318)
        wait(status, lambda s: s['stick_modes'] == {'left': 'text', 'right': 'resize'}, 'Workspace mode missing before service restart')
        graphical(directory, 'systemctl --user restart minion-gamepad.service')
        wait(status, lambda s: not s['keys'] and not s['ready'] and s['stick_modes'] == {'left': 'scroll', 'right': 'windows'}, 'Service restart retained modifiers')
        wait(keyboard_keys, lambda keys: not keys, 'New keyboard started with Ctrl held')
        control('emit', [[3, 5, 0]])
        wait(status, lambda s: s['ready'], 'Mapping did not resume after neutral return')
        report['checks']['service_restart_waits_for_neutral'] = True
        report['final_status'] = status()
        report['service_state'] = graphical(directory, 'systemctl --user is-active minion-gamepad.service')
        report['passed'] = all(report['checks'].values())
        print('Lifecycle passed: disconnect, raw passthrough, controller chord, lock/unlock and service restart.', flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        if daemon_started:
            try:
                control('stop')
                root('for attempt in $(seq 1 30); do test -e /run/minion-gamepad-test || exit 0; sleep .1; done; exit 1')
                report['fixture_removed'] = True
            except Exception as error:
                report['cleanup_error'] = str(error)
                report['passed'] = False
        monitor.close()
        report['finished_at'] = time.time()
        (directory / 'gamepad-mapping-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
