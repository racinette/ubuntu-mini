#!/usr/bin/env python3
"""Supply missing WIN Mini motion-sensor firmware from pinned linux-firmware."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
FILENAME = 'bmi260-init-data.fw'


def manifest():
    data = json.loads((HERE / 'firmware.json').read_text())
    if (data['source'] != 'https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware'
            or len(data['revision']) != 40
            or any(c not in '0123456789abcdef' for c in data['revision'])
            or set(data['files']) != {FILENAME, 'LICENSE.bmi260'}):
        raise ValueError('Invalid sensor firmware manifest')
    for item in data['files'].values():
        if (not isinstance(item['size'], int) or not 0 < item['size'] <= 16384
                or len(item['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in item['sha256'])):
            raise ValueError('Invalid sensor firmware checksum/size')
    return data


def needed(root=Path('/')):
    try:
        model = tuple((root / 'sys/class/dmi/id' / name).read_text().strip()
                      for name in ('sys_vendor', 'product_name'))
    except OSError:
        return False
    if model != ('GPD', 'G1617-01'):
        return False
    # Retain packaged firmware, including compressed files. Avoid an updates/
    # override so a future linux-firmware package can replace our fallback.
    return not any((root / directory / (FILENAME + suffix)).exists()
                   for directory in ('usr/lib/firmware', 'lib/firmware',
                                     'usr/lib/firmware/updates', 'lib/firmware/updates')
                   for suffix in ('', '.xz', '.zst'))


def install(root=Path('/'), asset_dir=None):
    data = manifest()
    if not needed(root):
        return False
    verified = {}
    for name, item in data['files'].items():
        if asset_dir is None:
            url = f"{data['source']}/+/{data['revision']}/{name}?format=TEXT"
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = base64.b64decode(response.read(32769), validate=True)
        else:
            payload = (asset_dir / name).read_bytes()
        if len(payload) != item['size'] or hashlib.sha256(payload).hexdigest() != item['sha256']:
            raise ValueError('Sensor firmware checksum/size mismatch: ' + name)
        verified[name] = payload
    # Validate both files before writing either; place the license first.
    for name, directory in (('LICENSE.bmi260', 'usr/share/doc/minion-firmware'),
                            (FILENAME, 'usr/lib/firmware')):
        target = root / directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.' + name,
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(verified[name])
                stream.flush()
                os.fchmod(stream.fileno(), 0o644)
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate manifest and report need without downloads or writes')
    parser.add_argument('--asset-dir', type=Path, help='Optional local directory containing the pinned firmware and license')
    args = parser.parse_args()
    manifest()
    if args.check:
        print('WIN Mini sensor firmware: ' + ('fallback needed' if needed() else 'no fallback needed'))
        return
    if os.geteuid() != 0:
        raise SystemExit('Run as root in the installed target')
    if install(asset_dir=args.asset_dir):
        print('Installed verified WIN Mini BMI260 firmware and license; driver loads on next boot/probe.')
    else:
        print('Sensor firmware retained, or target is not a WIN Mini 2023.')


if __name__ == '__main__':
    main()
