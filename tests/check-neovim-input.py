#!/usr/bin/env python3
"""Check Neovim input through a disposable PTY emulating Foot's reporting bug.

The duplicate press/release bytes were measured separately in real Foot 1.16.2.
This fixture checks startup negotiation and resume without sending desktop input.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT / 'setup/development/nvim.lua')
    parser.add_argument('--nvim', default=shutil.which('nvim'))
    args = parser.parse_args()
    if not args.nvim:
        parser.error('Install Neovim and the configured plugins first')
    with tempfile.TemporaryDirectory(prefix='minion-nvim-input-') as temporary:
        base = Path(temporary)
        fixture = base / 'fixture.txt'
        fixture.write_text('abcdef\n')
        server = base / 'nvim.sock'
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 100, 0, 0))
        env = dict(os.environ, TERM='foot', XDG_STATE_HOME=str(base / 'state'),
                   XDG_CACHE_HOME=str(base / 'cache'))
        process = subprocess.Popen([args.nvim, '-i', 'NONE', '-u', str(args.config.resolve()),
                                    '--cmd', 'lua vim.lsp.enable = function() end',
                                    '--listen', str(server), str(fixture)],
                                   stdin=slave, stdout=slave, stderr=slave, env=env, cwd=base)
        os.close(slave)
        pending = b''
        flags = [0]
        csi = re.compile(rb'\x1b\[([?=><]?)([0-9;]*)([ucn])')

        def pump(seconds=.15):
            nonlocal pending
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if not select.select([master], [], [], min(.02, max(0, deadline-time.monotonic())))[0]:
                    continue
                try:
                    pending += os.read(master, 65536)
                except OSError:
                    break
                end = 0
                for match in csi.finditer(pending):
                    prefix, value, command = match.groups()
                    if command == b'u':
                        if prefix == b'?':
                            os.write(master, b'\x1b[?0u')
                        elif prefix == b'>':
                            flags.append(int(value or b'0'))
                        elif prefix == b'=':
                            flags[-1] = int(value or b'0')
                        elif prefix == b'<' and len(flags) > 1:
                            flags.pop()
                    elif command == b'c' and prefix == b'':
                        os.write(master, b'\x1b[?62;4;6;22c')
                    elif command == b'n' and value == b'6':
                        os.write(master, b'\x1b[1;1R')
                    end = match.end()
                pending = pending[end:][-256:]

        def rpc(lua):
            result = subprocess.check_output([args.nvim, '--server', str(server), '--remote-expr',
                                              'luaeval(' + json.dumps(lua) + ')'],
                                             env=env, text=True, stderr=subprocess.DEVNULL, timeout=5)
            pump()
            return result.strip()

        def setup():
            rpc('(function() vim.cmd("stopinsert"); return 0 end)()')
            rpc('(function() vim.api.nvim_buf_set_lines(0,0,-1,false,{"abcdef"}); '
                'vim.api.nvim_win_set_cursor(0,{1,6}); vim.cmd("startinsert!"); return 0 end)()')

        def key(value, repeats=0):
            # Foot 1.16 sends these legacy keys again on release if flag 2 is set.
            os.write(master, value * (1 + repeats + bool(flags[-1] & 2)))
            pump()

        def lines():
            return json.loads(rpc('vim.json.encode(vim.api.nvim_buf_get_lines(0,0,-1,false))'))

        try:
            deadline = time.monotonic() + 8
            while not server.exists():
                pump(.05)
                assert process.poll() is None and time.monotonic() < deadline, 'Editor failed to start'
            pump(.5)
            for phase in ('startup', 'resume'):
                if phase == 'resume':
                    # TUI renegotiates event reporting on resume; exercise the hook.
                    flags[-1] = 3
                    rpc('(function() vim.api.nvim_exec_autocmds("VimResume",{}); return 0 end)()')
                assert flags[-1] == 1 and len(flags) == 2, 'Release reporting remained enabled or mode stack grew'
                setup()
                key(b'\r')
                assert lines() == ['abcdef', ''], f'{phase}: Enter duplicated'
                setup()
                key(b'\x7f')
                assert lines() == ['abcde'], f'{phase}: Backspace duplicated'
                setup()
                key(b'\x7f', repeats=2)
                assert lines() == ['abc'], f'{phase}: intentional held-key repeats lost'
            # Exit must pop exactly Neovim's mode, leaving the shell in legacy mode.
            try:
                rpc('(function() vim.cmd("qa!"); return 0 end)()')
            except subprocess.CalledProcessError:
                pass
            process.wait(timeout=5)
            pump()
            assert flags == [0], 'Editor left keyboard mode enabled after exit'
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            os.close(master)
    print('Passed: Foot negotiation, single Enter/Backspace, intentional repeat, resume hook and keyboard mode cleanup.')


if __name__ == '__main__':
    main()
