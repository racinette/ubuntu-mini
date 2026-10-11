#!/usr/bin/env python3
"""Install the pinned proxy service without enabling it or changing routes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent


def atomic_install(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as target:
            target.write(data)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if (release.get('ID', '').strip('"') != 'ubuntu'
            or release.get('VERSION_ID', '').strip('"') != '24.04'
            or not Path('/run/systemd/system').is_dir()):
        raise ValueError('Run in installed Ubuntu 24.04 with systemd')
    architecture = {'x86_64': 'linux-amd64', 'aarch64': 'linux-arm64'}.get(platform.machine())
    if not architecture:
        raise ValueError('Unsupported proxy architecture')
    if not Path('/usr/bin/resolvectl').is_file():
        raise SystemExit('Missing resolvectl. Install Ubuntu systemd-resolved before proxy setup.')
    manifest = json.loads((HERE / 'artifacts.json').read_text())
    artifact = manifest['artifacts'][architecture]
    if args.check:
        print('Proxy prerequisites passed; no downloads, installation or route changes')
        return
    if os.geteuid() != 0:
        raise ValueError('Run with sudo')
    binary = Path('/usr/local/lib/minion-proxy/mihomo')
    if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != artifact['binary_sha256']:
        print('Downloading verified Mihomo ' + manifest['version'], flush=True)
        with urllib.request.urlopen(artifact['url'], timeout=120) as response:
            archive = response.read(80 * 1024 * 1024)
        if hashlib.sha256(archive).hexdigest() != artifact['sha256']:
            raise ValueError('Mihomo download checksum mismatch')
        content = gzip.decompress(archive)
        if hashlib.sha256(content).hexdigest() != artifact['binary_sha256']:
            raise ValueError('Mihomo binary checksum mismatch')
        atomic_install(binary, content, 0o755)
    # Boot must not depend on a movable, user-writable source checkout. The
    # administrator uses manage.py in the repo; systemd uses this owned copy.
    atomic_install(binary.parent / 'manage.py', (HERE / 'manage.py').read_bytes(), 0o644)
    atomic_install(Path('/etc/systemd/system/minion-proxy.service'),
                   (HERE / 'minion-proxy.service').read_bytes(), 0o644)
    state = Path('/var/lib/minion/proxy')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    print('Proxy service installed; existing configuration and activation state retained.')
    print('From the repository, configure with: sudo python3 setup/proxy/manage.py configure')
    print('Enable with: sudo systemctl enable --now minion-proxy.service')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        raise SystemExit('Proxy installation failed; check target prerequisites and download connectivity')
