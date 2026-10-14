#!/usr/bin/env python3
"""Test swap retention, allocation, rollback and reruns using isolated files."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'setup/base/swap.py'
spec = importlib.util.spec_from_file_location('swap_setup', SOURCE)
swap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(swap)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        swap.SWAP = root / 'swapfile'
        swap.FSTAB = root / 'fstab'
        swap.PROC_SWAPS = root / 'proc-swaps'
        swap.MEMINFO = root / 'meminfo'
        swap.ENTRY = f'{swap.SWAP} none swap sw,nofail 0 0\n'
        original = '# Personal fstab\n/dev/root / ext4 defaults 0 1\n'
        swap.FSTAB.write_text(original)
        swap.PROC_SWAPS.write_text('Filename Type Size Used Priority\n')
        swap.MEMINFO.write_text('MemTotal: 24000000 kB\n')
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command[0] == 'dd':
                assert swap.SWAP.stat().st_mode & 0o777 == 0o600
                kwargs['stdout'].write(b'isolated allocation fixture')
            if command[0] == 'swapon':
                swap.PROC_SWAPS.write_text(f'Filename Type Size Used Priority\n{swap.SWAP} file 8192 0 -2\n')
            return SimpleNamespace(returncode=0)

        with patch.object(swap.subprocess, 'check_output', return_value='ext4\n'), \
             patch.object(swap.shutil, 'disk_usage', return_value=SimpleNamespace(free=20 * 1024**3)), \
             patch.object(swap.subprocess, 'run', side_effect=run):
            assert swap.plan()[0] == 8192
            assert swap.install()
            assert [c[0] for c in calls] == ['dd', 'mkswap', 'systemctl', 'swapon']
            assert 'count=8192' in calls[0]
            assert swap.FSTAB.read_text().startswith(original.rstrip())
            assert swap.FSTAB.read_text().count(swap.ENTRY) == 1
            before = swap.SWAP.read_bytes(), swap.FSTAB.read_bytes()
            calls.clear()
            assert not swap.install()
            assert not calls
            assert before == (swap.SWAP.read_bytes(), swap.FSTAB.read_bytes())
            swap.PROC_SWAPS.write_text('Filename Type Size Used Priority\n')
            assert not swap.install()
            assert calls == [['swapon', str(swap.SWAP)]]
            swap.FSTAB.write_text(original + f'{swap.SWAP} none swap noauto 0 0\n')
            calls.clear()
            assert not swap.install() and not calls
            swap.FSTAB.write_text(original + '/custom-swap none swap defaults 0 0\n')
            assert swap.plan()[0] is None
            swap.FSTAB.write_text(original)
            swap.SWAP.unlink()
            swap.PROC_SWAPS.write_text('Filename Type Size Used Priority\n/dev/zram0 partition 8192 0 100\n')
            assert swap.plan()[0] is None
            swap.PROC_SWAPS.write_text('Filename Type Size Used Priority\n')
            for failing in ('dd', 'mkswap', 'swapon'):
                def fail(command, **kwargs):
                    if command[0] == failing:
                        raise subprocess.CalledProcessError(1, command)
                    return run(command, **kwargs)
                with patch.object(swap.subprocess, 'run', side_effect=fail):
                    try:
                        swap.install()
                    except subprocess.CalledProcessError:
                        pass
                    else:
                        raise AssertionError('Expected failure')
                assert not swap.SWAP.exists()
                assert swap.FSTAB.read_text() == original
            with patch.object(swap.subprocess, 'check_output', return_value='btrfs\n'):
                assert swap.plan()[0] is None
            with patch.object(swap.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**3)):
                assert swap.plan()[0] is None
            swap.SWAP.symlink_to(root / 'missing')
            try:
                swap.plan()
            except ValueError:
                pass
            else:
                raise AssertionError('Existing symlink accepted')
    print('Passed: swap retention, private allocation, fstab preservation, boot entry, reruns and failure rollback.')


if __name__ == '__main__':
    main()
