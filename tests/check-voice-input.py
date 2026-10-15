#!/usr/bin/env python3
"""Check verified dictation installation and personal-setting retention in isolation."""
import hashlib
import importlib.util
import importlib.machinery
import json
from pathlib import Path
import tempfile
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch
import tomllib

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('voice', PROJECT / 'setup/desktop/voice.py')
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)
loader = importlib.machinery.SourceFileLoader('voice_control', str(voice.HERE / 'minion-voice'))
control_spec = importlib.util.spec_from_loader(loader.name, loader)
control = importlib.util.module_from_spec(control_spec)
loader.exec_module(control)


def main():
    config = tomllib.loads((voice.HERE / 'voxtype.toml').read_text())
    assert config['whisper']['language'] == 'en'
    assert config['whisper']['mode'] == 'local' and not config['whisper']['translate']
    assert not config['hotkey']['enabled'] and not config['output']['auto_submit']
    assert config['output']['driver_order'] == ['wtype', 'clipboard']
    def keyboard(layout, identifier=control.KEYBOARD, vendor=1):
        return dict(type='keyboard', identifier=identifier, vendor=vendor, xkb_active_layout_name=layout)
    assert control.language_for([keyboard('English (US)')]) == 'en'
    assert control.language_for([keyboard('Russian'), keyboard('English (US)', 'other', 123)]) == 'ru'
    assert control.language_for([keyboard('Russian', 'other')]) == 'ru'
    for inputs in ([], [keyboard('German')], [keyboard('Russian', 'one'), keyboard('English (US)', 'two')]):
        try:
            control.language_for(inputs)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsupported or ambiguous layout accepted')
    with tempfile.TemporaryDirectory(prefix='minion-voice-test-') as temporary:
        root = Path(temporary)
        assets = root / 'assets'; assets.mkdir()
        artifacts = {}
        for kind, data in [('runtime', b'test executable'), ('model', b'test multilingual model')]:
            name = kind + '.bin'
            (assets / name).write_bytes(data)
            artifacts[kind] = dict(filename=name, size=len(data),
                                   sha256=hashlib.sha256(data).hexdigest(), url='https://invalid.example/' + name)
        user = SimpleNamespace(pw_dir=str(root / 'home'), pw_uid=1000, pw_gid=1000)
        with patch.object(voice, 'ARTIFACTS', artifacts), patch.object(voice.os, 'geteuid', return_value=0), \
                patch.object(voice.os, 'chown'), patch.object(voice.urllib.request, 'urlopen', side_effect=AssertionError('Network used')):
            voice.install(user, assets, root)
            binary = root / 'usr/local/bin/voxtype'
            model = root / 'usr/local/share/minion/voice/model.bin'
            assert binary.read_bytes() == b'test executable' and binary.stat().st_mode & 0o777 == 0o755
            assert model.read_bytes() == b'test multilingual model'
            personal = Path(user.pw_dir) / '.config/voxtype/config.toml'
            assert personal.stat().st_mode & 0o777 == 0o600
            personal.write_text('# personal\n[whisper]\nlanguage="ru"\n')
            before = {p: p.stat().st_mtime_ns for p in (binary, model, personal)}
            voice.install(user, assets, root)
            assert before == {p: p.stat().st_mtime_ns for p in before}
            assert personal.read_text().startswith('# personal')
            binary.write_bytes(b'personal executable')
            try:
                voice.install(user, assets, root)
            except ValueError as error:
                assert 'modified' in str(error)
            else:
                raise AssertionError('Modified binary overwritten')
            assert binary.read_bytes() == b'personal executable'

        # A failed download must neither replace the old target nor leave staging files.
        target = root / 'payload'; target.write_bytes(b'previous')
        artifact = artifacts['runtime']
        for data in (b'wrong checksum!', b'oversized payload for this artifact'):
            (assets / artifact['filename']).write_bytes(data)
            previous = voice.digest(target)
            try:
                voice.install_payload(artifact, target, previous, assets)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid download accepted')
            assert target.read_bytes() == b'previous'
        (assets / artifact['filename']).write_bytes(b'test executable')
        voice.install_payload(artifact, target, voice.digest(target), assets)
        assert target.read_bytes() == b'test executable'
        target.unlink(); target.symlink_to(model)
        try:
            voice.install_payload(artifact, target, asset_dir=assets)
        except ValueError:
            pass
        else:
            raise AssertionError('Symlink accepted')

        runtime = root / 'runtime'
        (runtime / 'voxtype').mkdir(parents=True)
        (runtime / 'minion-voice').mkdir()
        state = runtime / 'voxtype/state'; state.write_text('idle')
        language = ['English (US)']
        locked = [False]
        commands = []
        def fake_run(*command):
            commands.append(command)
            if command[0] == 'swaymsg': return json.dumps([keyboard(language[0])])
            if command[:3] == ('systemctl', '--user', 'show'): return 'active' if locked[0] else 'inactive'
            if command[:3] == ('systemctl', '--user', 'restart'): state.write_text('idle')
            if command == ('voxtype', 'record', 'start'): state.write_text('recording')
            if command == ('voxtype', 'record', 'cancel'): state.write_text('idle')
            if command == ('voxtype', 'record', 'stop'): state.write_text('transcribing')
            return ''
        with patch.object(control, 'run', side_effect=fake_run):
            environment = runtime / 'minion-voice/language.env'
            control.control('toggle', runtime)
            assert environment.read_text() == 'VOXTYPE_LANGUAGE=en\n'
            language[0] = 'Russian'
            control.control('toggle', runtime)
            assert commands[-1] == ('voxtype', 'record', 'stop')
            assert environment.read_text() == 'VOXTYPE_LANGUAGE=en\n'  # Frozen for the recording.
            before = len(commands)
            control.control('toggle', runtime)
            assert len(commands) == before  # Busy transcription consumes duplicate activations.
            control.control('cancel', runtime)
            control.control('start', runtime)
            assert environment.read_text() == 'VOXTYPE_LANGUAGE=ru\n'
            control.control('cancel', runtime)
            commands.clear()
            control.control('start', runtime)
            assert not any(c[:3] == ('systemctl', '--user', 'restart') for c in commands)
            control.control('cancel', runtime)
            locked[0] = True
            commands.clear()
            control.control('toggle', runtime)
            assert not any(c[0] in ('voxtype', 'swaymsg') for c in commands)
        # Cancelling waits for an in-flight activation instead of being lost
        # through the nonblocking coalescing used for repeated toggles.
        for action, expected in [('cancel', control.fcntl.LOCK_EX),
                                 ('toggle', control.fcntl.LOCK_EX | control.fcntl.LOCK_NB)]:
            with patch.dict(os.environ, XDG_RUNTIME_DIR=str(runtime)), \
                    patch.object(sys, 'argv', ['minion-voice', action]), \
                    patch.object(control.fcntl, 'flock') as flock, patch.object(control, 'control') as dispatch:
                control.main()
                assert flock.call_args.args[1] == expected
                dispatch.assert_called_once_with(action, runtime)
    print('Passed: verified downloads/upgrades, personal defaults/reruns, US/RU layout selection, per-recording language freeze, idle-only restarts, busy/lock guards and cancellation.')


if __name__ == '__main__':
    main()
