#!/usr/bin/env python3
"""Check Snap Store command selection without installing anything on the host."""
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / 'setup/desktop/browser.py'
for installed in (False, True):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0 if installed or command[:2] != ['snap', 'list'] else 1)

    with patch.object(sys, 'argv', [str(script)]), patch('os.geteuid', return_value=0), patch('subprocess.run', side_effect=run):
        try:
            runpy.run_path(str(script), run_name='__main__')
        except SystemExit as error:
            assert error.code == 0
    expected = [['snap', 'list', 'firefox']]
    if not installed:
        expected.append(['snap', 'install', 'firefox', '--channel=latest/stable'])
    assert calls == expected, calls
print('Snap Store selection and existing-browser preservation passed (isolated commands).')
