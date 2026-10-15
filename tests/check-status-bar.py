#!/usr/bin/env python3
"""Check bar state changes and failure handling without accessing host services."""
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import shutil
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
        assert status.batteries(supplies)[0]['instance'] == 'BAT0'
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

        hwmon = root / 'hwmon'; hwmon.mkdir()
        def sensor(name, driver, **values):
            directory = hwmon / name; directory.mkdir(exist_ok=True)
            (directory / 'name').write_text(driver)
            for key, value in values.items():
                (directory / key).write_text(str(value))
            return directory
        assert not status.temperatures(hwmon, supplies)[0]
        cpu = sensor('hwmon0', 'k10temp', temp1_label='Tctl', temp1_input=67000,
                     temp2_label='Tdie', temp2_input=65000, temp3_label='Tccd1', temp3_input=69000)
        sensor('hwmon1', 'amdgpu', temp1_label='edge', temp1_input=58000,
               temp2_label='junction', temp2_input=71000)
        ssd = sensor('hwmon2', 'nvme', temp1_label='Composite', temp1_input=40500,
                     temp2_label='Sensor 1', temp2_input=43000)
        sensor('hwmon3', 'acpitz', temp1_input=44000)
        sensor('hwmon4', 'nvme', temp1_label='Composite', temp1_input=39000)
        # The same physical file must not appear twice through class symlinks.
        (hwmon / 'hwmon9').symlink_to(cpu, target_is_directory=True)
        supply('BAT0', temp=315)
        supply('mouse', temp=400)
        thermal, detail = status.temperatures(hwmon, supplies)
        assert thermal[0]['full_text'] == 'CPU65° GPU58° SSD40° Bat32°'
        assert thermal[0]['short_text'] == 'CPU65°'
        assert detail.count('/ Tdie:') == 1 and '/ Tctl: 67.0 °C' in detail
        assert '/ junction: 71.0 °C' in detail and '/ Sensor 1: 43.0 °C' in detail
        assert 'acpitz' in detail and 'BAT0 / battery: 31.5 °C' in detail and 'mouse' not in detail
        (cpu / 'temp2_input').unlink()
        assert status.temperatures(hwmon, supplies)[0][0]['full_text'].startswith('Ctl67°')
        (cpu / 'temp2_input').write_text('65000')
        for value in ('garbage', 'NaN', '2147483647', '-273150', '151000'):
            (cpu / 'temp2_input').write_text(value)
            assert '/ Tdie:' not in status.temperatures(hwmon, supplies)[1]
        (cpu / 'temp2_input').write_text('65000')
        (cpu / 'temp2_fault').write_text('1')
        assert '/ Tdie:' not in status.temperatures(hwmon, supplies)[1]
        (cpu / 'temp2_fault').unlink()
        (cpu / 'temp2_enable').write_text('0')
        assert '/ Tdie:' not in status.temperatures(hwmon, supplies)[1]
        (cpu / 'temp2_enable').unlink()
        unknown = root / 'unknown'; unknown.mkdir()
        (unknown / 'hwmon0').mkdir()
        (unknown / 'hwmon0/temp1_input').write_text('-5000')
        assert status.temperatures(unknown, root / 'missing')[0][0]['full_text'] == 'Temp-5°'

        automatic = {'hhd': {'settings': {'tdp_enable': False}}}
        manual = {'hhd': {'settings': {'tdp_enable': True, 'tdp_ready': True}},
                  'tdp': {'smu': {'std': {'skin_limit': 18}}, 'qam': {'tdp': 15}}}
        for state, expected in ((automatic, 'Auto'), (manual, 'Limit 18W'), (None, 'Power ?'),
                                ({}, 'Power ?'), ([], 'Power ?'),
                                ({'hhd': {'settings': {'tdp_enable': True, 'tdp_ready': False}}}, 'Power ?')):
            with patch.object(status, 'hhd_state', return_value=state):
                assert status.power()[0]['full_text'] == expected
        with patch.object(status, 'hhd_state', return_value=manual):
            assert 'not measured' in status.power()[1]
        for value in (True, '18', -1, float('inf'), float('nan'), 9999, 10**400):
            invalid = {'hhd': manual['hhd'], 'tdp': {'smu': {'std': {'skin_limit': value}}}}
            with patch.object(status, 'hhd_state', return_value=invalid):
                assert status.power()[0]['full_text'] == 'Limit ?'
        token = root / 'token'; token.write_text('private123')
        with patch.object(status.http.client, 'HTTPConnection') as client:
            connection = client.return_value
            response = connection.getresponse.return_value
            response.status = 200
            response.read.return_value = json.dumps(manual).encode()
            assert status.hhd_state(token) == manual
            client.assert_called_with('127.0.0.1', 5335, timeout=1)
            assert connection.request.call_args.args == ('GET', '/api/v1/state')
            assert connection.request.call_args.kwargs['headers']['Authorization'] == 'Bearer private123'
            for payload in (b'not json', b'[]', b'x' * (256 * 1024 + 1)):
                response.read.return_value = payload
                assert status.hhd_state(token) is None
            for code in (401, 302, 500):
                response.status = code
                assert status.hhd_state(token) is None
            connection.getresponse.side_effect = TimeoutError
            assert status.hhd_state(token) is None
            assert connection.close.called
        with patch.object(status.http.client, 'HTTPConnection') as client:
            assert status.hhd_state(root / 'no-token') is None
            client.assert_not_called()

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
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"wifi","button":3}\n')), \
                patch.object(status, 'run') as run:
            status.clicks({'wifi': '<Guest> & friends'})
            assert run.call_args.args[-3:] == ('--', 'Wi-Fi', '&lt;Guest&gt; &amp; friends')
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"wifi","button":1}\n')), \
                patch.object(status.subprocess, 'Popen') as launch:
            status.clicks({})
            assert launch.call_args.args == (['nm-connection-editor'],)
            assert launch.call_args.kwargs['start_new_session'] is True
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"proxy","button":1}\n')), \
                patch.object(status.subprocess, 'Popen') as launch:
            status.clicks({})
            assert launch.call_args.args == (['minion-proxy-ui'],)
            assert launch.call_args.kwargs['start_new_session'] is True
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"battery","instance":"BAT0","button":1}\n')), \
                patch.object(status.subprocess, 'Popen') as launch, \
                patch.object(status, 'run', return_value='[{"success":true}]') as run:
            status.clicks({})
            assert launch.call_args.args == (['gnome-power-statistics',
                '--device=/org/freedesktop/UPower/devices/battery_BAT0'],)
            assert launch.call_args.kwargs['start_new_session'] is True
            assert run.call_args.args == ('swaymsg', '-r',
                '[app_id="^(gnome-power-statistics|org.gnome.PowerStats)$"] focus')
        with patch.object(status.subprocess, 'Popen') as launch, \
                patch.object(status, 'run', return_value='[{"success":true}]'):
            status.launch_battery_statistics('bad/path; command')
            assert launch.call_args.args == (['gnome-power-statistics'],)
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"battery","button":3}\n')), \
                patch.object(status.subprocess, 'Popen') as launch:
            status.clicks({})
            launch.assert_not_called()
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"temperatures","button":1}\n')), \
                patch.object(status, 'run') as run:
            status.clicks({'temperatures': 'CPU <die>: 65 °C\nSSD: 40 °C'})
            assert run.call_args.args[-2:] == ('Temperatures', 'CPU &lt;die&gt;: 65 °C\nSSD: 40 °C')
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"power","button":1}\n')), \
                patch.object(status.subprocess, 'Popen') as launch:
            status.clicks({})
            assert launch.call_args.args == (['minion-hhd-ui'],)
            assert launch.call_args.kwargs['start_new_session'] is True

        # Run the actual streaming entry point with isolated CLI providers.
        binary = root / 'bin'; binary.mkdir()
        fixture = root / 'state.json'
        data = {'nmcli': '*:67:Cafe: "Guest"', 'wpctl': 'Volume: 0.42',
                'systemctl': 'LoadState=loaded\nActiveState=active',
                'swaymsg': json.dumps([virtual, physical]), 'hhd': automatic}
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
        for name in ('nmcli', 'wpctl', 'systemctl', 'swaymsg'):
            path = binary / name; path.write_text(provider); path.chmod(0o755)
        runtime = root / 'runtime'; (runtime / 'minion-gamepad').mkdir(parents=True)
        mode = runtime / 'minion-gamepad/stick-mode'; mode.write_text('L:Scroll R:Windows\n')
        awake = runtime / 'minion-idle/keep-awake'
        awake.parent.mkdir()
        with patch.dict(os.environ, XDG_RUNTIME_DIR=str(runtime)):
            for left in ('Scroll', 'Text'):
                for right in ('Windows', 'Resize'):
                    label = f'L:{left} R:{right}'
                    mode.write_text(label + '\n')
                    assert status.stick_mode()['full_text'] == label
            mode.write_text('unknown\n')
            assert status.stick_mode()['full_text'] == 'L:Scroll R:Windows'
            mode.write_text('L:Scroll R:Windows\n')
            assert status.awake_mode()['full_text'] == 'Awake OFF'
            awake.write_text('1\n')
            assert status.awake_mode()['full_text'] == 'Awake ON'
            assert status.awake_mode()['color'] == '#9ece6a'
            awake.write_text('0\n')
            voice = runtime / 'voxtype/state'
            voice.parent.mkdir()
            assert status.voice_mode()['full_text'] == 'Mic OFF'
            for state, label in [('idle', 'Mic'), ('recording', 'Mic REC'),
                                 ('transcribing', 'Mic …'), ('outputting', 'Mic …'), ('bad', 'Mic OFF')]:
                voice.write_text(state)
                assert status.voice_mode()['full_text'] == label
            voice.write_text('recording')
            assert status.voice_mode()['color'] == '#f7768e'
            voice.write_text('idle')
        for button, action in [(1, 'toggle'), (3, 'cancel')]:
            with patch.object(status.sys, 'stdin', io.StringIO(json.dumps({'name': 'voice', 'button': button}) + '\n')), \
                    patch.object(status.subprocess, 'Popen') as launch:
                status.clicks({})
                assert launch.call_args.args[0] == ['minion-voice', action]
        with patch.object(status.sys, 'stdin', io.StringIO('[\n{"name":"awake","button":1}\n')), \
                patch.object(status, 'run') as run:
            status.clicks({})
            run.assert_called_once_with('minion-idle-controls', 'toggle-awake')
        # Isolate filesystem and API providers too: never query host hardware/HHD.
        entry = '''import json,runpy,sys
from pathlib import Path
module=runpy.run_path(sys.argv[1])
main=module['main']; scope=main.__globals__
thermal=scope['temperatures']; battery=scope['batteries']
scope['temperatures']=lambda:thermal(Path(sys.argv[2]),Path(sys.argv[3]))
scope['batteries']=lambda:battery(Path(sys.argv[3]))
scope['hhd_state']=lambda:json.loads(Path(sys.argv[4]).read_text()).get('hhd')
main()
'''
        process = subprocess.Popen([sys.executable, '-c', entry, str(SOURCE), str(hwmon), str(supplies), str(fixture)], stdin=subprocess.PIPE,
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
                        'layout': 'RU', 'stick': 'L:Scroll R:Windows', 'power': 'Auto', 'awake': 'Awake OFF',
                        'temperatures': 'CPU65° GPU58° SSD40° Bat32°'}
            deadline = time.monotonic() + 8
            while True:
                first = frame()
                if all(first.get(name) == value for name, value in expected.items()):
                    break
                # Cold interpreter startup in fake providers can exceed the CLI timeout.
                assert time.monotonic() < deadline, first
            data.update(nmcli='', wpctl='Volume: 0.42 [MUTED]', systemctl='LoadState=loaded\nActiveState=failed',
                        swaymsg=json.dumps([dict(physical, xkb_active_layout_name='English (US)')]), hhd=manual)
            (cpu / 'temp2_input').write_text('72000')
            (ssd / 'temp1_input').write_text('48000')
            mode.write_text('L:Text R:Resize\n'); awake.write_text('1\n'); save()
            deadline = time.monotonic() + 9
            while True:
                current = frame()
                if current['proxy'] == 'Proxy FAIL':
                    break
                assert time.monotonic() < deadline, 'Slow indicators did not refresh'
            assert (current['wifi'], current['audio'], current['layout'], current['stick']) == (
                'Wi-Fi disconnected', 'Muted', 'US', 'L:Text R:Resize')
            assert current['power'] == 'Limit 18W'
            assert current['awake'] == 'Awake ON'
            assert current['temperatures'] == 'CPU72° GPU58° SSD48° Bat32°'
            data.update(wpctl='TIMEOUT', swaymsg=None); save()
            deadline = time.monotonic() + 5
            while True:
                current = frame()
                if current['audio'] == 'Vol ?' and 'layout' not in current:
                    break
                assert time.monotonic() < deadline, 'Unavailable providers froze status'
            data['hhd'] = None; save()
            shutil.rmtree(hwmon)
            (supplies / 'BAT0/temp').unlink()
            deadline = time.monotonic() + 9
            while True:
                current = frame()
                if current['power'] == 'Power ?' and 'temperatures' not in current:
                    break
                assert time.monotonic() < deadline, 'Lost power/sensor providers froze status'
            hwmon.mkdir()
            sensor('hwmon8', 'k10temp', temp1_label='Tctl', temp1_input=61000)
            data['hhd'] = automatic; save()
            deadline = time.monotonic() + 9
            while True:
                current = frame()
                if current.get('temperatures') == 'Ctl61°' and current['power'] == 'Auto':
                    break
                assert time.monotonic() < deadline, 'Reconnected providers did not recover'
        finally:
            process.terminate()
            process.wait(timeout=4)
            errors = process.stderr.read().decode()
            assert not errors, errors
    print('Passed: battery/network/audio/proxy/layout, read-only HHD targets/auth/failures, temperature channels/units/filtering/hotplug, safe clicks and live JSON updates.')


if __name__ == '__main__':
    main()
