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
        r'^#define\s+((?:KEY|BTN|ABS|EV|REL)_\w+)\s+(0x[\da-fA-F]+|\d+)\b', header, re.M)}
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
        'A+B': 'interrupt', 'UP+A+B': 'suspend_job', 'DOWN+A+B': 'end_input',
    }
    assert profile['chords'] == expected
    assert profile['actions']['BTN_THUMBL'] == 'legend' and profile['actions']['BTN_THUMBR'] == 'stick_context'
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
        def frame(tokens=(), shift=False, ctrl=False, buttons=(), active=True, at=None):
            nonlocal frames
            previous = set(state.raw_keys)
            state.raw_keys = {XBOX_FACE_CODES[t] for t in tokens if t in XBOX_FACE_CODES} | set(buttons)
            horizontal, vertical = config['chord_axes']
            state.raw_axes.update({horizontal: -1 if 'LEFT' in tokens else 1 if 'RIGHT' in tokens else 0,
                                  vertical: -1 if 'UP' in tokens else 1 if 'DOWN' in tokens else 0,
                                  config['shift_trigger']: 255 if shift else 0,
                                  config['ctrl_trigger']: 255 if ctrl else 0})
            state.frame(state.raw_keys - previous, previous - state.raw_keys,
                        frames * .03 if at is None else at, active)
            frames += 1
        def reset():
            state.reset()
            state.mode = 'desktop'
            state.grabbed = state.ready = True
            state.raw_keys.clear()
            state.raw_axes = {axis: 0 for axis in state.ranges}
            keyboard.events.clear()
        def downs():
            return [code for kind, code, value in keyboard.events if kind == codes.EV_KEY and value == 1]
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
                if presses[0] not in XBOX_FACE_CODES:
                    continue
                face_count = sum(token in XBOX_FACE_CODES for token in tokens)
                if any(token not in XBOX_FACE_CODES for token in presses[:face_count]):
                    continue
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
        for invalid in (({'A', 'Y'}, set()), ({'Y', 'B'}, set()),
                        ({'Y'}, {'UP', 'Y'}, {'Y'}, {'Y', 'B'}, {'B'}, set())):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                for held in invalid: frame(held)
                assert not keyboard.events and not dispatch.called
        # X stays independent even beside a shortcut; it is never deferred or re-pressed.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame({'X', 'Y'}); frame({'X', 'UP', 'Y'}); frame({'X'}); frame()
            dispatch.assert_called_once_with('copy')
        assert downs() == [codes.KEY_BACKSPACE]

        # A face prefix has no timeout; directions alone act on press, not release.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame({'Y'}, at=0); frame({'Y'}, at=60)
            assert not keyboard.events and not dispatch.called
            frame({'Y', 'UP'}, at=61); frame({'Y', 'UP'}, at=90)
            assert not keyboard.events and not dispatch.called
            frame(at=91); dispatch.assert_called_once_with('copy')
        for direction, key in [('UP', codes.KEY_UP), ('DOWN', codes.KEY_DOWN),
                               ('LEFT', codes.KEY_LEFT), ('RIGHT', codes.KEY_RIGHT)]:
            reset(); frame({direction}, at=0)
            assert downs() == [key] and not state.keys
            frame({direction}, at=.39); assert downs() == [key]
            frame(at=.4); assert downs() == [key] and not state.dpad_navigation

        # Wrong-order and simultaneous controls cannot execute a named shortcut
        # or leak Enter/Escape/Tab, even if held after the direction is released.
        for chord in expected:
            tokens = set(chord.split('+'))
            face = tokens & set(XBOX_FACE_CODES)
            directions = tokens - face
            if not directions:
                continue
            for simultaneous in (False, True):
                reset()
                with patch.object(state, 'dispatch') as dispatch:
                    if not simultaneous:
                        frame(directions, at=0)
                    frame(tokens, at=.1)
                    before = list(keyboard.events)
                    frame(tokens, at=10); frame(face, at=11); frame(face, at=20); frame(at=21)
                    assert keyboard.events == before and not dispatch.called
                    assert not state.dpad_navigation and not state.text_gesture.previous
                    assert not set(downs()) & {codes.KEY_ENTER, codes.KEY_ESC, codes.KEY_TAB}

        # The entire A+B prefix must precede the direction. Holds do not repeat,
        # unassigned directions do not fall back to Ctrl+C, and a rolling press
        # during release invalidates the gesture.
        for sequence in (
                ({'A'}, {'A', 'UP'}, {'A', 'B', 'UP'}, set()),
                ({'B'}, {'A', 'B', 'DOWN'}, set()),
                ({'A', 'B'}, {'A', 'B', 'LEFT'}, set()),
                ({'A', 'B'}, {'A'}, {'A', 'UP'}, set())):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                for held in sequence: frame(held)
                assert not keyboard.events and not dispatch.called
        for direction, action in ((None, 'interrupt'), ('UP', 'suspend_job'), ('DOWN', 'end_input')):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                frame({'A', 'B'}, at=0); frame({'A', 'B'}, at=60)
                held = {'A', 'B'} | ({direction} if direction else set())
                frame(held, at=61); frame(held, at=120)
                assert not keyboard.events and not dispatch.called
                frame(at=121); dispatch.assert_called_once_with(action)

        # Explicit repeats accelerate, do not depend on polling frequency,
        # respect current modifiers, stop at neutral and bound scheduling gaps.
        def hold_dpad(direction, frequency):
            reset(); frame({direction}, at=0)
            counts = []
            for second in range(3):
                before = len(downs())
                for step in range(1, frequency + 1):
                    frame({direction}, at=second + step / frequency)
                counts.append(len(downs()) - before)
            return counts
        horizontal = hold_dpad('LEFT', 100)
        assert horizontal[0] < horizontal[1] <= horizontal[2] and 24 <= horizontal[2] <= 26
        assert all(abs(a - b) <= 1 for a, b in zip(horizontal, hold_dpad('LEFT', 30)))
        vertical = hold_dpad('UP', 100)
        assert vertical[0] < vertical[1] <= vertical[2] and 24 <= vertical[2] <= 26
        assert vertical == horizontal, 'D-pad directions have different held repeat rates'
        horizontal_axis = config['chord_axes'][0]
        original_key = config['dpad'][horizontal_axis][0]
        config['dpad'][horizontal_axis][0] = codes.KEY_HOME
        reset(); frame({'LEFT'}, at=0)
        assert downs() == [codes.KEY_HOME], 'Navigation ignored a personal D-pad mapping'
        config['dpad'][horizontal_axis][0] = original_key
        reset(); frame({'LEFT'}, at=0)
        for step in range(1, 201): frame({'LEFT'}, at=step / 100)
        before = len(downs()); frame({'LEFT'}, at=100)
        assert len(downs()) - before <= 3, 'Stall produced a repeat backlog'
        frame(at=100.1); before = list(keyboard.events)
        frame(at=101); assert keyboard.events == before
        frame({'RIGHT'}, at=102)
        assert downs()[-1] == codes.KEY_RIGHT
        before = len(downs()); frame({'RIGHT'}, at=102.39)
        assert len(downs()) == before, 'New direction retained the old acceleration'
        frame({'UP'}, at=102.4)
        assert downs()[-1] == codes.KEY_UP
        before = len(downs()); frame({'UP'}, at=102.79)
        assert len(downs()) == before, 'Rolling direction retained acceleration'
        frame({'A', 'UP'}, at=103)
        before = list(keyboard.events)
        with patch.object(state, 'dispatch') as dispatch:
            frame({'UP'}, at=105); frame(at=106)
            assert keyboard.events == before and not dispatch.called
        for shift, ctrl in itertools.product((False, True), repeat=2):
            reset(); frame({'LEFT'}, shift=shift, ctrl=ctrl, at=0)
            for step in range(1, 201): frame({'LEFT'}, shift=shift, ctrl=ctrl, at=step / 100)
            assert downs().count(codes.KEY_LEFT) > 20
            assert state.keys == ({codes.KEY_LEFTSHIFT} if shift else set()) | ({codes.KEY_LEFTCTRL} if ctrl else set())
            frame({'LEFT'}, at=2.01); assert not state.keys
            frame(at=2.02); assert not state.dpad_navigation

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
        # Terminal controls emit literal Ctrl+C/Z/D, never Ctrl+Shift variants,
        # restore triggers, and fail closed in GUI/unidentified clients.
        terminal_cases = {'interrupt': codes.KEY_C, 'suspend_job': codes.KEY_Z, 'end_input': codes.KEY_D}
        for app in ('foot', 'terminal', 'gui', 'unknown'):
            for action, key in terminal_cases.items():
                for shift, ctrl in itertools.product((False, True), repeat=2):
                    reset(); frame(shift=shift, ctrl=ctrl); keyboard.events.clear()
                    held = set(state.keys)
                    context = (patch.object(state, 'focused_application', side_effect=ValueError()) if app == 'unknown'
                               else patch.object(state, 'focused_application', return_value=app))
                    with context, patch.object(state, 'notify'):
                        state.dispatch(action)
                    if app in ('foot', 'terminal'):
                        live = set(held)
                        pressed = 0
                        for kind, code, value in keyboard.events:
                            if value: live.add(code)
                            else: live.discard(code)
                            if code == key and value == 1:
                                assert live == {codes.KEY_LEFTCTRL, key}, (app, action, live)
                                pressed += 1
                        assert pressed == 1
                    else:
                        assert not keyboard.events, (app, action)
                    assert state.keys == held
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
        assert state.stick_mode == 'window'
        with patch.object(state, 'notify'), patch.object(state, 'command') as command:
            frame(buttons=(318,)); assert state.stick_pending is None
            frame(); assert state.stick_pending == 'workspace' and state.stick_mode == 'window'
            # Both sticks must be centered; returning only one is insufficient.
            state.raw_axes[config['right_stick'][0]] = 32767
            state.raw_axes[config['left_stick'][0]] = -32768
            state.tick(0, True)
            assert not keyboard.events and not command.called
            state.raw_axes[config['right_stick'][0]] = 0
            state.tick(.1, True)
            assert state.stick_pending == 'workspace' and not command.called
            state.raw_axes[config['left_stick'][0]] = 0
            state.tick(.2, True)
            assert state.stick_mode == 'workspace' and state.stick_pending is None
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(.3, True); command.assert_called_with('resize grow width 5 ppt')
            state.raw_axes[config['right_stick'][0]] = 0
            state.raw_axes[config['left_stick'][0]] = -32768
            state.tick(.4, True); command.assert_called_with('focus left')
            frame(shift=True)
            state.raw_axes[config['left_stick'][0]] = 32767
            state.tick(.5, True); command.assert_called_with('move right')
            frame(); frame(buttons=(318,)); frame()
            assert state.stick_pending == 'window'
            command.reset_mock(); state.tick(1, True)
            assert not command.called and state.stick_mode == 'workspace'
            state.raw_axes[config['left_stick'][0]] = 0
            state.tick(2, True)
            assert state.stick_mode == 'window' and not state.stick_pending
        assert (directory / 'stick-mode').read_text().strip() == 'window'

        window = {'id': 42, 'rect': {'x': -960, 'y': 20, 'width': 960, 'height': 500}}
        # The virtual device exposes both mouse and keyboard capabilities.
        capabilities = mapper.output_capabilities(config, codes)
        assert codes.BTN_LEFT in capabilities[codes.EV_KEY]
        assert {codes.KEY_C, codes.KEY_Z, codes.KEY_D} <= set(capabilities[codes.EV_KEY])
        assert set(capabilities[codes.EV_REL]) == {codes.REL_X, codes.REL_Y, codes.REL_WHEEL,
            codes.REL_HWHEEL, codes.REL_WHEEL_HI_RES, codes.REL_HWHEEL_HI_RES}
        # Wheel detents have full 120-unit magnitude and correct direction, with
        # trigger releases/restores ordered around them on the same event stream.
        for shift, ctrl in itertools.product((False, True), repeat=2):
            for axis, value, wheel, precise, sign in (
                    (config['left_stick'][0], -32768, codes.REL_HWHEEL, codes.REL_HWHEEL_HI_RES, -1),
                    (config['left_stick'][0], 32767, codes.REL_HWHEEL, codes.REL_HWHEEL_HI_RES, 1),
                    (config['left_stick'][1], -32768, codes.REL_WHEEL, codes.REL_WHEEL_HI_RES, 1),
                    (config['left_stick'][1], 32767, codes.REL_WHEEL, codes.REL_WHEEL_HI_RES, -1)):
                reset(); frame(shift=shift, ctrl=ctrl)
                held = set(state.keys); keyboard.events.clear()
                with patch.object(state, 'focused_window', return_value=window), patch.object(
                        state, 'command', return_value=True) as command:
                    state.raw_axes[axis] = value
                    state.tick(0, True)
                    command.assert_called_once_with('seat seat0 cursor set -480 270')
                    relative = [event for event in keyboard.events if event[0] == codes.EV_REL]
                    assert relative == [(codes.EV_REL, precise, sign * 120), (codes.EV_REL, wheel, sign)]
                    first_wheel = keyboard.events.index(relative[0])
                    last_wheel = keyboard.events.index(relative[-1])
                    for key in held:
                        assert keyboard.events.index((codes.EV_KEY, key, 0)) < first_wheel
                        assert keyboard.events.index((codes.EV_KEY, key, 1)) > last_wheel
                    assert state.keys == held
                    state.raw_axes[axis] = 0
                    command.reset_mock(); keyboard.events.clear(); state.tick(1, True)
                    assert not command.called and not keyboard.events and state.scroll_target is None
                frame(); assert not state.keys
        reset()
        with patch.object(state, 'focused_window', return_value=window), patch.object(state, 'command', return_value=True):
            state.scroll('down', 3, 0, True)
            assert keyboard.events == [(codes.EV_REL, codes.REL_WHEEL_HI_RES, -360),
                                       (codes.EV_REL, codes.REL_WHEEL, -3)]

        def scrolled(value, frequency=100):
            reset(); state.raw_axes[config['left_stick'][1]] = value
            with patch.object(state, 'scroll') as scroll:
                for step in range(frequency + 1):
                    state.tick(step / frequency, True)
                return sum(call.args[1] for call in scroll.call_args_list)
        slow_scroll, fast_scroll = scrolled(19660), scrolled(32767)
        assert 1 <= slow_scroll <= 3 and 18 <= fast_scroll <= 19
        assert abs(scrolled(32767, 30) - fast_scroll) <= 1
        assert scrolled(17000) == 0
        # Both sticks retain independent continuous speeds when used together.
        reset(); frame(shift=True, ctrl=True)
        state.raw_axes[config['left_stick'][1]] = 32767
        state.raw_axes[config['right_stick'][0]] = 32767
        with patch.object(state, 'focused_window', return_value=window), patch.object(state, 'command', return_value=True) as command:
            for step in range(101):
                state.tick(step / 100, True)
            assert 39 <= sum(key == codes.KEY_RIGHT for key in downs()) <= 41
            assert 18 <= -sum(value for kind, code, value in keyboard.events
                             if kind == codes.EV_REL and code == codes.REL_WHEEL) <= 19
            assert state.keys == {codes.KEY_LEFTSHIFT, codes.KEY_LEFTCTRL}
        frame(); assert not state.keys

        # Missing windows or rejected cursor positioning must not scroll elsewhere.
        reset(); state.raw_axes[config['left_stick'][1]] = 32767
        with patch.object(state, 'focused_window', side_effect=ValueError('No window')), patch.object(state, 'command') as command:
            state.tick(0, True); assert not command.called
        reset(); state.raw_axes[config['left_stick'][1]] = 32767
        with patch.object(state, 'focused_window', return_value=window), patch.object(state, 'command', return_value=False) as command:
            state.tick(0, True)
            command.assert_called_once_with('seat seat0 cursor set -480 270')
        # Retarget held scrolling when the focused window changes.
        other = {'id': 43, 'rect': {'x': 0, 'y': 0, 'width': 600, 'height': 400}}
        reset(); state.raw_axes[config['left_stick'][1]] = 32767
        with patch.object(state, 'focused_window', side_effect=(window, other)), patch.object(state, 'command', return_value=True) as command:
            state.tick(0, True); state.tick(.21, True)
            assert 'seat seat0 cursor set 300 200' in [call.args[0] for call in command.call_args_list]

        # Text navigation uses exactly the trigger modifiers, in all directions.
        for shift, ctrl in itertools.product((False, True), repeat=2):
            modifiers = ({codes.KEY_LEFTSHIFT} if shift else set()) | ({codes.KEY_LEFTCTRL} if ctrl else set())
            for axis, value, key in ((config['right_stick'][0], -32768, codes.KEY_LEFT),
                                     (config['right_stick'][0], 32767, codes.KEY_RIGHT),
                                     (config['right_stick'][1], -32768, codes.KEY_UP),
                                     (config['right_stick'][1], 32767, codes.KEY_DOWN)):
                reset(); state.stick_mode = 'window'; frame(shift=shift, ctrl=ctrl)
                state.raw_axes[axis] = value
                with patch.object(state, 'shortcut', wraps=state.shortcut) as shortcut:
                    state.tick(0, True)
                    shortcut.assert_called_once_with(key, modifiers)
                assert state.keys == modifiers
                state.raw_axes[axis] = 0
                state.tick(.1, True); frame()
                assert not state.keys
        # Triggers change navigation/selection while the stick remains deflected.
        reset(); state.stick_mode = 'window'
        state.raw_axes[config['right_stick'][0]] = 32767
        with patch.object(state, 'shortcut', wraps=state.shortcut) as shortcut:
            state.tick(0, True)
            for index, (shift, ctrl) in enumerate(((True, False), (True, True), (False, True), (False, False)), 1):
                modifiers = ({codes.KEY_LEFTSHIFT} if shift else set()) | ({codes.KEY_LEFTCTRL} if ctrl else set())
                frame(shift=shift, ctrl=ctrl)
                shortcut.reset_mock(); state.tick(index * .06, True)
                assert shortcut.called
                assert all(call.args == (codes.KEY_RIGHT, modifiers) for call in shortcut.call_args_list)
                assert state.keys == modifiers
        # Existing personal profiles using either old action name toggle the context.
        for action in ('selection', 'text_navigation'):
            reset(); state.stick_mode = 'workspace'
            with patch.object(state, 'notify'):
                state.dispatch(action)
                state.tick(0, True)
            assert state.stick_mode == 'window'

        # Continuous selection scales with deflection, not the input polling rate.
        def selected(axis, value, frequency=100):
            reset(); state.stick_mode = 'window'
            state.raw_axes[axis] = value
            for step in range(frequency + 1):
                state.tick(step / frequency, True)
            assert not state.keys
            return sum(key in (codes.KEY_RIGHT, codes.KEY_DOWN) for key in downs())

        horizontal, vertical = config['right_stick']
        with patch.object(state, 'command') as command:
            light = selected(horizontal, 19660)
            fast = selected(horizontal, 32767)
            assert 3 <= light <= 7 and 39 <= fast <= 41, (light, fast)
            assert abs(selected(horizontal, 32767, 30) - fast) <= 1
            assert abs(selected(horizontal, 32767, 60) - fast) <= 1
            assert 9 <= selected(vertical, 32767) <= 11
            reset(); state.stick_mode = 'window'
            state.raw_axes[horizontal] = 17000
            state.tick(0, True); state.tick(.1, True)
            assert not keyboard.events
            state.raw_axes[horizontal] = 32767
            state.tick(.2, True)
            state.raw_axes[horizontal] = 0
            state.tick(.21, True); state.tick(1, True)
            assert downs() == [codes.KEY_RIGHT] and not state.keys
            # Reversing starts a single precise step with no leftover movement.
            state.raw_axes[horizontal] = -32768
            state.tick(1.01, True)
            assert downs() == [codes.KEY_RIGHT, codes.KEY_LEFT]
            # A stalled loop does not accumulate seconds of repeat events.
            keyboard.events.clear(); state.tick(100, True)
            assert sum(key == codes.KEY_LEFT for key in downs()) <= 4
            # Returning to a light deflection immediately slows the movement.
            state.raw_axes[horizontal] = -19660
            keyboard.events.clear()
            for step in range(1, 101):
                state.tick(100 + step / 100, True)
            assert 3 <= sum(key == codes.KEY_LEFT for key in downs()) <= 7
            assert not state.keys and not command.called

        for reason in ('reset', 'disconnect', 'inactive', 'paused', 'passthrough'):
            reset(); state.device = Device(); state.stick_mode = 'workspace'; frame({'X'}, shift=True, ctrl=True)
            frame({'X', 'UP', 'A'}, shift=True, ctrl=True)
            if reason == 'reset': state.reset()
            elif reason == 'disconnect': state.detach()
            elif reason == 'inactive': state.tick(0, False)
            elif reason == 'paused':
                (directory / 'paused').touch(); state.tick(0, True); (directory / 'paused').unlink()
            else:
                with patch.object(state, 'notify'): state.toggle()
            assert not state.keys and state.stick_mode == 'window' and not state.stick_pending
            assert state.motion_time == [None, None] and state.motion_credit == [0, 0]
            assert not state.text_gesture.previous and not state.pending_buttons
            assert not state.dpad_navigation and state.dpad_since is None and state.dpad_credit == 0
        state.device = None

        # Persistent legend, L3 toggling, and no action escaping the overlay.
        reset()
        process = SimpleNamespace(stdin=__import__('io').StringIO(), poll=lambda: None,
                                  terminate=lambda: None, wait=lambda **kw: 0)
        with patch.object(mapper.subprocess, 'Popen', return_value=process):
            frame(buttons=(317,)); assert not state.legend_open()
            frame(); assert state.legend_open() and not keyboard.events
        with patch.object(state, 'command') as command:
            state.device = Device()
            state.raw_axes[config['left_stick'][0]] = 32767
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(0, True)
            assert not command.called and not keyboard.events
            state.raw_axes[config['left_stick'][0]] = 0
            state.raw_axes[config['right_stick'][0]] = 0
        legend = state.legend_text()
        assert all(mapper.ACTION_LABELS[action] in legend for action in expected.values())
        with patch.object(state, 'dispatch') as dispatch:
            frame({'A'}); frame({'UP', 'A'}); state.close_legend(); frame()
            assert not dispatch.called, 'Gesture escaped a closed legend'
        for direction in (None, 'UP', 'DOWN'):
            state.legend = process
            with patch.object(state, 'dispatch') as dispatch:
                frame({'A', 'B'})
                if direction: frame({'A', 'B', direction})
                frame()
                assert not dispatch.called, 'Terminal command escaped the legend'
            state.close_legend()
        state.legend = process
        frame({'DOWN'}, at=100)
        state.close_legend(); before = list(keyboard.events)
        frame({'DOWN'}, at=101); frame(at=102)
        assert keyboard.events == before, 'Navigation escaped a closed legend'
        with patch.object(mapper.subprocess, 'Popen', return_value=process):
            # A fresh stdin is needed after opening the first overlay closed it.
            process.stdin = __import__('io').StringIO()
            frame(buttons=(317,)); frame(); assert state.legend_open()
            frame(buttons=(317,)); frame(); assert not state.legend_open()

        # User profiles cannot bring X back into shortcuts or load old character outputs.
        for changes in ({'chords': {'UP+X': 'copy'}}, {'chords': {'UP+Y': 'KEY_E'}},
                        {'selection_rate': [40, 4]}, {'selection_rate': [0, 40]},
                        {'selection_line_rate': [2, 101]}, {'selection_rate': [4, True]},
                        {'selection_rate': 'fast'}, {'scroll_rate': [18, 1]},
                        {'dpad_rate': [30, 4]}, {'dpad_line_rate': [4, True]},
                        {'dpad_repeat_delay': 0}, {'dpad_acceleration_time': 0}):
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
        print(f'Passed: {len(expected)} named shortcuts, {orders} face-first press/release orders, unlimited prefixes, terminal-only Ctrl+C/Z/D and pair-prefix guards, wrong-order/simultaneous suppression, immediate/accelerated D-pad navigation, Xbox codes, Backspace holds, modifier restoration, terminal guards, shared contexts/both-stick neutral switch, scroll targeting/direction/speed/modifiers/failure handling, text navigation/speed, legend capture, lifecycle reset and profile validation.')


if __name__ == '__main__':
    main()
