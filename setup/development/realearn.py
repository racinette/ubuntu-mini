#!/usr/bin/python3
"""Install pinned ReaLearn and the device's native REAPER controller preset."""
import argparse
import base64
import configparser
import hashlib
import json
import os
import re
from pathlib import Path
import struct
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
RELEASE = json.loads((HERE / 'realearn-release.json').read_text())
ACTION_ID = 'RS' + hashlib.sha1(b'ubuntu-mini/reaper-gamepad.lua').hexdigest()
PLUGIN_NAME = 'VSTi: Helgobox - ReaLearn & Playtime (Helgoboss)'
REQUEST_COUNT = 15


def preset():
    """ReaLearn's documented, backward-compatible JSON state format."""
    mappings = []

    def add(name, cc, target, page=None, menu=False, mode=None, fine=None):
        entry = dict(id='device-' + str(len(mappings)), name=name,
                     source=dict(type=0, channel=15, number=cc),
                     mode=dict(buttonUsage='press-only', **(mode or {})),
                     target=target, feedbackIsEnabled=False)
        conditions = []
        if page is not None:
            conditions.append(f'p[0] == {page}')
        if menu is not None:
            conditions.append(f'p[6] == {int(menu)}')
        if fine is not None:
            conditions.append(f'p[5] == {int(fine)}')
        if conditions:
            entry.update(activationType='expression', eelCondition=' && '.join(conditions))
        mappings.append(entry)

    def action(name, cc, command, page=None, menu=False):
        add(name, cc, dict(type=0, commandName=str(command), invocationType=0), page, menu)

    def increment(name, cc, target, reverse=False, page=None, menu=False, step=.01, fine=None, wrap=False):
        add(name, cc, target, page, menu,
            dict(type=1, reverseIsEnabled=reverse, minStepSize=step, maxStepSize=step,
                 minStepFactor=1, maxStepFactor=1, rotateIsEnabled=wrap), fine)

    def parameter(index):
        return dict(type=63, paramIndex=index)

    def request(name, cc, value, page=None, menu=False):
        add(name, cc, parameter(3), page, menu,
            dict(minTargetValue=value / (REQUEST_COUNT - 1), maxTargetValue=value / (REQUEST_COUNT - 1)))

    def absolute(name, target, page):
        add(name, 20, target, page)
        mappings[-1]['source']['is14Bit'] = True
        mappings[-1]['mode'] = {} # Every value, including zero; never press-only.

    for page in range(3):
        value = ((page + 1) % 3) / 2
        add('Next control page', 12, parameter(0), page=page, menu=None,
            mode=dict(minTargetValue=value, maxTargetValue=value))
    request('Open/close actions', 13, 1, menu=None)
    request('Confirm action', 18, 2, menu=True)
    request('Cancel actions', 19, 5, menu=True)
    request('Select item at cursor', 18, 6, 0)
    request('Activate selected track control', 18, 8, 1)
    request('Open/close selected effect', 18, 4, 2)
    action('Stop', 19, 1016, 0)
    for page in (1, 2):
        add('Return to Arrange', 19, parameter(0), page, mode=dict(minTargetValue=0, maxTargetValue=0))
    action('Play / stop', 16, 40044, menu=None)
    action('Save project', 17, 40026, menu=None)
    # A held trigger selects fine adjustment; unlike action buttons this mapping
    # deliberately accepts both 127 and 0, including reset/release.
    add('Fine adjustment', 22, parameter(5), menu=None)
    mappings[-1]['mode'] = {}
    for cc, reverse in ((2, True), (3, False), (6, True), (7, False)):
        increment('Choose menu action', cc, parameter(4), reverse, menu=True)
    for cc, command in ((0, 40416), (1, 40417)):
        action('Select previous / next item', cc, command, 0)
    for cc, command in ((24, 40646), (25, 40647)):
        action('Move edit cursor by grid', cc, command, 0)
    for cc, command in ((2, 40286), (3, 40285),
                        (4, 40140), (5, 40141), (6, 40138), (7, 40139),
                        (8, 1011), (9, 1012), (10, 40111), (11, 40112)):
        action('Arrange navigation', cc, command, 0)
    request('Split selected items', 15, 3, 0)
    request('Loop time selection', 14, 4, 0)
    # Track controls follow the vertical TCP, with a visible control selector.
    for cc, command in ((2, 40286), (3, 40285)):
        action('Select mixer track', cc, command, 1)
    for cc, reverse in ((0, True), (1, False), (24, True), (25, False)):
        increment('Choose track control', cc, parameter(8), reverse, 1)
    for cc, direction in ((4, 'left'), (5, 'right'), (6, 'up'), (7, 'down')):
        request('Navigate track controls ' + direction, cc, 11 + cc - 4, 1)
    for cc, reverse in ((8, True), (9, False), (10, False), (11, True)):
        request('Set selected track switch', cc, 9 if reverse else 10, 1)
        mappings[-1]['eelCondition'] += ' && p[8] >= 2 && p[8] <= 5'
    for field, kind in ((0, 2), (1, 4)):
        absolute('Set selected knob position', dict(type=kind, trackGUID='selected'), 1)
        mappings[-1]['eelCondition'] += f' && p[8] == {field}'
    request('Mute track', 15, 3, 1)
    request('Solo track', 14, 4, 1)
    # FX: indices belong to this controller, so opening a plugin UI never
    # silently retargets the sticks. The display clamps indices to real objects.
    for cc, index, reverse in ((0, 2, True), (1, 2, False), (24, 2, True), (25, 2, False), (2, 1, True), (3, 1, False)):
        increment('Choose FX / parameter', cc, parameter(index), reverse, 2)
    for cc, command in ((4, 40286), (5, 40285), (6, 40286), (7, 40285)):
        action('Select FX track', cc, command, 2)
    target = dict(type=1, trackGUID='selected', fxAnchor='dynamic', fxExpression='p[1]',
                  paramType='dynamic', paramExpression='p[2]')
    absolute('Set FX knob position', target, 2)
    request('Bypass FX', 15, 3, 2)
    request('Show/hide FX window', 14, 4, 2)
    for cc, name, command in ((32, 'Copy items', 40698), (33, 'Paste', 40058),
                              (34, 'Undo', 40029), (35, 'Redo', 40030),
                              (36, 'Cut items', 40699), (37, 'Select track items', 40421),
                              (38, 'Zoom selected items', 41622), (39, 'Save', 40026),
                              (40, 'Insert track', 40001), (41, 'Arm tracks', 9),
                              (42, 'Previous marker', 40172), (43, 'Next marker', 40173),
                              (44, 'Record', 1013), (46, 'Duplicate items', 41295),
                              (47, 'Delete items', 40006)):
        action(name, cc, command, menu=None)
    request('Toggle input monitoring', 45, 7, menu=None)
    mappings.append(dict(id='device-display', name='Start control display',
                         source=dict(category='reaper', reaperSourceType='timer', timerMillis=1000),
                         mode={}, target=dict(type=0, commandName=ACTION_ID, invocationType=0)))
    parameters = {}
    for index, name, count, labels in ((0, 'Page', 3, ['Arrange', 'Mixer', 'FX']),
                                      (1, 'FX', 128, []), (2, 'Parameter', 256, []),
                                      (3, 'Request', REQUEST_COUNT, []), (4, 'Menu action', 32, []),
                                      (5, 'Fine', 2, []), (6, 'Actions open', 2, []),
                                      (7, 'Send', 128, []),
                                      (8, 'Track control', 7, ['Volume', 'Pan', 'Mute', 'Solo', 'Arm', 'Monitoring', 'FX'])):
        parameters[str(index)] = dict(name=name, valueCount=count, valueLabels=labels, value=0)
    return dict(mainUnit=dict(version=RELEASE['version'], name='Device gamepad',
                             controlDeviceId='0', letMatchedEventsThrough=False,
                             letUnmatchedEventsThrough=True, parameters=parameters, mappings=mappings),
                additionalUnits=[])


