#!/usr/bin/env python3
"""Check firmware corruption refusal and retention without touching hardware."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sensor_firmware', Path(__file__).resolve().parents[1] / 'setup/desktop/firmware.py')
firmware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firmware)


def main():
    pinned = firmware.manifest()
    assert pinned['files'][firmware.FILENAME]['size'] == 8192
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        dmi = root / 'sys/class/dmi/id'
        assets = root / 'assets'
        assets.mkdir()
        payloads = {firmware.FILENAME: b'fixture firmware', 'LICENSE.bmi260': b'fixture license'}
        fixture = json.loads(json.dumps(pinned))
        for name, payload in payloads.items():
            (assets / name).write_bytes(payload)
            fixture['files'][name] = {'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        target = root / 'usr/lib/firmware' / firmware.FILENAME
        license_path = root / 'usr/share/doc/minion-firmware/LICENSE.bmi260'
        with patch.object(firmware, 'manifest', return_value=fixture), patch.object(firmware.urllib.request, 'urlopen', side_effect=AssertionError('Unexpected network')):
            assert not firmware.install(root, assets)
            dmi.mkdir(parents=True)
            (dmi / 'sys_vendor').write_text('Other')
            (dmi / 'product_name').write_text('G1617-01')
            assert not firmware.install(root, assets)
            (dmi / 'sys_vendor').write_text('GPD\n')
            assert firmware.needed(root)
            for name in payloads:
                (assets / name).write_bytes(b'corrupt')
                try:
                    firmware.install(root, assets)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Corrupt artifact accepted')
                assert not target.exists() and not license_path.exists()
                (assets / name).write_bytes(payloads[name])
            target.parent.mkdir(parents=True)
            for suffix in ('.xz', '.zst', ''):
                existing = target.with_name(target.name + suffix)
                existing.write_bytes(b'newer packaged firmware')
                assert not firmware.install(root)
                assert existing.read_bytes() == b'newer packaged firmware'
                existing.unlink()
            assert firmware.install(root, assets)
            assert target.read_bytes() == payloads[firmware.FILENAME]
            assert license_path.read_bytes() == payloads['LICENSE.bmi260']
            assert target.stat().st_mode & 0o777 == 0o644
            assert not firmware.install(root)
            assert not list(target.parent.glob('.*'))
            target.unlink()
        urls = []
        def download(url, timeout):
            urls.append(url)
            name = url.rsplit('/', 1)[1].split('?', 1)[0]
            return io.BytesIO(base64.b64encode(payloads[name]))
        with patch.object(firmware, 'manifest', return_value=fixture), patch.object(firmware.urllib.request, 'urlopen', side_effect=download):
            assert firmware.install(root)
        assert len(urls) == 2 and all('/+/' + pinned['revision'] + '/' in url for url in urls)
        assert target.read_bytes() == payloads[firmware.FILENAME]
    print('Passed: model guard, pinned downloads, corruption refusal, package retention and licensed installation.')


if __name__ == '__main__':
    main()
