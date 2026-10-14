#!/usr/bin/env python3
"""Check terminal directory selection and safe launch arguments without a desktop."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'setup/desktop/minion-terminal'
loader = importlib.machinery.SourceFileLoader('terminal', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
terminal = importlib.util.module_from_spec(spec)
loader.exec_module(terminal)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        home = root / 'home'
        home.mkdir()
        project = root / 'a project; $(do not execute) Привет'
        project.mkdir()
        proc = root / 'proc'
        parent = proc / '100'
        child = proc / '101'
        (parent / 'task/100').mkdir(parents=True)
        child.mkdir()
        executable = root / 'foot'
        executable.touch()
        (parent / 'exe').symlink_to(executable)
        (parent / 'cwd').symlink_to(home)
        (child / 'cwd').symlink_to(project)
        children = parent / 'task/100/children'
        children.write_text('101 ')
        node = {'focused': True, 'pid': 100, 'app_id': 'custom-foot'}
        tree = {'nodes': [{'focused': False, 'pid': 200}], 'floating_nodes': [node]}
        assert terminal.focused_window(tree) is node
        with patch.object(terminal.Path, 'home', return_value=home):
            assert terminal.terminal_directory(node, proc) == project
            assert terminal.terminal_directory(None, proc) == home
            assert terminal.terminal_directory({'pid': '../100'}, proc) == home
            assert terminal.terminal_directory({'pid': True}, proc) == home
            children.write_text('101 102')
            assert terminal.terminal_directory(node, proc) == home  # Ambiguous server.
            children.write_text('101')
            (child / 'cwd').unlink()
            (child / 'cwd').symlink_to(root / 'deleted-directory')
            assert terminal.terminal_directory(node, proc) == home
            (child / 'cwd').unlink()
            (child / 'cwd').symlink_to(project)
            (parent / 'exe').unlink()
            executable.rename(root / 'firefox')
            (parent / 'exe').symlink_to(root / 'firefox')
            assert terminal.terminal_directory(node, proc) == home
        with patch.object(terminal.subprocess, 'check_output', return_value=json.dumps(tree)), \
             patch.object(terminal, 'terminal_directory', return_value=project), \
             patch.object(sys, 'argv', ['minion-terminal']), patch.object(terminal.os, 'execvp') as execute:
            terminal.main()
            execute.assert_called_once_with('foot', ['foot', '--working-directory', str(project)])
        with patch.object(terminal.subprocess, 'check_output', side_effect=OSError), \
             patch.object(terminal.Path, 'home', return_value=home), \
             patch.object(sys, 'argv', ['minion-terminal']), patch.object(terminal.os, 'execvp') as execute:
            terminal.main()
            execute.assert_called_once_with('foot', ['foot', '--working-directory', str(home)])
    print('Passed: focused shell directory, custom Foot IDs, safe paths and fallback on unavailable/ambiguous clients.')


if __name__ == '__main__':
    main()
