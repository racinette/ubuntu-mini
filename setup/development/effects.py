#!/usr/bin/env python3
"""Install checksum-pinned native VST3 guitar effects as the desktop user."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
ARTIFACTS = json.loads((HERE / 'effects-artifacts.json').read_text())
MAX_DOWNLOAD = 64 * 1024 * 1024


def hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob('*'))
            if path.is_file() and path.name != '.minion-install.json'}


def payload(artifact, cache, asset_dir=None):
    cached = cache / (artifact['sha256'] + '-' + artifact['filename'])
    source = Path(asset_dir) / artifact['filename'] if asset_dir else cached
    if source.exists():
        if source.stat().st_size > MAX_DOWNLOAD:
            raise ValueError(f'Plugin download exceeds size limit: {source}')
        data = source.read_bytes()
    else:
        if asset_dir:
            raise FileNotFoundError(source)
        with urllib.request.urlopen(artifact['url'], timeout=60) as response:
            data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD or hashlib.sha256(data).hexdigest() != artifact['sha256']:
        raise ValueError(f'Plugin checksum mismatch: {artifact["name"]}')
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


def unpack(data, artifact, destination):
    if artifact['format'] == 'deb':
        package = destination / 'release.deb'
        package.write_bytes(data)
        data = subprocess.run(['dpkg-deb', '--fsys-tarfile', str(package)],
                              check=True, timeout=60, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > 300 * 1024 * 1024:
            raise ValueError('Plugin archive exceeds size limit')
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe plugin archive entry')
        archive.extractall(destination, members=members, filter='data')


def install(asset_dir=None):
    if os.geteuid() == 0:
        raise SystemExit('Run this installer as the desktop user, not root')
    home = Path.home()
    root = home / '.vst3'
    cache = Path(os.environ.get('XDG_CACHE_HOME', home / '.cache')) / 'minion/audio/effects'
    for artifact in ARTIFACTS:
        target = root / Path(artifact['bundle']).name
        marker = target / '.minion-install.json'
        previous = json.loads(marker.read_text()) if marker.is_file() else None
        if target.exists() and (target.is_symlink() or not previous or
                                any(p.is_symlink() for p in target.rglob('*')) or
                                previous.get('files') != hashes(target)):
            raise RuntimeError(f'Existing plugin is unmanaged or modified: {target}')
        if previous and previous.get('artifact') == artifact:
            print(f'Retaining {artifact["name"]} {artifact["version"]}', flush=True)
            continue
        data = payload(artifact, cache, asset_dir)
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.minion-effect-', dir=root) as temporary:
            staging = Path(temporary)
            unpack(data, artifact, staging)
            prepared = staging / artifact['bundle']
            binary = prepared / 'Contents/x86_64-linux' / (artifact['name'] + '.so')
            if not binary.is_file():
                raise ValueError(f'Archive lacks native VST3: {artifact["name"]}')
            if artifact.get('license'):
                resources = prepared / 'Contents/Resources'
                resources.mkdir(exist_ok=True)
                shutil.copyfile(staging / artifact['license'], resources / 'LICENSE.txt')
            (prepared / '.minion-install.json').write_text(json.dumps(
                dict(artifact=artifact, files=hashes(prepared)), indent=2) + '\n')
            backup = staging / 'previous'
            if target.exists():
                target.rename(backup)
            try:
                prepared.rename(target)
            except OSError:
                if backup.exists():
                    backup.rename(target)
                raise
        print(f'Installed {artifact["name"]} {artifact["version"]}: {target}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='List releases without downloads or writes')
    parser.add_argument('--asset-dir', type=Path, help='Use previously downloaded, checksum-verified releases')
    args = parser.parse_args()
    if args.check:
        for artifact in ARTIFACTS:
            print(f'{artifact["name"]} {artifact["version"]}: {artifact["sha256"]}')
    else:
        install(args.asset_dir)
