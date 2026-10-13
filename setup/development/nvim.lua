-- Default Neovim configuration for project browsing, editing and navigation.
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1
vim.g.mapleader = ' '
vim.opt.termguicolors = true
vim.opt.mouse = 'a'
vim.opt.clipboard = 'unnamedplus'
vim.opt.keymodel = 'startsel,stopsel'
vim.opt.number = true
vim.opt.signcolumn = 'yes'
vim.opt.wrap = false
vim.opt.scrolloff = 3
vim.opt.sidescrolloff = 3
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.updatetime = 1000
vim.opt.ttimeoutlen = 20
vim.opt.autoread = true
vim.opt.swapfile = false
vim.opt.undofile = false
vim.opt.modeline = false
vim.opt.exrc = false
vim.opt.laststatus = 3
vim.opt.showmode = false
vim.opt.statusline = ' F1 Help  F2 Tree  F3 Files  F4 Search %= %y %l:%c %m%r '
vim.cmd('syntax enable')

for _, plugin in ipairs({ 'mini.nvim', 'nvim-tree.lua', 'nvim-lspconfig' }) do
  vim.cmd.packadd(plugin)
end
require('mini.icons').setup({ style = 'ascii' })
require('mini.pick').setup({
  window = { config = function()
    return { width = math.max(20, vim.o.columns - 6), height = math.max(5, vim.o.lines - 6) }
  end },
})
require('mini.extra').setup()
local pick, extra = MiniPick.builtin, MiniExtra.pickers
local tree = require('nvim-tree.api')
local root_markers = { '.git', 'Cargo.toml', 'go.mod', 'pyproject.toml', 'package.json', 'CMakeLists.txt' }
local start_path = vim.fn.argc() > 0 and vim.fn.fnamemodify(vim.fn.argv(0), ':p') or vim.fn.getcwd()
local project_root = vim.fs.root(start_path, root_markers)
if not project_root and vim.fn.isdirectory(start_path) == 1 then project_root = start_path end
if project_root then vim.api.nvim_set_current_dir(project_root) end
require('nvim-tree').setup({
  sync_root_with_cwd = true,
  update_focused_file = { enable = true, update_root = true },
  view = { width = 26 },
  renderer = {
    group_empty = true,
    icons = { show = { file = false, folder = false, folder_arrow = false, git = false, modified = false, diagnostics = false, bookmarks = false } },
  },
  actions = { open_file = { quit_on_open = true, window_picker = { enable = false } } },
  git = { enable = true },
  on_attach = function(buf)
    tree.map.on_attach.default(buf)
    -- Add handheld navigation to the usual file-tree controls.
    local function map(key, action, description)
      vim.keymap.set('n', key, action, { buffer = buf, silent = true, nowait = true, desc = description })
    end
    map('<CR>', tree.node.open.edit, 'Open file/folder')
    map('<Right>', tree.node.open.edit, 'Open file/folder')
    map('<Left>', tree.node.navigate.parent_close, 'Parent/collapse folder')
    map('<BS>', function()
      project_root = nil
      tree.tree.change_root_to_parent()
    end, 'Browse parent directory')
    map('<Esc>', tree.tree.close, 'Close tree')
    map('<Tab>', tree.tree.close, 'Return to code')
    map('q', tree.tree.close, 'Close tree')
    map('R', tree.tree.reload, 'Refresh files')
    map('f', tree.filter.live.start, 'Filter files')
    map('F', tree.filter.live.clear, 'Clear filter')
    map('H', tree.filter.dotfiles.toggle, 'Toggle hidden files')
    map('<2-LeftMouse>', tree.node.open.edit, 'Open file/folder')
  end,
})

local function select_project(args)
  if vim.bo[args.buf].buftype == '' then
    -- Choose a project when browsing from home, but keep searches there while
    -- following definitions into dependency sources and standard libraries.
    if not project_root then
      project_root = vim.fs.root(args.buf, root_markers)
      if project_root then vim.api.nvim_set_current_dir(project_root) end
    end
  end
end
vim.api.nvim_create_autocmd({ 'BufReadPost', 'BufNewFile' }, { callback = select_project })
vim.api.nvim_create_autocmd({ 'FocusGained', 'BufEnter', 'CursorHold' }, {
  callback = function() if vim.fn.getcmdwintype() == '' then vim.cmd('checktime') end end,
})

