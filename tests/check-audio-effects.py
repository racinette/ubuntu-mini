#!/usr/bin/env python3
"""Check plugin archive validation, personal-file retention and offline reruns."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('effects', PROJECT / 'setup/development/effects.py')
effects = importlib.util.module_from_spec(spec)
spec.loader.exec_module(effects)


def archive(name, content=b'fixture plugin', kind=tarfile.REGTYPE):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:xz') as bundle:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.linkname = '/tmp/foreign'
        member.size = len(content) if kind == tarfile.REGTYPE else 0
        bundle.addfile(member, io.BytesIO(content) if member.size else None)
    return output.getvalue()


with tempfile.TemporaryDirectory(prefix='minion-effects-check-') as temporary:
    home = Path(temporary)
    asset = dict(name='Fixture', version='1', filename='fixture.tar.xz',
                 format='tar.xz', bundle='release/Fixture.vst3', url='https://example.invalid/plugin')
    data = archive(asset['bundle'] + '/Contents/x86_64-linux/Fixture.so')
    asset['sha256'] = hashlib.sha256(data).hexdigest()
    assets = home / 'downloads'
    assets.mkdir()
    (assets / asset['filename']).write_bytes(data)
    cache = home / 'cache'

    assert effects.payload(asset, cache, assets) == data
    (assets / asset['filename']).write_bytes(b'corrupted')
    try:
        effects.payload(asset, cache, assets)
    except ValueError:
        pass
    else:
        raise AssertionError('Corrupted plugin was accepted')
    (assets / asset['filename']).write_bytes(data)
    for entry, kind in (('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                        ('release/link', tarfile.SYMTYPE), ('release/hard', tarfile.LNKTYPE)):
        try:
            effects.unpack(archive(entry, kind=kind), asset, home / 'unsafe')
        except ValueError:
            pass
        else:
            raise AssertionError(f'Unsafe archive accepted: {entry}')
    assert not (home / 'unsafe').exists()

    with patch.object(effects.os, 'geteuid', return_value=1000), \
         patch.object(effects.Path, 'home', return_value=home), \
         patch.object(effects, 'ARTIFACTS', [asset]), \
         patch.dict(os.environ, {'XDG_CACHE_HOME': str(cache)}), \
         patch.object(effects.urllib.request, 'urlopen', side_effect=AssertionError('Unexpected download')), \
         contextlib.redirect_stdout(io.StringIO()):
        effects.install(assets)
        target = home / '.vst3/Fixture.vst3'
        binary = target / 'Contents/x86_64-linux/Fixture.so'
        marker = target / '.minion-install.json'
        timestamp = marker.stat().st_mtime_ns
        with patch.object(effects, 'payload', side_effect=AssertionError('Unchanged plugin requested an archive')):
            effects.install()
        assert marker.stat().st_mtime_ns == timestamp
        assert binary.read_bytes() == b'fixture plugin'
        binary.write_bytes(b'personal changes')
        try:
            effects.install(assets)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Modified plugin was overwritten')
        assert binary.read_bytes() == b'personal changes'
        marker.unlink()
        try:
            effects.install(assets)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Unmanaged plugin was overwritten')

with patch.object(effects.os, 'geteuid', return_value=0):
    try:
        effects.install()
    except SystemExit:
        pass
    else:
        raise AssertionError('User plugin installer accepted root')

print('Passed: checksums, unsafe archive refusal, modified/unmanaged preservation, offline reruns and user-only installation.')
