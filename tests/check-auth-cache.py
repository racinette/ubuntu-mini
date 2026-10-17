#!/usr/bin/env python3
"""Test bounded authentication defaults and retained SSH settings without host changes."""
import importlib.util
import os
from pathlib import Path
import socket
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
        auth.LEGACY_UNITS = home / 'legacy-units'
        auth.SUDOERS.mkdir()
        auth.UNITS.mkdir()
        auth.LEGACY_UNITS.mkdir()
        for directory in (auth.UNITS, auth.LEGACY_UNITS):
            (directory / 'minion-ssh-agent.service').write_text('Old managed agent')
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
        assert 'IdentityAgent' not in defaults.read_text()
        assert all(not (d / 'minion-ssh-agent.service').exists() for d in (auth.UNITS, auth.LEGACY_UNITS))
        override = (auth.UNITS / 'ssh-agent.service.d/60-minion-session.conf').read_text()
        assert 'ExecStart=/usr/lib/openssh/agent-launch start -- -t 1h' in override
        assert 'Environment=SSH_AUTH_SOCK=\n' in override
        assert 'PartOf=minion-session.target' in override
        assert config.stat().st_mode & 0o777 == 0o600
        personal = 'Host personal\n    IdentityAgent /personal/agent\n    AddKeysToAgent no\n    User someone\n'
        config.write_text(personal)
        with patch.object(auth.subprocess, 'run'), patch.object(auth.os, 'chown'):
            auth.install(user)
            before = config.read_bytes(), defaults.read_bytes(), sudoers.read_bytes()
            auth.install(user)
            assert before == (config.read_bytes(), defaults.read_bytes(), sudoers.read_bytes())
        assert config.read_text().startswith(personal)
        # Migrate only the old managed socket option; keep personal edits.
        defaults.write_text(defaults.read_text() + 'IdentityAgent /run/user/%i/minion-ssh-agent/socket\n# My setting\nServerAliveInterval 30\n')
        with patch.object(auth.subprocess, 'run'), patch.object(auth.os, 'chown'):
            auth.install(user)
        assert 'minion-ssh-agent/socket' not in defaults.read_text()
        assert '# My setting\nServerAliveInterval 30\n' in defaults.read_text()
        # Parse with real OpenSSH, substituting an isolated include path for ~.
        candidate = home / 'ssh-check.conf'
        candidate.write_text(config.read_text().replace('~/.ssh/minion.conf', str(defaults)))
        def effective(host):
            return subprocess.check_output(['ssh', '-G', '-F', str(candidate), host], text=True, stderr=subprocess.DEVNULL)
        assert 'identityagent /personal/agent\n' in effective('personal')
        assert 'addkeystoagent false\n' in effective('personal')
        common = effective('example.invalid')
        assert 'addkeystoagent 3600\n' in common
        assert 'identityagent ' not in common
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
        defaults.write_text(defaults.read_text() + 'IdentityAgent /run/user/%i/minion-ssh-agent/socket\n')
        old_defaults = defaults.read_bytes()
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
        assert defaults.read_bytes() == old_defaults
        # Existing forwarded/personal sockets win; stale and absent sockets recover.
        runtime = home / 'run'
        runtime.mkdir()
        sockets = []
        try:
            for name in ('openssh_agent', 'forwarded'):
                sock = socket.socket(socket.AF_UNIX)
                sock.bind(str(runtime / name))
                sockets.append(sock)
            (runtime / 'alias').symlink_to(runtime / 'openssh_agent')
            for supplied, expected in [('', 'openssh_agent'), ('missing', 'openssh_agent'), ('alias', 'openssh_agent'), ('forwarded', 'forwarded')]:
                env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), MINION_SHELL_LOADED='1',
                           SSH_AUTH_SOCK=str(runtime / supplied) if supplied else '')
                selected = subprocess.check_output(['bash', '--noprofile', '--norc', '-ic',
                    'source "$1"; printf "%s" "$SSH_AUTH_SOCK"', 'fixture', str(SOURCE.with_name('bashrc.bash'))],
                    env=env, text=True, stderr=subprocess.DEVNULL)
                assert selected == str(runtime / expected)
        finally:
            for sock in sockets:
                sock.close()
        try:
            auth.sudo_policy('fixture\nALL=(ALL) NOPASSWD:ALL')
        except ValueError:
            pass
        else:
            raise AssertionError('Account-name injection accepted')
    print('Passed: packaged agent override, legacy migration, forwarded-agent retention, stale-socket recovery, bounded caches, user precedence, idempotence and rollback.')


if __name__ == '__main__':
    main()
