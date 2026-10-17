#!/usr/bin/env python3
"""Check agent child-window placement, ambiguity and process ancestry parsing."""
import copy
import json
from pathlib import Path
import runpy
import tempfile
from unittest.mock import patch

policy = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'setup/desktop/minion-workspaces'))


def main():
    tree = {'nodes': [
        {'type': 'workspace', 'id': 10, 'name': '1: project "Привет"', 'nodes': [
            {'id': 11, 'pid': 100, 'nodes': []}]},
        {'type': 'workspace', 'id': 20, 'name': '2', 'floating_nodes': [
            {'id': 21, 'pid': 200, 'nodes': []}], 'nodes': [
            {'id': 22, 'pid': 300, 'focused': True, 'nodes': []}]},
    ]}
    origin = policy['window_origin']
    ancestors = lambda pid: iter({300: [250, 150, 100, 2], 200: [2]}.get(pid, []))
    assert origin(tree, 22, ancestors)['id'] == 10
    assert origin(tree, 21, ancestors) is None  # Independent launch.
    assert origin(tree, 999, ancestors) is None  # Closed before processing.
    renamed = copy.deepcopy(tree)
    renamed['nodes'][0]['name'] = '7: renamed'
    assert origin(renamed, 22, ancestors)['name'] == '7: renamed'
    same = copy.deepcopy(tree)
    same['nodes'][1]['nodes'].append(same['nodes'][0]['nodes'].pop())
    assert origin(same, 22, ancestors) is None
    shared = copy.deepcopy(tree)
    shared['nodes'][1]['nodes'].append({'id': 23, 'pid': 100})
    assert origin(shared, 22, ancestors) is None  # Ambiguous Foot server.
    reused = copy.deepcopy(tree)
    reused['nodes'][0]['nodes'].append({'id': 12, 'pid': 300})
    assert origin(reused, 22, ancestors) is None  # Browser/shared process.
    nearest = copy.deepcopy(tree)
    nearest['nodes'][1]['nodes'].append({'id': 23, 'pid': 250})
    assert origin(nearest, 22, ancestors) is None  # Nearest ancestor wins.
    scratch = copy.deepcopy(tree)
    scratch['nodes'][0]['name'] = '__i3_scratch'
    assert origin(scratch, 22, ancestors) is None
    assert tree['nodes'][1]['nodes'][0]['focused']  # Selection is side-effect free.
    with tempfile.TemporaryDirectory() as temporary:
        proc = Path(temporary)
        for pid, parent in [(300, 250), (250, 100), (100, 1)]:
            directory = proc / str(pid)
            directory.mkdir()
            (directory / 'stat').write_text(f'{pid} (a (process) name) S {parent} 0 0')
        assert list(policy['parent_pids'](300, proc)) == [250, 100]
        (proc / '100/stat').write_text('100 (cycle) S 300 0 0')
        assert list(policy['parent_pids'](300, proc)) == [250, 100]
        (proc / '250/cmdline').write_bytes(b'/opt/codex\0app-server\0--listen\0')
        assert list(policy['parent_pids'](300, proc)) == []  # Shared daemon, not client origin.
        (proc / '250/cmdline').write_bytes(b'/opt/codex\0resume\0')
        assert list(policy['parent_pids'](300, proc)) == [250, 100]  # Ordinary CLI still works.
        (proc / '250/stat').write_text('malformed')
        assert list(policy['parent_pids'](300, proc)) == [250]
        assert list(policy['parent_pids']('../300', proc)) == []
        assert list(policy['parent_pids'](True, proc)) == []
        assert list(policy['parent_pids'](999, proc)) == []
        with patch.object(policy['parent_pids'].__globals__['os'], 'getuid', return_value=-1):
            assert list(policy['parent_pids'](300, proc)) == []
    # Exercise the actual IPC command builder, retaining Unicode/quoted names.
    function_globals = policy['place_child_window'].__globals__
    with patch.dict(function_globals, {'window_origin': lambda *_: tree['nodes'][0]}), \
            patch.object(function_globals['subprocess'], 'check_output',
                         side_effect=[json.dumps(tree), '[{"success":true}]']) as ipc:
        policy['place_child_window'](22)
        command = ipc.call_args.args[0][-1]
        assert command == '[con_id=22] move container to workspace ' + json.dumps(tree['nodes'][0]['name'])
        assert 'focus' not in command
    print('Passed: agent ancestry, current/renamed/floating workspaces, independent launches, shared-process ambiguity, scratchpad, safe IPC and disappearing processes.')


if __name__ == '__main__':
    main()