def monitoring_fx(state):
    data = json.dumps(state, separators=(',', ':')).encode()
    # Native REAPER VST2 chunk header: plugin ID, magic, I/O layout, chunk size,
    # chunk flag and reserved word. No personal audio/theme settings are stored.
    header = struct.pack('<11I', 1751282284, 4276969198, 2, 1, 0, 2, 0, 0, len(data), 1, 0)
    encoded = base64.b64encode(data).decode()
    return ('SHOW -1\nLASTSEL 0\nDOCKED 0\nBYPASS 0 0 0\n'
            f'<VST "{PLUGIN_NAME}" helgobox-x64.so 0 "Device gamepad" '
            '1751282284<5653546862726C68656C676F626F7872> ""\n  ' +
            base64.b64encode(header).decode() + '\n' +
            ''.join('  ' + encoded[i:i + 128] + '\n' for i in range(0, len(encoded), 128)) +
            '  AFByb2dyYW0gMQAAAAAA\n>\nWAK 0 0\n')


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staging = Path(stream.name)
        try:
            stream.write(data)
            os.fchmod(stream.fileno(), 0o644)
            stream.close()
            staging.replace(path)
        finally:
            staging.unlink(missing_ok=True)


def retarget_controller(chain, index, replacement=None):
    """Change the input, optionally replacing our controller state explicitly."""
    pattern = r'(<VST [^\n]*"Device gamepad"[^\n]*\n)(.*?)(\n>\n)'
    def replace(match):
        lines = match[2].splitlines()
        header = bytearray(base64.b64decode(lines[0].strip()))
        state = json.loads(base64.b64decode(''.join(line.strip() for line in lines[1:-1])))
        if replacement is not None:
            state = replacement
        state['mainUnit']['controlDeviceId'] = str(index)
        data = json.dumps(state, separators=(',', ':')).encode()
        struct.pack_into('<I', header, 32, len(data))
        encoded = base64.b64encode(data).decode()
        return (match[1] + '  ' + base64.b64encode(header).decode() + '\n' +
                '\n'.join('  ' + encoded[i:i + 128] for i in range(0, len(encoded), 128)) +
                '\n' + lines[-1] + match[3])
    result, count = re.subn(pattern, replace, chain, flags=re.S)
    if count != 1:
        raise ValueError('Cannot identify the existing device controller state')
    return result


