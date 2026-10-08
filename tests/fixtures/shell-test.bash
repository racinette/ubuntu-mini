# VM fixture only: observe the line editor after real Foot keyboard events.
source "$HOME/.bashrc"
ble-bind -x C-f12 'printf "%s" "$_ble_edit_str" > "$HOME/mini-os-edit-result.txt"'
printf '%s\n' "$BLE_VERSION" "$__atuin_initialized" > "$HOME/mini-os-shell-startup.txt"
