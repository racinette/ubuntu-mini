#!/usr/bin/env python3
"""Set up an existing Ubuntu Server installation, without installer state."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import shlex
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def required_assets():
    assets = [(item['filename'], item['sha256']) for item in
              json.loads((ROOT / 'shell/artifacts.json').read_text()).values()]
    for item in json.loads((ROOT / 'desktop/browser-snaps.json').read_text()):
        assets.extend((item[k], item[k + '_sha256']) for k in ('snap', 'assert'))
    for filename, checksum in assets:
        if Path(filename).name != filename or len(checksum) != 64:
            raise ValueError('Invalid artifact manifest')
    return assets


def preflight(args):
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            release[key] = value.strip('"')
    if release.get('ID') != 'ubuntu' or release.get('VERSION_ID') != '24.04':
        raise ValueError('This setup supports Ubuntu 24.04 only')
    if platform.machine() != 'x86_64':
        raise ValueError('This setup supports amd64 machines only')
    username = args.user or os.environ.get('SUDO_USER')
    if not username or username == 'root':
        raise ValueError('Use sudo from your normal account, or pass --user USERNAME')
    user = pwd.getpwnam(username)
    if user.pw_uid < 1000 or Path(user.pw_shell).name != 'bash' or not Path(user.pw_dir).is_dir():
        raise ValueError('Select an existing regular user with a home directory and Bash login shell')
    if not Path('/run/systemd/system').is_dir():
        raise ValueError('Run in the booted installed system, not an installer/chroot')
    active_dm = Path('/etc/systemd/system/display-manager.service')
    if active_dm.exists() and active_dm.resolve().name != 'greetd.service':
        raise ValueError('Another display manager is configured; this setup targets Ubuntu Server')
    if args.asset_url:
        parts = urlsplit(args.asset_url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('--asset-url must be a plain HTTP(S) directory URL')
        asset_url = args.asset_url.rstrip('/')
        print('Checking artifact cache availability...', flush=True)
        for filename, _ in required_assets():
            request = urllib.request.Request(asset_url + '/' + filename, method='HEAD')
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise ValueError('Artifact cache refused: ' + filename)
    elif args.asset_dir:
        assets = args.asset_dir.resolve()
        print('Verifying local shell/browser artifacts...', flush=True)
        for filename, checksum in required_assets():
            path = assets / filename
            if not path.is_file() or digest(path) != checksum:
                raise ValueError('Missing or incorrect artifact: ' + str(path))
        asset_url = assets.as_uri()
    else:
        asset_url = None
        print('Online setup: Ubuntu repositories, Snap Store and verified upstream shell downloads.', flush=True)
    return user, asset_url


def backup_configuration(path, user):
    paths = [Path(name) for name in (
        '/etc/greetd', '/etc/mini-os', '/etc/netplan', '/etc/pam.d/greetd',
        '/etc/pam.d/greetd-greeter', '/etc/systemd/system/greetd.service.d',
        '/etc/xdg/xdg-desktop-portal/sway-portals.conf',
        '/etc/systemd/user/mini-os-session.target', '/etc/systemd/user/mako.service.d',
        '/etc/systemd/user/xdg-desktop-portal.service.d',
        '/etc/systemd/user/xdg-desktop-portal-gtk.service.d',
        '/etc/systemd/user/xdg-desktop-portal-wlr.service.d',
        '/etc/udev/rules.d/60-mini-os-gamepad-uinput.rules',
        '/etc/modules-load.d/mini-os-gamepad.conf',
        '/usr/local/share/mini-os/bashrc.bash')]
    paths.extend(Path('/etc/systemd/user').glob('mini-os-*.service'))
    paths.extend(Path('/usr/local/bin').glob('mini-os-*'))
    paths.append(Path(user.pw_dir) / '.bashrc')
    with tarfile.open(path, 'w:gz', dereference=False) as archive:
        for source in paths:
            if source.exists() or source.is_symlink():
                archive.add(source, arcname=str(source).lstrip('/'))
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', help='Existing account; defaults to the account invoking sudo')
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument('--asset-dir', type=Path, help='Optional local cache of pinned shell/browser artifacts')
    transport.add_argument('--asset-url', help='Explicit HTTP(S) artifact cache; APT sources remain as configured')
    parser.add_argument('--check', action='store_true', help='Check target prerequisites and any explicit cache without changing the system')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit('Ubuntu 24.04 Python 3.12 or later is required')
    if not args.check and os.geteuid() != 0:
        raise SystemExit('Run with sudo, e.g. sudo ./setup.sh')
    try:
        user, asset_url = preflight(args)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error)) from error
    print(f'Setup target: {user.pw_name}. Existing Ubuntu APT sources will be used.', flush=True)
    if args.check:
        print('Checks passed. No changes made. Run sudo ./setup.sh with the same options to apply.', flush=True)
        return
    state = Path('/var/lib/mini-os/setup')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    with (state / 'setup.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another setup run is active')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
        run_dir = state / stamp
        run_dir.mkdir(mode=0o700)
        backup_configuration(run_dir / 'configuration-before.tar.gz', user)
        report = {'username': user.pw_name, 'started_at_utc': stamp, 'passed': False,
                  'source_sha256': {str(p.relative_to(ROOT.parent)): digest(p) for folder in ('base', 'desktop', 'shell')
                                    for p in sorted((ROOT / folder).iterdir()) if p.is_file()},
                  'steps': [], 'reboot_required': True}
        with (run_dir / 'setup.log').open('w', buffering=1) as log:
            env = dict(os.environ, DEBIAN_FRONTEND='noninteractive', LC_ALL='C')

            def run(*command):
                command = [str(arg) for arg in command]
                line = '+ ' + shlex.join(command)
                print(line, flush=True)
                log.write(line + '\n')
                process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                code = process.wait()
                report['steps'].append({'command': command, 'returncode': code})
                if code:
                    raise RuntimeError(f'Command failed ({code}): ' + shlex.join(command))

            try:
                run('apt-get', 'update')
                run('apt-get', 'install', '-y', '--no-install-recommends',
                    *(ROOT / 'base/packages.txt').read_text().split())
                run(sys.executable, ROOT / 'desktop/provision.py', '--user', user.pw_name, '--defer-activation')
                cache_options = ['--asset-url', asset_url] if asset_url else []
                run(sys.executable, ROOT / 'shell/provision.py', user.pw_name, *cache_options)
                run('systemctl', 'start', 'snapd.socket')
                run(sys.executable, ROOT / 'desktop/browser.py', *cache_options)
                report['passed'] = True
                (state / 'last-success.json').write_text(json.dumps({'run': str(run_dir)}, indent=2) + '\n')
            except Exception as error:
                report['error'] = str(error)
                print(f'Setup stopped: {error}\nLog: {run_dir / "setup.log"}', file=sys.stderr)
                raise SystemExit(1) from error
            finally:
                report['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                (run_dir / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'Setup completed. Log and configuration backup: {run_dir}', flush=True)
        print('Reboot when ready. Then log in with your existing username and password.', flush=True)


if __name__ == '__main__':
    main()
