#!/usr/bin/env python3
"""Check persistent modes, continuous Wayland control and retained settings."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

DESKTOP = Path(__file__).resolve().parents[1] / 'setup/desktop'


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main():
    control = load('night_light', DESKTOP / 'minion-night-light')
    comfort = load('comfort', DESKTOP / 'comfort.py')
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        # Exercise the actual provisioning block without touching host units.
        source = (DESKTOP / 'provision.py').read_text()
        start = source.index('# Prefer packaged applet/night-light units')
        end = source.index('# Merge the renderer', start)
        commands = []
        def local_path(path):
            return home / str(path).lstrip('/')
        def write(path, text):
            target = local_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        for directory in ('/etc/systemd/user', '/etc/xdg/systemd/user'):
            for name in ('minion-bluetooth-applet', 'minion-night-light'):
                write(directory + '/' + name + '.service', 'Old managed unit')
        write('/etc/systemd/user/gammastep.service.d/personal.conf', '# Retain personal override\n')
        context = dict(HERE=DESKTOP, Path=local_path, write=write, run=lambda *args: commands.append(args))
        exec(compile(source[start:end], 'packaged-desktop-services', 'exec'), context)
        for directory in ('/etc/systemd/user', '/etc/xdg/systemd/user'):
            assert not list(local_path(directory).glob('minion-*.service'))
        assert local_path('/etc/systemd/user/gammastep.service.d/personal.conf').read_text() == '# Retain personal override\n'
        assert ('systemctl', '--global', 'disable', 'gammastep-indicator.service') in commands
        assert ('systemctl', '--global', 'mask', 'gammastep-indicator.service') in commands
        assert control.SERVICE == 'gammastep.service'
        assert 'ExecStart=/usr/local/bin/minion-night-light run' in local_path('/etc/systemd/user/gammastep.service.d/60-minion-session.conf').read_text()
        assert 'PartOf=minion-session.target' in local_path('/etc/systemd/user/blueman-applet.service.d/60-minion-session.conf').read_text()
        before_units = {p: p.read_bytes() for p in home.rglob('*.conf')}
        exec(compile(source[start:end], 'packaged-desktop-services', 'exec'), context)
        assert all(p.read_bytes() == content for p, content in before_units.items())
        user = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid(), pw_gid=os.getgid())
        with patch.object(comfort.subprocess, 'check_output', return_value='Etc/UTC\n'), \
             patch.object(comfort.subprocess, 'run') as run, patch.object(comfort.os, 'chown'):
            comfort.install(user)
            run.assert_any_call(['timedatectl', 'set-timezone', 'Europe/Minsk'], check=True)
            run.assert_any_call(['timedatectl', 'set-ntp', 'true'], check=True)
        config = home / '.config/gammastep/config.ini'
        config.write_text(config.read_text().replace('4500', '4200'))
        before = config.read_bytes()
        with patch.object(comfort.subprocess, 'check_output', return_value='Europe/Berlin\n'), \
             patch.object(comfort.subprocess, 'run') as run, patch.object(comfort.os, 'chown'):
            comfort.install(user)
            assert run.call_count == 1  # Retain a personal timezone and temperature.
        assert config.read_bytes() == before
        with patch.dict(os.environ, XDG_CONFIG_HOME=str(home / '.config')):
            _, state = control.paths()
            assert control.selected_mode(state) == 'auto'

            def invoke(mode):
                with patch.object(sys, 'argv', ['minion-night-light', mode]):
                    control.main()

            with patch.object(control.subprocess, 'run') as run:
                invoke('on')
                run.assert_any_call(['systemctl', '--user', 'restart', control.SERVICE], check=True)
            assert state.read_text() == 'on\n'
            with patch.object(control.os, 'execvp', side_effect=SystemExit) as execute:
                try:
                    invoke('run')
                except SystemExit:
                    pass
                execute.assert_called_once_with('gammastep',
                    ['gammastep', '-c', str(config), '-t', '4200:4200'])
            with patch.object(control.subprocess, 'run'):
                invoke('off')
            with patch.object(control.os, 'execvp') as execute:
                invoke('run')
                execute.assert_not_called()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                invoke('status')
            assert output.getvalue() == 'off\n'
            with patch.object(control.subprocess, 'run'):
                invoke('auto')
            with patch.object(control.os, 'execvp', side_effect=SystemExit) as execute:
                try:
                    invoke('run')
                except SystemExit:
                    pass
                execute.assert_called_once_with('gammastep', ['gammastep', '-c', str(config)])
            with patch.object(control.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
                with patch.object(sys, 'argv', ['minion-night-light']):
                    control.main()
            assert state.read_text() == 'auto\n'  # Cancelling the menu changes nothing.
    print('Passed: packaged unit migration/reruns, indicator conflict prevention, timezone/config preservation, persistent modes and continuous Wayland control.')


if __name__ == '__main__':
    main()
