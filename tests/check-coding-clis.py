#!/usr/bin/env python3
"""Check CLI installer isolation, failure handling and retention without downloads."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('coding_clis', PROJECT / 'setup/agents/provision.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)

with tempfile.TemporaryDirectory(prefix='minion-cli-check-') as temporary:
    user = SimpleNamespace(pw_name='fixture', pw_uid=1234, pw_gid=1235,
                           pw_shell='/bin/bash', pw_dir=temporary)
    with patch.dict(os.environ, {'HOME': '/root', 'SUDO_USER': 'someone',
                                'CODEX_HOME': '/root/private', 'XDG_CONFIG_HOME': '/root/config',
                                'ANTHROPIC_API_KEY': 'secret', 'BASH_ENV': '/root/injected',
                                'HTTPS_PROXY': 'http://127.0.0.1:7890'}, clear=True):
        env = provision.user_environment(user)
    assert env['HOME'] == temporary and env['USER'] == 'fixture'
    assert env['PATH'].startswith(temporary + '/.local/bin:')
    assert env['HTTPS_PROXY'] == 'http://127.0.0.1:7890'
    assert not {'SUDO_USER', 'CODEX_HOME', 'XDG_CONFIG_HOME', 'ANTHROPIC_API_KEY', 'BASH_ENV'} & env.keys()
    assert env['CODEX_NON_INTERACTIVE'] == '1'

    # Foot starts interactive, non-login Bash. PATH must work without .profile,
    # and sourcing the integration twice must not duplicate the directory.
    result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-ic',
                             'MINION_SHELL_LOADED=1; source "$1"; source "$1"; printf "%s" "$PATH"',
                             'check', str(PROJECT / 'setup/shell/bashrc.bash')],
                            env={'HOME': temporary, 'PATH': '/usr/bin:/bin'},
                            text=True, capture_output=True, check=True)
    assert result.stdout == temporary + '/.local/bin:/usr/bin:/bin'

    with patch.object(provision.os, 'getgrouplist', return_value=[1235, 44]), \
         patch.object(provision.subprocess, 'run') as run:
        provision.run_as_user(user, env, '/bin/sh', '/tmp/installer')
    kwargs = run.call_args.kwargs
    assert kwargs['user'] == 1234 and kwargs['group'] == 1235
    assert kwargs['extra_groups'] == [1235, 44]
    assert kwargs['env'] == env and kwargs['cwd'] == temporary
    assert kwargs['stdin'] == subprocess.DEVNULL and kwargs['check']

    for installer in provision.INSTALLERS:
        name, url, shell, arguments = installer
        existing = temporary + '/.local/bin/' + name
        with patch.object(provision.shutil, 'which', return_value=existing), \
             patch.object(provision, 'run_as_user') as run, \
             patch.object(provision.tempfile, 'TemporaryDirectory', side_effect=AssertionError('Unexpected download')), \
             contextlib.redirect_stdout(io.StringIO()):
            provision.install_cli(user, env, *installer)
        run.assert_not_called()

        # A partial download must never reach the shell, and must be cleaned up.
        calls = []
        def failed_download(target_user, environment, *command, **kwargs):
            calls.append(command)
            destination = Path(command[command.index('--output') + 1])
            destination.write_text('#!/bin/sh\nexit 0\n')
            raise subprocess.CalledProcessError(22, command)

        with patch.object(provision.shutil, 'which', return_value=None), \
             patch.object(provision.os, 'chown'), \
             patch.object(provision, 'run_as_user', side_effect=failed_download), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                provision.install_cli(user, env, *installer)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError('Failed download was accepted')
        assert len(calls) == 1 and calls[0][0] == '/usr/bin/curl'
        assert not Path(calls[0][calls[0].index('--output') + 1]).exists()

        with patch.object(provision.shutil, 'which', return_value=None), \
             patch.object(provision.os, 'chown'), \
             patch.object(provision, 'run_as_user'), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                provision.install_cli(user, env, *installer)
            except RuntimeError as error:
                assert 'without a usable command' in str(error)
            else:
                raise AssertionError('Installer success without a command was accepted')

    with patch.object(provision.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}), \
         patch.object(provision.platform, 'machine', return_value='x86_64'), \
         patch.object(provision, 'target_user', return_value=user), \
         patch.object(provision.subprocess, 'run', side_effect=AssertionError('Check ran a command')), \
         patch.object(sys, 'argv', ['provision.py', 'fixture', '--check']), \
         contextlib.redirect_stdout(io.StringIO()):
        provision.main()

print('Passed: user privilege/environment isolation, existing command retention, partial/missing installation refusal, Bash PATH and read-only preflight.')
