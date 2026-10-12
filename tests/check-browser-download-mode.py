#!/usr/bin/env python3
"""Check Snap Store command selection without installing anything on the host."""
from pathlib import Path
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
import tempfile
from itertools import product
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / 'setup/desktop/browser.py'
for firefox_installed, chromium_installed in product((False, True), repeat=2):
    installed = {'firefox': firefox_installed, 'chromium': chromium_installed}
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        present = command[:2] != ['snap', 'list'] or installed[command[2]]
        return subprocess.CompletedProcess(command, 0 if present else 1)

    with patch.object(sys, 'argv', [str(script)]), patch('os.geteuid', return_value=0), patch('subprocess.run', side_effect=run):
        try:
            runpy.run_path(str(script), run_name='__main__')
        except SystemExit as error:
            assert error.code == 0
    expected = []
    for browser in ('firefox', 'chromium'):
        expected.append(['snap', 'list', browser])
        if not installed[browser]:
            expected.append(['snap', 'install', browser, '--channel=latest/stable'])
    assert calls == expected, calls
print('Snap Store selection and existing-browser preservation passed (isolated commands).')

# Exercise the same signed-cache path with isolated artifacts and Snap calls.
original = json.loads(script.with_name('browser-snaps.json').read_text())
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    cached_script = root / 'browser.py'
    shutil.copyfile(script, cached_script)
    manifest = json.loads(json.dumps(original))
    for item in manifest:
        for kind in ('snap', 'assert'):
            payload = (item['name'] + ':' + kind).encode()
            (root / item[kind]).write_bytes(payload)
            item[kind + '_sha256'] = hashlib.sha256(payload).hexdigest()
    manifest_file = root / 'browser-snaps.json'
    manifest_file.write_text(json.dumps(manifest))
    names = {item['name'] for item in manifest}
    for present in (set(), names - {'chromium'}, names):
        calls = []
        def cached_run(command, **kwargs):
            calls.append(command)
            code = int(command[:2] == ['snap', 'list'] and command[2] not in present)
            return subprocess.CompletedProcess(command, code)
        with patch.object(sys, 'argv', [str(cached_script), '--asset-url', root.as_uri()]), \
                patch('os.geteuid', return_value=0), patch('subprocess.run', side_effect=cached_run), \
                patch('urllib.request.urlopen', side_effect=AssertionError('Local cache attempted network access')):
            runpy.run_path(str(cached_script), run_name='__main__')
        pending = [item for item in manifest if item['name'] not in present]
        assert [cmd for cmd in calls if cmd[:2] == ['snap', 'ack']] == [
            ['snap', 'ack', root / item['assert']] for item in pending]
        assert [cmd for cmd in calls if cmd[:2] == ['snap', 'install']] == [
            ['snap', 'install', root / item['snap']] for item in pending]
        assert [cmd for cmd in calls if cmd[:2] == ['snap', 'switch']] == [
            ['snap', 'switch', '--channel=latest/stable', item['name']] for item in pending]
    # Refuse damaged Chromium artifacts before acknowledging/installing them.
    chromium = next(item for item in manifest if item['name'] == 'chromium')
    (root / chromium['snap']).write_bytes(b'corrupted')
    present = names - {'chromium'}
    calls = []
    with patch.object(sys, 'argv', [str(cached_script), '--asset-url', root.as_uri()]), \
            patch('os.geteuid', return_value=0), patch('subprocess.run', side_effect=cached_run):
        try:
            runpy.run_path(str(cached_script), run_name='__main__')
        except ValueError as error:
            assert 'digest mismatch' in str(error)
        else:
            raise AssertionError('Damaged cached Chromium accepted')
    assert all(cmd[:2] == ['snap', 'list'] for cmd in calls)
print('Signed-cache checks passed: complete dependency order, mixed reruns, local transport and damaged-artifact refusal.')
