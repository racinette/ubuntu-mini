#!/usr/bin/env python3
"""Check REAPER archive validation, user installation and existing-install retention."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reaper', PROJECT / 'setup/development/reaper.py')
reaper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reaper)


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:xz') as bundle:
        for name, content, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.mode = 0o755
            member.linkname = '/tmp/foreign'
            member.size = len(content) if kind == tarfile.REGTYPE else 0
            bundle.addfile(member, io.BytesIO(content) if member.size else None)
    return output.getvalue()


# A small executable fixture exercises the subprocess installation path without
# opening REAPER, invoking XDG tools or touching the real user's home.
installer = b'''#!/bin/sh
set -eu
test "$1" = --install
test "$3" = --integrate-user-desktop
test "$4" = --quiet
test "$#" = 4
mkdir -p "$2/REAPER" "$HOME/.local/share/applications"
cp "$(dirname "$0")/REAPER/reaper" "$2/REAPER/reaper"
printf '%s\\n' '[Desktop Entry]' 'Name=REAPER' > "$HOME/.local/share/applications/cockos-reaper.desktop"
'''
data = archive([
    ('reaper_linux_x86_64/install-reaper.sh', installer, tarfile.REGTYPE),
    ('reaper_linux_x86_64/REAPER/reaper', b'#!/bin/sh\nexit 0\n', tarfile.REGTYPE),
])
release = dict(version='fixture', filename='fixture.tar.xz',
               sha256=hashlib.sha256(data).hexdigest(), url='https://example.invalid/reaper')

with tempfile.TemporaryDirectory(prefix='minion-reaper-check-') as temporary:
    home = Path(temporary)
    assets = home / 'downloads'
    assets.mkdir()
    downloaded = assets / release['filename']
    downloaded.write_bytes(data)
    cache = home / 'cache'
    with patch.object(reaper, 'RELEASE', release):
        assert reaper.payload(cache, assets) == data
        with patch.object(reaper.urllib.request, 'urlopen', side_effect=AssertionError('Unexpected network')):
            assert reaper.payload(cache) == data
        downloaded.write_bytes(b'corrupted')
        try:
            reaper.payload(cache, assets)
        except ValueError:
            pass
        else:
            raise AssertionError('Corrupted download was accepted')
        downloaded.write_bytes(data)
        with patch.object(reaper, 'MAX_DOWNLOAD', 1):
            try:
                reaper.payload(cache, assets)
            except ValueError:
                pass
            else:
                raise AssertionError('Oversized download was accepted')

    for name, kind in (('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                       ('release/link', tarfile.SYMTYPE), ('release/hard', tarfile.LNKTYPE),
                       ('release/device', tarfile.CHRTYPE)):
        try:
            reaper.unpack(archive([(name, b'unsafe', kind)]), home / 'unsafe')
        except ValueError:
            pass
        else:
            raise AssertionError(f'Unsafe archive accepted: {name}')
    assert not (home / 'unsafe').exists()

    config = home / '.config/REAPER/reaper.ini'
    config.parent.mkdir(parents=True)
    config.write_text('Personal audio settings and theme\n')
    with patch.object(reaper.os, 'geteuid', return_value=1000), \
         patch.object(reaper.platform, 'machine', return_value='x86_64'), \
         patch.object(reaper.Path, 'home', return_value=home), \
         patch.object(reaper.shutil, 'which', return_value=None), \
         patch.object(reaper, 'RELEASE', release), \
         patch.dict(os.environ, {'HOME': str(home), 'XDG_CACHE_HOME': str(cache)}), \
         patch.object(reaper.urllib.request, 'urlopen', side_effect=AssertionError('Unexpected network')), \
         contextlib.redirect_stdout(io.StringIO()):
        reaper.install(assets)
        binary = home / 'opt/REAPER/reaper'
        link = home / '.local/bin/reaper'
        desktop = home / '.local/share/applications/cockos-reaper.desktop'
        assert os.access(binary, os.X_OK)
        assert link.resolve() == binary and desktop.is_file()
        assert config.read_text() == 'Personal audio settings and theme\n'

        # Existing installations (including a different version) are retained
        # without downloading or running the installer, even with a custom config.
        binary.write_text('#!/bin/sh\n# personal version\n')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (binary, desktop, config)}
        with patch.object(reaper, 'payload', side_effect=AssertionError('Existing install requested archive')), \
             patch.object(reaper.subprocess, 'run', side_effect=AssertionError('Existing install ran installer')):
            reaper.install()
            with patch.object(reaper.shutil, 'which', return_value='/custom/reaper'):
                reaper.install()
        assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}

        binary.unlink()
        with patch.object(reaper, 'payload', side_effect=AssertionError('Broken install requested archive')):
            try:
                reaper.install()
            except RuntimeError:
                pass
            else:
                raise AssertionError('Broken installation was overwritten')
        (home / 'opt/REAPER').rmdir()
        try:
            reaper.install()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Dangling command was replaced')

with patch.object(reaper.os, 'geteuid', return_value=0):
    try:
        reaper.install()
    except SystemExit:
        pass
    else:
        raise AssertionError('User installer accepted root')

with tempfile.TemporaryDirectory(prefix='minion-reaper-preflight-') as temporary:
    result = subprocess.run([sys.executable, str(PROJECT / 'setup/development/reaper.py'), '--check'],
                            env=dict(os.environ, HOME=temporary, XDG_CACHE_HOME=temporary),
                            text=True, capture_output=True, check=True)
    assert reaper.RELEASE['version'] in result.stdout
    assert not list(Path(temporary).iterdir())

print('Passed: REAPER checksums, unsafe archives, user installation, launcher/command, retained settings/installations and read-only preflight.')
