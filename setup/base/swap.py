#!/usr/bin/python3
"""Add persistent swap when the installation has no existing swap policy."""
import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

SWAP = Path('/var/lib/minion/swapfile')
FSTAB = Path('/etc/fstab')
PROC_SWAPS = Path('/proc/swaps')
MEMINFO = Path('/proc/meminfo')
MIB = 1024 ** 2
ENTRY = f'{SWAP} none swap sw,nofail 0 0\n'


def active_swaps():
    return [line.split()[0] for line in PROC_SWAPS.read_text().splitlines()[1:] if line.strip()]


def configured_swaps(text):
    return [parts[0] for line in text.splitlines()
            if not line.lstrip().startswith('#') and len(parts := line.split()) >= 3 and parts[2] == 'swap']


def plan():
    configured = configured_swaps(FSTAB.read_text())
    active = active_swaps()
    if any(source != str(SWAP) for source in configured + active):
        return None, 'Existing swap configuration retained.'
    if str(SWAP) in configured:
        for line in FSTAB.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == str(SWAP) and 'noauto' in parts[3].split(','):
                return None, 'Existing manually activated swap policy retained.'
        return 0, 'Existing Minion swap entry retained.'
    if SWAP.exists() or SWAP.is_symlink():
        raise ValueError(f'{SWAP} already exists without an fstab entry; inspect it before retrying.')
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', '/var/lib'], text=True).strip()
    if filesystem not in ('ext4', 'xfs'):
        return None, f'Automatic swapfile skipped on {filesystem}; configure filesystem-specific swap separately.'
    memory_kib = int(next(line.split()[1] for line in MEMINFO.read_text().splitlines()
                          if line.startswith('MemTotal:')))
    size_mib = min(8192, max(1024, memory_kib // 2048))
    if shutil.disk_usage('/var/lib').free < (size_mib + 2048) * MIB:
        return None, 'Automatic swapfile skipped: insufficient free space with 2 GiB reserved.'
    return size_mib, f'Create {size_mib} MiB swap at {SWAP}.'


def write_fstab(text):
    mode = stat.S_IMODE(FSTAB.stat().st_mode)
    with tempfile.NamedTemporaryFile(mode='w', dir=FSTAB.parent, prefix='.minion-fstab-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            temporary.chmod(mode)
            temporary.replace(FSTAB)
        finally:
            temporary.unlink(missing_ok=True)


def install():
    size, message = plan()
    print(message, flush=True)
    if size is None:
        return False
    if size == 0:
        if not SWAP.is_file() or SWAP.is_symlink():
            raise ValueError('Configured Minion swapfile is missing or is not a regular file')
        if stat.S_IMODE(SWAP.stat().st_mode) != 0o600:
            raise ValueError('Configured Minion swapfile must have private 0600 permissions')
        if str(SWAP) not in active_swaps():
            subprocess.run(['swapon', str(SWAP)], check=True)
        return False
    SWAP.parent.mkdir(parents=True, exist_ok=True)
    original = FSTAB.read_text()
    persisted = False
    # Exclusive creation and a private descriptor prevent overwriting another file.
    descriptor = os.open(SWAP, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            subprocess.run(['dd', 'if=/dev/zero', 'bs=1M', f'count={size}', 'conv=fsync', 'status=none'],
                           stdout=stream, check=True)
        subprocess.run(['mkswap', '-L', 'minion-swap', str(SWAP)], check=True)
        write_fstab(original.rstrip() + '\n\n# Minion memory-pressure fallback\n' + ENTRY)
        persisted = True
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['swapon', str(SWAP)], check=True)
    except BaseException:
        # Do not delete storage the kernel is already using, even on interruption.
        if str(SWAP) not in active_swaps():
            if persisted:
                write_fstab(original)
                subprocess.run(['systemctl', 'daemon-reload'], check=False)
            SWAP.unlink(missing_ok=True)
        raise
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Describe swap setup without changing anything')
    args = parser.parse_args()
    if args.check:
        print(plan()[1])
    else:
        if os.geteuid() != 0:
            raise SystemExit('Run with sudo to configure system swap')
        install()


if __name__ == '__main__':
    main()
