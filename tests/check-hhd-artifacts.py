#!/usr/bin/env python3
"""Check download refusal and verified-cache behavior without host installation."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hhd_provision', PROJECT / 'setup/hhd/provision.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)

with tempfile.TemporaryDirectory(prefix='minion-hhd-check-') as scratch:
    cache = Path(scratch) / 'cache'
    archive = {'filename': 'test.tar.gz', 'sha256': hashlib.sha256(b'approved').hexdigest(),
               'url': 'https://example.invalid/test.tar.gz'}
    with patch.object(provision, 'CACHE', cache):
        for contents in (b'corrupted', b'<html>download unavailable</html>'):
            with patch.object(provision.urllib.request, 'urlopen', return_value=io.BytesIO(contents)):
                try:
                    provision.fetch(archive)
                except ValueError as error:
                    assert 'checksum mismatch' in str(error)
                else:
                    raise AssertionError('An unverified release was accepted')
            assert not list(cache.iterdir()), 'Rejected artifacts must leave no cache entry'
        with patch.object(provision.urllib.request, 'urlopen', return_value=io.BytesIO(b'approved')):
            target = provision.fetch(archive)
        with patch.object(provision.urllib.request, 'urlopen', side_effect=AssertionError('Unexpected network request')):
            assert provision.fetch(archive) == target
        target.write_bytes(b'tampered')
        with patch.object(provision.urllib.request, 'urlopen', return_value=io.BytesIO(b'bad replacement')):
            try:
                provision.fetch(archive)
            except ValueError:
                pass
            else:
                raise AssertionError('An altered cache entry was trusted')
        assert target.read_bytes() == b'tampered'
        assert list(cache.iterdir()) == [target]
print('Passed: corrupted downloads/cache refused, temporary files removed and verified cache reused offline.')
