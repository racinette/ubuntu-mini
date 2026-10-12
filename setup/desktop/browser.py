#!/usr/bin/env python3
"""Install Firefox and Chromium from the Snap Store or a verified asset cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlsplit

BROWSERS = ('firefox', 'chromium')

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--asset-url', help='Optional pinned artifact cache; otherwise use the Snap Store')
args = p.parse_args()
if os.geteuid() != 0: raise SystemExit('Run as root inside the target')
if not args.asset_url:
    # Snap resolves and verifies the current stable browser and its dependencies.
    # Keep an existing installation and its selected channel on rerun.
    for browser in BROWSERS:
        if subprocess.run(['snap', 'list', browser], capture_output=True).returncode != 0:
            subprocess.run(['snap', 'install', browser, '--channel=latest/stable'], check=True)
    print('Firefox and Chromium are installed; existing revisions and channels are retained on rerun')
    raise SystemExit(0)
manifest = json.loads(Path(__file__).with_name('browser-snaps.json').read_text())
required = {'snapd', 'core24', 'core26', 'cups', 'bare', 'gtk-common-themes', 'mesa-2404', 'gnome-46-2404', *BROWSERS}
names = [item['name'] for item in manifest]
if len(set(names)) != len(names) or not required.issubset(names):
    raise SystemExit('The complete Firefox/Chromium runtime manifest is required')
# Inspect before fetching: a rerun preserves installed revisions and channels.
pending = [item for item in manifest if subprocess.run(
    ['snap', 'list', item['name']], capture_output=True).returncode != 0]
transport = urlsplit(args.asset_url)
local_assets = None
if transport.scheme == 'file':
    if transport.netloc not in ('', 'localhost'):
        raise SystemExit('Local artifacts require a local file URL')
    local_assets = Path(urllib.request.url2pathname(transport.path))
with tempfile.TemporaryDirectory(prefix='minion-browser-') as scratch:
    root = local_assets if local_assets is not None else Path(scratch)
    for item in pending:
        for kind in ('assert', 'snap'):
            target = root / item[kind]
            if local_assets is None:
                with urllib.request.urlopen(args.asset_url.rstrip('/') + '/' + target.name, timeout=120) as response, target.open('wb') as file:
                    while chunk := response.read(1024**2):
                        file.write(chunk)
            with target.open('rb') as file:
                actual = hashlib.file_digest(file, 'sha256').hexdigest()
            if actual != item[kind + '_sha256']:
                raise ValueError('Cached artifact digest mismatch: ' + target.name)
        subprocess.run(['snap', 'ack', root / item['assert']], check=True)
    for item in pending:
        # Reapplying does not revert an already installed/newer browser revision.
        check = subprocess.run(['snap', 'list', item['name']], capture_output=True)
        if check.returncode == 0: continue
        subprocess.run(['snap', 'install', root / item['snap']], check=True)
        subprocess.run(['snap', 'switch', '--channel=latest/stable', item['name']], check=True)
print('Firefox, Chromium and their signed runtime dependencies are installed')
