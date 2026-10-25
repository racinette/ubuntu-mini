#!/usr/bin/env python3
"""Verify controller installation preserves personal DAW/MIDI configuration."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('realearn', PROJECT / 'setup/development/realearn.py')
realearn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(realearn)

with tempfile.TemporaryDirectory(prefix='realearn-install-check-') as temporary:
    root = Path(temporary)
    resource = root / 'REAPER'
    resource.mkdir()
    assets = root / 'assets'
    assets.mkdir()
    content = b'fixture plugin'
    release = dict(version='2.18.4', assets=[dict(file='FX/helgobox-x64.so', filename='plugin.so',
                   sha256=hashlib.sha256(content).hexdigest(), url='https://example.invalid/plugin')])
    (assets / 'plugin.so').write_bytes(content)
    ini = resource / 'reaper.ini'
    ini.write_text('[reaper]\nlinux_audio_mode=3\nlastproject=/personal/song.rpp\nmidiins=1\nmidiins_cs=1\nmidiins_all=1\n')
    devices = resource / 'reaper-midihw-alsa.ini'
    devices.write_text('[mididevcache]\nit0=2\nin0=Personal USB interface\n')
    keys = resource / 'reaper-kb.ini'
    keys.write_text('KEY 1 83 40757 0\n')
    with patch.object(realearn.os, 'geteuid', return_value=1000), \
         patch.object(realearn, 'reaper_running', return_value=False), \
         patch.object(realearn, 'RELEASE', release), \
         contextlib.redirect_stdout(io.StringIO()):
        realearn.install(resource, assets)
        assert 'lastproject=/personal/song.rpp' in ini.read_text()
        assert 'linux_audio_mode=3' in ini.read_text()
        assert 'midiins=3' in ini.read_text() and 'midiins_all=1' in ini.read_text()
        assert 'in0=Personal USB interface' in devices.read_text() and 'in1=virtual' in devices.read_text()
        assert keys.read_text().startswith('KEY 1 83 40757 0\n')
        assert keys.read_text().count(realearn.ACTION_ID) == 1
        state = json.loads((resource / 'Data/device-gamepad.json').read_text())
        assert (resource / 'Scripts/Device/reaper-control-outline.py').read_bytes() == (PROJECT / 'setup/development/reaper-control-outline.py').read_bytes()
        assert (resource / 'Scripts/Device/reaper-control-navigation.lua').read_bytes() == (PROJECT / 'setup/development/reaper-control-navigation.lua').read_bytes()
        for name in ('reaper-ui.lua', 'reaper-ui.py','reaper-transport.lua'):
            assert (resource / 'Scripts/Device' / name).read_bytes() == (PROJECT / 'setup/development' / name).read_bytes()
        assert state['mainUnit']['controlDeviceId'] == '1'
        chain = resource / 'reaper-hwoutfx.ini'
        before = chain.read_bytes()
        # Save a personally customized controller and ensure a setup rerun does
        # not reset its mappings or parameters.
        chain.write_bytes(before + b'// personal controller customization\n')
        realearn.install(resource, assets)
        assert chain.read_bytes() == before + b'// personal controller customization\n'
        assert keys.read_text().count(realearn.ACTION_ID) == 1
        chain.write_text('Personal monitoring chain\n')
        before = {p: p.read_bytes() for p in (ini, keys, devices, chain)}
        try:
            realearn.install(resource, assets)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Foreign monitoring chain replaced')
        assert before == {p: p.read_bytes() for p in before}
        # A JACK resource must not retain the ALSA-only virtual-device cache
        # entry, and reruns must keep its reserved input index stable.
        chain.write_text(realearn.monitoring_fx(state))
        ini.write_text(ini.read_text().replace('linux_audio_mode=3','linux_audio_mode=0'))
        realearn.install(resource, assets)
        assert 'in1=virtual' not in devices.read_text()
        assert 'in0=Personal USB interface' in devices.read_text()
        assert 'in1=MIDI Input 2' in (resource/'reaper-midihw-linux.ini').read_text()
        realearn.install(resource, assets)
        assert json.loads((resource/'Data/device-gamepad.json').read_text())['mainUnit']['controlDeviceId']=='1'
        assert 'linux_audio_mode=0' in ini.read_text()
        # Reproduce the installed resource: an owned input at slot zero that
        # JACK's existing cache reports as unavailable, plus unrelated devices.
        state['mainUnit']['controlDeviceId'] = '0'
        state['mainUnit']['name'] = 'Personally customized controller'
        chain.write_text(realearn.monitoring_fx(state) + '// customization\n')
        (resource/'Data/device-gamepad.json').write_text(json.dumps(state))
        ini.write_text('[reaper]\nlinux_audio_mode=0\nmidiins=1\nmidiins_cs=1\nmidiins_all=0\n')
        (resource/'reaper-midihw-linux.ini').write_text('[mididevcache]\nit0=1\nin0=MIDI Input 1\nit1=1\nin1=MIDI Input 2\nit64=1\nin64=Personal interface\n')
        realearn.install(resource, assets)
        assert 'midiins=2\n' in ini.read_text()
        assert 'in64=Personal interface' in (resource/'reaper-midihw-linux.ini').read_text()
        assert chain.read_text().endswith('// customization\n')
        expected = realearn.retarget_controller(realearn.monitoring_fx(state), 1)
        assert chain.read_text() == expected + '// customization\n'
        chain.write_text(chain.read_text().replace('BYPASS 0 0 0', 'BYPASS 1 0 0'))
        realearn.install(resource, assets)
        assert chain.read_text() == expected + '// customization\n'
        realearn.install(resource, assets, update_controller=True)
        assert chain.read_text().endswith('// customization\n')
        assert 'Personally customized controller' not in chain.read_text()
        assert realearn.retarget_controller(realearn.monitoring_fx(realearn.preset()), 1) + '// customization\n' == chain.read_text()
        chain.unlink()
        (assets / 'plugin.so').write_bytes(b'corrupted')
        try:
            realearn.install(resource, assets)
        except ValueError:
            pass
        else:
            raise AssertionError('Corrupted plugin accepted')
        with patch.object(realearn, 'reaper_running', return_value=True):
            try:
                realearn.install(resource, assets)
            except RuntimeError as error:
                assert 'close REAPER' in str(error)
            else:
                raise AssertionError('Running REAPER configuration rewritten')

state = realearn.preset()
mappings=state['mainUnit']['mappings']
hold=next(m for m in mappings if m['name']=='Hold area chooser')
assert hold['source']['number']==26 and hold['mode']=={} and hold['target']['paramIndex']==12
cancel=next(m for m in mappings if m['name']=='Cancel held area chooser')
assert cancel['source']['number']==31 and cancel['mode']['minTargetValue']==.5
assert state['mainUnit']['parameters']['12']['valueLabels']==['Released','Cancelled','Held']
assert state['mainUnit']['parameters']['14']['valueCount']==65536
assert not any(int(m['target'].get('commandName','0'))>=60000 for m in mappings if m['target']['type']==0 and m['target'].get('commandName','0').isdecimal())
assert {m['source']['number'] for m in mappings if m['name']=='Previous / next REAPER window'}=={48,49}
assert state['mainUnit']['parameters']['3']['valueCount']==29
assert state['mainUnit']['parameters']['15']['valueCount']==2
assert {m['source']['number'] for m in mappings if m['name']=='Navigate held area chooser'}=={27,28,29,30}
chain = realearn.monitoring_fx(state)
lines = chain.splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith('<VST '))
end = lines.index('>', start)
encoded = ''.join(line.strip() for line in lines[start + 2:end - 1])
assert json.loads(base64.b64decode(encoded)) == state
assert all(m['source'].get('channel', 15) == 15 for m in state['mainUnit']['mappings'])
assert not state['mainUnit'].get('wantsKeyboardInput')
assert all(m['target']['type'] != 57 for m in state['mainUnit']['mappings'])
print('Passed: ReaLearn checksums, native monitoring serialization, preserved DAW/keyboard/MIDI configuration, isolated controller input, reruns and running-instance refusal.')

# FX direction events request spatial traversal and never issue track actions.
fx_stick=[m for m in mappings if m['source'].get('number') in (4,5,6,7) and 'p[0] == 2' in m.get('eelCondition','')]
assert len(fx_stick)==4
for mapping in fx_stick:
    cc=mapping['source']['number']
    assert mapping['target']=={'type':63,'paramIndex':3}
    assert abs(mapping['mode']['minTargetValue']-(11+cc-4)/28)<.000001
    assert 'p[9] == 0' in mapping['eelCondition'] and 'p[6] == 0' in mapping['eelCondition']
fx_knob=next(m for m in mappings if m['name']=='Set FX knob position')
assert 'p[15] == 1' in fx_knob['eelCondition']
print('Passed: window bumpers, window-local FX spatial requests and numeric-control-only absolute knob gate.')