def reaper_running():
    for entry in Path('/proc').iterdir():
        if entry.name.isdecimal():
            try:
                if (entry / 'exe').resolve().name == 'reaper':
                    return True
            except (FileNotFoundError, PermissionError):
                pass
    return False


def install(resource=None, asset_dir=None, update_controller=False):
    if os.geteuid() == 0:
        raise SystemExit('Run as the desktop user')
    resource = resource or Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'REAPER'
    chain = resource / 'reaper-hwoutfx.ini'
    current_chain = chain.read_text() if chain.exists() else ''
    if current_chain.strip() and '"Device gamepad"' not in current_chain:
        raise RuntimeError('Monitoring FX already exist; add the device preset alongside them in REAPER')
    # Installation changes startup files; never race a running REAPER session.
    if reaper_running():
        raise RuntimeError('Save and close REAPER before installing its controller integration')
    cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'minion/audio/realearn'
    for asset in RELEASE['assets']:
        target = resource / 'UserPlugins' / asset['file']
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != asset['sha256']:
            raise RuntimeError('ReaLearn differs from the pinned version; retaining ' + str(target))
        source = (asset_dir or cache) / asset['filename']
        if source.exists():
            data = source.read_bytes()
        else:
            if asset_dir:
                raise FileNotFoundError(source)
            with urllib.request.urlopen(asset['url'], timeout=60) as response:
                data = response.read(96 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != asset['sha256']:
            raise ValueError('ReaLearn checksum mismatch: ' + asset['filename'])
        if not source.exists():
            atomic(source, data)
        atomic(resource / 'UserPlugins' / asset['file'], data)
    config_path = resource / 'Helgoboss/ReaLearn/realearn.ini'
    if not config_path.exists():
        atomic(config_path, b'[main]\nshowed_welcome_screen=1\nsend_errors_to_dev=0\nnotify_about_updates=0\n')
    atomic(resource / 'Scripts/Device/reaper-gamepad.lua', (HERE / 'reaper-gamepad.lua').read_bytes())
    atomic(resource / 'Scripts/Device/reaper-control-outline.py', (HERE / 'reaper-control-outline.py').read_bytes())
    atomic(resource / 'Scripts/Device/reaper-control-navigation.lua', (HERE / 'reaper-control-navigation.lua').read_bytes())
    keys = resource / 'reaper-kb.ini'
    current = keys.read_text() if keys.exists() else ''
    if ACTION_ID not in current:
        atomic(keys, (current.rstrip() + '\nSCR 4 0 ' + ACTION_ID +
                      ' "Custom: Gamepad controls" "Device/reaper-gamepad.lua"\n').lstrip().encode())
    # JACK exposes numbered MIDI input ports; other Linux audio backends use
    # ALSA's virtual RawMIDI input. A RawMIDI cache entry makes the same numbered
    # JACK input unavailable, so never seed it for a JACK session.
    ini = resource / 'reaper.ini'
    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.optionxform = str
    config.read(ini)
    if not config.has_section('reaper'):
        config.add_section('reaper')
    cache_path = resource / 'reaper-midihw-alsa.ini'
    devices = configparser.ConfigParser(interpolation=None)
    devices.read(cache_path)
    if not devices.has_section('mididevcache'):
        devices.add_section('mididevcache')
    inputs = devices['mididevcache']
    indices = [index for index in range(62) if inputs.get(f'in{index}') == 'virtual']
    if len(indices) > 1:
        raise RuntimeError('Several virtual MIDI input slots exist; reconcile before setup')
    saved_state = resource / 'Data/device-gamepad.json'
    if current_chain.strip() and saved_state.exists():
        index = int(json.loads(saved_state.read_text())['mainUnit']['controlDeviceId'])
        if not 0 <= index < 62:
            raise ValueError('Invalid saved controller MIDI input')
    else:
        used = int(config['reaper'].get('midiins', '0'))
        index = indices[0] if indices else next(index for index in range(62)
                                               if f'in{index}' not in inputs and not used & (1 << index))
    previous_index = index
    if config['reaper'].get('linux_audio_mode') == '0':
        if inputs.get(f'in{index}') == 'virtual' and inputs.get(f'it{index}') == '1':
            del inputs[f'in{index}']
            del inputs[f'it{index}']
        jack_cache_path = resource / 'reaper-midihw-linux.ini'
        jack_devices = configparser.ConfigParser(interpolation=None)
        jack_devices.read(jack_cache_path)
        if not jack_devices.has_section('mididevcache'):
            jack_devices.add_section('mididevcache')
        jack_inputs = jack_devices['mididevcache']
        # The first JACK port may be named after a physical MIDI bridge. Reserve
        # an unused numbered virtual input instead, preserving other devices.
        used = int(config['reaper'].get('midiins', '0'))
        candidates = ([index] if current_chain.strip() else []) + list(range(1, 32))
        index = next(candidate for candidate in candidates
                     if candidate >= 1 and
                     jack_inputs.get(f'in{candidate}', f'MIDI Input {candidate + 1}') == f'MIDI Input {candidate + 1}' and
                     (candidate == previous_index and current_chain.strip() or not used & (1 << candidate)))
        jack_inputs[f'it{index}'] = '1'
        jack_inputs[f'in{index}'] = f'MIDI Input {index + 1}'
    else:
        inputs[f'it{index}'], inputs[f'in{index}'] = '1', 'virtual'
    for key in ('midiins', 'midiins_cs'):
        mask = int(config['reaper'].get(key, '0'))
        if current_chain.strip() and index != previous_index:
            mask &= ~(1 << previous_index)
        config['reaper'][key] = str(mask | (1 << index))
    config['reaper']['midiins_all'] = str(int(config['reaper'].get('midiins_all', '0')) & ~(1 << index))
    import io
    for target, content in ((ini, config), (cache_path, devices)):
        out = io.StringIO()
        content.write(out, space_around_delimiters=False)
        atomic(target, out.getvalue().encode())
    if config['reaper'].get('linux_audio_mode') == '0':
        out = io.StringIO()
        jack_devices.write(out, space_around_delimiters=False)
        atomic(jack_cache_path, out.getvalue().encode())
    state = preset()
    state['mainUnit']['controlDeviceId'] = str(index)
    if not current_chain.strip():
        atomic(chain, monitoring_fx(state).encode())
    else:
        updated = (retarget_controller(current_chain, index, state if update_controller else None)
                   if index != previous_index or update_controller else current_chain)
        # This FX supplies the controller in every profile, even while its UI
        # is hidden. A bypassed instance cannot receive any controller input.
        updated = re.sub(r'(^BYPASS )1( [^\n]*\n<VST [^\n]*"Device gamepad")',
                         r'\g<1>0\2', updated, flags=re.M)
        if updated != current_chain:
            atomic(chain, updated.encode())
    atomic(resource / 'Data/device-gamepad.json', json.dumps(state, indent=2).encode() + b'\n')
    print(f'ReaLearn {RELEASE["version"]} and gamepad pages installed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--update-controller', action='store_true',
                        help='Replace the device controller mappings with the current repository layout')
    args = parser.parse_args()
    if args.check:
        print('ReaLearn ' + RELEASE['version'] + ': Arrange, Mixer and FX pages')
    else:
        install(asset_dir=args.asset_dir, update_controller=args.update_controller)
