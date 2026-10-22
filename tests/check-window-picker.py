#!/usr/bin/env python3
"""Check window-picker cancellation and child cleanup without a compositor."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

PROJECT = Path(__file__).resolve().parents[1]


def wait_for(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for picker fixture')


with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    sway = directory / 'swaymsg'
    sway.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys
if sys.argv[-1] == 'get_tree':
    print(json.dumps({'type':'workspace', 'name':'1', 'nodes':[
        {'id':42, 'app_id':'foot', 'name':'Example', 'focused':True}]}))
else:
    pathlib.Path(os.environ['FIXTURE_ROOT'], 'focused').write_text(sys.argv[-1])
    print('[{"success":true}]')
''')
    fuzzel = directory / 'fuzzel'
    fuzzel.write_text('''#!/usr/bin/python3
import os, pathlib, signal, sys, time
root = pathlib.Path(os.environ['FIXTURE_ROOT'])
sys.stdin.read()
if os.environ.get('FIXTURE_ACCEPT'):
    print('0')
else:
    def stop(*_):
        (root / 'stopped').touch()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    (root / 'ready').touch()
    while True:
        time.sleep(.02)
''')
    sway.chmod(0o755)
    fuzzel.chmod(0o755)
    environment = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ['PATH'],
                       FIXTURE_ROOT=str(directory), SWAYSOCK='fixture', XDG_RUNTIME_DIR=str(directory))
    command = ['/usr/bin/python3', str(PROJECT / 'setup/desktop/minion-window-picker')]
    picker = subprocess.Popen(command, env=environment)
    try:
        wait_for(lambda: (directory / 'ready').exists())
        picker.terminate()
        assert picker.wait(timeout=3) == 0
        assert (directory / 'stopped').exists(), 'Child overlay survived cancellation'
        assert not (directory / 'focused').exists(), 'Cancellation selected a window'
        subprocess.run(command, env=dict(environment, FIXTURE_ACCEPT='1'), check=True, timeout=5)
        assert (directory / 'focused').read_text() == '[con_id=42] focus'
    finally:
        if picker.poll() is None:
            picker.kill()
            picker.wait()
print('Passed: picker cancellation closes its overlay, preserves focus and releases its lock; selection focuses its target.')
