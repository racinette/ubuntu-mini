#!/usr/bin/env python3
"""Check download refusal and verified-cache behavior without host installation."""
import hashlib
import importlib.util
import io
import contextlib
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
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

    # Exercise enrollment decisions without loading modules or touching EFI.
    certificate = Path(scratch) / 'MOK.der'
    certificate.write_bytes(b'fixture')

    def module_check(*, loads=False, secure=True, matches=True, enrolled=False,
                     pending=False, interactive=False, import_status=0, serial_signer=False,
                     keyring_warning=False, unknown_enrollment=False):
        commands = []

        def run(command, **kwargs):
            command = tuple(command)
            commands.append(command)
            status, output, error = 0, '', ''
            if command == ('modprobe', 'acpi_call'):
                status, error = (0, '') if loads else (1, 'Key was rejected by service')
            elif command == ('mokutil', '--sb-state'):
                output = 'SecureBoot enabled' if secure else 'SecureBoot disabled'
            elif command == ('modinfo', '-F', 'sig_key', 'acpi_call'):
                output = '00:11:22\n' if serial_signer else 'AA:BB:CC\n'
            elif command[0] == 'openssl':
                output = 'serial=' + ('001122' if matches else '998877') + '\n'
                output += 'X509v3 Subject Key Identifier:\n    ' + ('AA:BB:CC' if matches else '11:22:33') + '\n'
            elif command[:2] == ('mokutil', '--test-key'):
                status = 0 if enrolled and not keyring_warning else 1
                output = str(certificate) + (' is already enrolled\n' if enrolled else ' is not enrolled\n')
                if keyring_warning:
                    error = 'Failed to accesss kernel trusted keyring: Required key not available'
                if unknown_enrollment:
                    output, status = '', 1
            elif command == ('mokutil', '--list-new'):
                output = 'Serial Number:\n    00:11:22\nSubject Key Identifier: AA:BB:CC' if pending else ''
            elif command[:2] == ('mokutil', '--import'):
                assert 'capture_output' not in kwargs, 'Do not capture password interaction'
                status = import_status
            else:
                raise AssertionError(command)
            return subprocess.CompletedProcess(command, status, output, error)

        output = io.StringIO()
        with patch.object(provision, 'MOK_CERTIFICATE', certificate), \
             patch.object(provision.sys, 'stdin', SimpleNamespace(isatty=lambda: interactive)), \
             patch.object(provision.subprocess, 'run', side_effect=run), \
             contextlib.redirect_stdout(output):
            provision.check_acpi_module()
        imports = [cmd for cmd in commands if cmd[:2] == ('mokutil', '--import')]
        return commands, imports, output.getvalue()

    commands, imports, output = module_check(loads=True)
    assert commands == [('modprobe', 'acpi_call')]
    for settings in ({'secure': False}, {'matches': False}, {'enrolled': True}, {'pending': True}):
        assert not module_check(interactive=True, **settings)[1], settings
    _, imports, output = module_check()
    assert not imports and 'No interactive terminal' in output
    _, imports, output = module_check(interactive=True)
    assert imports == [('mokutil', '--import', str(certificate))]
    assert 'Enrollment queued' in output
    _, imports, output = module_check(interactive=True, import_status=1)
    assert len(imports) == 1 and 'Enrollment was not queued' in output
    _, imports, output = module_check(interactive=True, serial_signer=True)
    assert len(imports) == 1 and 'Enrollment queued' in output
    assert not module_check(interactive=True, serial_signer=True, matches=False)[1]
    assert not module_check(interactive=True, serial_signer=True, pending=True)[1]
    _, imports, output = module_check(interactive=True, enrolled=True, keyring_warning=True)
    assert not imports and 'The signing key is enrolled.' in output
    _, imports, output = module_check(interactive=True, unknown_enrollment=True)
    assert not imports and 'Could not determine' in output

print('Passed: corrupted downloads/cache refused, verified cache reused, module checks and enrollment decisions isolated from host EFI.')
