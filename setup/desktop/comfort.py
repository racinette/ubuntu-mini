"""Seed clock and night-light defaults, retaining personal configuration."""
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def install(user):
    # Ubuntu Server commonly starts in UTC. Retain any already chosen local zone.
    zone = subprocess.check_output(['timedatectl', 'show', '-p', 'Timezone', '--value'],
                                   text=True).strip()
    if zone in ('Etc/UTC', 'UTC'):
        subprocess.run(['timedatectl', 'set-timezone', 'Europe/Minsk'], check=True)
    subprocess.run(['timedatectl', 'set-ntp', 'true'], check=True)
    config = Path(user.pw_dir) / '.config/gammastep/config.ini'
    if not config.exists():
        missing = [parent for parent in config.parents if not parent.exists()]
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text((HERE / 'gammastep.conf').read_text())
        config.chmod(0o600)
        for path in [config, *missing]:
            os.chown(path, user.pw_uid, user.pw_gid)
