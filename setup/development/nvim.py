#!/usr/bin/env python3
"""Install the target user's default Neovim configuration and pinned plugins."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import time

HERE = Path(__file__).resolve().parent


def git(directory, *arguments):
    for attempt in range(3):
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null',
                                 '-c', 'http.version=HTTP/1.1', '-C', str(directory), *arguments],
                                text=True, capture_output=True, timeout=180,
                                env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
        if result.returncode == 0:
            return result.stdout.strip()
        if arguments[0] != 'fetch' or attempt == 2:
            raise RuntimeError(result.stderr.strip() or 'Git plugin operation failed')
        time.sleep(1)


def install():
    if os.geteuid() == 0:
        raise SystemExit('Run this installer as the desktop user, not root')
    home = Path.home()
    config_base = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    data_base = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    config = config_base / 'nvim'
    data = data_base / 'nvim'
    plugins = data / 'site/pack/minion/start'
    legacy_plugins = data_base / 'minion-view/site/pack/minion/start'
    plugins.mkdir(parents=True, exist_ok=True)
    for plugin in json.loads(HERE.joinpath('nvim-plugins.json').read_text()):
        target = plugins / plugin['name']
        previous = legacy_plugins / plugin['name']
        if not target.exists() and previous.exists():
            if git(previous, 'rev-parse', 'HEAD') == plugin['commit'] and not git(previous, 'status', '--porcelain'):
                shutil.copytree(previous, target, symlinks=True)
        if target.exists():
            current = git(target, 'rev-parse', 'HEAD')
            if git(target, 'status', '--porcelain'):
                raise RuntimeError(f'Plugin has personal changes; reconcile before reinstalling: {target}')
            if current == plugin['commit']:
                continue
        # Complete and verify a new checkout before replacing an installed one.
        with tempfile.TemporaryDirectory(prefix='.minion-plugin-', dir=plugins.parent) as scratch:
            checkout = Path(scratch) / plugin['name']
            checkout.mkdir()
            git(checkout, 'init', '--quiet')
            git(checkout, 'fetch', '--quiet', '--depth=1', plugin['url'], plugin['commit'])
            git(checkout, 'checkout', '--quiet', '--detach', 'FETCH_HEAD')
            if git(checkout, 'rev-parse', 'HEAD') != plugin['commit']:
                raise RuntimeError(f'Plugin revision mismatch: {plugin["name"]}')
            backup = Path(scratch) / 'previous'
            if target.exists():
                target.rename(backup)
            try:
                checkout.rename(target)
            except OSError:
                if backup.exists():
                    backup.rename(target)
                raise
        print(f'Installed {plugin["name"]} {plugin["tag"]}', flush=True)
    files = [
        ('nvim.lua', config / 'init.lua', 0o600, True),
        ('minion-nvim.desktop', home / '.local/share/applications/minion-nvim.desktop', 0o644, False),
    ]
    for source, target, mode, seed in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        if seed and (target.exists() or target.is_symlink()):
            continue
        content = HERE.joinpath(source).read_bytes()
        if source.endswith('.desktop'):
            # Desktop launchers do not activate mise or Cargo through Bash.
            environment = f'PATH={home}/.local/bin:{home}/.local/share/mise/shims:{home}/.cargo/bin:/usr/local/bin:/usr/bin:/bin'
            for character in ('\\', '"', '$', '`'):
                environment = environment.replace(character, '\\' + character)
            content = content.replace(b'@NVIM_ENV@', f'"{environment}"'.encode())
            content += f'Path={home}\n'.encode()
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.minion-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(content)
                stream.flush()
                os.fchmod(stream.fileno(), mode)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    # Retire the old entry point only when it still belongs to this setup.
    wrapper = home / '.local/bin/minion-projects'
    if wrapper.is_file() and 'NVIM_APPNAME' in wrapper.read_text() and 'minion-view' in wrapper.read_text():
        wrapper.unlink()
    old_desktop = home / '.local/share/applications/minion-projects.desktop'
    if old_desktop.is_file() and 'minion-projects' in old_desktop.read_text():
        old_desktop.unlink()
    print('Neovim installed. Run nvim . to browse a project, or select Neovim in the launcher.', flush=True)


if __name__ == '__main__':
    install()
