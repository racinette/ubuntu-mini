"""Add the layout popup style while retaining existing notification settings."""
import os
from pathlib import Path
import re
import tempfile

HERE = Path(__file__).resolve().parent


def install(user):
    config = Path(user.pw_dir) / '.config/mako/config'
    text = config.read_text() if config.exists() else (HERE / 'mako.conf').read_text()
    # An existing app-specific rule is a personal preference, including styling
    # or intentionally hiding these popups. Never replace or duplicate it.
    if re.search(r'^\[[^\]\n]*\bapp-name\s*=\s*"?minion-layout"?(?:\s|\])', text, re.MULTILINE):
        return False
    missing = [parent for parent in config.parents if not parent.exists()]
    config.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=config.parent, delete=False) as stream:
        stream.write(text.rstrip() + '\n\n' + (HERE / 'layout-popup.conf').read_text())
        prepared = Path(stream.name)
    prepared.chmod(0o600)
    os.chown(prepared, user.pw_uid, user.pw_gid)
    prepared.replace(config)
    for parent in missing:
        os.chown(parent, user.pw_uid, user.pw_gid)
    return True
