"""Configure bounded sudo caching and a shared desktop SSH agent."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SUDOERS = Path('/etc/sudoers.d')
UNITS = Path('/etc/systemd/user')
LEGACY_UNITS = Path('/etc/xdg/systemd/user')


def sudo_policy(username):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*\$?', username):
        raise ValueError('Unsupported sudoers account name')
    return ('# Minion: bounded authentication cache shared by this account.\n'
            f'Defaults:{username} timestamp_type=global, timestamp_timeout=15\n')


def install_sudo(user):
    target = SUDOERS / ('60-minion-auth-' + user.pw_name)
    policy = sudo_policy(user.pw_name)
    if target.is_symlink():
        raise ValueError('Refusing a symlink for the managed sudoers policy')
    if target.exists() and target.read_text() == policy:
        return
    before = target.read_bytes() if target.exists() else None
    with tempfile.NamedTemporaryFile(mode='w', dir=SUDOERS, prefix='.minion-auth-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(policy)
            stream.flush()
            temporary.chmod(0o440)
            subprocess.run(['visudo', '-c', '-f', str(temporary)], check=True)
            temporary.replace(target)
            try:
                subprocess.run(['visudo', '-c'], check=True)
            except BaseException:
                if before is None:
                    target.unlink()
                else:
                    temporary.write_bytes(before)
                    temporary.chmod(0o440)
                    temporary.replace(target)
                raise
        finally:
            temporary.unlink(missing_ok=True)


def user_write(path, text, user):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.minion-auth-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            temporary.chmod(0o600)
            os.chown(temporary, user.pw_uid, user.pw_gid)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def install(user):
    install_sudo(user)
    install_ssh(user)


def install_ssh(user):
    directory = Path(user.pw_dir) / '.ssh'
    if directory.is_symlink():
        raise ValueError('Configure the SSH include manually when ~/.ssh is a symlink')
    if not directory.exists():
        directory.mkdir(mode=0o700)
        os.chown(directory, user.pw_uid, user.pw_gid)
    config = directory / 'config'
    defaults = directory / 'minion.conf'
    if config.is_symlink() or defaults.is_symlink():
        raise ValueError('SSH config symlinks are retained; add the Minion include manually')
    original_defaults = defaults.read_text() if defaults.exists() else None
    text = config.read_text() if config.exists() else ''
    include = '    Include ~/.ssh/minion.conf'
    original = text if config.exists() else None
    if include not in text.splitlines():
        user_write(config, text.rstrip() + '\n\n# Minion defaults; personal host options above take precedence.\nHost *\n' + include + '\n', user)
    # Validate as the account, since a personal Match exec must never run as root.
    try:
        if original_defaults is None:
            user_write(defaults, (HERE / 'ssh-agent.conf').read_text(), user)
        else:
            # Remove only the formerly managed socket override, preserving edits.
            migrated = ''.join(line for line in original_defaults.splitlines(keepends=True)
                               if line.strip() != 'IdentityAgent /run/user/%i/minion-ssh-agent/socket')
            if migrated != original_defaults:
                user_write(defaults, migrated, user)
        subprocess.run(['ssh', '-G', '-F', str(config), 'minion-config-check.invalid'],
                       user=user.pw_uid, group=user.pw_gid, extra_groups=[],
                       env={'HOME': user.pw_dir, 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                       stdout=subprocess.DEVNULL, check=True)
    except BaseException:
        if original is None:
            config.unlink(missing_ok=True)
        else:
            user_write(config, original, user)
        if original_defaults is None:
            defaults.unlink(missing_ok=True)
        elif defaults.read_text() != original_defaults:
            user_write(defaults, original_defaults, user)
        raise
    dropin = UNITS / 'ssh-agent.service.d/60-minion-session.conf'
    dropin.parent.mkdir(parents=True, exist_ok=True)
    dropin.write_text((HERE / 'ssh-agent-session.conf').read_text())
    dropin.chmod(0o644)
    for directory in (UNITS, LEGACY_UNITS):
        (directory / 'minion-ssh-agent.service').unlink(missing_ok=True)
