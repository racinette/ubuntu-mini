#!/usr/bin/env python3
"""Install the official coding CLIs for the selected desktop user."""
import argparse
import json
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


def install_cli_preferences(user):
    """Merge attribution preferences and seed Claude's wheel speed multiplier."""
    settings = (
        ('.claude/settings.json', {'commit': '', 'pr': ''}, {}),
        ('.cursor/cli-config.json',
         {'attributeCommitsToAgent': False, 'attributePRsToAgent': False},
         {'version': 1, 'editor': {'vimMode': False}, 'permissions': {'allow': [], 'deny': []}}),
    )
    for name, attribution, initial in settings:
        target = Path(user.pw_dir) / name
        if target.exists():
            data = json.loads(target.read_text())
        else:
            data = initial.copy()
        if not isinstance(data, dict) or not isinstance(data.get('attribution', {}), dict):
            raise ValueError(f'Expected JSON objects in {target} and its attribution setting')
        updated = {**data, 'attribution': {**data.get('attribution', {}), **attribution}}
        if name == '.claude/settings.json':
            environment = data.get('env', {})
            if not isinstance(environment, dict):
                raise ValueError(f'Expected an env JSON object in {target}')
            updated['env'] = {'CLAUDE_CODE_SCROLL_SPEED': '3', **environment}
        if data == updated:
            continue
        if not target.parent.exists():
            target.parent.mkdir(mode=0o700, parents=True)
            if os.geteuid() == 0:
                os.chown(target.parent, user.pw_uid, user.pw_gid)
        mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                os.fchmod(stream.fileno(), mode)
                if os.geteuid() == 0:
                    os.fchown(stream.fileno(), user.pw_uid, user.pw_gid)
                json.dump(updated, stream, indent=2)
                stream.write('\n')
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f'Applied coding CLI preferences: {target}', flush=True)


def install_bubblewrap_profile(
        source=Path('/usr/share/apparmor/extra-profiles/bwrap-userns-restrict'),
        target=Path('/etc/apparmor.d/bwrap-userns-restrict'),
        enabled=Path('/sys/module/apparmor/parameters/enabled')):
    """Enable Ubuntu's bubblewrap exception while retaining global userns policy."""
    if not target.exists():
        contents = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(contents)
        target.chmod(0o644)
    else:
        print(f'Retaining existing bubblewrap AppArmor profile: {target}', flush=True)
    if enabled.exists() and enabled.read_text().strip() == 'Y':
        subprocess.run(['/usr/sbin/apparmor_parser', '-r', str(target)], check=True)
    else:
        print('AppArmor is inactive; bubblewrap profile installed for future boots.', flush=True)


def install_codex_defaults(target=Path('/etc/codex/config.toml')):
    """Seed system defaults without replacing existing system or user settings."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('x') as stream:
            stream.write(HERE.joinpath('codex.toml').read_text())
        target.chmod(0o644)
    except FileExistsError:
        print(f'Retaining existing Codex system settings: {target}', flush=True)


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
    install_bubblewrap_profile()
    install_codex_defaults()
    env = user_environment(user)
    for installer in INSTALLERS:
        install_cli(user, env, *installer)
    install_cli_preferences(user)
    print(f'Coding CLIs ready for {user.pw_name}. Open a new terminal; run codex, claude or agent to sign in.')


if __name__ == '__main__':
    main()
