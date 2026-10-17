"""Seed native CLI notification hooks, retaining unrelated user configuration."""
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
COMMAND = '/usr/local/bin/minion-agent-notify'


def seed_codex(text):
    before = tomllib.loads(text)
    expected = copy.deepcopy(before)
    defaults = {
        'tui': {'notifications': ['agent-turn-complete', 'approval-requested', 'plan-mode-prompt'],
                'notification_method': 'bel'},
    }
    existing = expected.setdefault('tui', {})
    if not isinstance(existing, dict):
        raise ValueError('Expected a Codex tui table')
    additions = ''
    for key, value in defaults['tui'].items():
        if key not in existing:
            existing[key] = value
            additions += key + ' = ' + json.dumps(value) + '\n'
    updated = text
    if additions:
        header = re.search(r'^\[tui\]\s*(?:#[^\n]*)?$', updated, re.MULTILINE)
        if header:
            updated = updated[:header.end()] + '\n' + additions + updated[header.end():]
        else:
            updated = updated.rstrip() + '\n\n[tui]\n' + additions
    # Verify semantic preservation, even for unusual TOML quoting/multiline values.
    if tomllib.loads(updated) != expected:
        raise ValueError('Cannot safely add notifications to this Codex configuration')
    return updated


def add_hook(data, event, definition):
    hooks = data.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('Expected a hooks object')
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        raise ValueError('Expected a hook event array')
    if definition not in entries:
        entries.append(definition)


def seed_claude(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a Claude settings object')
    data = copy.deepcopy(data)
    add_hook(data, 'Stop', {'hooks': [{'type': 'command', 'command': COMMAND + ' claude', 'timeout': 10}]})
    add_hook(data, 'Notification', {'matcher': 'permission_prompt|elicitation_dialog',
             'hooks': [{'type': 'command', 'command': COMMAND + ' claude', 'timeout': 10}]})
    return data


def seed_cursor(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a Cursor hooks object')
    data = copy.deepcopy(data)
    if data.setdefault('version', 1) != 1:
        raise ValueError('Unsupported Cursor hooks version')
    add_hook(data, 'stop', {'command': COMMAND + ' cursor'})
    return data


def seed_foot(text):
    # The Codex UI emits BEL in the actual terminal, unlike its shared daemon's
    # external notify hook. Foot converts it to urgency + a brief popup.
    from configparser import ConfigParser
    config = ConfigParser(interpolation=None, strict=False)
    config.read_string(text)
    defaults = {'main': {'notify': 'notify-send -a minion-agent-attention -t 3000 ${title} ${body}'},
                'bell': {'urgent': 'yes', 'notify': 'yes'}}
    for section, settings in defaults.items():
        additions = ''.join(key + '=' + value + '\n' for key, value in settings.items()
                            if not config.has_option(section, key))
        if not additions:
            continue
        header = re.search(r'^\[' + section + r'\][ \t]*(?:#[^\n]*)?$', text, re.MULTILINE)
        if header:
            text = text[:header.end()] + '\n' + additions + text[header.end():]
        else:
            text = text.rstrip() + '\n\n[' + section + ']\n' + additions
    return text


def prepare(user):
    home = Path(user.pw_dir)
    result = []
    for relative, transform in (
            ('.codex/config.toml', seed_codex),
            ('.claude/settings.json', lambda s: json.dumps(seed_claude(json.loads(s or '{}')), indent=2) + '\n'),
            ('.cursor/hooks.json', lambda s: json.dumps(seed_cursor(json.loads(s or '{}')), indent=2) + '\n'),
            ('.config/foot/foot.ini', seed_foot)):
        path = home / relative
        text = path.read_text() if path.exists() else ''
        updated = transform(text)
        if updated != text:
            result.append((path, updated))
    return result


def write_user(path, text, user):
    missing = [parent for parent in path.parents if not parent.exists()]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        prepared = Path(stream.name)
        try:
            stream.write(text)
            os.fchmod(stream.fileno(), path.stat().st_mode & 0o777 if path.exists() else 0o600)
            if os.geteuid() == 0:
                os.fchown(stream.fileno(), user.pw_uid, user.pw_gid)
        except BaseException:
            prepared.unlink(missing_ok=True)
            raise
    try:
        prepared.replace(path)
    finally:
        prepared.unlink(missing_ok=True)
    if os.geteuid() == 0:
        for parent in missing:
            os.chown(parent, user.pw_uid, user.pw_gid)


def install(user):
    # Validate all existing user files before installing or changing any file.
    updates = prepare(user)
    target = Path(COMMAND)
    target.write_bytes((HERE / 'minion-agent-notify').read_bytes())
    target.chmod(0o755)
    for path, text in updates:
        write_user(path, text, user)
