"""Seed layout styling and agent sounds, retaining personal notification rules."""
import os
from pathlib import Path
import re
import tempfile

HERE = Path(__file__).resolve().parent


def seed(text):
    # An existing app-specific rule is a personal preference, including styling
    # or intentionally hiding these popups. Never replace or duplicate it.
    rules = {'minion-layout': (HERE / 'layout-popup.conf').read_text()}
    for app in ('minion-agent', 'minion-agent-attention'):
        rules[app] = (f'[app-name={app}]\n'
                      'on-notify=exec pw-play --volume=0.35 --media-role=Notification '
                      '/usr/share/sounds/freedesktop/stereo/message-new-instant.oga\n')
    for app, rule in rules.items():
        if not re.search(r'^\[[^\]\n]*\bapp-name\s*=\s*"?' + re.escape(app) +
                         r'"?(?:\s|\])', text, re.MULTILINE):
            text = text.rstrip() + '\n\n' + rule
    return text


def install(user):
    config = Path(user.pw_dir) / '.config/mako/config'
    text = config.read_text() if config.exists() else (HERE / 'mako.conf').read_text()
    updated = seed(text)
    if updated == text and config.exists():
        return False
    missing = [parent for parent in config.parents if not parent.exists()]
    config.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=config.parent, delete=False) as stream:
        stream.write(updated)
        prepared = Path(stream.name)
    prepared.chmod(0o600)
    os.chown(prepared, user.pw_uid, user.pw_gid)
    prepared.replace(config)
    for parent in missing:
        os.chown(parent, user.pw_uid, user.pw_gid)
    return True