local function back()
  vim.cmd('normal! ' .. vim.api.nvim_replace_termcodes('<C-o>', true, false, true))
end
local function lsp(action)
  if #vim.lsp.get_clients({ bufnr = 0 }) == 0 then
    return vim.notify('No language server attached to this file yet')
  end
  action()
end
local mappings = {
  ['<F2>'] = { tree.tree.toggle, 'File tree' },
  ['<F3>'] = { pick.files, 'Find file' },
  ['<C-p>'] = { pick.files, 'Find file' },
  ['<F4>'] = { pick.grep_live, 'Search project text' },
  ['<C-f>'] = { pick.grep_live, 'Search project text' },
  ['<F5>'] = { function() extra.lsp({ scope = 'document_symbol' }) end, 'File symbols' },
  ['<F6>'] = { function() extra.lsp({ scope = 'workspace_symbol_live' }) end, 'Search project symbols' },
  ['<CR>'] = { function() lsp(vim.lsp.buf.definition) end, 'Go to definition' },
  ['gd'] = { function() lsp(vim.lsp.buf.definition) end, 'Go to definition' },
  ['gr'] = { function() lsp(function() extra.lsp({ scope = 'references' }) end) end, 'Find references' },
  ['K'] = { function() lsp(vim.lsp.buf.hover) end, 'Documentation/type' },
  ['<BS>'] = { back, 'Previous location' },
  ['<Esc>'] = { back, 'Previous location' },
  ['<M-Left>'] = { back, 'Navigation back' },
  ['<M-Right>'] = { '<C-i>', 'Navigation forward' },
  ['<Tab>'] = { '<Cmd>bnext<CR>', 'Next open file' },
  ['<S-Tab>'] = { '<Cmd>bprevious<CR>', 'Previous open file' },
}
for key, mapping in pairs(mappings) do
  vim.keymap.set('n', key, mapping[1], { silent = true, desc = mapping[2] })
end

vim.keymap.set('n', '<F1>', function()
  local lines = {
    'Neovim — project navigation', '',
    'F2          Open/close file tree',
    'F3 / Ctrl+P Find a file by name',
    'F4 / Ctrl+F Search text across the project',
    'F5 / F6     File symbols / search project symbols',
    'Enter / gd  Follow definition',
    'gr          Find references',
    'K           Documentation and type information',
    'Esc / BS    Return to previous location',
    'Alt+Left/Right  Back/forward through jump history',
    'Tab         Next open file (Shift+Tab: previous)',
    '/, n, N     Search this file; next/previous match',
    'Arrows      Navigate; Left/Right browse folders',
    'Stick/wheel Scroll; touchpad clicks select code',
    'i / Esc     Start editing / return to normal mode',
    ':w          Save file',
    ':q / :qa    Quit window / Neovim', '',
    'Pickers: type to filter, arrows to move, Enter to open, Esc to cancel.',
    'Tree: Backspace browses the parent directory; R refreshes.',
  }
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.bo[buf].modifiable = false
  local win = vim.api.nvim_open_win(buf, true, {
    relative = 'editor', style = 'minimal', border = 'rounded',
    width = math.min(74, vim.o.columns - 4), height = math.min(#lines, vim.o.lines - 4),
    row = 1, col = 1,
  })
  for _, key in ipairs({ '<Esc>', '<CR>', 'q', '<F1>' }) do
    vim.keymap.set('n', key, function() vim.api.nvim_win_close(win, true) end, { buffer = buf })
  end
end, { desc = 'Project navigation help' })

local servers = {
  'gopls', 'rust_analyzer', 'tsc', 'pyright', 'bashls', 'jsonls', 'yamlls', 'taplo', 'clangd', 'html', 'cssls',
}
for _, server in ipairs(servers) do
  vim.lsp.enable(server)
end
vim.diagnostic.config({ virtual_text = false, signs = false, underline = true })

vim.api.nvim_create_autocmd('VimEnter', {
  callback = function()
    if vim.fn.argc() == 0 or vim.fn.isdirectory(vim.fn.argv(0)) == 1 then
      tree.tree.open({ path = project_root or vim.fn.getcwd() })
    end
  end,
})
