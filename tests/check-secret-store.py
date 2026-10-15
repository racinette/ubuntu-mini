#!/usr/bin/env python3
"""Check retained GPG settings and standard pass usage with a disposable vault."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


store = load('secret_store', PROJECT / 'setup/shell/secret_store.py')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        user = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid(), pw_gid=os.getgid())
        # Real file writes, with only privileged ownership mocked.
        with patch.object(store.os, 'chown'), patch.object(store.os, 'fchown'):
            store.install(user)
            config = home / '.gnupg/gpg-agent.conf'
            assert config.stat().st_mode & 0o777 == 0o600
            assert config.parent.stat().st_mode & 0o777 == 0o700
            assert 'default-cache-ttl 900' in config.read_text()
            assert 'max-cache-ttl 3600' in config.read_text()
            config.write_text('# Personal configuration\ndefault-cache-ttl 42\n')
            (config.parent / 'private-key-fixture').write_text('untouched')
            vault = home / '.password-store'
            vault.mkdir()
            (vault / '.gpg-id').write_text('personal-recipient\n')
            before = {p: p.read_bytes() for p in (config, config.parent / 'private-key-fixture', vault / '.gpg-id')}
            store.install(user)
            assert all(p.read_bytes() == value for p, value in before.items())
            config.unlink()
            config.symlink_to(home / 'outside')
            try:
                store.install(user)
            except ValueError:
                pass
            else:
                raise AssertionError('Symlinked settings accepted')

    print('Passed: private GPG settings, retained keys/store/personal settings and symlink refusal.')
    if '--integration' in sys.argv:
        integration()


def integration():
    """Use a disposable, unprotected fixture key; never touch the personal store."""
    with tempfile.TemporaryDirectory(prefix='minion-pass-check-') as temporary:
        root = Path(temporary)
        gnupg = root / 'gnupg'
        gnupg.mkdir(mode=0o700)
        env = dict(os.environ, GNUPGHOME=str(gnupg), PASSWORD_STORE_DIR=str(root / 'store'))
        def run(*args, **kwargs):
            return subprocess.run(args, env=env, capture_output=True, timeout=90, **kwargs)
        try:
            generated = run('gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                            '--status-fd', '1', '--quick-generate-key', 'Disposable test fixture',
                            'rsa2048', 'encr', '0', check=True, text=True)
            fingerprint = next(line.split()[-1] for line in generated.stdout.splitlines()
                               if line.startswith('[GNUPG:] KEY_CREATED '))
            run('pass', 'init', fingerprint, check=True)
            token = 'synthetic-fixture-token'
            run('pass', 'insert', '--multiline', 'cloud/test', input=(token+'\n').encode(), check=True)
            encrypted = root / 'store/cloud/test.gpg'
            assert token.encode() not in encrypted.read_bytes()
            command = ['/bin/bash', '-c',
                       '( token="$(pass show cloud/test)" && MINION_FIXTURE_TOKEN="$token" "$@" )',
                       'check', sys.executable, '-c',
                       'import os,sys; assert os.environ["MINION_FIXTURE_TOKEN"] == "synthetic-fixture-token"; '
                       'assert sys.argv[1] == "literal ; argument"; print("received"); sys.exit(7)', 'literal ; argument']
            received = run(*command)
            assert received.returncode == 7 and received.stdout == b'received\n'
            assert token.encode() not in received.stdout + received.stderr
            sentinel = root / 'never-created'
            blocked = run('/bin/bash', '-c',
                          '( token="$(pass show cloud/missing)" && MINION_FIXTURE_TOKEN="$token" touch "$1" )',
                          'check', str(sentinel))
            assert blocked.returncode != 0 and not sentinel.exists()
        finally:
            run('gpgconf', '--kill', 'gpg-agent')
    print('Passed: real encrypted pass entry and standard shell lookup/injection, literal arguments, exit status and failed-lookup guard.')


if __name__ == '__main__':
    main()
