#!/usr/bin/env python3
"""Check service handoff, terminal progress and failures without disk writes."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import types
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'install.sh'
PAYLOAD = SOURCE.read_text().split("<<'MINI_OS_INSTALL_PYTHON'\n", 1)[1].rsplit('\nMINI_OS_INSTALL_PYTHON', 1)[0]
installer = types.ModuleType('installer')
exec(compile(PAYLOAD, str(SOURCE), 'exec'), installer.__dict__)


def main():
    # Nested sudo PTYs hide the physical VT from both SUDO_TTY and ps(self).
    with patch.dict(os.environ, {'SUDO_TTY':'/dev/pts/0'}), \
         patch.object(installer, 'run', side_effect=[SimpleNamespace(stdout='23 pts/0 python3'),
                                                   SimpleNamespace(stdout='1 tty2 sudo')]):
        assert installer.progress_console(False) == 3
    with patch.dict(os.environ, {'SUDO_TTY':'/dev/pts/0'}), \
         patch.object(installer, 'run', side_effect=[SimpleNamespace(stdout='23 pts/0 python3'),
                                                   SimpleNamespace(stdout='1 ? sshd')]):
        assert installer.progress_console(False) is None
    with patch.dict(os.environ, {'SUDO_TTY':'/dev/tty3'}):
        assert installer.progress_console(False) == 4
        assert installer.progress_console(True) is None
    with tempfile.TemporaryDirectory(prefix='ubuntu-mini-launch-test-') as temporary:
        root = Path(temporary)
        work = root / 'work'
        configuration = root / 'autoinstall.yaml'
        state = root / 'subiquity'
        state.mkdir()
        (state / 'server-state').write_text('WAITING')
        original = dict(label='gpt', device='/dev/fixture', sectorsize=512,
                        firstlba=2048, lastlba=48*installer.GIB//512-1, partitions=[])
        plan = installer.make_plan(original, 20*installer.GIB)
        plan['identity'] = dict(serial='fixture')
        before = copy.deepcopy(plan)
        commands = []

        def path(value):
            return {'/autoinstall.yaml': configuration,
                    '/run/subiquity': state,
                    '/run/subiquity/server-state': state / 'server-state',
                    '/proc/cmdline': root / 'cmdline',
                    '/var/log/installer/curtin-install.log': root / 'curtin.log',
                    '/run/mini-os-install': root / 'old-work'}.get(str(value), Path(value))

        (root / 'cmdline').write_text('quiet')

        def run(*args, **kwargs):
            commands.append(args)
            # A stop here would kill a caller living in the original service.
            assert not (args[:2] == ('systemctl', 'stop') and any('subiquity' in str(a) for a in args))
            output = 'tty2\n' if args[0] == 'ps' else 'hash-placeholder\n'
            return SimpleNamespace(stdout=output, stderr='', returncode=0)

        with patch.object(installer, 'WORK', work), patch.object(installer, 'Path', side_effect=path), \
             patch.dict(os.environ, {'SUDO_TTY':'/dev/tty2'}), \
             patch.object(installer, 'run', side_effect=run), \
             patch.object(installer, 'verify_original'), patch.object(installer, 'installer_state', return_value='WAITING'), \
             patch.object(installer.sys, 'argv', ['-', str(SOURCE)]), contextlib.redirect_stdout(io.StringIO()):
            args = SimpleNamespace(mirror=None, no_follow=False)
            installer.start_install(args, plan, root / 'snap', dict(hostname='fixture', username='fixture',
                login_password='private-account', luks_passphrase='private-encryption'))
        assert before['original'] == plan['original']
        assert plan['progress_console'] == 3
        assert (work / 'launch.sh').exists() and (work / 'install.sh').exists()
        assert (work / 'luks.key').read_text() == 'private-encryption'
        assert work.stat().st_mode & 0o777 == 0o700
        assert (work / 'luks.key').stat().st_mode & 0o777 == 0o600
        assert 'private-encryption' not in configuration.read_text()
        assert 'private-account' not in configuration.read_text()
        units = [c for c in commands if c[0] == 'systemd-run']
        assert len(units) == 2 and '--follow' in units[0] and '--launch' in units[1]
        assert '--unit=ubuntu-mini-install-console' in units[0]
        assert '--property=TTYPath=/dev/tty3' in units[0]
        assert '--unit=ubuntu-mini-install' in units[1]

        # Simulate the original service killing its own shell during handoff.
        # The worker has already inherited all input and can still install.
        worker_commands = []
        class Server:
            returncode = 0
            def __init__(self, argv):
                assert argv == ['/bin/sh', str(work / 'launch.sh')]
                assert not state.exists()
                state.mkdir()
                (state / 'server-state').write_text('DONE')
                (work / 'verification.json').write_text('{"passed": true}')
                self.calls = 0
            def poll(self):
                self.calls += 1
                return None if self.calls == 1 else self.returncode

        def worker_run(*args, **kwargs):
            worker_commands.append(args)
            if args[:2] == ('systemctl', 'stop'):
                assert (work / 'launch.sh').exists()
                (work / 'original-shell-terminated').touch()
            return SimpleNamespace(stdout='', stderr='', returncode=0)

        with patch.object(installer, 'WORK', work), patch.object(installer, 'Path', side_effect=path), \
             patch.object(installer, 'run', side_effect=worker_run), \
             patch.object(installer, 'live_environment', return_value=root/'snap'), \
             patch.object(installer, 'inventory', return_value=before), patch.object(installer, 'verify_original'), \
             patch.object(installer.subprocess, 'Popen', side_effect=Server), \
             patch.object(installer.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            installer.launch_worker()
        assert (work/'original-shell-terminated').exists()
        assert json.loads((work/'status.json').read_text())['stage'] == 'complete'
        assert (work/'previous-session').exists()
        assert ('chvt', '3') in worker_commands

        class FailedServer:
            returncode = 7
            def __init__(self, argv): pass
            def poll(self): return self.returncode
        # A process that exits before verification must fail visibly, remove
        # the temporary key, and never report success.
        (work/'verification.json').unlink()
        (state/'server-state').unlink()
        state.rmdir()
        (work/'previous-session').rename(state)
        with patch.object(installer, 'WORK', work), patch.object(installer, 'Path', side_effect=path), \
             patch.object(installer, 'run', side_effect=worker_run), \
             patch.object(installer, 'live_environment', return_value=root/'snap'), \
             patch.object(installer, 'inventory', return_value=before), patch.object(installer, 'verify_original'), \
             patch.object(installer.subprocess, 'Popen', side_effect=FailedServer), contextlib.redirect_stdout(io.StringIO()):
            try:
                installer.launch_worker()
            except ValueError as error:
                assert 'status 7' in str(error)
            else:
                raise AssertionError('An unverified failed installer was accepted')
        assert not (work/'luks.key').exists()
        assert json.loads((work/'status.json').read_text())['stage'] == 'failed'

        output = io.StringIO()
        with patch.object(installer, 'WORK', work), patch.object(installer, 'Path', side_effect=path), \
             patch.object(installer, 'service_properties', return_value={'ActiveState': 'failed'}), \
             contextlib.redirect_stdout(output):
            assert installer.follow_progress() == 1
        assert 'failed' in output.getvalue() and 'status 7' in output.getvalue()

        # A quiet but active installer emits a heartbeat. Closing its viewer
        # never sends a stop command to the independent service.
        now = [0]
        def sleep(_):
            now[0] += 16
            if now[0] > 32:
                raise KeyboardInterrupt
        output = io.StringIO()
        with patch.object(installer, 'Path', side_effect=path), \
             patch.object(installer, 'status_record', return_value={'stage':'installing','message':'Quiet step'}), \
             patch.object(installer, 'service_properties', return_value={'ActiveState':'active'}), \
             patch.object(installer.time, 'monotonic', side_effect=lambda:now[0]), \
             patch.object(installer.time, 'sleep', side_effect=sleep), contextlib.redirect_stdout(output):
            assert installer.follow_progress() == 0
        assert 'Still watching' in output.getvalue() and 'Installation continues' in output.getvalue()

        # Status is usable after the original installer has stopped and never
        # probes or writes disks, asks credentials or checks the live API.
        output = io.StringIO()
        with patch.object(installer.sys, 'argv', ['-',str(SOURCE),'--status']), \
             patch.object(installer.os, 'geteuid', return_value=0), \
             patch.object(installer, 'status_record', return_value={'stage':'failed','message':'Test failure'}), \
             patch.object(installer, 'service_properties', return_value={'ActiveState':'failed'}), \
             patch.object(installer, 'Path', side_effect=path), \
             patch.object(installer, 'live_environment', side_effect=AssertionError('Live API queried')), \
             patch.object(installer, 'inventory', side_effect=AssertionError('Disk inspected')), \
             contextlib.redirect_stdout(output):
            installer.main()
        assert 'Test failure' in output.getvalue()
    print('Passed: independent service handoff, dedicated console, failed-start reporting, '
          'temporary-key cleanup, quiet-step heartbeat, viewer interruption and read-only status.')


if __name__ == '__main__':
    main()
