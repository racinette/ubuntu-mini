#!/usr/bin/env python3
"""Check shortcut gestures, held editing keys and selection lifecycle without host input."""
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
loader = importlib.machinery.SourceFileLoader('mapper', str(PROJECT / 'setup/desktop/minion-gamepad'))
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
    header = Path('/usr/include/linux/input-event-codes.h').read_text()
    constants = {name: int(value, 0) for name, value in re.findall(
        r'^#define\s+((?:KEY|BTN|ABS|EV)_\w+)\s+(0x[\da-fA-F]+|\d+)\b', header, re.M)}
    codes = SimpleNamespace(**constants, ecodes=constants)
    profile = json.loads((PROJECT / 'setup/desktop/gamepad.json').read_text())
    expected = {
        'UP+Y': 'copy', 'DOWN+Y': 'paste', 'LEFT+Y': 'undo', 'RIGHT+Y': 'redo',
        'UP+LEFT+Y': 'cut', 'UP+RIGHT+Y': 'select_all', 'DOWN+LEFT+Y': 'find', 'DOWN+RIGHT+Y': 'save',
        'UP+A': 'close', 'DOWN+A': 'layout', 'LEFT+A': 'fullscreen', 'RIGHT+A': 'floating',
        'UP+LEFT+A': 'file_manager', 'UP+RIGHT+A': 'split', 'DOWN+LEFT+A': 'equalize', 'DOWN+RIGHT+A': 'screenshot',
        'UP+B': 'page_up', 'DOWN+B': 'page_down', 'LEFT+B': 'home', 'RIGHT+B': 'end',
        'UP+LEFT+B': 'document_home', 'UP+RIGHT+B': 'document_end',
        'DOWN+LEFT+B': 'previous_match', 'DOWN+RIGHT+B': 'next_match',
    }
    assert profile['chords'] == expected
    assert profile['actions']['BTN_THUMBL'] == 'legend' and profile['actions']['BTN_THUMBR'] == 'selection'
    with tempfile.TemporaryDirectory(prefix='minion-shortcut-test-') as temporary:
        directory = Path(temporary)
        def path(value):
            return PROJECT / 'setup/desktop/gamepad.json' if str(value) == '/etc/minion/gamepad.json' else Path(value)
        with patch.object(mapper, 'Path', side_effect=path):
            config = mapper.configuration(directory / 'no-profile.json', codes)
        keyboard = Keyboard()
        state = mapper.Mapper(config, keyboard, codes, directory)
        state.ranges = {axis: (-1, 1) for axis in config['dpad']}
        state.ranges.update({axis: (0, 255) for axis in (config['shift_trigger'], config['ctrl_trigger'])})
        state.ranges.update({axis: (-32768, 32767) for axis in config['left_stick'] + config['right_stick']})
        frames = 0
        def frame(tokens=(), shift=False, ctrl=False, buttons=(), active=True):
            nonlocal frames
            previous = set(state.raw_keys)
            state.raw_keys = {XBOX_FACE_CODES[t] for t in tokens if t in XBOX_FACE_CODES} | set(buttons)
            horizontal, vertical = config['chord_axes']
            state.raw_axes.update({horizontal: -1 if 'LEFT' in tokens else 1 if 'RIGHT' in tokens else 0,
                                  vertical: -1 if 'UP' in tokens else 1 if 'DOWN' in tokens else 0,
                                  config['shift_trigger']: 255 if shift else 0,
                                  config['ctrl_trigger']: 255 if ctrl else 0})
            state.frame(state.raw_keys - previous, previous - state.raw_keys, frames * .03, active)
            frames += 1
        def reset():
            state.reset()
            state.mode = 'desktop'
            state.grabbed = state.ready = True
            state.raw_keys.clear()
            state.raw_axes = {axis: 0 for axis in state.ranges}
            keyboard.events.clear()
        def downs():
            return [code for kind, code, value in keyboard.events if value == 1]
        for face, output in (('A', codes.KEY_ENTER), ('B', codes.KEY_ESC), ('Y', codes.KEY_TAB)):
            reset(); frame({face}); frame({face})
            assert not keyboard.events
            frame()
            assert keyboard.events == [(codes.EV_KEY, output, 1), (codes.EV_KEY, output, 0)]
        reset(); frame({'X'})
        assert keyboard.events == [(codes.EV_KEY, codes.KEY_BACKSPACE, 1)]
        frame({'X'}); frame({'X'})
        assert len(keyboard.events) == 1 and state.keys == {codes.KEY_BACKSPACE}
        frame()
        assert keyboard.events[-1] == (codes.EV_KEY, codes.KEY_BACKSPACE, 0)
        reset(); frame({'X'}, ctrl=True)
        assert downs() == [codes.KEY_LEFTCTRL, codes.KEY_BACKSPACE]
        frame(ctrl=True)
        assert state.keys == {codes.KEY_LEFTCTRL}
        frame(); assert not state.keys

        orders = 0
        for chord, action in expected.items():
            tokens = chord.split('+')
            for presses in itertools.permutations(tokens):
                for releases in itertools.permutations(tokens):
                    reset()
                    with patch.object(state, 'dispatch') as dispatch:
                        held = set()
                        for token in presses:
                            held.add(token); frame(held)
                            assert not keyboard.events and not dispatch.called
                        for token in releases:
                            held.remove(token); frame(held)
                            if held:
                                assert not keyboard.events and not dispatch.called
                        dispatch.assert_called_once_with(action)
                    assert not keyboard.events
                    orders += 1
        for invalid in (({'A', 'Y'}, set()), ({'A', 'B'}, set()),
                        ({'UP', 'Y'}, {'Y'}, {'Y', 'B'}, {'B'}, set())):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                for held in invalid: frame(held)
                assert not keyboard.events and not dispatch.called
        # X stays independent even beside a shortcut; it is never deferred or re-pressed.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame({'X', 'UP', 'Y'}); frame({'X'}); frame()
            dispatch.assert_called_once_with('copy')
        assert downs() == [codes.KEY_BACKSPACE]

        # Assert actual emitted shortcuts independently of the mapping table.
        key_cases = {
            'copy': ('KEY_C', {'KEY_LEFTCTRL'}), 'paste': ('KEY_V', {'KEY_LEFTCTRL'}),
            'cut': ('KEY_X', {'KEY_LEFTCTRL'}), 'undo': ('KEY_Z', {'KEY_LEFTCTRL'}),
            'redo': ('KEY_Z', {'KEY_LEFTCTRL', 'KEY_LEFTSHIFT'}),
            'select_all': ('KEY_A', {'KEY_LEFTCTRL'}), 'find': ('KEY_F', {'KEY_LEFTCTRL'}),
            'save': ('KEY_S', {'KEY_LEFTCTRL'}), 'page_up': ('KEY_PAGEUP', set()),
            'page_down': ('KEY_PAGEDOWN', set()), 'home': ('KEY_HOME', set()), 'end': ('KEY_END', set()),
            'document_home': ('KEY_HOME', {'KEY_LEFTCTRL'}), 'document_end': ('KEY_END', {'KEY_LEFTCTRL'}),
            'previous_match': ('KEY_F3', {'KEY_LEFTSHIFT'}), 'next_match': ('KEY_F3', set()),
        }
        for action, (key_name, names) in key_cases.items():
            for triggers in (False, True):
                reset(); frame(shift=triggers, ctrl=triggers); keyboard.events.clear()
                with patch.object(state, 'focused_application', return_value='gui'):
                    state.dispatch(action)
                modifiers = {getattr(codes, n) for n in names}
                if action in {'page_up', 'page_down', 'home', 'end', 'document_home', 'document_end'} and triggers:
                    modifiers |= {codes.KEY_LEFTSHIFT, codes.KEY_LEFTCTRL}
                key = getattr(codes, key_name)
                live = {codes.KEY_LEFTSHIFT, codes.KEY_LEFTCTRL} if triggers else set()
                for kind, code, value in keyboard.events:
                    if value: live.add(code)
                    else: live.discard(code)
                    if code == key and value == 1:
                        assert live == modifiers | {key}, (action, triggers, live)
                assert state.keys == ({codes.KEY_LEFTSHIFT, codes.KEY_LEFTCTRL} if triggers else set())
        for app in ('foot', 'terminal', 'unknown'):
            for action in ('copy', 'paste', 'cut', 'undo', 'redo', 'select_all', 'find', 'save', 'next_match', 'previous_match'):
                reset()
                context = (patch.object(state, 'focused_application', side_effect=ValueError()) if app == 'unknown'
                           else patch.object(state, 'focused_application', return_value=app))
                with context, patch.object(state, 'notify'):
                    state.dispatch(action)
                if app == 'foot' and action in ('copy', 'paste'):
                    assert downs() == [codes.KEY_LEFTCTRL, codes.KEY_LEFTSHIFT, codes.KEY_C if action == 'copy' else codes.KEY_V]
                else:
                    assert not keyboard.events, (app, action)
        for action, command in {'close': 'kill', 'fullscreen': 'fullscreen toggle', 'floating': 'floating toggle',
                                'layout': 'layout toggle tabbed split', 'split': 'split toggle',
                                'file_manager': 'exec thunar', 'screenshot': 'exec grim - | wl-copy --type image/png'}.items():
            reset()
            with patch.object(state, 'command') as run:
                state.dispatch(action); run.assert_called_once_with(command)
            assert not keyboard.events
        reset(); frame({'X'})
        with patch.object(state, 'focused_application', return_value='gui'):
            state.dispatch('copy')
        assert downs().count(codes.KEY_BACKSPACE) == 1 and state.keys == {codes.KEY_BACKSPACE}

        # Classify the real client executable, including custom Foot app IDs.
        for executable, app_id, expected_app in (('foot', 'custom-editor', 'foot'),
                                                  ('footclient', 'custom-terminal', 'foot'),
                                                  ('kitty', 'custom', 'terminal'),
                                                  ('firefox', 'org.mozilla.firefox', 'gui')):
            tree = {'nodes': [], 'floating_nodes': [{'focused': True, 'pid': 123, 'app_id': app_id}]}
            with patch.object(mapper, 'ipc', return_value=tree), patch.object(
                    mapper.os, 'readlink', return_value='/usr/bin/' + executable):
                assert state.focused_application() == expected_app

        for button, action in ((315, 'terminal'), (314, 'window_picker'), (316, 'launcher')):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                frame(buttons=(button,)); frame(buttons=(button,))
                assert not dispatch.called
                frame(); dispatch.assert_called_once_with(action)
        for button, step in ((310, -1), (311, 1)):
            reset()
            with patch.object(state, 'workspace') as workspace:
                frame(buttons=(button,)); assert not workspace.called
                frame(); workspace.assert_called_once_with(step)
        reset()
        state.device = SimpleNamespace(ungrab=lambda: None)
        with patch.object(state, 'dispatch') as dispatch, patch.object(state, 'notify'):
            frame(buttons=(314, 315))
            for _ in range(30): frame(buttons=(314, 315))
            frame(buttons=(315,)); assert state.mode == 'desktop'
            frame(); assert state.mode == 'passthrough' and not dispatch.called
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame(buttons=(314, 315)); frame()
            assert state.mode == 'desktop' and not dispatch.called

        class Device:
            path, name = '/dev/fixture', 'Fixture'
            def ungrab(self): pass
            def close(self): pass
        state.device = Device()
        reset()
        with patch.object(state, 'notify'), patch.object(state, 'command') as command:
            frame(buttons=(318,)); assert state.right_pending is None
            frame(); assert state.right_pending == 'select' and state.right_mode == 'resize'
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(0, True)
            assert not keyboard.events and not command.called and state.right_pending == 'select'
            state.raw_axes[config['right_stick'][0]] = 0
            state.tick(.1, True)
            assert state.right_mode == 'select' and state.right_pending is None
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(.2, True)
            assert downs() == [codes.KEY_LEFTSHIFT, codes.KEY_RIGHT] and not state.keys
            count = len(keyboard.events)
            state.tick(.3, True); assert len(keyboard.events) == count
            state.tick(.7, True); assert len(keyboard.events) > count
            frame(ctrl=True); keyboard.events.clear()
            state.tick(1, True)
            assert codes.KEY_RIGHT in downs() and state.keys == {codes.KEY_LEFTCTRL}
            assert not command.called
            frame(buttons=(318,)); frame()
            assert state.right_pending == 'resize'
            state.tick(2, True); assert not command.called
            state.raw_axes[config['right_stick'][0]] = 0
            state.tick(3, True); assert state.right_mode == 'resize'
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(4, True); command.assert_called_with('resize grow width 5 ppt')
        assert (directory / 'right-stick-mode').read_text().strip() == 'resize'
        for reason in ('reset', 'disconnect', 'inactive', 'paused', 'passthrough'):
            reset(); state.device = Device(); state.right_mode = 'select'; frame({'X'}, shift=True, ctrl=True)
            frame({'X', 'UP', 'A'}, shift=True, ctrl=True)
            if reason == 'reset': state.reset()
            elif reason == 'disconnect': state.detach()
            elif reason == 'inactive': state.tick(0, False)
            elif reason == 'paused':
                (directory / 'paused').touch(); state.tick(0, True); (directory / 'paused').unlink()
            else:
                with patch.object(state, 'notify'): state.toggle()
            assert not state.keys and state.right_mode == 'resize' and not state.right_pending
            assert not state.text_gesture.previous and not state.pending_buttons
        state.device = None

        # Persistent legend, L3 toggling, and no action escaping the overlay.
        reset()
        process = SimpleNamespace(stdin=__import__('io').StringIO(), poll=lambda: None,
                                  terminate=lambda: None, wait=lambda **kw: 0)
        with patch.object(mapper.subprocess, 'Popen', return_value=process):
            frame(buttons=(317,)); assert not state.legend_open()
            frame(); assert state.legend_open() and not keyboard.events
        legend = state.legend_text()
        assert all(mapper.ACTION_LABELS[action] in legend for action in expected.values())
        with patch.object(state, 'dispatch') as dispatch:
            frame({'UP', 'A'}); state.close_legend(); frame()
            assert not dispatch.called, 'Gesture escaped a closed legend'
        with patch.object(mapper.subprocess, 'Popen', return_value=process):
            # A fresh stdin is needed after opening the first overlay closed it.
            process.stdin = __import__('io').StringIO()
            frame(buttons=(317,)); frame(); assert state.legend_open()
            frame(buttons=(317,)); frame(); assert not state.legend_open()

        # User profiles cannot bring X back into shortcuts or load old character outputs.
        for changes in ({'chords': {'UP+X': 'copy'}}, {'chords': {'UP+Y': 'KEY_E'}}):
            personal = directory / 'bad.json'; personal.write_text(json.dumps(changes))
            with patch.object(mapper, 'Path', side_effect=path):
                try: mapper.configuration(personal, codes)
                except ValueError: pass
                else: raise AssertionError('Invalid shortcut profile accepted')
        saved = config['chords']; config['chords'] = {}; reset()
        frame({'UP'}); frame({'UP'})
        assert keyboard.events == [(codes.EV_KEY, codes.KEY_UP, 1)]
        frame(); assert keyboard.events[-1] == (codes.EV_KEY, codes.KEY_UP, 0)
        config['chords'] = saved
        print(f'Passed: 24 named shortcuts, {orders} press/release orders, independent Xbox codes, holdable Backspace, modifier restoration, terminal guards, selection/repeat/neutral transition, legend capture, lifecycle reset and profile validation.')


if __name__ == '__main__':
    main()
