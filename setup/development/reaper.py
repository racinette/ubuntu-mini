#!/usr/bin/env python3
"""Install the official checksum-pinned Linux REAPER release as the desktop user."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
RELEASE = json.loads((HERE / 'reaper-release.json').read_text())
MAX_DOWNLOAD = 64 * 1024 * 1024


def payload(cache, asset_dir=None):
    cached = cache / (RELEASE['sha256'] + '-' + RELEASE['filename'])
    source = Path(asset_dir) / RELEASE['filename'] if asset_dir else cached
    if source.exists():
        if source.stat().st_size > MAX_DOWNLOAD:
            raise ValueError('REAPER download exceeds size limit')
        data = source.read_bytes()
    else:
        if asset_dir:
            raise FileNotFoundError(source)
        with urllib.request.urlopen(RELEASE['url'], timeout=60) as response:
            data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD or hashlib.sha256(data).hexdigest() != RELEASE['sha256']:
        raise ValueError('REAPER checksum mismatch')
    if not cached.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        try:
            temporary_path.replace(cached)
        finally:
            temporary_path.unlink(missing_ok=True)
    return data


def unpack(data, destination):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > 300 * 1024 * 1024:
            raise ValueError('REAPER archive exceeds size limit')
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '..' in path.parts or
                    not (member.isfile() or member.isdir())):
                raise ValueError('Unsafe REAPER archive entry')
        archive.extractall(destination, members=members, filter='data')


def install(asset_dir=None):
    if os.geteuid() == 0:
        raise SystemExit('Run this installer as the desktop user, not root')
    if platform.machine() != 'x86_64':
        raise SystemExit('This REAPER release supports Linux x86_64 only')
    home = Path.home()
    target = home / 'opt/REAPER'
    existing = shutil.which('reaper')
    if not existing and (target / 'reaper').is_file() and os.access(target / 'reaper', os.X_OK):
        existing = str(target / 'reaper')
    if existing:
        print(f'Retaining installed REAPER: {existing}', flush=True)
        return
    if target.exists() or target.is_symlink():
        raise RuntimeError(f'Existing REAPER directory has no usable executable: {target}')
    command = home / '.local/bin/reaper'
    if command.exists() or command.is_symlink():
        raise RuntimeError(f'Existing REAPER command is not usable: {command}')
    cache = Path(os.environ.get('XDG_CACHE_HOME', home / '.cache')) / 'minion/audio/reaper'
    data = payload(cache, asset_dir)
    with tempfile.TemporaryDirectory(prefix='minion-reaper-') as temporary:
        staging = Path(temporary)
        unpack(data, staging)
        release = staging / 'reaper_linux_x86_64'
        if not (release / 'install-reaper.sh').is_file() or not (release / 'REAPER/reaper').is_file():
            raise ValueError('REAPER archive lacks the installer or executable')
        # Use Cockos's installer for its launcher, icons, MIME types and
        # uninstaller. Never request a root-owned /usr/local/bin symlink.
        subprocess.run(['/bin/sh', str(release / 'install-reaper.sh'),
                        '--install', str(target.parent), '--integrate-user-desktop', '--quiet'],
                       check=True, stdin=subprocess.DEVNULL, timeout=180)
    if not (target / 'reaper').is_file() or not os.access(target / 'reaper', os.X_OK):
        raise RuntimeError('REAPER installer completed without a usable executable')
    command.parent.mkdir(parents=True, exist_ok=True)
    command.symlink_to(target / 'reaper')
    print(f'Installed REAPER {RELEASE["version"]}: {target}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Show the pinned release without downloads or writes')
    parser.add_argument('--asset-dir', type=Path, help='Use a previously downloaded release')
    args = parser.parse_args()
    if args.check:
        print(f'REAPER {RELEASE["version"]}: {RELEASE["sha256"]}')
    else:
        install(args.asset_dir)
