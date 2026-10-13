#!/usr/bin/env python3
"""Install the target user's Neovim project viewer and pinned plugins."""
import json
import os
from pathlib import Path
import subprocess
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
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'minion-view'
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'minion-view'
    plugins = data / 'site/pack/minion/start'
    plugins.mkdir(parents=True, exist_ok=True)
    for plugin in json.loads(HERE.joinpath('viewer-plugins.json').read_text()):
        target = plugins / plugin['name']
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
        ('viewer.lua', config / 'init.lua', 0o600, True),
        ('minion-projects', home / '.local/bin/minion-projects', 0o755, False),
        ('minion-projects.desktop', home / '.local/share/applications/minion-projects.desktop', 0o644, False),
    ]
    for source, target, mode, seed in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        if seed and (target.exists() or target.is_symlink()):
            continue
        content = HERE.joinpath(source).read_bytes()
        if source.endswith('.desktop'):
            # Desktop launchers inherit a system PATH without ~/.local/bin.
            launcher = str(home / '.local/bin/minion-projects')
            for character in ('\\', '"', '$', '`'):
                launcher = launcher.replace(character, '\\' + character)
            content = content.replace(b' minion-projects --home', f' "{launcher}" --home'.encode())
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.minion-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(content)
                stream.flush()
                os.fchmod(stream.fileno(), mode)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    print('Project viewer installed. Run minion-projects or choose Project viewer in the launcher.', flush=True)


if __name__ == '__main__':
    install()
