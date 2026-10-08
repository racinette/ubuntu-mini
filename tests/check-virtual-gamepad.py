#!/usr/bin/env python3
"""Exercise guest uinput controller events through evdev, Firefox and a Sway session."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time

from gui import capture, experiment, key, type_text
from qmp import Monitor
from session import graphical, ssh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
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

    def control(operation, kind='gamepad', events=None):
        request = {'operation': operation, 'kind': kind}
        if events is not None:
            request['events'] = events
        code = '''import json,socket
s=socket.socket(socket.AF_UNIX);s.connect('/run/mini-os-gamepad-test/control.sock')
s.sendall((%r+'\\n').encode());print(s.makefile().readline())
''' % json.dumps(request)
        result = json.loads(root('python3 -c ' + shlex.quote(code)))
        if 'error' in result:
            raise ValueError(result['error'])
        return result

    def browser():
        return json.loads(ssh(directory, "python3 -c 'import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8765/state\").read().decode())'"))

    def wait_browser(predicate, label):
        deadline = time.monotonic() + 12
        while True:
            value = browser()
            if predicate(value):
                return value
            if time.monotonic() > deadline:
                raise ValueError(label + ': ' + json.dumps(value))
            time.sleep(.1)

    def window_summary():
        tree = json.loads(graphical(directory, 'swaymsg -t get_tree'))

        def walk(node):
            result = [(node['id'], node.get('app_id'), node.get('focused'), node.get('num'))]
            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                result.extend(walk(child))
            return result

        return walk(tree)

    report = {'passed': False, 'kind': 'Guest kernel uinput; no USB transport or WIN Mini hardware emulation',
              'started_at': time.time(), 'baseline': str(parent)}
    daemon_started = False
    monitor = Monitor(directory / 'qmp.sock')
    try:
        if not ssh(directory, 'pgrep -x sway || true').strip():
            raise ValueError('Authenticate into the graphical session before this test')
        ssh(directory, 'mkdir -p ~/mini-os-gamepad-fixture')
        for filename in ('virtual-gamepad.py', 'gamepad-http.py', 'gamepad-test.html'):
            subprocess.run(['scp', '-i', str(directory / 'ssh-key'), '-P', str(state['ssh_port']),
                            '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                            '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'),
                            str(experiment.PROJECT / 'tests/fixtures' / filename),
                            'vmuser@127.0.0.1:mini-os-gamepad-fixture/' + filename], check=True, capture_output=True)
        root('modprobe uinput; modprobe joydev; systemd-run --quiet --unit=mini-os-virtual-gamepad python3 /home/vmuser/mini-os-gamepad-fixture/virtual-gamepad.py /run/mini-os-gamepad-test')
        daemon_started = True
        root('for attempt in $(seq 1 30); do test ! -S /run/mini-os-gamepad-test/control.sock || exit 0; sleep .1; done; exit 1')
        graphical(directory, 'systemctl --user stop mini-os-gamepad-http.service 2>/dev/null || true; systemd-run --user --quiet --unit=mini-os-gamepad-http python3 /home/vmuser/mini-os-gamepad-fixture/gamepad-http.py')
        created = control('create')
        root('udevadm settle')
        sysname = created['sysname']
        info = json.loads(root('python3 -c ' + shlex.quote(f'''
import json,subprocess
from pathlib import Path
p=Path('/sys/class/input/{sysname}')
nodes=[x.name for x in p.iterdir() if x.name.startswith(('event','js'))]
event=next(n for n in nodes if n.startswith('event'))
print(json.dumps({{'name':(p/'name').read_text().strip(),'nodes':nodes,
 'event':'/dev/input/'+event,
 'udev':subprocess.check_output(['udevadm','info','--query=property','--name=/dev/input/'+event],text=True)}}))
''')))
        report['device'] = info
        report['normal_user_can_read_events'] = ssh(directory, 'python3 -c ' + shlex.quote(
            f"import os;fd=os.open({info['event']!r},os.O_RDONLY|os.O_NONBLOCK);os.close(fd);print('OK')")).strip() == 'OK'
        report['joystick_classified'] = 'ID_INPUT_JOYSTICK=1' in info['udev'] and any(n.startswith('js') for n in info['nodes'])
        graphical(directory, 'swaymsg "exec firefox --new-window http://127.0.0.1:8765/"')
        deadline = time.monotonic() + 30
        while True:
            if 'firefox_firefox' in json.dumps(window_summary()):
                break
            if time.monotonic() > deadline:
                raise ValueError('Firefox did not open a window')
            time.sleep(.5)
        graphical(directory, 'swaymsg "[app_id=firefox_firefox] focus"; swaymsg "[app_id=firefox_firefox] fullscreen enable"')
        key(monitor, ['ctrl', 'l'])
        type_text(monitor, 'http://127.0.0.1:8765/\n')
        wait_browser(lambda s: s.get('api') == 'function' and s.get('focused'), 'Browser fixture did not load')
        control('emit', events=[[1, 304, 1]])
        first = wait_browser(lambda s: len(s.get('pads', [])) == 1 and any(b['pressed'] for b in s['pads'][0]['buttons']), 'Browser did not see first gamepad button')
        report['browser_initial'] = first
        control('emit', events=[[1, 304, 0]])
        rest = wait_browser(lambda s: len(s.get('pads', [])) == 1 and not any(b['pressed'] for b in s['pads'][0]['buttons']), 'Button release was lost')
        layout_before = window_summary()
        button_results = []
        for code in (304, 305, 307, 308, 310, 311, 314, 315, 316, 317, 318):
            observation = control('probe', events=[[1, code, 1]])
            active = wait_browser(lambda s: any(b['pressed'] for b in s['pads'][0]['buttons']), f'Button {code} press missing')
            kernel_press = [1, code, 1] in observation['events']
            indexes = [i for i, b in enumerate(active['pads'][0]['buttons']) if b['pressed']]
            release = control('probe', events=[[1, code, 0]])
            wait_browser(lambda s: not any(b['pressed'] for b in s['pads'][0]['buttons']), f'Button {code} release missing')
            if not kernel_press or [1, code, 0] not in release['events']:
                raise ValueError('Kernel button observation mismatch')
            button_results.append({'linux_code': code, 'browser_buttons': indexes, 'press_and_release': True})
        report['buttons'] = button_results
        axes = []
        neutral = {'axes': rest['pads'][0]['axes'], 'buttons': rest['pads'][0]['buttons']}
        for code, extremes in ((0, (-32768, 32767)), (1, (-32768, 32767)), (3, (-32768, 32767)),
                               (4, (-32768, 32767)), (2, (255,)), (5, (255,)), (16, (-1, 1)), (17, (-1, 1))):
            for value in extremes:
                observed = control('probe', events=[[3, code, value]])
                active = wait_browser(lambda s: any(abs(a - b) > .5 for a, b in zip(s['pads'][0]['axes'], neutral['axes']))
                                      or s['pads'][0]['buttons'] != neutral['buttons'], f'Axis {code} movement missing')
                if [3, code, value] not in observed['events']:
                    raise ValueError('Kernel axis observation mismatch')
                axes.append({'linux_code': code, 'value': value, 'browser_axes': active['pads'][0]['axes'],
                             'browser_buttons': active['pads'][0]['buttons']})
                control('emit', events=[[3, code, 0]])
                wait_browser(lambda s: all(abs(a - b) < .001 for a, b in zip(s['pads'][0]['axes'], neutral['axes']))
                             and s['pads'][0]['buttons'] == neutral['buttons'], f'Axis {code} did not return to neutral')
        report['axes'] = axes
        report['sway_layout_and_focus_unchanged'] = window_summary() == layout_before
        capture(monitor, directory, 'virtual-gamepad-browser')
        control('destroy')
        disconnected = wait_browser(lambda s: not s['pads'] and s['disconnections'] >= 1, 'Browser missed disconnect')
        control('create')
        root('udevadm settle')
        control('emit', events=[[1, 304, 1]])
        reconnected = wait_browser(lambda s: len(s['pads']) == 1 and s['connections'] >= 2
                                   and any(b['pressed'] for b in s['pads'][0]['buttons']), 'Browser missed reconnect')
        control('emit', events=[[1, 304, 0]])
        report['disconnect_reconnect'] = {'disconnected': disconnected, 'reconnected': reconnected}
        report['passed'] = all((report['normal_user_can_read_events'], report['joystick_classified'],
                               report['sway_layout_and_focus_unchanged'], len(button_results) == 11, len(axes) == 14))
        if not report['passed']:
            raise ValueError('Virtual gamepad acceptance failed')
        print('Virtual gamepad passed: user access, 11 buttons, both sticks, triggers, D-pad, Firefox and reconnect. Sway has no automatic controller mapping.', flush=True)
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
        (directory / 'virtual-gamepad-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
