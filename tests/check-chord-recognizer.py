#!/usr/bin/env python3
"""Check real mapper frames for every chord press/release order, without host input."""
import importlib.machinery
import importlib.util
import itertools
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
# xpad reports Xbox A/B/X/Y as BTN_A/B/X/Y. The historical Linux aliases
# put BTN_X at BTN_NORTH (0x133), and BTN_Y at BTN_WEST (0x134).
# Keep this fixture independent of FACE_NAMES and the loaded configuration.
XBOX_FACE_CODES = {'A': 0x130, 'B': 0x131, 'X': 0x133, 'Y': 0x134}
loader = importlib.machinery.SourceFileLoader('mapper', str(PROJECT / 'setup/desktop/mini-os-gamepad'))
spec = importlib.util.spec_from_loader(loader.name, loader)
mapper = importlib.util.module_from_spec(spec)
loader.exec_module(mapper)


class Keyboard:
    def __init__(self):
        self.events = []

    def write(self, kind, code, value):
        self.events.append((kind, code, value))

    def syn(self):
        pass


def main():
    # Use Linux's published codes; create no evdev/UInput device on the host.
    header = Path('/usr/include/linux/input-event-codes.h').read_text()
    constants = {name: int(value, 0) for name, value in re.findall(
        r'^#define\s+((?:KEY|BTN|ABS|EV)_\w+)\s+(0x[\da-fA-F]+|\d+)\b', header, re.M)}
    codes = SimpleNamespace(**constants, ecodes=constants)
    with tempfile.TemporaryDirectory(prefix='mini-os-chord-test-') as temporary:
        directory = Path(temporary)

        def path(value):
            return PROJECT / 'setup/desktop/gamepad.json' if str(value) == '/etc/mini-os/gamepad.json' else Path(value)

        with patch.object(mapper, 'Path', side_effect=path):
            config = mapper.configuration(directory / 'no-personal-profile.json', codes)
        keyboard = Keyboard()
        state = mapper.Mapper(config, keyboard, codes, directory)
        state.ranges = {axis: (-1, 1) for axis in config['dpad']}
        state.ranges.update({axis: (0, 255) for axis in (config['shift_trigger'], config['ctrl_trigger'])})
        state.ranges.update({axis: (-32768, 32767) for axis in config['left_stick'] + config['right_stick']})
        frames = 0

        def frame(tokens, shift=False, ctrl=False):
            nonlocal frames
            previous = set(state.raw_keys)
            state.raw_keys = {XBOX_FACE_CODES[t] for t in tokens if t in XBOX_FACE_CODES}
            horizontal, vertical = config['chord_axes']
            state.raw_axes = {horizontal: -1 if 'LEFT' in tokens else 1 if 'RIGHT' in tokens else 0,
                              vertical: -1 if 'UP' in tokens else 1 if 'DOWN' in tokens else 0,
                              config['shift_trigger']: 255 if shift else 0,
                              config['ctrl_trigger']: 255 if ctrl else 0}
            state.frame(state.raw_keys - previous, previous - state.raw_keys, frames * .03, True)
            frames += 1

        def reset():
            state.reset()
            state.grabbed = state.ready = True
            state.raw_keys.clear()
            keyboard.events.clear()

        for face, output in (('A', codes.KEY_ENTER), ('B', codes.KEY_ESC),
                             ('X', codes.KEY_BACKSPACE), ('Y', codes.KEY_TAB)):
            reset()
            frame({face})
            assert not keyboard.events, ('early single face', face)
            frame(set())
            assert keyboard.events == [(codes.EV_KEY, output, 1), (codes.EV_KEY, output, 0)], (face, keyboard.events)

        orders = 0
        for chord, output in config['chords'].items():
            for presses in itertools.permutations(chord):
                for releases in itertools.permutations(chord):
                    reset()
                    held = set()
                    for token in presses:
                        held.add(token)
                        frame(held)
                        assert not keyboard.events, ('early press', chord, presses)
                    for token in releases:
                        held.remove(token)
                        frame(held)
                        if held:
                            assert not keyboard.events, ('partial release', chord, releases)
                    assert keyboard.events == [(codes.EV_KEY, output, 1), (codes.EV_KEY, output, 0)], (chord, keyboard.events)
                    orders += 1
        for chord, output in config['chords'].items():
            reset()
            frame(chord)
            frame(chord, shift=True, ctrl=True)
            frame(set(), shift=True, ctrl=True)
            assert state.keys == {codes.KEY_LEFTSHIFT, codes.KEY_LEFTCTRL}
            assert keyboard.events[-2:] == [(codes.EV_KEY, output, 1), (codes.EV_KEY, output, 0)]
            frame(set())
            assert not state.keys
        for chord in ({'A', 'Y'}, {'A', 'B', 'Y'}, {'DOWN', 'X', 'Y'}):
            reset()
            frame(chord)
            frame(set())
            assert not keyboard.events, ('invalid/reserved', chord)
        reset()
        for held in ({'UP', 'A'}, {'A'}, {'A', 'B'}, {'B'}, set()):
            frame(held)
        assert not keyboard.events, 'Rolling press should cancel'
        reset()
        frame({'UP', 'A'})
        state.reset()
        state.ready = True
        frame(set())
        assert not keyboard.events, 'Reset should discard an unfinished chord'
        profile = json.loads((PROJECT / 'setup/desktop/gamepad.json').read_text())
        assert len(profile['chords']) == 48 and len(set(profile['chords'].values())) == 48
        assert profile['chords']['DOWN+A'] == 'KEY_SPACE'
        print(f'Passed: Xbox driver face codes, four single actions, {orders} press/release orders, all 48 late modifier combinations, invalid/reserved/rolling chords and reset.')


if __name__ == '__main__':
    main()
