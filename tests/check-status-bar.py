#!/usr/bin/env python3
"""Check bar state changes and failure handling without accessing host services."""
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / 'setup/desktop/minion-status'
loader = importlib.machinery.SourceFileLoader('status', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
status = importlib.util.module_from_spec(spec)
loader.exec_module(status)


def main():
    with tempfile.TemporaryDirectory(prefix='minion-status-test-') as temporary:
        root = Path(temporary)
        supplies = root / 'supplies'; supplies.mkdir()
        assert not status.batteries(supplies)
        def supply(name, **values):
            directory = supplies / name; directory.mkdir(exist_ok=True)
            for key, value in values.items():
                (directory / key).write_text(str(value) + '\n')
        supply('AC', type='Mains')
        supply('mouse', type='Battery', scope='Device', capacity=90)
        supply('absent', type='Battery', present=0, capacity=0)
        assert not status.batteries(supplies)
        supply('BAT0', type='Battery', present=1, capacity=73, status='Charging')
        assert status.batteries(supplies)[0]['full_text'] == '73% ↑'
        for value, expected in [('Discharging', '73% ↓'), ('Full', '73% Full'),
                                ('Not charging', '73% Idle'), ('invalid', '73% ?')]:
            supply('BAT0', status=value)
            assert status.batteries(supplies)[0]['full_text'] == expected
        for capacity in ('', '-1', '101', 'NaN', '99999999999999999999'):
            supply('BAT0', capacity=capacity)
            assert not status.batteries(supplies)
        supply('BAT0', capacity=0)
        supply('BAT1', type='Battery', capacity=100, status='Full')
        assert len(status.batteries(supplies)) == 2

        for output, expected in [('Volume: 0.42', 'Vol 42%'), ('Volume: 0.42 [MUTED]', 'Muted'),
                                 ('Volume: 1.20', 'Vol 120%'), ('Volume: 0.00', 'Vol 0%'),
                                 (None, 'Vol ?'), ('invalid', 'Vol ?')]:
            with patch.object(status, 'run', return_value=output):
                assert status.audio()['full_text'] == expected
        for state, expected in [('active', 'ON'), ('inactive', 'OFF'), ('failed', 'FAIL'),
                                ('activating', 'START'), ('deactivating', 'STOP')]:
            with patch.object(status, 'run', return_value=f'ActiveState={state}\nLoadState=loaded'):
                assert status.proxy()['full_text'] == 'Proxy ' + expected
        with patch.object(status, 'run', return_value='LoadState=not-found\nActiveState=inactive'):
            assert status.proxy()['full_text'] == 'Proxy N/A'
        with patch.object(status, 'run', return_value=None):
            assert status.proxy()['full_text'] == 'Proxy ?'
        with patch.object(status, 'run', return_value=':90:Other\n*:67:Cafe: "Guest"') as run:
            network, detail = status.wifi()
            assert network['full_text'] == 'Wi-Fi 67%' and detail == 'Cafe: "Guest"'
            assert run.call_args.args[-2:] == ('--rescan', 'no')
        for output, expected in [('', 'Wi-Fi disconnected'), (None, 'Wi-Fi ?')]:
            with patch.object(status, 'run', return_value=output):
                assert status.wifi()[0]['full_text'] == expected
        physical = dict(type='keyboard', vendor=1, name='Built-in keyboard',
                        xkb_layout_names=['English (US)', 'Russian'], xkb_active_layout_name='Russian')
        virtual = dict(physical, vendor=0x1209, name='Minion gamepad keyboard', xkb_active_layout_name='English (US)')
        with patch.object(status, 'run', return_value=json.dumps([virtual, physical])):
            assert status.keyboard_layout()[0]['full_text'] == 'RU'
        with patch.object(status, 'run', return_value=json.dumps([virtual, dict(physical, vendor=0)])):
            assert status.keyboard_layout()[0]['full_text'] == 'RU'
        for output in ('invalid', '{}', 'null', json.dumps([dict(physical, xkb_layout_names=['Russian'])])):
            with patch.object(status, 'run', return_value=output):
                assert not status.keyboard_layout()
        with patch.object(status.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 1)):
            assert status.run('fixture') is None
        with patch.object(status.subprocess, 'run', side_effect=FileNotFoundError):
            assert status.run('fixture') is None
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"wifi","button":1}\n')), \
                patch.object(status, 'run') as run:
            status.clicks({'wifi': '<Guest> & friends'})
            assert run.call_args.args[-3:] == ('--', 'Wi-Fi', '&lt;Guest&gt; &amp; friends')

        # Run the actual streaming entry point with isolated CLI providers.
        binary = root / 'bin'; binary.mkdir()
        fixture = root / 'state.json'
        data = {'nmcli': '*:67:Cafe: "Guest"', 'wpctl': 'Volume: 0.42',
                'systemctl': 'LoadState=loaded\nActiveState=active',
                'swaymsg': json.dumps([virtual, physical])}
        def save():
            staged = fixture.with_suffix('.new')
            staged.write_text(json.dumps(data)); staged.replace(fixture)
        save()
        provider = '#!' + sys.executable + '''
import json,os,sys,time
from pathlib import Path
name=Path(sys.argv[0]).name
value=json.loads(Path(os.environ['MINION_STATUS_FIXTURE']).read_text()).get(name)
if value is None: sys.exit(1)
if value == 'TIMEOUT': time.sleep(3)
print(value)
'''
        for name in data:
            path = binary / name; path.write_text(provider); path.chmod(0o755)
        runtime = root / 'runtime'; (runtime / 'minion-gamepad').mkdir(parents=True)
        mode = runtime / 'minion-gamepad/right-stick-mode'; mode.write_text('select\n')
        process = subprocess.Popen([sys.executable, str(SOURCE)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                   env={**os.environ, 'PATH': str(binary),
                                        'MINION_STATUS_FIXTURE': str(fixture), 'XDG_RUNTIME_DIR': str(runtime)})
        buffer = bytearray()
        def line(timeout=4):
            deadline = time.monotonic() + timeout
            while b'\n' not in buffer:
                ready, _, _ = select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))
                assert ready, 'Status stream stalled'
                chunk = os.read(process.stdout.fileno(), 65536)
                assert chunk, 'Status stream exited early'
                buffer.extend(chunk)
            end = buffer.index(b'\n'); result = bytes(buffer[:end]); del buffer[:end+1]
            return result.decode()
        def frame():
            return {item['name']: item['full_text'] for item in json.loads(line().removesuffix(','))}
        try:
            assert json.loads(line()) == {'version': 1, 'click_events': True}
            assert line() == '['
            expected = {'wifi': 'Wi-Fi 67%', 'audio': 'Vol 42%', 'proxy': 'Proxy ON',
                        'layout': 'RU', 'stick': 'R: Select'}
            deadline = time.monotonic() + 8
            while True:
                first = frame()
                if all(first.get(name) == value for name, value in expected.items()):
                    break
                # Cold interpreter startup in fake providers can exceed the CLI timeout.
                assert time.monotonic() < deadline, first
            data.update(nmcli='', wpctl='Volume: 0.42 [MUTED]', systemctl='LoadState=loaded\nActiveState=failed',
                        swaymsg=json.dumps([dict(physical, xkb_active_layout_name='English (US)')]))
            mode.write_text('resize\n'); save()
            deadline = time.monotonic() + 9
            while True:
                current = frame()
                if current['proxy'] == 'Proxy FAIL':
                    break
                assert time.monotonic() < deadline, 'Slow indicators did not refresh'
            assert (current['wifi'], current['audio'], current['layout'], current['stick']) == (
                'Wi-Fi disconnected', 'Muted', 'US', 'R: Resize')
            data.update(wpctl='TIMEOUT', swaymsg=None); save()
            deadline = time.monotonic() + 5
            while True:
                current = frame()
                if current['audio'] == 'Vol ?' and 'layout' not in current:
                    break
                assert time.monotonic() < deadline, 'Unavailable providers froze status'
        finally:
            process.terminate()
            process.wait(timeout=4)
            errors = process.stderr.read().decode()
            assert not errors, errors
    print('Passed: battery filtering/states, Wi-Fi signal/details, mute/volume, proxy lifecycle, physical keyboard layout, safe clicks, live JSON updates and provider failure/timeout handling.')


if __name__ == '__main__':
    main()
