#!/usr/bin/env python3
"""Check audio SDK installation boundaries and retention of personal projects."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_tooling', PROJECT / 'setup/development/audio.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)

with tempfile.TemporaryDirectory(prefix='minion-audio-check-') as temporary:
    home = Path(temporary)
    source = audio.SOURCES[0]
    sdk = home / 'sdk'
    checkout = sdk / source['name']
    checkout.mkdir(parents=True)
    personal = checkout / 'personal.cpp'
    personal.write_text('personal code\n')
    for head, status in ((source['commit'], ' M personal.cpp'), ('another-revision', '')):
        with patch.object(audio, 'git', side_effect=[head, status]), \
             patch.object(audio, 'run', side_effect=AssertionError('Modified SDK triggered a download')):
            try:
                audio.checkout(sdk, source)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Modified or foreign SDK was accepted')
        assert personal.read_text() == 'personal code\n'

    data = home / 'data'
    extension = data / 'SuperCollider/Extensions/VSTPlugin'
    extension.mkdir(parents=True)
    plugin = extension / 'plugin.so'
    plugin.write_bytes(b'installed plugin')
    marker = extension / '.minion-install.json'
    marker.write_text(json.dumps(dict(sources=audio.SOURCES, files=audio.hashes(extension))))
    starter = home / 'Projects/synth-lab'
    starter.mkdir(parents=True)
    edited = starter / 'Synth.cpp'
    edited.write_text('my synthesizer\n')
    with patch.object(audio.os, 'geteuid', return_value=1000), \
         patch.object(audio.Path, 'home', return_value=home), \
         patch.dict(os.environ, {'XDG_DATA_HOME': str(data), 'XDG_CACHE_HOME': str(home / 'cache')}), \
         patch.object(audio.shutil, 'which', return_value='/fixture/tool'), \
         patch.object(audio, 'checkout', side_effect=lambda base, src: base / src['name']), \
         patch.object(audio, 'run', side_effect=AssertionError('Unchanged installation rebuilt')), \
         contextlib.redirect_stdout(io.StringIO()):
        audio.install()
        assert edited.read_text() == 'my synthesizer\n'
        assert plugin.read_bytes() == b'installed plugin'
        plugin.write_bytes(b'my modified extension')
        try:
            audio.install()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Modified extension was overwritten')
        assert plugin.read_bytes() == b'my modified extension'

with patch.object(audio.os, 'geteuid', return_value=0):
    try:
        audio.install()
    except SystemExit:
        pass
    else:
        raise AssertionError('User builds accepted root execution')

print('Passed: SDK revision/dirty checks, modified extension refusal, project retention, unchanged reruns and user-only builds.')
