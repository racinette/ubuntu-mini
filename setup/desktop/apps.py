#!/usr/bin/env python3
"""Install additional desktop apps from their stable Snap channels."""
import os
import shutil
import subprocess


def install():
    if os.geteuid() != 0:
        raise SystemExit('Run as root inside the installed target')
    # Keep an existing native app or its selected Snap revision/channel.
    for app in ('telegram-desktop', 'gimp'):
        if shutil.which(app) or subprocess.run(['snap', 'list', app], capture_output=True).returncode == 0:
            print(f'Retaining installed {app}', flush=True)
            continue
        subprocess.run(['snap', 'install', app, '--channel=latest/stable'], check=True)


if __name__ == '__main__':
    install()
