#!/usr/bin/env python3
"""Install the verified static MetaCubeXD panel; retain the local API identity."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import secrets
import shutil
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent


def unpack(payload, destination):
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > 80 * 1024 * 1024:
            raise ValueError('Dashboard archive exceeds size limit')
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe dashboard archive entry')
        archive.extractall(destination, members=members, filter='data')
    if not (destination / 'index.html').is_file():
        raise ValueError('Dashboard archive lacks index.html')


def install(state, atomic_install, username=None, asset=None):
    manifest = json.loads((HERE / 'artifacts.json').read_text())['dashboard']
    target = state / 'ui'
    stamp = target / '.minion-version'
    if not (target / 'index.html').is_file() or not stamp.exists() or stamp.read_text().strip() != manifest['sha256']:
        if asset:
            payload = Path(asset).read_bytes()
        else:
            with urllib.request.urlopen(manifest['url'], timeout=60) as response:
                payload = response.read(16 * 1024 * 1024 + 1)
        if len(payload) > 16 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != manifest['sha256']:
            raise ValueError('Dashboard checksum mismatch')
        with tempfile.TemporaryDirectory(prefix='.dashboard-', dir=state) as temporary:
            prepared = Path(temporary) / 'ui'
            prepared.mkdir()
            unpack(payload, prepared)
            for path in prepared.rglob('*'):
                path.chmod(0o755 if path.is_dir() else 0o644)
            (prepared / '.minion-version').write_text(manifest['sha256'] + '\n')
            previous = state / '.ui-previous'
            if previous.exists():
                shutil.rmtree(previous)
            if target.exists():
                target.rename(previous)
            try:
                prepared.rename(target)
            except Exception:
                if previous.exists():
                    previous.rename(target)
                raise
            if previous.exists():
                shutil.rmtree(previous)
    settings = state / 'dashboard.json'
    if settings.exists():
        access = json.loads(settings.read_text())
        if not isinstance(access.get('secret'), str) or len(access['secret']) < 32:
            raise ValueError('Invalid existing dashboard identity')
    else:
        access = {'secret': secrets.token_urlsafe(32)}
        atomic_install(settings, (json.dumps(access) + '\n').encode(), 0o600)
    username = username or os.environ.get('SUDO_USER')
    if username and username != 'root':
        user = pwd.getpwnam(username)
        if user.pw_uid < 1000:
            raise ValueError('Dashboard access requires a regular desktop account')
        credential = Path('/etc/minion/proxy-dashboard.json')
        atomic_install(credential, (json.dumps(access) + '\n').encode(), 0o640)
        os.chown(credential, 0, user.pw_gid)
