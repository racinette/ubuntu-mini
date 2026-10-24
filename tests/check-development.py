#!/usr/bin/env python3
"""Check toolchain privilege boundaries, defaults and Docker conflict handling."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('development', PROJECT / 'setup/development/provision.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)

with tempfile.TemporaryDirectory(prefix='minion-development-check-') as temporary:
    home = Path(temporary)
    user = SimpleNamespace(pw_name='fixture', pw_uid=1234, pw_gid=1235,
                           pw_shell='/bin/bash', pw_dir=temporary)
    with patch.dict(os.environ, {'HOME': '/root', 'GITHUB_TOKEN': 'secret',
                                'CARGO_HOME': '/root/cargo', 'UV_PYTHON': '3.9',
                                'BASH_ENV': '/root/hook', 'MISE_GLOBAL_CONFIG_FILE': '/root/config',
                                'HTTPS_PROXY': 'http://127.0.0.1:7890'}, clear=True):
        env = provision.user_environment(user)
    assert env['HOME'] == temporary and env['USER'] == 'fixture'
    assert env['HTTPS_PROXY'] == 'http://127.0.0.1:7890'
    assert not {'GITHUB_TOKEN', 'CARGO_HOME', 'UV_PYTHON', 'BASH_ENV', 'MISE_GLOBAL_CONFIG_FILE'} & env.keys()
    with patch.object(provision.os, 'getgrouplist', return_value=[1235, 44]), \
         patch.object(provision.subprocess, 'run') as run:
        provision.run_as_user(user, env, '/bin/sh', '/tmp/install')
    assert run.call_args.kwargs['user'] == 1234
    assert run.call_args.kwargs['extra_groups'] == [1235, 44]
    assert run.call_args.kwargs['env'] == env

    # A truncated bootstrap must be discarded without executing any shell.
    commands = []
    def failed_download(target, environment, *command, **kwargs):
        commands.append(command)
        Path(command[command.index('--output') + 1]).write_text('partial installer')
        raise subprocess.CalledProcessError(22, command)
    with patch.object(provision.shutil, 'which', return_value=None), \
         patch.object(provision.os, 'chown'), \
         patch.object(provision, 'run_as_user', side_effect=failed_download):
        try:
            provision.bootstrap(user, env, 'mise', 'https://mise.run', '/bin/sh')
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('Failed bootstrap was accepted')
    assert len(commands) == 1 and commands[0][0] == '/usr/bin/curl'
    assert not Path(commands[0][commands[0].index('--output') + 1]).exists()

    # A previously selected Go version must not be replaced by latest, while
    # a missing Node selection must be installed and pinned immediately.
    commands = []
    def fake_user_run(target, environment, *command, **kwargs):
        commands.append((command, environment, kwargs))
        if 'ls' in command and '--json' in command:
            return SimpleNamespace(stdout=json.dumps([{'version': '1.23.0'}] if 'go' in command else []))
        return SimpleNamespace(stdout='')
    with patch.object(provision, 'TOOLS', ['go', 'node']), \
         patch.object(provision.os, 'chown'), \
         patch.object(provision, 'run_as_user', side_effect=fake_user_run):
        provision.install_mise_tools(user, env, '/mise')
    assert any(cmd == ('/mise', 'install', 'go') for cmd, _, _ in commands)
    assert not any('go@latest' in cmd for cmd, _, _ in commands)
    assert any(cmd == ('/mise', 'use', '--global', '--pin', 'node@latest') and
               environment['MISE_MINIMUM_RELEASE_AGE'] == '0s' for cmd, environment, _ in commands)
    assert all(kwargs['cwd'] != temporary for _, _, kwargs in commands)

    for existing_default in (False, True):
        if existing_default:
            (home / '.local/bin').mkdir(parents=True)
            (home / '.local/bin/python3').symlink_to('/a/user-selected/python')
        catalog = [dict(version=version, implementation='cpython', variant=variant) for version, variant in (
            ('3.13.10', 'default'), ('3.14.2', 'default'), ('3.15.0rc1', 'default'), ('3.15.0', 'freethreaded'))]
        with patch.object(provision, 'bootstrap', side_effect=lambda u, e, name, *a: '/' + name), \
             patch.object(provision, 'install_mise_tools'), \
             patch.object(provision.shutil, 'which', return_value='/ruff'), \
             patch.object(provision, 'run_as_user', return_value=SimpleNamespace(stdout=json.dumps(catalog))) as run:
            provision.install_toolchains(user)
        python_install = next(call.args for call in run.call_args_list if call.args[2:5] == ('/uv', 'python', 'install'))
        assert ('--default' in python_install) != existing_default
        assert 'cpython@3.14.2' in python_install
        assert not any(call.args[2:4] == ('/rustup', 'default') for call in run.call_args_list)
        assert any(call.args[2:6] == ('/rustup', 'toolchain', 'install', 'stable') for call in run.call_args_list)

    sources = home / 'sources'
    sources.mkdir()
    docker_source = sources / 'docker.sources'
    with patch.object(provision, 'DOCKER_SOURCE', docker_source), \
         patch.object(provision.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='')):
        provision.check_docker_repository('amd64')
        docker_source.write_text('User repository settings\n')
        try:
            provision.check_docker_repository('amd64')
        except ValueError:
            pass
        else:
            raise AssertionError('Existing repository was silently replaced')
        assert docker_source.read_text() == 'User repository settings\n'
        docker_source.unlink()
    with patch.object(provision, 'DOCKER_SOURCE', docker_source), \
         patch.object(provision.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='docker.io installed\n')):
        try:
            provision.check_docker_repository('amd64')
        except ValueError as error:
            assert 'docker.io' in str(error)
        else:
            raise AssertionError('Existing Docker runtime conflict was accepted')

    with patch.object(provision.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}), \
         patch.object(provision.platform, 'machine', return_value='x86_64'), \
         patch.object(provision, 'target_user', return_value=user), \
         patch.object(provision, 'check_docker_repository'), \
         patch.object(provision.subprocess, 'run', side_effect=AssertionError('Preflight installed software')), \
         patch.object(sys, 'argv', ['provision.py', 'fixture', '--check']), \
         contextlib.redirect_stdout(io.StringIO()):
        provision.main()

    # The normal setup must run the DAW installer through the same desktop-user
    # boundary as the other audio tools, never as the root coordinator.
    with patch.object(provision.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}), \
         patch.object(provision.platform, 'machine', return_value='x86_64'), \
         patch.object(provision, 'target_user', return_value=user), \
         patch.object(provision, 'check_docker_repository'), \
         patch.object(provision.os, 'geteuid', return_value=0), \
         patch.object(provision.subprocess, 'run'), \
         patch.object(provision, 'install_blender'), \
         patch.object(provision, 'install_toolchains'), \
         patch.object(provision, 'install_docker'), \
         patch.object(provision, 'run_as_user') as run, \
         patch.object(sys, 'argv', ['provision.py', 'fixture']), \
         contextlib.redirect_stdout(io.StringIO()):
        provision.main()
    run.assert_any_call(user, provision.user_environment(user), '/usr/bin/python3', provision.HERE / 'reaper.py')

print('Passed: development user isolation, immediate latest installation, retained selections, container-runtime/repository conflict refusal and read-only preflight.')
