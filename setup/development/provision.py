#!/usr/bin/env python3
"""Preinstall current development toolchains and Docker for the desktop user."""
import argparse
import json
import os
import platform
import pwd
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = json.loads(HERE.joinpath('tools.json').read_text())
COMPONENTS = ('rustfmt', 'clippy', 'rust-analyzer', 'rust-src')
DOCKER_PACKAGES = ('docker-ce', 'docker-ce-cli', 'containerd.io',
                   'docker-buildx-plugin', 'docker-compose-plugin')
DOCKER_CONFLICTS = ('docker.io', 'docker-compose', 'docker-compose-v2',
                    'docker-doc', 'podman-docker', 'containerd', 'runc')
DOCKER_SOURCE = Path('/etc/apt/sources.list.d/docker.sources')
DOCKER_KEY = Path('/etc/apt/keyrings/docker.asc')


def target_user(username):
    user = pwd.getpwnam(username)
    if user.pw_uid < 1000 or Path(user.pw_shell).name != 'bash' or not Path(user.pw_dir).is_dir():
        raise ValueError('Select an existing regular user with a home directory and Bash login shell')
    return user


def user_environment(user):
    # Installers/builds never receive root's credentials, shell hooks or home.
    env = {key: value for key, value in os.environ.items()
           if key.lower() in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
    home = user.pw_dir
    env.update(HOME=home, USER=user.pw_name, LOGNAME=user.pw_name,
               SHELL=user.pw_shell, LC_ALL='C.UTF-8', NO_COLOR='1',
               PATH=f'{home}/.local/bin:{home}/.cargo/bin:{home}/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin',
               MISE_YES='1', MISE_SELF_UPDATE_MINIMUM_RELEASE_AGE='0s',
               UV_NO_MODIFY_PATH='1', UV_INSTALL_DIR=f'{home}/.local/bin')
    return env


def run_as_user(user, env, *command, cwd=None, capture=False):
    return subprocess.run([str(arg) for arg in command], check=True, env=env,
                          cwd=cwd or user.pw_dir, stdin=subprocess.DEVNULL, timeout=3600,
                          user=user.pw_uid, group=user.pw_gid,
                          extra_groups=os.getgrouplist(user.pw_name, user.pw_gid),
                          umask=0o022, text=True, stdout=subprocess.PIPE if capture else None)


def bootstrap(user, env, name, url, shell, *arguments):
    executable = shutil.which(name, path=env['PATH'])
    if executable:
        print(f'Retaining {name}: {executable}', flush=True)
        return executable
    with tempfile.TemporaryDirectory(prefix=f'minion-{name}-') as temporary:
        scratch = Path(temporary)
        os.chown(scratch, user.pw_uid, user.pw_gid)
        script = scratch / 'install.sh'
        run_as_user(user, env, '/usr/bin/curl', '--fail', '--silent', '--show-error',
                    '--location', '--compressed', '--retry', '3', '--connect-timeout', '30',
                    '--max-time', '180', '--proto', '=https', '--proto-redir', '=https',
                    '--output', script, url)
        run_as_user(user, env, shell, script, *arguments)
    executable = shutil.which(name, path=env['PATH'])
    if not executable:
        raise RuntimeError(f'{name} installer completed without a usable executable')
    return executable


def install_mise_tools(user, env, mise):
    # Work outside the checkout and home so a project config cannot change the
    # global install or run its hooks. Existing global selections are retained.
    with tempfile.TemporaryDirectory(prefix='minion-toolchains-') as temporary:
        os.chown(temporary, user.pw_uid, user.pw_gid)
        # Install runtimes before npm/Go-based tools. mise parallelizes each
        # batch while remaining the sole writer of its configuration.
        for batch in (TOOLS[:3], TOOLS[3:]):
            existing, missing = [], []
            for tool in batch:
                result = run_as_user(user, env, mise, 'ls', tool, '--global', '--json',
                                     cwd=temporary, capture=True)
                (existing if json.loads(result.stdout) else missing).append(tool)
            if existing:
                run_as_user(user, env, mise, 'install', *existing, cwd=temporary)
            if missing:
                # Resolve at installation time, then record the exact version.
                # The fresh-install request explicitly asks for newest stable.
                run_as_user(user, dict(env, MISE_MINIMUM_RELEASE_AGE='0s'), mise,
                            'use', '--global', '--pin',
                            *[f'{tool}@latest' for tool in missing], cwd=temporary)
        run_as_user(user, env, mise, 'reshim', cwd=temporary)
        run_as_user(user, env, mise, 'ls', '--global', cwd=temporary)


def install_toolchains(user):
    env = user_environment(user)
    mise = bootstrap(user, env, 'mise', 'https://mise.run', '/bin/sh')
    uv = bootstrap(user, env, 'uv', 'https://astral.sh/uv/install.sh', '/bin/sh')
    rustup = bootstrap(user, env, 'rustup', 'https://sh.rustup.rs', '/bin/sh',
                       '-y', '--no-modify-path', '--profile', 'minimal',
                       '--default-toolchain', 'stable',
                       *[arg for component in COMPONENTS for arg in ('--component', component)])
    # Explicitly install, rather than letting first use download a compiler.
    # Do not change an existing rustup default (e.g. a pinned release/nightly).
    run_as_user(user, env, rustup, 'toolchain', 'install', 'stable', '--profile', 'minimal',
                *[arg for component in COMPONENTS for arg in ('--component', component)])
    home = Path(user.pw_dir)
    # uv's --default installs user-local python/python3, never /usr/bin/python3.
    # Preserve a user-local development Python selection on subsequent runs.
    has_default = any((home / '.local/bin' / name).exists() or
                      (home / '.local/bin' / name).is_symlink() for name in ('python', 'python3'))
    # Resolve from uv's download catalog, independently of existing installs
    # and ~/.python-version. Exclude prereleases and free-threaded variants.
    catalog = json.loads(run_as_user(user, env, uv, 'python', 'list', 'cpython',
                                    '--only-downloads', '--output-format', 'json', capture=True).stdout)
    versions = [item['version'] for item in catalog
                if item['implementation'] == 'cpython' and item['variant'] == 'default'
                and len(item['version'].split('.')) == 3
                and all(part.isdecimal() for part in item['version'].split('.'))]
    if not versions:
        raise RuntimeError('uv did not provide a stable CPython download for this platform')
    version = max(versions, key=lambda value: tuple(map(int, value.split('.'))))
    run_as_user(user, env, uv, 'python', 'install', f'cpython@{version}',
                *([] if has_default else ['--default']))
    if not shutil.which('ruff', path=env['PATH']):
        run_as_user(user, env, uv, 'tool', 'install', 'ruff')
    install_mise_tools(user, env, mise)
    run_as_user(user, env, uv, '--version')
    run_as_user(user, env, rustup, 'show')


def docker_source(architecture):
    return ('Types: deb\nURIs: https://download.docker.com/linux/ubuntu\n'
            f'Suites: noble\nComponents: stable\nArchitectures: {architecture}\n'
            f'Signed-By: {DOCKER_KEY}\n')


def check_docker_repository(architecture):
    # Never remove a different container runtime or rewrite its repository.
    status = subprocess.run(['dpkg-query', '-W', '-f=${Package} ${db:Status-Status}\n',
                             *DOCKER_CONFLICTS], check=False, text=True, capture_output=True)
    if status.returncode not in (0, 1):
        raise RuntimeError('Could not inspect installed container runtime packages')
    conflicts = [line.split()[0] for line in status.stdout.splitlines()
                 if line.endswith(' installed')]
    if conflicts:
        raise ValueError('Docker CE conflicts with installed packages: ' + ', '.join(conflicts) +
                         '. Resolve the existing container runtime before rerunning setup.')
    if DOCKER_SOURCE.exists() and DOCKER_SOURCE.read_text() != docker_source(architecture):
        raise ValueError(f'{DOCKER_SOURCE} already has different settings; reconcile it before setup')
    for source in [DOCKER_SOURCE.parent.parent / 'sources.list', *DOCKER_SOURCE.parent.glob('*.list'),
                   *DOCKER_SOURCE.parent.glob('*.sources')]:
        if source != DOCKER_SOURCE and source.exists() and 'download.docker.com' in source.read_text():
            raise ValueError(f'Docker repository already declared in {source}; reconcile it before setup')


def install_docker(user, architecture):
    check_docker_repository(architecture)
    DOCKER_KEY.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    # A failed transfer cannot replace the working key. APT verifies signed
    # repository metadata with this repository-scoped key.
    with tempfile.TemporaryDirectory(prefix='minion-docker-key-') as temporary:
        key = Path(temporary) / 'docker.asc'
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                        '--retry', '3', '--proto', '=https', '--proto-redir', '=https',
                        '--connect-timeout', '30', '--max-time', '180', '--output', str(key),
                        'https://download.docker.com/linux/ubuntu/gpg'], check=True)
        subprocess.run(['gpg', '--batch', '--show-keys', str(key)], check=True)
        shutil.copyfile(key, DOCKER_KEY)
        DOCKER_KEY.chmod(0o644)
    DOCKER_SOURCE.write_text(docker_source(architecture))
    DOCKER_SOURCE.chmod(0o644)
    subprocess.run(['apt-get', 'update'], check=True)
    subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends', *DOCKER_PACKAGES], check=True)
    subprocess.run(['usermod', '-aG', 'docker', user.pw_name], check=True)
    # enable --now is a no-op for an already running service; no forced restart.
    subprocess.run(['systemctl', 'enable', '--now', 'docker.service'], check=True)
    subprocess.run(['docker', '--host=unix:///var/run/docker.sock', 'info',
                    '--format', '{{.ServerVersion}}'], check=True, timeout=60)
    subprocess.run(['docker', 'compose', 'version'], check=True)
    subprocess.run(['docker', 'buildx', 'version'], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    parser.add_argument('--check', action='store_true', help='Check the target without downloads or writes')
    args = parser.parse_args()
    release = platform.freedesktop_os_release()
    if release.get('ID') != 'ubuntu' or release.get('VERSION_ID') != '24.04' or platform.machine() != 'x86_64':
        raise SystemExit('This setup supports Ubuntu 24.04 amd64 only')
    try:
        user = target_user(args.username)
        check_docker_repository('amd64')
    except (KeyError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
    if args.check:
        print(f'Development target: {user.pw_name}; mise, rustup, uv, Docker CE and SuperCollider/JUCE. No changes made.')
        return
    if os.geteuid() != 0:
        raise SystemExit('Run as root inside the installed target')
    subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends',
                    *HERE.joinpath('packages.txt').read_text().split(),
                    *HERE.joinpath('audio-packages.txt').read_text().split()], check=True)
    install_toolchains(user)
    run_as_user(user, user_environment(user), '/usr/bin/python3', HERE / 'nvim.py')
    run_as_user(user, user_environment(user), '/usr/bin/python3', HERE / 'audio.py')
    install_docker(user, 'amd64')
    print('Development toolchains ready. Log in again for Docker group access.', flush=True)


if __name__ == '__main__':
    main()
