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
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
# xpad reports Xbox A/B/X/Y as BTN_A/B/X/Y. The historical Linux aliases
# put BTN_X at BTN_NORTH (0x133), and BTN_Y at BTN_WEST (0x134).
# Keep this fixture independent of FACE_NAMES and the loaded configuration.
XBOX_FACE_CODES = {'SELECT': 314, 'A': 0x130, 'B': 0x131, 'X': 0x133, 'Y': 0x134}
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
        'UP+A': 'copy', 'DOWN+A': 'paste', 'LEFT+A': 'undo', 'RIGHT+A': 'redo',
        'UP+LEFT+A': 'cut', 'UP+RIGHT+A': 'select_all', 'DOWN+LEFT+A': 'find', 'DOWN+RIGHT+A': 'save',
        'UP+B': 'close', 'DOWN+B': 'equalize', 'LEFT+B': 'back', 'RIGHT+B': 'forward',
        'UP+LEFT+B': 'document_home', 'UP+RIGHT+B': 'document_end',
        'DOWN+LEFT+B': 'previous_match', 'DOWN+RIGHT+B': 'next_match',
        'SELECT+A': 'fullscreen', 'SELECT+B': 'floating', 'SELECT+Y': 'layout', 'SELECT+X': 'split',
        'A+B': 'interrupt', 'UP+A+B': 'suspend_job', 'DOWN+A+B': 'end_input',
    }
    assert profile['chords'] == expected
    assert profile['actions']['BTN_THUMBL'] == 'left_stick_context'
    assert profile['actions']['BTN_THUMBR'] == 'right_stick_context'
    assert profile['hold_actions'] == {'BTN_MODE': 'legend', 'BTN_START': 'file_manager'}
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
        for face, output in (('A', codes.KEY_ENTER), ('B', codes.KEY_ESC)):
            reset(); frame({face}); frame({face})
            assert not keyboard.events
            frame()
            assert keyboard.events == [(codes.EV_KEY, output, 1), (codes.EV_KEY, output, 0)]
        for ctrl in (False, True):
            reset(); frame({'Y'}, ctrl=ctrl)
            assert downs() == ([codes.KEY_LEFTCTRL] if ctrl else []) + [codes.KEY_SPACE]
            frame({'Y'}, ctrl=ctrl, at=60)
            assert downs().count(codes.KEY_SPACE) == 1 and codes.KEY_SPACE in state.keys
            frame(ctrl=ctrl)
            assert codes.KEY_SPACE not in state.keys
            frame(); assert not state.keys
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
                if presses[0] not in XBOX_FACE_CODES or 'SELECT' in tokens and presses[0] != 'SELECT':
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
        # Rolling A/B gestures cannot become a different shortcut during release.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            for held in ({'A'}, {'A', 'UP'}, {'A'}, {'A', 'B'}, {'B'}, set()):
                frame(held)
            assert not keyboard.events and not dispatch.called

        # Select has an unlimited prefix, consumes its picker action, and
        # suppresses immediate Space/Backspace for both release orders.
        for face, action in (('A','fullscreen'),('B','floating'),('Y','layout'),('X','split')):
            for release_select_first in (False, True):
                reset()
                with patch.object(state, 'dispatch') as dispatch:
                    frame({'SELECT'}, at=0); frame({'SELECT'}, at=60)
                    frame({'SELECT',face}, at=61); frame({'SELECT',face}, at=120)
                    assert not keyboard.events and not dispatch.called
                    remainder={face} if release_select_first else {'SELECT'}
                    frame(remainder, at=121); frame(remainder, at=180)
                    assert not keyboard.events and not dispatch.called
                    frame(at=181); dispatch.assert_called_once_with(action)
            for simultaneous in (False, True):
                reset()
                with patch.object(state, 'dispatch') as dispatch:
                    if not simultaneous: frame({face})
                    frame({'SELECT',face}); frame({'SELECT',face}, at=60)
                    frame({'SELECT'}); frame()
                    assert not dispatch.called and not state.keys
                    assert all(code in {codes.KEY_SPACE,codes.KEY_BACKSPACE} for kind,code,value in keyboard.events)
                    if simultaneous: assert not keyboard.events
        for sequence in (({'SELECT'},{'SELECT','UP'},set()),
                         ({'SELECT'},{'SELECT','A'},{'SELECT'},{'SELECT','B'},set()),
                         ({'SELECT'},{'SELECT','X','Y'},set())):
            reset()
            with patch.object(state,'dispatch') as dispatch:
                for held in sequence: frame(held)
                assert not keyboard.events and not dispatch.called and not state.keys
        # X stays independent even beside a shortcut; it is never deferred or re-pressed.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame({'X', 'A'}); frame({'X', 'UP', 'A'}); frame({'X'}); frame()
            dispatch.assert_called_once_with('copy')
        assert downs() == [codes.KEY_BACKSPACE]

        # A face prefix has no timeout; directions alone act on press, not release.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame({'A'}, at=0); frame({'A'}, at=60)
            assert not keyboard.events and not dispatch.called
            frame({'A', 'UP'}, at=61); frame({'A', 'UP'}, at=90)
            assert not keyboard.events and not dispatch.called
            frame(at=91); dispatch.assert_called_once_with('copy')
        for direction, key in [('UP', codes.KEY_UP), ('DOWN', codes.KEY_DOWN),
                               ('LEFT', codes.KEY_LEFT), ('RIGHT', codes.KEY_RIGHT)]:
            reset(); frame({direction}, at=0)
            assert downs() == [key] and not state.keys
            frame({direction}, at=.39); assert downs() == [key]
            frame(at=.4); assert downs() == [key] and not state.dpad_navigation

        # Wrong-order and simultaneous controls cannot execute a named shortcut
        # or leak Enter/Escape, even if held after the direction is released.
        for chord in expected:
            if 'SELECT' in chord:
                continue  # Select ordering is checked separately below.
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
                    assert not set(downs()) & {codes.KEY_ENTER, codes.KEY_ESC, codes.KEY_SPACE}

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
            'back': ('KEY_LEFT', {'KEY_LEFTALT'}), 'forward': ('KEY_RIGHT', {'KEY_LEFTALT'}),
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
                                'file_manager': 'exec thunar', 'screenshot': 'exec minion-screenshot'}.items():
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
        # Select toggles the owned picker; completed/cancelled pickers reopen,
        # and mapper lifecycle changes clean up a visible picker.
        reset()
        picker = Mock()
        picker.poll.return_value = None
        with patch.object(mapper.subprocess, 'Popen', return_value=picker) as popen:
            frame(buttons=(314,)); frame()
            popen.assert_called_once_with(['minion-window-picker'])
            assert state.picker is picker
            frame(buttons=(314,)); frame()
            picker.terminate.assert_called_once_with()
            assert state.picker is None and popen.call_count == 1
            picker.poll.return_value = 0
            frame(buttons=(314,)); frame()
            frame(buttons=(314,)); frame()
            assert popen.call_count == 3
            picker.poll.return_value = None
            state.reset()
            assert picker.terminate.call_count == 2 and state.picker is None
        # Start waits for release even on a long hold; a late Select overlap
        # must still suppress both launches and retain passthrough priority.
        for duration, action in ((.74, 'terminal'), (.75, 'file_manager'), (5, 'file_manager')):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                frame(buttons=(315,), at=10)
                frame(buttons=(315,), at=10 + duration)
                assert not dispatch.called
                frame(at=10 + duration)
                dispatch.assert_called_once_with(action)
                frame(at=20)
                dispatch.assert_called_once_with(action)
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame(buttons=(315,), at=10)
            frame(at=11)  # No intermediate held frame.
            dispatch.assert_called_once_with('file_manager')
        for first in (314, 315):
            for duration in (.1, 1):
                for last in (314, 315):
                    reset()
                    with patch.object(state, 'dispatch') as dispatch, patch.object(state, 'toggle') as toggle:
                        frame(buttons=(first,), at=10)
                        frame(buttons=(first,), at=12)
                        frame(buttons=(314, 315), at=13)
                        frame(buttons=(last,), at=13 + duration)
                        frame(at=15)
                        assert not dispatch.called
                        assert toggle.call_count == (1 if duration >= .75 else 0)
        for mode in ('paused', 'inactive', 'reset', 'passthrough'):
            reset()
            with patch.object(state, 'dispatch') as dispatch:
                frame(buttons=(315,), at=10)
                if mode == 'paused':
                    (directory / 'paused').touch()
                elif mode == 'reset':
                    state.reset()
                elif mode == 'passthrough':
                    state.mode = 'passthrough'
                frame(at=12, active=mode != 'inactive')
                if mode == 'paused':
                    (directory / 'paused').unlink()
                assert not dispatch.called

        # Menu hold fires once at the threshold, consumes release, and short
        # presses stay distinct even if a release frame arrives after the deadline.
        reset()
        with patch.object(state, 'dispatch') as dispatch:
            frame(buttons=(316,), at=10)
            frame(buttons=(316,), at=10.74); assert not dispatch.called
            frame(buttons=(316,), at=10.75); dispatch.assert_called_once_with('legend')
            frame(buttons=(316,), at=15); frame(at=16)
            dispatch.assert_called_once_with('legend')
            frame(buttons=(316,), at=20); frame(at=20.2)
            assert dispatch.call_args.args == ('launcher',) and dispatch.call_count == 2
            frame(buttons=(316,), at=30); frame(at=31)
            assert dispatch.call_args.args == ('legend',) and dispatch.call_count == 3
        for button, step in ((310, -1), (311, 1)):
            reset()
            with patch.object(state, 'workspace') as workspace:
                frame(buttons=(button,)); assert not workspace.called
                frame(); workspace.assert_called_once_with(step)
        normalize = mapper.workspace_policy['normalize']
        with patch.object(mapper.subprocess, 'check_output', side_effect=[
                json.dumps([{'num': 1, 'name': '1'}, {'num': 3, 'name': '3: code'},
                            {'num': 5, 'name': '5'}, {'num': -1, 'name': 'chat'}]),
                '[{"success":true},{"success":true}]']) as output:
            normalize()
            output.assert_called_with(['swaymsg', '-r', 'rename workspace "3: code" to "2: code"; rename workspace "5" to "3"'])
        with patch.object(mapper.subprocess, 'check_output', return_value=json.dumps([
                {'num': 1, 'name': '1'}, {'num': 2, 'name': '2'}])) as output:
            normalize()
            assert output.call_count == 1
        # Explicit duplicate prefixes retain their personal naming scheme.
        with patch.object(mapper.subprocess, 'check_output', return_value=json.dumps([
                {'num': 3, 'name': '3: a'}, {'num': 3, 'name': '3: b'}])) as output:
            normalize()
            assert output.call_count == 1

        # Forward navigation offers N+1; backward wrap from 1 skips that empty slot.
        # Only occupied workspaces extend N; a late Shift moves without following.
        assert config['workspace_numbers'] is None
        for current, highest, button, target, shift in (
                (3, 3, 311, 4, False), (4, 3, 311, 1, False),
                (1, 3, 310, 3, False), (3, 3, 310, 2, False),
                (4, 3, 310, 3, False), (1, 1, 310, 1, False),
                (1, 3, 311, 2, False), (2, 3, 311, 3, False),
                (9, 9, 311, 10, False), (1500, 1500, 311, 1501, False),
                (1, 0, 311, 1, False), (1, 0, 310, 1, False),
                (4, 3, 311, 1, True), (1, 3, 310, 3, True),
                (4, 3, 310, 3, True), (1, 1, 310, 1, True),
                (3, 3, 311, 4, True),
                (7, 3, 311, 1, False), (7, 3, 310, 4, False),
                (-1, 3, 310, 1, False), (-1, 3, 311, 1, False)):
            reset()
            workspaces = [{'type': 'workspace', 'num': highest, 'name': str(highest),
                           'nodes': [{'focused': current == highest}]}] if highest else []
            if current != highest:
                workspaces.append({'type': 'workspace', 'num': current, 'name': str(current),
                                   'focused': True})
            tree = {'nodes': workspaces}
            with patch.object(mapper, 'ipc', return_value=tree) as ipc, patch.object(state, 'command') as command:
                frame(buttons=(button,)); frame(buttons=(button,))
                assert not command.called and not ipc.called
                frame(shift=shift)
                operation = 'move container to workspace number' if shift else 'workspace number'
                command.assert_called_once_with(f'{operation} {target}')
                frame()
                assert command.call_count == 1
        # Explicit personal workspace lists retain their existing circular order.
        config['workspace_numbers'] = [1, 3, 8]
        for current, step, target in ((8, 1, 1), (1, -1, 8), (2, 1, 1), (2, -1, 8)):
            reset()
            with patch.object(mapper, 'ipc', return_value=[{'num': current, 'focused': True}]), patch.object(state, 'command') as command:
                state.workspace(step)
                command.assert_called_once_with(f'workspace number {target}')
        config['workspace_numbers'] = None
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
        assert state.stick_modes == ['scroll', 'windows']
        with patch.object(state, 'notify'), patch.object(state, 'command') as command:
            # Default movement scrolls and focuses windows in the same frame.
            state.raw_axes[config['left_stick'][0]] = -32768
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(0, True)
            assert any(kind == codes.EV_REL for kind, code, value in keyboard.events)
            command.assert_called_once_with('focus right')
            frame(buttons=(318,)); assert state.stick_pending == [None, None]
            frame(); assert state.stick_pending == [None, 'resize']
            command.reset_mock(); keyboard.events.clear(); state.tick(.1, True)
            assert any(kind == codes.EV_REL for kind, code, value in keyboard.events)
            assert not command.called and state.stick_modes == ['scroll', 'windows']
            # Centering only the right stick applies its change immediately.
            state.raw_axes[config['right_stick'][0]] = 0
            state.tick(.2, True)
            assert state.stick_modes == ['scroll', 'resize'] and state.stick_pending == [None, None]
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(.3, True); command.assert_called_with('resize grow width 5 ppt')
            frame(buttons=(317,)); frame()
            assert state.stick_pending == ['text', None]
            command.reset_mock(); state.tick(1, True)
            command.assert_called_once_with('resize grow width 5 ppt')
            assert state.stick_modes == ['scroll', 'resize']
            state.raw_axes[config['left_stick'][0]] = 0
            state.tick(1.1, True)
            assert state.stick_modes == ['text', 'resize']
            state.raw_axes[config['left_stick'][0]] = 32767
            keyboard.events.clear(); state.tick(1.2, True)
            assert codes.KEY_RIGHT in downs()
            # Right can return to Windows while left keeps navigating text.
            frame(buttons=(318,)); frame()
            assert state.stick_pending == [None, 'windows']
            keyboard.events.clear(); command.reset_mock(); state.tick(1.3, True)
            assert codes.KEY_RIGHT in downs() and not command.called
            state.raw_axes[config['right_stick'][0]] = 0
            state.tick(1.4, True)
            assert state.stick_modes == ['text', 'windows']
            state.raw_axes[config['left_stick'][0]] = 0
            state.raw_axes[config['right_stick'][0]] = -32768
            state.tick(1.5, True); command.assert_called_with('focus left')
            frame(shift=True)
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(1.6, True); command.assert_called_with('move right')
            frame(); frame(buttons=(317,)); frame(); state.tick(1.7, True)
            assert state.stick_modes == ['scroll', 'windows'] and state.stick_pending == [None, None]
            # A second click cancels only that stick's pending change.
            frame(buttons=(318,)); frame()
            assert state.stick_pending == [None, 'resize']
            frame(buttons=(318,)); frame()
            assert state.stick_pending == [None, None] and state.stick_modes == ['scroll', 'windows']
        assert (directory / 'stick-mode').read_text().strip() == 'L:Scroll R:Windows'
        for left, right in itertools.product(*mapper.STICK_MODES):
            reset(); state.stick_modes = [left, right]
            state.raw_axes[config['left_stick'][0]] = 32767
            state.raw_axes[config['right_stick'][0]] = 32767
            with patch.object(state, 'command') as command:
                state.tick(0, True)
            expected_commands = ['focus right' if right == 'windows' else 'resize grow width 5 ppt']
            assert [call.args[0] for call in command.call_args_list] == expected_commands
            assert any(kind == codes.EV_REL for kind, code, value in keyboard.events) == (left == 'scroll')
            assert (codes.KEY_RIGHT in downs()) == (left == 'text')
            assert not state.keys
        reset()

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
                with patch.object(state, 'focused_application', return_value='gui'), patch.object(
                        state, 'command', return_value=True) as command:
                    state.raw_axes[axis] = value
                    state.tick(0, True)
                    command.assert_not_called()
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
                    assert not command.called and not keyboard.events
                frame(); assert not state.keys
        reset()
        with patch.object(state, 'focused_window') as focused, patch.object(state, 'command') as command:
            state.scroll('down', 3)
            focused.assert_not_called()
            command.assert_not_called()
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
        # Scrolling and window movement operate concurrently in the default layout.
        reset(); frame(shift=True, ctrl=True)
        state.raw_axes[config['left_stick'][1]] = 32767
        state.raw_axes[config['right_stick'][0]] = 32767
        with patch.object(state, 'focused_application', return_value='gui'), patch.object(state, 'command') as command:
            for step in range(101):
                state.tick(step / 100, True)
            assert codes.KEY_RIGHT not in downs()
            assert 18 <= -sum(value for kind, code, value in keyboard.events
                             if kind == codes.EV_REL and code == codes.REL_WHEEL) <= 19
            assert state.keys == {codes.KEY_LEFTSHIFT, codes.KEY_LEFTCTRL}
            assert 2 <= command.call_count <= 6
            assert all(call.args == ('move right',) for call in command.call_args_list)
        frame(); assert not state.keys

        # Held scrolling needs no focused window or cursor-positioning command.
        reset(); state.raw_axes[config['left_stick'][1]] = 32767
        with patch.object(state, 'focused_window', side_effect=ValueError('No window')), patch.object(state, 'command') as command:
            state.tick(0, True); state.tick(.1, True); state.tick(.2, True)
            command.assert_not_called()
            assert sum(value for kind, code, value in keyboard.events
                       if kind == codes.EV_REL and code == codes.REL_WHEEL) == -4

        # Text navigation uses exactly the trigger modifiers, in all directions.
        for shift, ctrl in itertools.product((False, True), repeat=2):
            modifiers = ({codes.KEY_LEFTSHIFT} if shift else set()) | ({codes.KEY_LEFTCTRL} if ctrl else set())
            for axis, value, key in ((config['left_stick'][0], -32768, codes.KEY_LEFT),
                                     (config['left_stick'][0], 32767, codes.KEY_RIGHT),
                                     (config['left_stick'][1], -32768, codes.KEY_UP),
                                     (config['left_stick'][1], 32767, codes.KEY_DOWN)):
                reset(); state.stick_modes = ['text', 'windows']; frame(shift=shift, ctrl=ctrl)
                state.raw_axes[axis] = value
                with patch.object(state, 'shortcut', wraps=state.shortcut) as shortcut:
                    state.tick(0, True)
                    shortcut.assert_called_once_with(key, modifiers)
                assert state.keys == modifiers
                state.raw_axes[axis] = 0
                state.tick(.1, True); frame()
                assert not state.keys
        # Triggers change navigation/selection while the stick remains deflected.
        reset(); state.stick_modes = ['text', 'windows']
        state.raw_axes[config['left_stick'][0]] = 32767
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
            reset(); state.stick_modes = ['text', 'resize']
            with patch.object(state, 'notify'):
                state.dispatch(action)
                state.tick(0, True)
            assert state.stick_modes == ['scroll', 'windows']

        # Continuous selection scales with deflection, not the input polling rate.
        def selected(axis, value, frequency=100):
            reset(); state.stick_modes = ['text', 'windows']
            state.raw_axes[axis] = value
            for step in range(frequency + 1):
                state.tick(step / frequency, True)
            assert not state.keys
            return sum(key in (codes.KEY_RIGHT, codes.KEY_DOWN) for key in downs())

        horizontal, vertical = config['left_stick']
        with patch.object(state, 'command') as command:
            light = selected(horizontal, 19660)
            fast = selected(horizontal, 32767)
            assert 3 <= light <= 7 and 39 <= fast <= 41, (light, fast)
            assert abs(selected(horizontal, 32767, 30) - fast) <= 1
            assert abs(selected(horizontal, 32767, 60) - fast) <= 1
            assert 9 <= selected(vertical, 32767) <= 11
            reset(); state.stick_modes = ['text', 'windows']
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

        # Lid-close consumes physical input instead of releasing it to apps,
        # releases virtual keys/overlays, and suppresses all gesture paths.
        reset()
        device = Mock()
        state.device = device
        frame({'X'}, shift=True, ctrl=True)
        assert state.keys
        with patch.object(state, 'lid_closed', return_value=True), \
                patch.object(state, 'dispatch') as dispatch, patch.object(state, 'workspace') as workspace, \
                patch.object(state, 'command') as command, patch.object(state, 'toggle') as toggle:
            state.tick(200, True)
            assert not state.keys and state.grabbed and not state.ready and state.lid_blocked
            device.ungrab.assert_not_called()
            keyboard.events.clear()
            for button in (310, 311, 314, 315, 316, 317, 318):
                frame(buttons=(button,), at=201)
                frame(at=203)
            frame({'X', 'Y', 'UP'}, shift=True, ctrl=True)
            state.raw_axes[config['left_stick'][1]] = 32767
            state.raw_axes[config['right_stick'][0]] = 32767
            state.tick(204, True)
            frame(buttons=(314, 315), at=205); frame(at=207)
            assert not keyboard.events
            assert not dispatch.called and not workspace.called and not command.called and not toggle.called
            # Even passthrough gets a temporary grab while the lid is closed.
            state.mode = 'passthrough'
            state.grabbed = False
            state.tick(208, True)
            device.grab.assert_called_once_with()
            assert state.grabbed and state.mode == 'passthrough'
            state.mode = 'desktop'
        # A held control during reopening cannot generate a key or release action.
        keyboard.events.clear()
        frame({'X'})
        state.tick(209, True)
        assert not state.ready and not keyboard.events
        for axis in config['left_stick'] + config['right_stick']:
            state.raw_axes[axis] = 0
        frame(); state.tick(210, True)
        assert state.ready and not keyboard.events
        frame({'X'}); assert codes.KEY_BACKSPACE in downs()
        frame()
        state.device = None

        for reason in ('reset', 'disconnect', 'inactive', 'paused', 'passthrough'):
            reset(); state.device = Device(); state.stick_modes = ['text', 'resize']; frame({'X'}, shift=True, ctrl=True)
            state.stick_pending = ['scroll', None]
            frame({'X', 'UP', 'A'}, shift=True, ctrl=True)
            frame({'SELECT', 'Y'}, shift=True, ctrl=True)
            if reason == 'reset': state.reset()
            elif reason == 'disconnect': state.detach()
            elif reason == 'inactive': state.tick(0, False)
            elif reason == 'paused':
                (directory / 'paused').touch(); state.tick(0, True); (directory / 'paused').unlink()
            else:
                with patch.object(state, 'notify'): state.toggle()
            assert not state.keys and state.stick_modes == ['scroll', 'windows'] and state.stick_pending == [None, None]
            assert state.motion_time == [None, None] and state.motion_credit == [0, 0]
            assert not state.text_gesture.previous and not state.pending_buttons
            assert not state.select_gesture.previous and not state.select_in_legend
            assert not state.button_since
            assert not state.dpad_navigation and state.dpad_since is None and state.dpad_credit == 0
        state.device = None

        # Persistent legend on Menu hold, short-press dismissal and isolation.
        reset()
        process = SimpleNamespace(stdin=__import__('io').StringIO(), poll=lambda: None,
                                  terminate=lambda: None, wait=lambda **kw: 0)
        def menu_hold(at):
            frame(buttons=(316,), at=at)
            frame(buttons=(316,), at=at + .8)
            frame(at=at + .9)
        with patch.object(mapper.subprocess, 'Popen', return_value=process):
            frame(buttons=(316,), at=200); assert not state.legend_open()
            frame(buttons=(316,), at=200.8)
            assert state.legend_open() and not keyboard.events
            frame(at=201); assert state.legend_open() and state.launcher is None
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
            frame({'SELECT'}); frame({'SELECT', 'Y'}); state.close_legend(); frame()
            assert not dispatch.called and not state.keys, 'Layout gesture escaped the legend'
        state.legend = process
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
            menu_hold(300); assert state.legend_open()
            frame(buttons=(316,), at=301); frame(at=301.2)
            assert not state.legend_open() and state.launcher is None
            process.stdin = __import__('io').StringIO()
            menu_hold(302); assert state.legend_open()
            menu_hold(304); assert not state.legend_open() and state.launcher is None
        # A second Menu tap closes only the launcher owned by this mapper.
        with patch.object(mapper.subprocess, 'Popen', return_value=process) as popen:
            frame(buttons=(316,), at=306); frame(at=306.2)
            assert state.launcher is process
            frame(buttons=(316,), at=307); frame(at=307.2)
            assert state.launcher is None and popen.call_count == 1
            # Holding Menu replaces the owned launcher with the legend.
            frame(buttons=(316,), at=308); frame(at=308.2)
            process.stdin = __import__('io').StringIO()
            menu_hold(309)
            assert state.launcher is None and state.legend_open()
            state.reset()
            assert not state.legend_open() and state.launcher is None and not state.button_since

        # User profiles cannot bring X back into shortcuts or load old character outputs.
        for changes in ({'chords': {'UP+X': 'copy'}}, {'chords': {'UP+Y': 'copy'}}, {'chords': {'SELECT+UP': 'copy'}}, {'chords': {'UP+Y': 'KEY_E'}},
                        {'selection_rate': [40, 4]}, {'selection_rate': [0, 40]},
                        {'selection_line_rate': [2, 101]}, {'selection_rate': [4, True]},
                        {'selection_rate': 'fast'}, {'scroll_rate': [18, 1]},
                        {'dpad_rate': [30, 4]}, {'dpad_line_rate': [4, True]},
                        {'dpad_repeat_delay': 0}, {'dpad_acceleration_time': 0},
                        {'action_hold': 0}, {'hold_actions': {'BTN_MODE': 'unknown'}},
                        {'hold_actions': {'BTN_THUMBL': 'unknown'}},
                        {'hold_actions': {'BTN_TL': 'legend'}},
                        {'hold_actions': {'BTN_SELECT': 'legend'}},
                        {'workspace_numbers': []}, {'workspace_numbers': [1, 1]},
                        {'workspace_numbers': [0, 1]}, {'workspace_numbers': [True, 2]},
                        {'workspace_numbers': 'all'}, {'workspace_numbers': [[1]]}):
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
        print(f'Passed: {len(expected)} named shortcuts, {orders} face-first press/release orders, unlimited prefixes, terminal-only Ctrl+C/Z/D and pair-prefix guards, wrong-order/simultaneous suppression, immediate/accelerated D-pad navigation, Xbox codes, Backspace/Space holds and Select-first layout actions, modifier restoration, terminal guards, workspace compaction, dynamic wraparound and explicit-list compatibility, independent stick modes/individual neutral switches, Menu hold and launcher toggling, pointer-preserving wheel scrolling/direction/speed/modifiers, text navigation/speed, legend capture, lifecycle reset and profile validation.')


if __name__ == '__main__':
    main()
