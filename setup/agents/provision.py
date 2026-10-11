#!/usr/bin/env python3
"""Install the official coding CLIs for the selected desktop user."""
import argparse
import os
from pathlib import Path
import platform
import pwd
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
# These are the publishers' documented native installers, following their
# current release channels. Unlike the shell/HHD artifacts, they are not pinned.
INSTALLERS = (
    ('codex', 'https://chatgpt.com/codex/install.sh', 'sh', ()),
    ('claude', 'https://claude.ai/install.sh', 'bash', ('stable',)),
    ('agent', 'https://cursor.com/install', 'bash', ()),
)
SYSTEM_PATH = '/usr/local/bin:/usr/bin:/bin'


def target_user(username):
    user = pwd.getpwnam(username)
    if user.pw_uid < 1000 or Path(user.pw_shell).name != 'bash' or not Path(user.pw_dir).is_dir():
        raise ValueError('Select an existing regular user with a home directory and Bash login shell')
    return user


def user_environment(user):
    # Do not pass root's HOME, XDG paths, API keys, tool settings or sudo state
    # into installers. Network proxy settings still support explicit proxies.
    env = {key: value for key, value in os.environ.items()
           if key.lower() in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
    env.update(HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name,
               SHELL=user.pw_shell, PATH=f'{user.pw_dir}/.local/bin:{SYSTEM_PATH}',
               LC_ALL='C.UTF-8', NO_COLOR='1', CODEX_NON_INTERACTIVE='1')
    return env


def run_as_user(user, env, *command, timeout=1800):
    return subprocess.run([str(arg) for arg in command], check=True, env=env,
                          cwd=user.pw_dir, stdin=subprocess.DEVNULL, timeout=timeout,
                          user=user.pw_uid, group=user.pw_gid,
                          extra_groups=os.getgrouplist(user.pw_name, user.pw_gid), umask=0o022)


def install_cli(user, env, name, url, shell, arguments):
    command = shutil.which(name, path=env['PATH'])
    if command:
        # Even --version can rewrite upstream settings (notably Cursor's).
        # Retain existing executables without launching or shadowing them.
        print(f'Retaining existing {name}: {command}', flush=True)
        return
    with tempfile.TemporaryDirectory(prefix=f'minion-{name}-') as temporary:
        scratch = Path(temporary)
        os.chown(scratch, user.pw_uid, user.pw_gid)
        script = scratch / 'install.sh'
        print(f'Installing {name} for {user.pw_name} using {url}', flush=True)
        # Download to a file first: a failed or truncated request must never
        # execute as a partial shell pipeline. Both steps run without root.
        run_as_user(user, env, '/usr/bin/curl', '--fail', '--silent', '--show-error',
                    '--location', '--compressed', '--retry', '3', '--connect-timeout', '30',
                    '--max-time', '180', '--proto', '=https', '--proto-redir', '=https',
                    '--output', script, url, timeout=900)
        run_as_user(user, env, f'/bin/{shell}', script, *arguments)
    command = shutil.which(name, path=env['PATH'])
    if not command:
        raise RuntimeError(f'{name} installer completed without a usable command in ~/.local/bin')
    run_as_user(user, env, command, '--version', timeout=120)


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
    except (KeyError, ValueError) as error:
        raise SystemExit(str(error)) from error
    if args.check:
        print(f'Coding CLI target: {user.pw_name}; native codex, claude and agent installers. No changes made.')
        return
    if os.geteuid() != 0:
        raise SystemExit('Run as root inside the installed target')
    subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends',
                    *HERE.joinpath('packages.txt').read_text().split()], check=True)
    env = user_environment(user)
    for installer in INSTALLERS:
        install_cli(user, env, *installer)
    print(f'Coding CLIs ready for {user.pw_name}. Open a new terminal; run codex, claude or agent to sign in.')


if __name__ == '__main__':
    main()
