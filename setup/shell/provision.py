#!/usr/bin/env python3
"""Install pinned shell artifacts and opt a user into the interactive integration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('username')
p.add_argument('--asset-url', help='Optional artifact cache; otherwise use the pinned upstream release URLs')
args = p.parse_args()
if os.geteuid() != 0: raise SystemExit('Run as root inside the installed target')
user = pwd.getpwnam(args.username)
home = Path(user.pw_dir)
(home / '.config').mkdir(exist_ok=True)
os.chown(home / '.config', user.pw_uid, user.pw_gid)
artifacts = json.loads(HERE.joinpath('artifacts.json').read_text())
with tempfile.TemporaryDirectory(prefix='mini-os-shell-') as scratch:
    root = Path(scratch)
    for name, artifact in artifacts.items():
        archive = root / artifact['filename']
        url = args.asset_url.rstrip('/') + '/' + artifact['filename'] if args.asset_url else artifact['url']
        print('Downloading ' + name + ' from ' + url, flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as target:
            while chunk := response.read(1024**2):
                target.write(chunk)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != artifact['sha256']:
            raise ValueError('Artifact checksum mismatch: ' + name)
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter='data')
    source = root / 'atuin-x86_64-unknown-linux-musl/atuin'
    subprocess.run(['install', '-m', '755', source, '/usr/local/bin/atuin'], check=True)
    subprocess.run(['bash', root / 'ble-nightly/ble.sh', '--install', '/usr/local/share'], check=True)
Path('/usr/local/share/mini-os').mkdir(parents=True, exist_ok=True)
Path('/usr/local/share/mini-os/bashrc.bash').write_text(HERE.joinpath('bashrc.bash').read_text())
# Retain user-edited configuration on rerun, while refreshing the owned integration.
for relative, source in [('.config/atuin/config.toml', 'config.toml'), ('.config/foot/foot.ini', 'foot.ini')]:
    target = home / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(HERE.joinpath(source).read_text())
        target.chmod(0o600)
        os.chown(target, user.pw_uid, user.pw_gid)
    os.chown(target.parent, user.pw_uid, user.pw_gid)
bashrc = home / '.bashrc'
text = bashrc.read_text() if bashrc.exists() else ''
line = 'source /usr/local/share/mini-os/bashrc.bash'
if line not in text.splitlines():
    bashrc.write_text(text.rstrip() + '\n\n# Mini OS interactive Bash\n' + line + '\n')
    os.chown(bashrc, user.pw_uid, user.pw_gid)
    bashrc.chmod(0o644)
print('Pinned shell integration installed for ' + args.username)
