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
        target = '/home/vmuser/mini-os-controller-setup'
        stage_setup(directory, target)
        snapshot_command = "sha256sum /home/vmuser/.bashrc /home/vmuser/.config/foot/foot.ini /home/vmuser/.config/atuin/config.toml; if test ! -f /home/vmuser/.config/mini-os/gamepad.json; then true; else sha256sum /home/vmuser/.config/mini-os/gamepad.json; fi; sfdisk --json /dev/vda"
        before = root(snapshot_command)
        mirror = json.loads((experiment.PROJECT / '.local/mirror/server.json').read_text())['guest_url']
        output = root(target + '/setup.sh --asset-url ' + shlex.quote(mirror + '/assets'))
        (directory / 'gamepad-setup-console.log').write_text(output)
        after = root(snapshot_command)
        result = json.loads(root('python3 -c ' + shlex.quote('''
import json
from pathlib import Path
run=Path(json.loads(Path('/var/lib/mini-os/setup/last-success.json').read_text())['run'])
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
s=socket.socket(socket.AF_UNIX);s.connect('/run/mini-os-gamepad-test/control.sock')
s.sendall((%r+'\\n').encode());print(s.makefile().readline())
''' % json.dumps(request)
        result = json.loads(root('python3 -c ' + shlex.quote(code)))
        if 'error' in result:
            raise ValueError(result['error'])
        return result

    def pulse(kind, code, value=1, delay=.12):
        return control('pulse', [[kind, code, value]], [[kind, code, 0]], delay)

    def status():
        return json.loads(graphical(directory, 'mini-os-gamepad --status'))

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
 if d.name=='ubuntu-mini gamepad keyboard':
  print(json.dumps(d.active_keys()));break
else:raise ValueError('Mapped keyboard is missing')
''')))

    def tree():
        value = json.loads(graphical(directory, 'swaymsg -t get_tree'))

        def walk(node, workspace=None):
            if node.get('type') == 'workspace':
                workspace = node['name']
            result = [dict(node, workspace=workspace)] if node.get('app_id') else []
            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                result.extend(walk(child, workspace))
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
        ssh(directory, 'mkdir -p ~/mini-os-gamepad-fixture')
        for name in ('virtual-gamepad.py', 'gamepad-mapping-http.py', 'gamepad-mapping-test.html'):
            copy(experiment.PROJECT / 'tests/fixtures' / name, '/home/vmuser/mini-os-gamepad-fixture/' + name)
        root('modprobe joydev; systemd-run --quiet --unit=mini-os-virtual-gamepad python3 /home/vmuser/mini-os-gamepad-fixture/virtual-gamepad.py /run/mini-os-gamepad-test')
        daemon_started = True
        root('for attempt in $(seq 1 30); do test ! -S /run/mini-os-gamepad-test/control.sock || exit 0; sleep .1; done; exit 1')
        control('create')
        root('udevadm settle')
        attached = wait(status, lambda s: s['device'] and s['grabbed'] and s['ready'], 'Mapper did not acquire controller')
        report['initial_status'] = attached
        report['checks']['session_user_and_device_access'] = True
        graphical(directory, 'systemctl --user stop mini-os-gamepad-http.service 2>/dev/null || true; systemd-run --user --quiet --unit=mini-os-gamepad-http python3 /home/vmuser/mini-os-gamepad-fixture/gamepad-mapping-http.py')
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
        for button, expected in ((304, 'Enter'), (305, 'Escape'), (308, 'Backspace'), (307, 'Tab')):
            browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
            pulse(1, button)
            result = wait(browser, lambda s: any(e['type'] == 'keyup' and e['code'] == expected for e in s['events']), expected + ' was not delivered')
            face_results.append({'button': button, 'events': result['events'], 'text': result['text'], 'target': result['target']})
            if expected == 'Backspace' and result['text'] != 'hello worl':
                raise ValueError('Backspace did not edit browser text')
            if expected == 'Tab' and result['target'] != 'next':
                raise ValueError('Tab did not advance application focus')
        report['face_buttons'] = face_results
        report['checks']['face_keys_in_browser'] = True
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        control('emit', [[1, 308, 1]])
        time.sleep(.4)
        held_face = browser()
        if held_face['text'] != 'hello world' or held_face['events']:
            raise ValueError('Face key acted before release')
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Late Ctrl hold missing')
        control('emit', [[1, 308, 0]])
        release_combo = wait(browser, lambda s: s['text'] == 'hello ', 'Modifier added after button press was ignored')
        if not any(e['code'] == 'Backspace' and e['ctrl'] for e in release_combo['events']):
            raise ValueError('Released face key lost the held modifier')
        control('emit', [[3, 5, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Late Ctrl did not release')
        report['face_release_combination'] = release_combo
        report['checks']['face_release_and_late_modifier'] = True
        arrow_results = []
        for axis, value, expected in ((16, -1, 'ArrowLeft'), (16, 1, 'ArrowRight'), (17, -1, 'ArrowUp'), (17, 1, 'ArrowDown')):
            browser_set(text='hello world', selection=[6, 6], focus='editor', clear=True)
            pulse(3, axis, value)
            result = wait(browser, lambda s: any(e['type'] == 'keyup' and e['code'] == expected for e in s['events']), expected + ' was not delivered')
            arrow_results.append({'direction': expected, 'events': result['events']})
        report['arrows'] = arrow_results
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        control('emit', [[3, 16, -1]])
        time.sleep(.9)
        if browser()['events'] or browser()['selection'] != [11, 11]:
            raise ValueError('D-pad acted before release')
        control('emit', [[3, 16, 0]])
        released_arrow = wait(browser, lambda s: s['selection'] == [10, 10], 'Released D-pad did not move once')
        if sum(e['type'] == 'keydown' and e['code'] == 'ArrowLeft' for e in released_arrow['events']) != 1:
            raise ValueError('Released D-pad repeated')
        report['dpad_release'] = released_arrow['events']
        report['checks']['dpad_arrows_on_release'] = True

        profile = json.loads((experiment.PROJECT / 'setup/desktop/gamepad.json').read_text())
        chars = {'KEY_SPACE': ' ', 'KEY_APOSTROPHE': "'", 'KEY_MINUS': '-', 'KEY_SLASH': '/',
                 'KEY_COMMA': ',', 'KEY_DOT': '.', 'KEY_SEMICOLON': ';', 'KEY_EQUAL': '=',
                 'KEY_GRAVE': '`', 'KEY_BACKSLASH': '\\', 'KEY_LEFTBRACE': '[', 'KEY_RIGHTBRACE': ']'}
        shifted = dict(zip('`1234567890-=[]\\;\',./', '~!@#$%^&*()_+{}|:"<>?'))
        inputs = {'UP': [3, 17, -1], 'DOWN': [3, 17, 1], 'LEFT': [3, 16, -1], 'RIGHT': [3, 16, 1],
                  'A': [1, 304, 1], 'B': [1, 305, 1], 'X': [1, 308, 1], 'Y': [1, 307, 1]}
        chord_results = []
        for chord, output_key in profile['chords'].items():
            base = chars.get(output_key, output_key.removeprefix('KEY_').lower())
            events = [inputs[token] for token in chord.split('+')]
            for shift in (False, True):
                browser_set(text='', selection=[0, 0], focus='editor', clear=True)
                if shift:
                    control('emit', [[3, 2, 255]])
                    wait(keyboard_keys, lambda keys: keys == [42], 'Shift missing before chord')
                # Staggered presses allow all prefixes to be observed by the mapper.
                for event in events:
                    control('emit', [event])
                if browser()['text']:
                    raise ValueError('Chord typed before release: ' + chord)
                releases = list(reversed(events)) if shift else events
                for event in releases[:-1]:
                    control('emit', [[event[0], event[1], 0]])
                    if browser()['text']:
                        raise ValueError('Chord typed on partial release: ' + chord)
                event = releases[-1]
                control('emit', [[event[0], event[1], 0]])
                expected = shifted.get(base, base.upper()) if shift else base
                result = wait(browser, lambda s: s['text'] == expected, 'Incorrect chord output: ' + chord)
                downs = [e for e in result['events'] if e['type'] == 'keydown' and e['code'] != 'ShiftLeft']
                if len(downs) != 1 or downs[0]['key'] != expected:
                    raise ValueError('Chord leaked a constituent action: ' + chord)
                if shift:
                    control('emit', [[3, 2, 0]])
                    wait(keyboard_keys, lambda keys: not keys, 'Chord left Shift held')
                chord_results.append({'chord': chord, 'shift': shift, 'expected': expected, 'observed': result['text']})
        report['typing_chords'] = chord_results
        report['checks']['all_48_chords_and_us_shift_output'] = True

        for tokens in (['A', 'Y'], ['A', 'B', 'Y'], ['DOWN', 'X', 'Y']):
            browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
            events = [inputs[token] for token in tokens]
            control('emit', events)
            control('emit', [[e[0], e[1], 0] for e in events])
            time.sleep(.15)
            if browser()['text'] != 'preserved' or browser()['events']:
                raise ValueError('Invalid or reserved chord leaked single actions')
        report['checks']['invalid_and_reserved_chords_are_consumed'] = True
        browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
        control('emit', [inputs['UP'], inputs['A']])
        control('emit', [[3, 17, 0]])
        control('emit', [inputs['B']])
        control('emit', [[1, 304, 0], [1, 305, 0]])
        time.sleep(.15)
        if browser()['text'] != 'preserved' or browser()['events']:
            raise ValueError('Rolling a new button into a releasing chord typed unexpectedly')
        report['checks']['new_presses_during_chord_release_cancel'] = True

        trigger_cases = []
        for axis, key_code in ((2, 42), (5, 29)):
            for value, desired in ((95, []), (160, [key_code]), (130, [key_code]), (80, [])):
                control('emit', [[3, axis, value]])
                observed = wait(keyboard_keys, lambda keys: keys == desired, 'Trigger hysteresis mismatch')
                trigger_cases.append({'axis': axis, 'value': value, 'keyboard_keys': observed})
            control('emit', [[3, axis, 0]])
        report['trigger_hysteresis'] = trigger_cases
        report['checks']['trigger_thresholds_and_hysteresis'] = True

        browser_set(text='select this text', selection=[16, 16], focus='editor', clear=True)
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before letter chord shortcut')
        control('pulse', [inputs['LEFT'], inputs['X']], [[3, 16, 0], [1, 308, 0]], .12)
        report['ctrl_letter_chord'] = wait(browser, lambda s: s['selection'] == [0, 16], 'Ctrl+A letter chord did not select all')
        control('emit', [[3, 5, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Ctrl remained held after letter chord')
        report['checks']['ctrl_letter_chord_shortcut'] = True

        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Left trigger did not hold Shift')
        pulse(3, 16, -1)
        selected = wait(browser, lambda s: s['selection'] == [10, 11], 'Shift+arrow selection failed')
        report['shift_selection'] = selected
        browser_set(focus='next', clear=True)
        pulse(1, 307)
        reverse_focus = wait(browser, lambda s: s['target'] == 'editor', 'Shift+Tab navigation failed')
        report['shift_tab'] = reverse_focus
        control('emit', [[3, 2, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Shift did not release')
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Right trigger did not hold Ctrl')
        pulse(1, 308)
        deleted = wait(browser, lambda s: s['text'] == 'hello ', 'Ctrl+Backspace did not delete a word')
        report['ctrl_backspace'] = deleted
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        pulse(3, 16, -1)
        moved = wait(browser, lambda s: s['selection'] == [6, 6], 'Ctrl+arrow did not move by words')
        report['ctrl_arrow'] = moved
        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [29, 42], 'Two trigger holds did not combine')
        browser_set(text='hello world', selection=[11, 11], focus='editor', clear=True)
        pulse(3, 16, -1)
        selected_word = wait(browser, lambda s: s['selection'] == [6, 11], 'Ctrl+Shift+arrow did not select a word')
        report['ctrl_shift_selection'] = selected_word
        control('emit', [[3, 2, 0], [3, 5, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Combined modifiers did not release')
        # Establish a second tab explicitly; do not depend on Firefox welcome tabs.
        key(monitor, ['ctrl', 't'])
        wait(browser, lambda s: not s['focused'], 'Second browser tab did not open')
        key(monitor, ['ctrl', 'shift', 'tab'])
        wait(browser, lambda s: s['focused'], 'Could not return to the keyboard fixture')
        browser_set(focus='editor', clear=True)
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before browser tab navigation')
        pulse(1, 307)
        wait(browser, lambda s: not s['focused'], 'Ctrl+Tab did not switch browser tabs')
        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [29, 42], 'Ctrl+Shift missing before reverse tab navigation')
        pulse(1, 307)
        wait(browser, lambda s: s['focused'], 'Ctrl+Shift+Tab did not return to the browser fixture')
        control('emit', [[3, 2, 0], [3, 5, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Browser tab modifiers did not release')
        report['checks']['ctrl_tab_and_reverse_tab'] = True
        report['checks']['trigger_modifiers_and_combinations'] = True
        print('Application keys passed: 48 typing chords with Shift, release-only arrows, trigger holds and editing combinations.', flush=True)
        capture(monitor, directory, 'mapped-controller-browser')

        graphical(directory, 'swaymsg "[app_id=firefox_firefox] fullscreen disable; workspace number 2; layout splith; exec foot --app-id=mini-os-map-left --title=Controller-left /bin/sleep infinity"')
        wait(tree, lambda nodes: any(n['app_id'] == 'mini-os-map-left' for n in nodes), 'First Foot window missing')
        graphical(directory, 'swaymsg "exec foot --app-id=mini-os-map-right --title=Controller-right /bin/sleep infinity"')
        wait(tree, lambda nodes: any(n['app_id'] == 'mini-os-map-right' for n in nodes), 'Second Foot window missing')
        pulse(3, 0, -32768)
        focus = wait(tree, lambda nodes: any(n['app_id'] == 'mini-os-map-left' and n['focused'] for n in nodes), 'Left stick did not change window focus')
        report['focus_windows'] = [{'app_id': n['app_id'], 'focused': n['focused'], 'rect': n['rect']} for n in focus]
        action_count = len(status()['actions'])
        pulse(3, 0, 32767, 1.1)
        repeated_actions = status()['actions'][action_count:]
        if not 2 <= len(repeated_actions) <= 6 or any(a['command'] != 'focus right' for a in repeated_actions):
            raise ValueError('Stick repeat was absent or unbounded')
        frozen = status()['actions']
        control('emit', [[3, 0, 1000], [3, 1, -500]])
        time.sleep(.4)
        if status()['actions'] != frozen:
            raise ValueError('Neutral stick jitter caused a window action')
        control('emit', [[3, 0, 0], [3, 1, 0]])
        report['checks']['stick_repeat_and_deadzone'] = True
        report['stick_repeat_actions'] = repeated_actions
        graphical(directory, 'swaymsg "[app_id=mini-os-map-right] focus"')
        before_move = next(n for n in tree() if n['app_id'] == 'mini-os-map-right')['rect']
        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Shift hold missing before window move')
        pulse(3, 0, -32768)
        after_move = wait(tree, lambda nodes: next(n for n in nodes if n['app_id'] == 'mini-os-map-right')['rect']['x'] < before_move['x'], 'Shift+stick did not move the window')
        control('emit', [[3, 2, 0]])
        wait(keyboard_keys, lambda keys: not keys, 'Shift remained held after move')
        before_resize = next(n for n in after_move if n['app_id'] == 'mini-os-map-right')['rect']
        pulse(3, 3, 32767)
        resized = wait(tree, lambda nodes: next(n for n in nodes if n['app_id'] == 'mini-os-map-right')['rect']['width'] > before_resize['width'], 'Right stick did not resize the window')
        report['window_move_and_resize'] = {'before_move': before_move, 'after_move': before_resize,
                                         'after_resize': next(n for n in resized if n['app_id'] == 'mini-os-map-right')['rect']}
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
        sent = wait(tree, lambda nodes: any(n['app_id'] == 'mini-os-map-right' and n['workspace'] == '3' for n in nodes), 'Shift+bumper did not send the window to a workspace')
        control('emit', [[3, 2, 0]])
        report['checks']['focus_move_resize_and_workspace_clicks'] = True
        report['checks']['bumper_release_and_late_modifier'] = True
        capture(monitor, directory, 'mapped-controller-windows')
        print('Sway actions passed: focus, Shift+move, resize, bumper clicks and Shift+workspace move.', flush=True)

        def picker_processes():
            return ssh(directory, 'pgrep -x fuzzel || true').splitlines()

        def workspace_layout():
            def find(node, parent=None):
                if node.get('id') == terminal_id:
                    return parent['layout']
                for child in node.get('nodes', []) + node.get('floating_nodes', []):
                    result = find(child, node)
                    if result:
                        return result
            return find(json.loads(graphical(directory, 'swaymsg -t get_tree')))

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

        control('emit', [[1, 317, 1]])
        time.sleep(.4)
        if workspace_layout() != 'splith':
            raise ValueError('L3 changed layout before release')
        control('emit', [[1, 317, 0]])
        wait(workspace_layout, lambda layout: layout == 'tabbed', 'L3 did not select tabbed layout')
        pulse(1, 317)
        wait(workspace_layout, lambda layout: layout == 'splith', 'L3 did not restore the split layout')
        control('emit', [[1, 318, 1]])
        time.sleep(.4)
        if next(n for n in tree() if n['id'] == terminal_id)['fullscreen_mode']:
            raise ValueError('R3 changed fullscreen before release')
        control('emit', [[1, 318, 0]])
        wait(tree, lambda nodes: next(n for n in nodes if n['id'] == terminal_id)['fullscreen_mode'] == 1, 'R3 did not enable fullscreen')
        pulse(1, 318)
        wait(tree, lambda nodes: next(n for n in nodes if n['id'] == terminal_id)['fullscreen_mode'] == 0, 'R3 did not leave fullscreen')
        report['checks']['stick_click_layout_and_fullscreen_on_release'] = True

        pulse(1, 318)
        wait(tree, lambda nodes: next(n for n in nodes if n['id'] == terminal_id)['fullscreen_mode'] == 1, 'Fullscreen missing before launcher')
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
        report['checks']['menu_launcher_on_release'] = True

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
        chosen = wait(tree, lambda nodes: any(n['app_id'] == 'mini-os-map-right' and n['focused'] for n in nodes), 'Picker did not focus the selected window across workspaces')
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
        print('Extra buttons passed: release-only terminal, launcher, window picker, layout and fullscreen.', flush=True)

        graphical(directory, 'swaymsg "workspace number 1; [app_id=firefox_firefox] focus"')
        browser_set(text='preserved', selection=[9, 9], focus='editor', clear=True)
        control('emit', [inputs['UP'], inputs['A']])
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before disconnect')
        control('destroy')
        wait(status, lambda s: s['device'] is None and not s['keys'], 'Disconnect left mapped keys held')
        wait(keyboard_keys, lambda keys: not keys, 'Kernel keyboard retained Ctrl after disconnect')
        control('create')
        root('udevadm settle')
        wait(status, lambda s: s['device'] and s['grabbed'] and s['ready'], 'Reconnect failed')
        if browser()['text'] != 'preserved' or any(e['code'] != 'ControlLeft' for e in browser()['events']):
            raise ValueError('Disconnect committed an unfinished typing chord')
        report['checks']['disconnect_discards_unfinished_typing_chord'] = True
        report['checks']['disconnect_reconnect_releases_modifiers'] = True

        graphical(directory, 'swaymsg "workspace number 1; [app_id=firefox_firefox] focus; [app_id=firefox_firefox] fullscreen enable"')
        browser_set(text='hello', selection=[5, 5], focus='editor', clear=True)
        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before passthrough')
        graphical(directory, 'mini-os-gamepad --toggle')
        wait(status, lambda s: s['mode'] == 'passthrough' and not s['grabbed'] and not s['keys'], 'Passthrough did not release keyboard or source grab')
        wait(keyboard_keys, lambda keys: not keys, 'Ctrl remained held in passthrough')
        control('emit', [[3, 5, 0]])
        control('emit', [[1, 304, 1]])
        raw = wait(browser, lambda s: any(p['buttons'][0]['pressed'] for p in s['pads']), 'Firefox did not receive raw controller in passthrough')
        control('emit', [[1, 304, 0]])
        if raw['text'] != 'hello' or any(e['code'] == 'Enter' for e in raw['events']):
            raise ValueError('Passthrough still produced keyboard Enter')
        report['passthrough_browser'] = raw
        control('pulse', [[1, 314, 1], [1, 315, 1]], [[1, 314, 0], [1, 315, 0]], 1.2)
        wait(status, lambda s: s['mode'] == 'desktop' and s['ready'] and s['grabbed'], 'Controller chord did not restore desktop mode')
        report['checks']['passthrough_and_controller_toggle'] = True

        frozen_windows = {n['id'] for n in tree()}
        frozen_actions = status()['actions']
        control('emit', [[1, 315, 1]])
        control('emit', [[1, 314, 1]])
        time.sleep(1)
        if status()['mode'] != 'desktop' or {n['id'] for n in tree()} != frozen_windows or picker_processes():
            raise ValueError('Held toggle chord acted before release')
        control('emit', [[1, 315, 0]])
        if status()['mode'] != 'desktop' or picker_processes():
            raise ValueError('Partial chord release triggered an action')
        control('emit', [[1, 314, 0]])
        wait(status, lambda s: s['mode'] == 'passthrough', 'Full chord release did not toggle passthrough')
        if status()['actions'] != frozen_actions or {n['id'] for n in tree()} != frozen_windows or picker_processes():
            raise ValueError('Toggle chord also dispatched an individual action')
        control('pulse', [[1, 315, 1], [1, 314, 1]], [[1, 314, 0], [1, 315, 0]], 1)
        wait(status, lambda s: s['mode'] == 'desktop' and s['ready'], 'Reverse-order chord release did not restore navigation')
        control('pulse', [[1, 314, 1], [1, 315, 1]], [[1, 315, 0], [1, 314, 0]], .12)
        time.sleep(.3)
        if status()['mode'] != 'desktop' or status()['actions'] != frozen_actions or picker_processes():
            raise ValueError('Short overlapping chord dispatched an individual action')
        report['checks']['chord_release_consumes_individual_actions'] = True

        control('emit', [[3, 2, 255]])
        wait(keyboard_keys, lambda keys: keys == [42], 'Shift missing before lock')
        graphical(directory, 'mini-os-lock')
        wait(status, lambda s: s['paused'] and not s['grabbed'] and not s['keys'], 'Lock did not pause and release mapped keys')
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
        key(monitor, ['ctrl', 'alt', 'f2'])
        wait(status, lambda s: not s['session_active'] and not s['grabbed'] and not s['keys'], 'Inactive graphical session kept injecting keys')
        wait(keyboard_keys, lambda keys: not keys, 'Ctrl remained held on another console')
        control('emit', [[3, 5, 0]])
        key(monitor, ['ctrl', 'alt', 'f1'])
        wait(status, lambda s: s['session_active'] and s['ready'] and s['grabbed'], 'Mapping did not resume on the graphical console')
        report['checks']['inactive_console_releases_modifiers'] = True

        control('emit', [[3, 5, 255]])
        wait(keyboard_keys, lambda keys: keys == [29], 'Ctrl missing before service restart')
        graphical(directory, 'systemctl --user restart mini-os-gamepad.service')
        wait(status, lambda s: not s['keys'] and not s['ready'], 'Service restart injected held modifiers')
        wait(keyboard_keys, lambda keys: not keys, 'New keyboard started with Ctrl held')
        control('emit', [[3, 5, 0]])
        wait(status, lambda s: s['ready'], 'Mapping did not resume after neutral return')
        report['checks']['service_restart_waits_for_neutral'] = True
        report['final_status'] = status()
        report['service_state'] = graphical(directory, 'systemctl --user is-active mini-os-gamepad.service')
        report['passed'] = all(report['checks'].values())
        print('Lifecycle passed: disconnect, raw passthrough, controller chord, lock/unlock and service restart.', flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        if daemon_started:
            try:
                control('stop')
                root('for attempt in $(seq 1 30); do test -e /run/mini-os-gamepad-test || exit 0; sleep .1; done; exit 1')
                report['fixture_removed'] = True
            except Exception as error:
                report['cleanup_error'] = str(error)
                report['passed'] = False
        monitor.close()
        report['finished_at'] = time.time()
        (directory / 'gamepad-mapping-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
