#!/usr/bin/env python3
"""Check CLI installer isolation, failure handling and retention without downloads."""
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

    # Attribution preferences update existing configs without losing unrelated
    # model, permission or plugin choices; reruns avoid rewriting matching files.
    with patch.object(provision.os, 'geteuid', return_value=1234), contextlib.redirect_stdout(io.StringIO()):
        provision.install_cli_preferences(user)
    claude = Path(temporary) / '.claude/settings.json'
    cursor = Path(temporary) / '.cursor/cli-config.json'
    assert json.loads(claude.read_text()) == {'attribution': {'commit': '', 'pr': ''},
                                            'env': {'CLAUDE_CODE_SCROLL_SPEED': '3'}}
    cursor_data = json.loads(cursor.read_text())
    assert cursor_data['version'] == 1 and cursor_data['permissions'] == {'allow': [], 'deny': []}
    assert cursor_data['attribution'] == {'attributeCommitsToAgent': False, 'attributePRsToAgent': False}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in (claude, cursor))
    claude.write_text(json.dumps({'model': 'personal-model', 'enabledPlugins': {'example': True},
                                 'env': {'PERSONAL_SETTING': 'keep'},
                                 'attribution': {'commit': 'co-author', 'pr': 'branding', 'sessionUrl': False}}))
    cursor_data.update(model={'modelId': 'personal-model'}, permissions={'allow': ['Shell(ls)'], 'deny': []})
    cursor_data['attribution'].update(attributeCommitsToAgent=True, attributePRsToAgent=True, futureSetting='keep')
    cursor.write_text(json.dumps(cursor_data))
    with patch.object(provision.os, 'geteuid', return_value=0), \
         patch.object(provision.os, 'fchown') as chown, contextlib.redirect_stdout(io.StringIO()):
        provision.install_cli_preferences(user)
    assert chown.call_count == 2
    assert all(call.args[1:] == (user.pw_uid, user.pw_gid) for call in chown.call_args_list)
    claude_data = json.loads(claude.read_text())
    assert claude_data['model'] == 'personal-model' and claude_data['enabledPlugins'] == {'example': True}
    assert claude_data['attribution'] == {'commit': '', 'pr': '', 'sessionUrl': False}
    assert claude_data['env'] == {'CLAUDE_CODE_SCROLL_SPEED': '3', 'PERSONAL_SETTING': 'keep'}
    updated_cursor = json.loads(cursor.read_text())
    assert updated_cursor['model'] == cursor_data['model'] and updated_cursor['permissions'] == cursor_data['permissions']
    assert updated_cursor['attribution'] == {'attributeCommitsToAgent': False, 'attributePRsToAgent': False, 'futureSetting': 'keep'}
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (claude, cursor)]
    provision.install_cli_preferences(user)
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in (claude, cursor)]
    claude_data['env']['CLAUDE_CODE_SCROLL_SPEED'] = '5'
    claude.write_text(json.dumps(claude_data))
    provision.install_cli_preferences(user)
    assert json.loads(claude.read_text()) == claude_data
    for invalid in ('{broken', '[]', '{"attribution": false}', '{"env": false}'):
        claude.write_text(invalid)
        try:
            provision.install_cli_preferences(user)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid settings were overwritten')
        assert claude.read_text() == invalid

    # Profile loading is part of installation, not a system-wide sysctl change.
    source = Path(temporary) / 'packaged-profile'
    source.write_text('profile fixture {}\n')
    profile = Path(temporary) / 'apparmor.d/bwrap-userns-restrict'
    enabled = Path(temporary) / 'apparmor-enabled'
    enabled.write_text('Y\n')
    with patch.object(provision.subprocess, 'run') as run:
        provision.install_bubblewrap_profile(source, profile, enabled)
        run.assert_called_once_with(['/usr/sbin/apparmor_parser', '-r', str(profile)], check=True)
    assert profile.read_bytes() == source.read_bytes() and profile.stat().st_mode & 0o777 == 0o644
    profile.write_text('# Personal profile edits\nprofile fixture {}\n')
    saved = profile.read_bytes()
    with patch.object(provision.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
        provision.install_bubblewrap_profile(source, profile, enabled)
        run.assert_called_once_with(['/usr/sbin/apparmor_parser', '-r', str(profile)], check=True)
    assert profile.read_bytes() == saved
    enabled.write_text('N\n')
    with patch.object(provision.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
        provision.install_bubblewrap_profile(source, profile, enabled)
        run.assert_not_called()
    absent = Path(temporary) / 'absent'
    try:
        provision.install_bubblewrap_profile(absent, absent.with_name('never-created'), enabled)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError('Missing packaged profile was silently accepted')
    assert not absent.with_name('never-created').exists()
    enabled.write_text('Y\n')
    with patch.object(provision.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'apparmor_parser')), \
         contextlib.redirect_stdout(io.StringIO()):
        try:
            provision.install_bubblewrap_profile(source, profile, enabled)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('Failed AppArmor profile load was silently accepted')

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
         patch.object(provision, 'install_bubblewrap_profile', side_effect=AssertionError('Check changed AppArmor')), \
         patch.object(provision, 'install_cli_preferences', side_effect=AssertionError('Check changed preferences')), \
         patch.object(provision.subprocess, 'run', side_effect=AssertionError('Check ran a command')), \
         patch.object(sys, 'argv', ['provision.py', 'fixture', '--check']), \
         contextlib.redirect_stdout(io.StringIO()):
        provision.main()

    with patch.object(provision.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}), \
         patch.object(provision.platform, 'machine', return_value='x86_64'), \
         patch.object(provision, 'target_user', return_value=user), \
         patch.object(provision.os, 'geteuid', return_value=0), \
         patch.object(provision.subprocess, 'run') as packages, \
         patch.object(provision, 'install_bubblewrap_profile') as apparmor, \
         patch.object(provision, 'install_codex_defaults'), \
         patch.object(provision, 'install_cli_preferences') as preferences, \
         patch.object(provision, 'install_cli') as install, \
         patch.object(sys, 'argv', ['provision.py', 'fixture']), \
         contextlib.redirect_stdout(io.StringIO()):
        provision.main()
        assert {'bubblewrap', 'apparmor-profiles', 'apparmor-utils'} <= set(packages.call_args.args[0])
        apparmor.assert_called_once_with()
        assert install.call_count == len(provision.INSTALLERS)
        preferences.assert_called_once_with(user)

print('Passed: user privilege/environment isolation, attribution merge/ownership/idempotence/invalid-file refusal, Claude scroll default/personal speed retention, existing command retention, partial/missing installation refusal, bubblewrap profile installation/retention/loading/failure handling, Bash PATH and read-only preflight.')
