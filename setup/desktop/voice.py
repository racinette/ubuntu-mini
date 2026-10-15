#!/usr/bin/env python3
"""Install pinned local dictation and seed personal configuration as root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
ARTIFACTS = json.loads((HERE / 'voice-artifacts.json').read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install_payload(artifact, target, previous=None, asset_dir=None, mode=0o644):
    if target.is_symlink():
        raise ValueError(f'Refusing symlink at dictation install path: {target}')
    if target.exists():
        actual = digest(target)
        if actual == artifact['sha256']:
            print(f'Retaining {artifact["filename"]}', flush=True)
            return
        if actual != previous:
            raise ValueError(f'Existing dictation file is unmanaged or modified: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        source = Path(asset_dir) / artifact['filename'] if asset_dir else None
        print(f'Installing verified {artifact["filename"]}', flush=True)
        with (source.open('rb') if source else urllib.request.urlopen(artifact['url'], timeout=60)) as stream:
            with staging.open('wb') as output:
                size = 0
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > artifact['size']:
                        raise ValueError('Dictation download exceeds expected size')
                    output.write(chunk)
        if size != artifact['size'] or digest(staging) != artifact['sha256']:
            raise ValueError(f'Dictation checksum/size mismatch: {artifact["filename"]}')
        staging.chmod(mode)
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)


def seed_config(user):
    config = Path(user.pw_dir) / '.config/voxtype/config.toml'
    if config.exists() or config.is_symlink():
        return  # Preserve personal engine, model, language and output settings.
    missing = [p for p in config.parents if not p.exists()]
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text((HERE / 'voxtype.toml').read_text())
    config.chmod(0o600)
    for path in [config, *missing]:
        os.chown(path, user.pw_uid, user.pw_gid)


def install(user, asset_dir=None, root=Path('/')):
    if os.geteuid() != 0:
        raise SystemExit('Run the dictation installer as root with --user USERNAME')
    share = root / 'usr/local/share/minion/voice'
    marker = share / 'install.json'
    previous = json.loads(marker.read_text()) if marker.exists() else {}
    for name, target, mode in (
        ('runtime', root / 'usr/local/bin/voxtype', 0o755),
        ('model', share / ARTIFACTS['model']['filename'], 0o644),
    ):
        install_payload(ARTIFACTS[name], target, previous.get(name, {}).get('sha256'), asset_dir, mode)
    share.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=share, delete=False) as stream:
        json.dump(ARTIFACTS, stream, indent=2)
        stream.write('\n')
        staging = Path(stream.name)
    staging.chmod(0o644)
    staging.replace(marker)
    seed_config(user)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', default=os.environ.get('SUDO_USER'))
    parser.add_argument('--asset-dir', type=Path, help='Directory of already downloaded release/model files')
    parser.add_argument('--check', action='store_true', help='List pinned artifacts without downloads or changes')
    args = parser.parse_args()
    if args.check:
        for artifact in ARTIFACTS.values():
            print(f'{artifact["filename"]}: {artifact["sha256"]}')
    else:
        if not args.user or args.user == 'root':
            parser.error('Pass --user with an existing regular desktop account')
        user = pwd.getpwnam(args.user)
        if user.pw_uid < 1000 or not Path(user.pw_dir).is_dir():
            parser.error('Select an existing regular desktop account')
        install(user, args.asset_dir)
