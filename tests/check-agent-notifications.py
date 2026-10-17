#!/usr/bin/env python3
"""Check notification event filtering, origin selection and safe config merging."""
import copy
import importlib.util
import json
from pathlib import Path
import runpy
import tempfile
import tomllib
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('agent_notifications', ROOT / 'setup/agents/agent_notifications.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
hook = runpy.run_path(str(ROOT / 'setup/agents/minion-agent-notify'))

for source in ('', '# personal\nmodel = "personal"\n',
               '[tui]\nmouse_scroll_speed = 5.0 # keep\n[other]\nvalue = 1\n'):
    updated = config.seed_codex(source)
    parsed = tomllib.loads(updated)
    assert 'notify' not in parsed  # Backend hooks cannot identify the active UI.
    assert parsed['tui']['notifications'] == ['agent-turn-complete', 'approval-requested', 'plan-mode-prompt']
    assert config.seed_codex(updated) == updated
    if 'mouse_scroll_speed' in source:
        assert parsed['tui']['mouse_scroll_speed'] == 5.0
        assert '# keep' in updated and parsed['other'] == {'value': 1}
personal = 'notify = ["my-hook"]\n[tui]\nnotifications = false\nnotification_method = "osc9"\n'
assert config.seed_codex(personal) == personal
for invalid in ('[tui', 'tui = false'):
    try:
        config.seed_codex(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid Codex configuration accepted')

for transform, data in ((config.seed_claude, {'model': 'personal', 'hooks': {'Stop': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': '/personal/hook'}]}]}}),
        (config.seed_cursor, {'version': 1, 'hooks': {'stop': [{'command': '/personal/hook'}]}})):
    original = copy.deepcopy(data)
    updated = transform(data)
    assert data == original
    event = 'Stop' if transform == config.seed_claude else 'stop'
    assert updated['hooks'][event][0] == data['hooks'][event][0]
    assert len(updated['hooks'][event]) == 2
    assert transform(updated) == updated
    for invalid in ([], {'hooks': []}, {'hooks': {event: {}}}):
        try:
            transform(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Malformed hook settings accepted')
for text in ('[main]\nfont=personal\n', '[bell]\nurgent=no\n[colors]\nalpha=0.9\n'):
    updated = config.seed_foot(text)
    assert config.seed_foot(updated) == updated and text.strip().splitlines()[0] in updated
    if 'urgent=no' in text:
        assert 'urgent=no' in updated and 'urgent=yes' not in updated

with tempfile.TemporaryDirectory() as temporary:
    user = SimpleNamespace(pw_dir=temporary)
    p = Path(temporary) / '.claude/settings.json'
    p.parent.mkdir(); p.write_text('{broken')
    try:
        config.prepare(user)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid JSON was accepted')
    assert not (Path(temporary) / '.codex/config.toml').exists()

event = hook['event']
assert event('codex', {'type': 'agent-turn-complete'}) is None
assert event('codex', {'type': 'unknown'}) is None
assert event('cursor', {'status': 'completed'}) == 'Cursor Agent finished.'
assert event('cursor', {'status': 'aborted'}) is None
assert event('cursor', {'status': 'error'}) is None
assert event('claude', {'hook_event_name': 'Stop'}) == 'Claude finished.'
assert event('claude', {'hook_event_name': 'SubagentStop'}) is None
assert event('claude', {'hook_event_name': 'Stop', 'background_tasks': [{'id': 'busy'}]}) is None
assert event('claude', {'hook_event_name': 'Notification', 'notification_type': 'idle_prompt'}) is None
assert event('claude', {'hook_event_name': 'Notification', 'notification_type': 'permission_prompt'})
assert event('claude', []) is None

tree = {'nodes': [{'type': 'workspace', 'id': 1, 'name': '6 <project>', 'nodes': [
    {'id': 22, 'pid': 100, 'focused': False}]}]}
assert hook['origin'](tree, [300, 200, 100])[0]['id'] == 22
assert hook['origin'](tree, [999]) is None
ambiguous = copy.deepcopy(tree)
ambiguous['nodes'][0]['nodes'].append({'id': 23, 'pid': 100})
assert hook['origin'](ambiguous, [100]) is None
scratch = copy.deepcopy(tree); scratch['nodes'][0]['name'] = '__i3_scratch'
assert hook['origin'](scratch, [100]) is None
globals_ = hook['alert'].__globals__
with patch.object(globals_['subprocess'], 'check_output', side_effect=[json.dumps(tree), '[{"success":true}]']) as ipc, \
        patch.object(globals_['subprocess'], 'run') as notify:
    hook['alert']('Codex finished.', [100])
    assert ipc.call_args.args[0][-1] == '[con_id=22] urgent enable'
    assert notify.call_args.args[0][-1] == 'Workspace 6 &lt;project&gt;.'
    assert '-t' in notify.call_args.args[0] and '3000' in notify.call_args.args[0]
focused = copy.deepcopy(tree); focused['nodes'][0]['nodes'][0]['focused'] = True
with patch.object(globals_['subprocess'], 'check_output', return_value=json.dumps(focused)) as ipc, \
        patch.object(globals_['subprocess'], 'run') as notify:
    hook['alert']('Codex finished.', [100])
    assert ipc.call_count == 1
    notify.assert_not_called()

print('Passed: CLI event filters, focus suppression, safe workspace urgency, shared-server refusal, private popup text, config preservation, idempotence and invalid-config refusal.')
