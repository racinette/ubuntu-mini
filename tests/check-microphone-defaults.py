#!/usr/bin/env python3
"""Check first-login microphone defaults and retention without host changes."""
import configparser
import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace


PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_audio', PROJECT / 'setup/desktop/audio.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    home = root / 'home'
    home.mkdir()
    user = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid(), pw_gid=os.getgid())
    dmi = root / 'dmi'
    dmi.mkdir()
    target = home / '.local/state/wireplumber/default-routes'

    assert not audio.seed_microphone_level(user, dmi)
    (dmi / 'sys_vendor').write_text('Other vendor\n')
    (dmi / 'product_name').write_text('G1617-01\n')
    assert not audio.seed_microphone_level(user, dmi)
    (dmi / 'sys_vendor').write_text('GPD\n')
    (dmi / 'product_name').write_text('Other model\n')
    assert not audio.seed_microphone_level(user, dmi)
    assert not target.exists()
    (dmi / 'product_name').write_text('G1617-01\n')

    assert audio.seed_microphone_level(user, dmi)
    state = configparser.ConfigParser(interpolation=None, delimiters=('=',))
    state.optionxform = str
    state.read(target)
    values = state['default-routes']
    # Independently name the tested input route and check the cubic UI scale.
    key = 'alsa_card.pci-0000_63_00.6:input:analog-input-internal-mic:channelVolumes'
    assert set(values) == {key}
    linear = [float(x) for x in values[key].split(';') if x]
    assert len(linear) == 2 and all(abs(x**(1/3) - 0.10) < 1e-9 for x in linear)
    assert target.stat().st_mode & 0o777 == 0o600
    for path in (target, target.parent, target.parent.parent, home / '.local'):
        assert (path.stat().st_uid, path.stat().st_gid) == (user.pw_uid, user.pw_gid)
    seeded = target.read_bytes()
    assert not audio.seed_microphone_level(user, dmi)
    assert target.read_bytes() == seeded

    # Preserve the entire file when a saved volume exists, including a user's
    # choice of 100%, separate scalar volume, mute, balance and other devices.
    for volume in (key + '=1;1;', key + '=0.008;0.027;',
                   key.removesuffix('channelVolumes') + 'volume=0.5'):
        original = ('# personal audio preferences\n[default-routes]\n' + volume
                    + '\n' + key.removesuffix('channelVolumes') + 'mute=true\n'
                    + 'bluez_card.AA_BB:input:headset:channelVolumes=0.5;\n')
        target.write_text(original)
        assert not audio.seed_microphone_level(user, dmi)
        assert target.read_text() == original

    # Merge a new input into existing speaker/headset state without rewriting it.
    original = ('# comment\n[default-routes] # section comment\n'
                'alsa_card.pci-0000_63_00.6:output:analog-output-speaker:channelVolumes=0.064;0.064;\n'
                'bluez_card.AA_BB:input:headset:channelVolumes=0.5;\n'
                '[other-state]\nunchanged=100%')
    target.write_text(original)
    assert audio.seed_microphone_level(user, dmi)
    assert target.read_text().replace(key + '=0.001;0.001;\n', '') == original
    target.write_text('[other-state]\nunchanged=100%')
    assert audio.seed_microphone_level(user, dmi)
    assert target.read_text().startswith('[other-state]\nunchanged=100%\n[default-routes]\n')

print('Microphone defaults passed: target model/route, nominal gain, ownership, reruns and saved audio preferences.')
