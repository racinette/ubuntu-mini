#!/usr/bin/env python3
"""Check popup deduplication, replacement, expiry and retained personal styling."""
import importlib.machinery
import importlib.util
import os
import io
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

DESKTOP = Path(__file__).resolve().parents[1] / 'setup/desktop'


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main():
    popup = load('layout_popup', DESKTOP / 'minion-layout-popup')
    settings = load('popup_settings', DESKTOP / 'notifications.py')
    def keyboard(name='English (US)', identifier=popup.KEYBOARD, vendor=1):
        return dict(type='keyboard', identifier=identifier, vendor=vendor,
                    xkb_layout_names=['English (US)', 'Russian'], xkb_active_layout_name=name)
    physical = keyboard()
    virtual = dict(keyboard('Russian', 'gamepad', 4617), name='Minion gamepad keyboard')
    assert popup.selected_layout([virtual, physical]) == 'English (US)'
    assert popup.selected_layout([keyboard('Russian', 'external')]) == 'Russian'
    assert popup.selected_layout([virtual]) is None
    assert popup.selected_layout([dict(physical, xkb_layout_names=['English (US)'])]) is None
    tracker = popup.Popup([physical])
    with patch.object(popup.subprocess, 'run', return_value=SimpleNamespace(stdout='42\n')) as send:
        tracker.update([virtual, physical])
        send.assert_not_called()
        tracker.update([virtual, keyboard('Russian')])
        assert send.call_count == 1
        command = send.call_args.args[0]
        assert command[-2:] == ['RU', 'Russian']
        assert command[command.index('-t')+1] == '1000'
        assert '-e' in command and command[command.index('-r')+1] == '0'
        tracker.update([keyboard('Russian')])
        assert send.call_count == 1
        tracker.update([physical])
        assert send.call_count == 2
        assert send.call_args.args[0][send.call_args.args[0].index('-r')+1] == '42'
        tracker.update([]); tracker.update([physical])
        assert send.call_count == 2  # Hotplug/restart baseline is quiet.
        tracker.update([keyboard('<custom>')])
        assert send.call_args.args[0][-1] == '&lt;custom&gt;'
    with patch.object(popup.subprocess, 'run', side_effect=subprocess.TimeoutExpired('notify-send', 3)):
        tracker.update([physical])  # A notification failure must not kill the watcher.
    for acknowledgement in ('', '{"success":true}\n'):
        process = SimpleNamespace(stdout=io.StringIO(acknowledgement + '{"change":"xkb_layout"}\n'),
                                  terminate=lambda: None, wait=lambda timeout: None)
        with patch.object(popup.subprocess, 'Popen', return_value=process), \
                patch.object(popup.subprocess, 'run', return_value=SimpleNamespace(stdout='43\n')) as send, \
                patch.object(popup, 'inputs', side_effect=[[physical], [keyboard('Russian')]]), \
                patch.object(popup.signal, 'signal'):
            try:
                popup.main()
            except RuntimeError as error:
                assert str(error) == 'Sway keyboard subscription ended'
            else:
                raise AssertionError('Ended subscription silently accepted')
            assert send.call_count == 1
            assert send.call_args.args[0][-2:] == ['RU', 'Russian']
    with tempfile.TemporaryDirectory(prefix='minion-layout-style-') as temporary:
        user = SimpleNamespace(pw_dir=temporary, pw_uid=os.getuid(), pw_gid=os.getgid())
        with patch.object(settings.os, 'chown'):
            assert settings.install(user)
            config = Path(temporary) / '.config/mako/config'
            first = config.read_bytes()
            assert config.stat().st_mode & 0o777 == 0o600
            assert b'anchor=center' in first and b'default-timeout=1000' in first
            assert first.count(b'on-notify=exec pw-play') == 2
            assert b'[app-name=minion-agent]' in first
            assert b'[app-name=minion-agent-attention]' in first
            assert b'--volume=0.35 --media-role=Notification' in first
            assert b'/usr/share/sounds/freedesktop/stereo/message-new-instant.oga' in first
            assert not settings.install(user)
            assert config.read_bytes() == first
            for rule in ('[app-name=minion-layout]', '[app-name="minion-layout"]',
                         '[app-name = "minion-layout" urgency=low]'):
                personal = '# personal\nfont=Sans 12\n\n' + rule + '\ninvisible=1\n'
                config.write_text(personal)
                assert settings.install(user)  # Add independent agent rules only.
                assert config.read_text().startswith(personal)
                assert config.read_text().count('minion-layout') == 1
                assert not settings.install(user)
            personal = ('# personal\n[app-name=minion-agent]\non-notify=none\n'
                        '[app-name="minion-agent-attention"]\non-notify=exec my-sound\n')
            config.write_text(personal)
            assert settings.install(user)  # Add independent layout styling only.
            assert config.read_text().startswith(personal)
            assert 'pw-play' not in config.read_text()
            assert not settings.install(user)
            config.write_text('# personal\nfont=Sans 12\n')
            assert settings.install(user)
            assert config.read_text().startswith('# personal\nfont=Sans 12\n')
    print('Passed: physical layout selection, quiet startup/hotplug, duplicate suppression, popup replacement/expiry, failure handling and personal-style retention.')


if __name__ == '__main__':
    main()
