#!/usr/bin/env python3
"""Verify relocated setup, guest staging and VM launch commands without host changes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from session import experiment, setup_sources, stage_setup

PROJECT = Path(__file__).resolve().parents[1]


def load_setup():
    source = PROJECT / 'setup/base/setup.py'
    spec = importlib.util.spec_from_file_location('setup_coordinator', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    sources = setup_sources()
    assert len(sources) == 22
    assert all(p.is_file() for p in sources)
    assert all(p == PROJECT / 'setup.sh' or p.is_relative_to(PROJECT / 'setup') for p in sources)
    assert {p.name for p in sources}.isdisjoint({'first-boot.py', 'mini-os-first-boot.service'})
    with tempfile.TemporaryDirectory(prefix='mini-os-layout-test-') as temporary:
        directory = Path(temporary)
        clone = directory / 'clone'
        for source in sources:
            target = clone / source.relative_to(PROJECT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        result = subprocess.run([str(clone / 'setup.sh'), '--help'], cwd=directory,
                                text=True, capture_output=True, check=True)
        assert '--check' in result.stdout and '--asset-dir' in result.stdout

        guest = directory / 'guest-state'
        guest.mkdir()
        (guest / 'state.json').write_text(json.dumps({'ssh_port': 2222}))
        copies = []
        with patch('session.ssh', return_value=''), patch('session.subprocess.run', side_effect=lambda cmd, **kw: copies.append(cmd)):
            staged = stage_setup(guest, '/home/vmuser/mini-os-test', include_gitignore=True)
        assert len(staged) == 23 and len(copies) == 23
        assert {cmd[-1].removeprefix('vmuser@127.0.0.1:/home/vmuser/mini-os-test/') for cmd in copies} == {
            str(p.relative_to(PROJECT)) for p in staged}
        for invalid in ('/etc/mini-os', '/home/vmuser/../root', 'relative/path'):
            try:
                stage_setup(guest, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe staging target accepted')

        setup = load_setup()
        state = directory / 'setup-state'
        commands = []

        def target_path(value):
            return state if str(value) == '/var/lib/mini-os/setup' else Path(value)

        def fake_process(command, **kwargs):
            commands.append(command)
            return SimpleNamespace(stdout=io.StringIO(''), wait=lambda: 0)

        with patch.object(setup, 'Path', side_effect=target_path), \
             patch.object(setup, 'preflight', return_value=(SimpleNamespace(pw_name='fixture'), None)), \
             patch.object(setup, 'backup_configuration'), \
             patch.object(setup.os, 'geteuid', return_value=0), \
             patch.object(setup.subprocess, 'Popen', side_effect=fake_process), \
             patch.object(sys, 'argv', ['setup.sh']), contextlib.redirect_stdout(io.StringIO()):
            setup.main()
        report = json.loads((Path(json.loads((state / 'last-success.json').read_text())['run']) / 'result.json').read_text())
        assert report['passed']
        expected = {str(p.relative_to(PROJECT)) for p in sources if p != PROJECT / 'setup.sh'}
        assert set(report['source_sha256']) == expected
        assert all(experiment.digest(PROJECT / name) == checksum for name, checksum in report['source_sha256'].items())
        scripts = [cmd[1] for cmd in commands if cmd[0] == sys.executable]
        assert scripts == [str(PROJECT / 'setup' / name) for name in (
            'desktop/provision.py', 'shell/provision.py', 'desktop/browser.py')]

        vm = directory / 'vm'
        vm.mkdir()
        for name in ('disk.qcow2', 'OVMF_VARS.fd'):
            (vm / name).write_bytes(b'fixture')
        (vm / 'firmware.json').write_text(json.dumps({'secure_boot': True}))
        launches = []

        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def bind(self, address): assert address == ('127.0.0.1', 0)
            def getsockname(self): return ('127.0.0.1', 2222)

        class Monitor:
            def __init__(self, path): pass
            def execute(self, command): return {'enabled': True}
            def close(self): pass

        def fake_qemu(command, **kwargs):
            launches.append(command)
            return SimpleNamespace(pid=12345, poll=lambda: None)

        with patch.object(experiment, 'require_stopped'), \
             patch.object(experiment, 'digest', return_value=experiment.ISO_SHA256), \
             patch.object(experiment.socket, 'socket', return_value=Socket()), \
             patch.object(experiment.subprocess, 'Popen', side_effect=fake_qemu), \
             patch.object(experiment, 'Monitor', Monitor), contextlib.redirect_stdout(io.StringIO()):
            experiment.launch(vm, 'install', window=True)
            experiment.launch(vm, 'boot')
        install, boot = launches
        assert any('media=cdrom' in item for item in install)
        assert not any('media=cdrom' in item for item in boot)
        assert not any('seed.iso' in item or 'autoinstall' in item for command in launches for item in command)
        assert '-kernel' not in install and '-initrd' not in install
        assert 'q35,accel=kvm,smm=on' in install
        assert any('readonly=on' in item and 'OVMF_CODE' in item for item in install)
        for value in ('/dev/sda', str(directory / 'foreign'), str(experiment.ROOT / '..' / 'outside')):
            try:
                experiment.select_directory(value)
            except ValueError:
                pass
            else:
                raise AssertionError('Non-fixture VM path accepted')
    print('Passed: relocated entry point, 22 setup sources, guest staging, coordinator hashes/paths and manual Secure Boot VM commands.')


if __name__ == '__main__':
    main()
