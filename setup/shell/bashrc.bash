# Source at the end of the user's .bashrc. Noninteractive shells remain plain Bash.
[[ $- == *i* ]] || return
# Terminal fallback for GPG; the desktop normally uses a graphical pinentry.
if [[ -t 0 ]]; then
  export GPG_TTY=$(tty)
fi
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# Preserve forwarded/personal agents; recover stale sockets or canonicalize aliases.
if [[ -S "${XDG_RUNTIME_DIR:-/run/user/$UID}/openssh_agent" &&
      ( ! -S "${SSH_AUTH_SOCK:-}" || "${SSH_AUTH_SOCK:-}" -ef "${XDG_RUNTIME_DIR:-/run/user/$UID}/openssh_agent" ) ]]; then
  export SSH_AUTH_SOCK="${XDG_RUNTIME_DIR:-/run/user/$UID}/openssh_agent"
fi
[[ ${MINION_SHELL_LOADED-} ]] && return
MINION_SHELL_LOADED=1
# Foot 1.16.2 can duplicate Enter/Backspace with Codex keyboard enhancement.
export CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT=1
if [[ -d "$HOME/.cargo/bin" ]]; then
  case ":$PATH:" in
    *":$HOME/.cargo/bin:"*) ;;
    *) export PATH="$HOME/.cargo/bin:$PATH" ;;
  esac
fi
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate bash)"
fi
source /usr/local/share/blesh/ble.sh --attach=none
eval "$(/usr/local/bin/atuin init bash)"
# Keep '?' ordinary shell input; this profile uses Atuin for local history.
ble-bind -f '?' self-insert
# Foot sends Ctrl+W for Ctrl+Backspace. Bind after Atuin, independent of layout.
ble-bind -f C-w kill-backward-sword
ble-attach
