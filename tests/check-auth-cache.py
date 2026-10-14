#!/usr/bin/env python3
"""Test bounded authentication defaults and retained SSH settings without host changes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'setup/shell/auth.py'
spec = importlib.util.spec_from_file_location('auth_setup', SOURCE)
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        auth.SUDOERS = home / 'sudoers'
        auth.UNITS = home / 'units'
        auth.SUDOERS.mkdir()
        auth.UNITS.mkdir()
        user = SimpleNamespace(pw_name='fixture', pw_dir=str(home), pw_uid=os.getuid(), pw_gid=os.getgid())
        with patch.object(auth.subprocess, 'run') as run, patch.object(auth.os, 'chown'):
            auth.install(user)
            validation = next(c for c in run.call_args_list if c.args[0][0] == 'ssh')
            assert validation.kwargs['user'] == user.pw_uid
            assert validation.kwargs['group'] == user.pw_gid
        sudoers = auth.SUDOERS / '60-minion-auth-fixture'
        assert 'timestamp_type=global, timestamp_timeout=15' in sudoers.read_text()
        assert sudoers.stat().st_mode & 0o777 == 0o440
        config = home / '.ssh/config'
        defaults = home / '.ssh/minion.conf'
        assert 'AddKeysToAgent 1h' in defaults.read_text()
        assert config.stat().st_mode & 0o777 == 0o600
        personal = 'Host personal\n    IdentityAgent /personal/agent\n    AddKeysToAgent no\n    User someone\n'
        config.write_text(personal)
        with patch.object(auth.subprocess, 'run'), patch.object(auth.os, 'chown'):
            auth.install(user)
            before = config.read_bytes(), defaults.read_bytes(), sudoers.read_bytes()
            auth.install(user)
            assert before == (config.read_bytes(), defaults.read_bytes(), sudoers.read_bytes())
        assert config.read_text().startswith(personal)
        # Parse with real OpenSSH, substituting an isolated include path for ~.
        candidate = home / 'ssh-check.conf'
        candidate.write_text(config.read_text().replace('~/.ssh/minion.conf', str(defaults)))
        def effective(host):
            return subprocess.check_output(['ssh', '-G', '-F', str(candidate), host], text=True, stderr=subprocess.DEVNULL)
        assert 'identityagent /personal/agent\n' in effective('personal')
        assert 'addkeystoagent false\n' in effective('personal')
        common = effective('example.invalid')
        assert 'addkeystoagent 3600\n' in common
        assert f'identityagent /run/user/{os.getuid()}/minion-ssh-agent/socket\n' in common
        # A failed full sudoers validation restores the previous owned file.
        old = '# Existing managed policy\n'
        sudoers.chmod(0o640)
        sudoers.write_text(old)
        sudoers.chmod(0o440)
        def reject(command, **kwargs):
            if command == ['visudo', '-c']:
                raise subprocess.CalledProcessError(1, command)
        with patch.object(auth.subprocess, 'run', side_effect=reject):
            try:
                auth.install_sudo(user)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError('Expected validation rejection')
        assert sudoers.read_text() == old
        # A failed SSH parse restores the user's original file byte-for-byte.
        config.write_text(personal)
        def reject_ssh(command, **kwargs):
            if command[0] == 'ssh':
                raise subprocess.CalledProcessError(255, command)
        with patch.object(auth.subprocess, 'run', side_effect=reject_ssh), patch.object(auth.os, 'chown'):
            try:
                auth.install(user)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError('Expected invalid SSH config rejection')
        assert config.read_text() == personal
        try:
            auth.sudo_policy('fixture\nALL=(ALL) NOPASSWD:ALL')
        except ValueError:
            pass
        else:
            raise AssertionError('Account-name injection accepted')
    print('Passed: bounded sudo/SSH defaults, user precedence, user-context validation, idempotence and rollback.')


if __name__ == '__main__':
    main()
