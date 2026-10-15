#!/usr/bin/env python3
"""Exercise project scope with real Neovim and the installed pinned plugins.

Run after development setup. No language servers, network or desktop are used;
all edited files and editor state belong to a temporary directory.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
CHECK = r'''
local function run()
  local tree = require('nvim-tree.api')
  local base = vim.env.MINION_TEST_BASE
  local expected = vim.fs.normalize(vim.env.MINION_TEST_ROOT)
  local action = vim.env.MINION_TEST_ACTION
  local function scope()
    assert(vim.fs.normalize(vim.fn.getcwd()) == expected, 'Working directory changed unexpectedly')
    assert(vim.fs.normalize(tree.tree.get_nodes().absolute_path) == expected, 'Tree scope differs from working directory')
  end
  local function edit(path)
    vim.cmd.edit(vim.fn.fnameescape(path))
  end
  local function key(lhs)
    vim.api.nvim_feedkeys(vim.keycode(lhs), 'xt', false)
  end
  local function picker(lhs, query)
    local result, error, queried
    local timer = vim.uv.new_timer()
    local attempts = 0
    timer:start(30, 30, vim.schedule_wrap(function()
      attempts = attempts + 1
      if MiniPick.is_picker_active() then
        if not queried then
          queried = true
          MiniPick.set_picker_query(vim.split(query, ''))
        else
          local matches = MiniPick.get_picker_matches()
          if matches and #matches.all > 0 then
            result = MiniPick.get_picker_items()
            timer:stop()
            vim.api.nvim_feedkeys(vim.keycode('<CR>'), 't', false)
            return
          end
        end
      end
      if attempts > 150 then
        error = 'Picker did not find fixture: ' .. lhs
        timer:stop()
        if MiniPick.is_picker_active() then MiniPick.stop() end
      end
    end))
    vim.fn.maparg(lhs, 'n', false, true).callback()
    timer:stop()
    timer:close()
    assert(result and not error, error or 'Picker did not run')
    return result
  end
  tree.tree.open()
  scope()
  if action == 'external' or action == 'pickers' then
    tree.tree.close()
    edit(base .. '/project/nested/example.txt')
    tree.tree.open({ focus = false })
    edit(base .. '/outside/dependency.txt')
    vim.wait(200)
    scope()
    if action == 'pickers' then
      picker('<F3>', 'example')
      assert(vim.api.nvim_buf_get_name(0) == base .. '/project/nested/example.txt', 'File search left scope')
      picker('<F4>', 'LOCAL_NEEDLE')
      assert(vim.api.nvim_buf_get_name(0) == base .. '/project/nested/example.txt', 'Text search left scope')
      tree.tree.open()
      scope()
    else
      key('<M-Left>')
      assert(vim.api.nvim_buf_get_name(0) == base .. '/project/nested/example.txt', 'Back lost source')
      key('<M-Right>')
      assert(vim.api.nvim_buf_get_name(0) == base .. '/outside/dependency.txt', 'Forward lost target')
      tree.tree.open()
      scope()
    end
  elseif (action or ''):match('^stale%-') then
    tree.tree.close()
    local source = base .. '/project/nested/example.txt'
    local target = base .. '/outside/dependency.txt'
    local lines = {}
    for i = 1, 100 do lines[i] = 'original line ' .. i end
    local forward = action == 'stale-forward'
    vim.fn.writefile(lines, source)
    if forward then vim.fn.writefile(lines, target) end
    edit(source)
    vim.cmd.clearjumps()
    vim.api.nvim_win_set_cursor(0, {90, 12})
    edit(target)
    if forward then
      vim.api.nvim_win_set_cursor(0, {90, 12})
      key('<M-Left>')
      assert(vim.api.nvim_buf_get_name(0) == source, 'Initial back did not reach source')
      vim.fn.writefile({'short', 'last'}, target)
    else
      vim.fn.writefile(action == 'stale-empty' and {} or {'short', 'last'}, source)
    end
    vim.cmd.checktime()
    local lhs = forward and '<M-Right>' or action == 'stale-escape' and '<Esc>'
      or action == 'stale-backspace' and '<BS>' or '<M-Left>'
    local ok, err = pcall(vim.fn.maparg(lhs, 'n', false, true).callback)
    assert(ok, 'Shortened-file navigation raised an error: ' .. tostring(err))
    assert(vim.api.nvim_buf_get_name(0) == (forward and target or source), 'Stale jump lost target file')
    local position = action == 'stale-empty' and {1, 0} or {2, 3}
    assert(vim.deep_equal(vim.api.nvim_win_get_cursor(0), position), 'Stale jump was not clipped to surviving text')
    key(forward and '<M-Left>' or '<M-Right>')
    assert(vim.api.nvim_buf_get_name(0) == (forward and source or target), 'Stale jump broke reverse history')
    key(lhs)
    assert(vim.deep_equal(vim.api.nvim_win_get_cursor(0), position), 'Repeating stale jump did not recover')
    tree.tree.open()
    scope()
  elseif action == 'jump-error' then
    tree.tree.close()
    local source = base .. '/project/nested/example.txt'
    edit(source)
    edit(base .. '/outside/dependency.txt')
    local hook = vim.api.nvim_create_autocmd('BufEnter', {
      buffer = vim.fn.bufnr(source), callback = function() error('UNRELATED_JUMP_FAILURE') end,
    })
    local ok, err = pcall(vim.fn.maparg('<M-Left>', 'n', false, true).callback)
    vim.api.nvim_del_autocmd(hook)
    assert(not ok and tostring(err):find('UNRELATED_JUMP_FAILURE', 1, true), 'Unrelated navigation error was hidden')
  elseif action == 'parent' then
    key('<BS>')
    expected = base
    scope()
    tree.tree.close()
    edit(base .. '/project/nested/example.txt')
    scope()
    tree.tree.open()
    scope()
    vim.cmd.vsplit(vim.fn.fnameescape(base .. '/outside/dependency.txt'))
    vim.wait(200)
    scope()
  elseif action == 'cd' then
    tree.tree.close()
    vim.cmd.cd(vim.fn.fnameescape(base .. '/outside'))
    expected = base .. '/outside'
    edit(expected .. '/dependency.txt')
    tree.tree.open()
    scope()
  elseif action == 'tree-root' then
    tree.tree.change_root(base .. '/outside')
    expected = base .. '/outside'
    scope()
    tree.tree.close()
    edit(expected .. '/dependency.txt')
    scope()
  elseif action == 'quit-window' then
    tree.tree.close()
    edit(base .. '/project/nested/example.txt')
    tree.tree.open()
    assert(#vim.api.nvim_list_wins() == 2, 'Fixture needs tree and code windows')
    vim.cmd.q()
    assert(#vim.api.nvim_list_wins() == 1, ':q should close one window')
    assert(vim.api.nvim_buf_get_name(0) == base .. '/project/nested/example.txt', ':q closed code instead of tree')
  elseif action == 'hold' then
    vim.fn.writefile({'ready'}, vim.env.MINION_TEST_READY)
    assert(vim.wait(10000, function() return vim.fn.filereadable(vim.env.MINION_TEST_RELEASE) == 1 end, 30), 'Concurrent test timed out')
    scope()
  end
end
vim.defer_fn(function()
  local ok, err = xpcall(run, debug.traceback)
  if not ok then io.stderr:write(err .. '\n') end
  vim.cmd(ok and 'qa!' or 'cquit 1')
end, 200)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT / 'setup/development/nvim.lua')
    parser.add_argument('--nvim', default=shutil.which('nvim'))
    args = parser.parse_args()
    if not args.nvim:
        parser.error('Neovim and the configured plugins must be installed first')
    with tempfile.TemporaryDirectory(prefix='minion-neovim-') as temporary:
        base = Path(temporary)
        nested = base / 'project/nested'
        nested.mkdir(parents=True)
        (base / 'project/.git').mkdir()
        (base / 'project/package.json').write_text('{}')
        (nested / 'example.txt').write_text('LOCAL_NEEDLE\n')
        outside = base / 'outside'
        outside.mkdir()
        (outside / 'dependency.txt').write_text('OUTSIDE_NEEDLE\n')
        script = base / 'check.lua'
        script.write_text(CHECK)
        cases = [
            ('dot', nested, ['.'], nested, ''),
            ('relative directory', base / 'project', ['nested'], nested, ''),
            ('absolute directory', outside, [str(nested)], nested, ''),
            ('file infers project', nested, ['example.txt'], base / 'project', ''),
            ('no arguments', nested, [], nested, ''),
            ('no markers', outside, ['.'], outside, ''),
            ('external file and history', nested, ['.'], nested, 'external'),
            ('back after external file shortening', nested, ['.'], nested, 'stale-back'),
            ('escape after external file shortening', nested, ['.'], nested, 'stale-escape'),
            ('backspace after external file shortening', nested, ['.'], nested, 'stale-backspace'),
            ('forward after external file shortening', nested, ['.'], nested, 'stale-forward'),
            ('back after external file emptying', nested, ['.'], nested, 'stale-empty'),
            ('unrelated navigation errors remain visible', nested, ['.'], nested, 'jump-error'),
            ('file and text search after external navigation', nested, ['.'], nested, 'pickers'),
            ('parent scope survives opening project files', base / 'project', ['.'], base / 'project', 'parent'),
            ('explicit cd', nested, ['.'], nested, 'cd'),
            ('explicit tree root', nested, ['.'], nested, 'tree-root'),
            (':q leaves other windows', nested, ['.'], nested, 'quit-window'),
        ]

        def launch(name, cwd, arguments, root, action):
            state = base / ('state-' + name.replace('/', '-'))
            state.mkdir()
            env = dict(os.environ, MINION_TEST_BASE=str(base), MINION_TEST_ROOT=str(root),
                       MINION_TEST_ACTION=action, XDG_STATE_HOME=str(state),
                       XDG_CACHE_HOME=str(state / 'cache'), XDG_RUNTIME_DIR=str(state))
            # Scope checks do not need to launch real language-server processes.
            command = [args.nvim, '--headless', '--cmd',
                       'lua vim.lsp.enable = function() end', '-u', str(args.config.resolve()),
                       '-c', 'luafile ' + str(script), *arguments]
            return command, cwd, env

        for case in cases:
            # External-edit regressions shorten these files; each editor case
            # starts with its own original contents, including search needles.
            (nested / 'example.txt').write_text('LOCAL_NEEDLE\n')
            (outside / 'dependency.txt').write_text('OUTSIDE_NEEDLE\n')
            command, cwd, env = launch(*case)
            run = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=15)
            assert run.returncode == 0, f'{case[0]}:\n{run.stdout}\n{run.stderr}'
            print('Passed:', case[0], flush=True)

        # Reuse the ordinary saved editor state, as a real restart would.
        command, cwd, env = launch('restart', base / 'project', ['.'], base / 'project', 'parent')
        for action in ('parent', ''):
            env['MINION_TEST_ACTION'] = action
            run = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=15)
            assert run.returncode == 0, run.stdout + run.stderr
        print('Passed: fresh launch ignores previous browsing scope with saved editor state', flush=True)

        # Keep A running while B changes its scope, then verify A is unchanged.
        command, cwd, env = launch('instance-a', nested, ['.'], nested, 'hold')
        ready, release = base / 'ready', base / 'release'
        env.update(MINION_TEST_READY=str(ready), MINION_TEST_RELEASE=str(release))
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import time
            deadline = time.monotonic() + 5
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.03)
            assert ready.exists(), 'First Neovim instance did not start'
            command, cwd, env = launch('instance-b', base / 'project', ['.'], base / 'project', 'parent')
            run = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=15)
            assert run.returncode == 0, run.stdout + run.stderr
            release.touch()
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 0, stdout + stderr
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        print('Passed: simultaneous Neovim instances keep independent roots', flush=True)


if __name__ == '__main__':
    main()
