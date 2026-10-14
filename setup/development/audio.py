#!/usr/bin/env python3
"""Install pinned JUCE sources, SuperCollider's VST3 host and a synth starter."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SOURCES = json.loads(HERE.joinpath('audio-sources.json').read_text())


def run(*command, **kwargs):
    return subprocess.run([str(arg) for arg in command], check=True, timeout=1800, **kwargs)


def git(directory, *arguments):
    return run('git', '-c', 'core.hooksPath=/dev/null', '-c', 'http.version=HTTP/1.1',
               '-C', directory, *arguments, text=True, capture_output=True,
               env=dict(os.environ, GIT_TERMINAL_PROMPT='0')).stdout.strip()


def checkout(base, source):
    target = base / source['name']
    if target.exists():
        if git(target, 'rev-parse', 'HEAD') != source['commit'] or git(target, 'status', '--porcelain'):
            raise RuntimeError(f'SDK has personal changes or another revision: {target}')
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.minion-sdk-', dir=target.parent) as scratch:
        staged = Path(scratch) / 'source'
        staged.mkdir()
        git(staged, 'init', '--quiet')
        git(staged, 'fetch', '--quiet', '--depth=1', source['url'], source['commit'])
        git(staged, 'checkout', '--quiet', '--detach', 'FETCH_HEAD')
        if git(staged, 'rev-parse', 'HEAD') != source['commit']:
            raise RuntimeError(f'SDK revision mismatch: {source["name"]}')
        staged.rename(target)
    print(f'Installed {source["name"]}', flush=True)
    return target


def hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob('*'))
            if path.is_file() and path.name != '.minion-install.json'}


def install():
    if os.geteuid() == 0:
        raise SystemExit('Run this installer as the desktop user, not root')
    for command in ('git', 'cmake', 'ninja', 'g++', 'sclang', 'scsynth', 'pw-jack'):
        if not shutil.which(command):
            raise RuntimeError(f'Missing {command}; install the audio packages and development tools first')
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    cache = Path(os.environ.get('XDG_CACHE_HOME', home / '.cache'))
    sdk = data / 'minion/audio'
    sources = [checkout(sdk, source) for source in SOURCES]
    # SuperCollider's default Linux extension directory follows XDG_DATA_HOME.
    extension = data / 'SuperCollider/Extensions/VSTPlugin'
    marker = extension / '.minion-install.json'
    previous = json.loads(marker.read_text()) if marker.is_file() else None
    if extension.exists() and (not previous or previous.get('files') != hashes(extension)):
        raise RuntimeError(f'Existing VSTPlugin extension is unmanaged or modified: {extension}')
    if not previous or previous.get('sources') != SOURCES:
        extension.parent.mkdir(parents=True, exist_ok=True)
        build = cache / 'minion/audio/vstplugin-build'
        with tempfile.TemporaryDirectory(prefix='.minion-vst-', dir=extension.parent) as scratch:
            staging = Path(scratch)
            run('cmake', '-S', sources[1], '-B', build, '-G', 'Ninja',
                '-DCMAKE_BUILD_TYPE=Release', '-DPD=OFF', '-DSC=ON', '-DTESTSUITE=OFF',
                '-DVST2=OFF', '-DVST3=ON', '-DWINE=OFF', '-DBUILD_HOST32=OFF',
                '-DSC_INCLUDEDIR=/usr/include/SuperCollider',
                f'-DVST3DIR={sources[2].parent}', f'-DSC_INSTALLDIR={staging}')
            run('cmake', '--build', build, '--parallel', '2')
            run('cmake', '--install', build)
            staged = staging / 'VSTPlugin'
            record = dict(sources=SOURCES, files=hashes(staged))
            (staged / '.minion-install.json').write_text(json.dumps(record, indent=2) + '\n')
            backup = staging / 'previous'
            if extension.exists():
                extension.rename(backup)
            try:
                staged.rename(extension)
            except OSError:
                if backup.exists():
                    backup.rename(extension)
                raise
    starter = home / 'Projects/synth-lab'
    if not starter.exists():
        starter.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(HERE / 'synth-lab', starter)
        print(f'Created editable starter: {starter}', flush=True)
    else:
        print(f'Retaining existing project: {starter}', flush=True)
    print('Audio tools ready. See ~/Projects/synth-lab/README.md.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='List pinned sources without downloads or writes')
    args = parser.parse_args()
    if args.check:
        for source in SOURCES:
            print(f'{source["name"]}: {source["commit"]}')
    else:
        install()
