"""Install pass integration without creating keys or opening a password store."""
import argparse
import os
from pathlib import Path
import pwd
import tempfile

HERE = Path(__file__).resolve().parent


def install(user):
    directory = Path(user.pw_dir) / '.gnupg'
    target = directory / 'gpg-agent.conf'
    if directory.is_symlink() or target.is_symlink():
        raise ValueError('Configure GPG defaults manually when its directory/config is a symlink')
    if not directory.exists():
        directory.mkdir(mode=0o700)
        os.chown(directory, user.pw_uid, user.pw_gid)
    # Existing GPG settings and all keys/stores belong to the user.
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write((HERE / 'gpg-agent.conf').read_bytes())
                stream.flush()
                os.fchmod(stream.fileno(), 0o600)
                os.fchown(stream.fileno(), user.pw_uid, user.pw_gid)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    args = parser.parse_args()
    user = pwd.getpwnam(args.username)
    if os.geteuid() != 0:
        raise SystemExit('Run as root to install the integration')
    if user.pw_uid < 1000 or not Path(user.pw_dir).is_dir():
        raise SystemExit('Select an existing regular desktop account')
    install(user)


if __name__ == '__main__':
    main()
