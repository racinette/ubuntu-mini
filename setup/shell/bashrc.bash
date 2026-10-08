# Source at the end of the user's .bashrc. Noninteractive shells remain plain Bash.
[[ $- == *i* ]] || return
[[ ${MINI_OS_SHELL_LOADED-} ]] && return
MINI_OS_SHELL_LOADED=1
source /usr/local/share/blesh/ble.sh --attach=none
eval "$(/usr/local/bin/atuin init bash)"
# Keep '?' ordinary shell input; this profile uses Atuin for local history.
ble-bind -f '?' self-insert
# Foot sends Ctrl+W for Ctrl+Backspace. Bind after Atuin, independent of layout.
ble-bind -f C-w kill-backward-sword
ble-attach
