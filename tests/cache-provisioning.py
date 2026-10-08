#!/usr/bin/env python3
"""Fill or verify the pinned shell/browser cache, without installing on the host."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

project = Path(__file__).resolve().parents[1]
assets = project / '.local/mirror/assets'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--check', action='store_true', help='Verify existing files without network requests')
args = p.parse_args()
assets.mkdir(parents=True, exist_ok=True)

def verify(filename, expected):
    if Path(filename).name != filename:
        raise ValueError('Artifact filename must be plain')
    path = assets / filename
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while chunk := file.read(1024**2):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError('Cached digest mismatch: ' + filename)
    return True

for item in json.loads((project / 'setup/shell/artifacts.json').read_text()).values():
    if not verify(item['filename'], item['sha256']):
        if args.check:
            raise SystemExit('Missing pinned artifact: ' + item['filename'])
        subprocess.run(['python3', project / 'tests/cache-asset.py', item['url'],
                        item['sha256'], item['filename']], check=True)
for item in json.loads((project / 'setup/desktop/browser-snaps.json').read_text()):
    present = [verify(item[kind], item[kind + '_sha256']) for kind in ('snap', 'assert')]
    if not all(present):
        if args.check:
            raise SystemExit('Missing pinned Snap bundle: ' + item['name'])
        # A retained .snap can be reused by snap download. Never replace a
        # successfully verified cached pair with changing assertion metadata.
        subprocess.run(['snap', 'download', item['name'], '--revision=' + item['revision'],
                        '--basename=' + str(assets / Path(item['snap']).stem)], check=True)
        if not all(verify(item[kind], item[kind + '_sha256']) for kind in ('snap', 'assert')):
            raise ValueError('Incomplete downloaded bundle: ' + item['name'])
if not args.check:
    shutil.copyfile(project / 'tests/fixtures/desktop-test.html', assets / 'desktop-test.html')
print('Pinned shell and signed browser cache verified')
