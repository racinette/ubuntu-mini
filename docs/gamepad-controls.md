# Gamepad desktop controls

Post-install setup installs this profile automatically. In the WIN Mini's gamepad mode, the controller navigates applications and the Sway desktop. The hardware mouse mode and trackpad remain independently available. Use the physical QWERTY keyboard for typing.

| Control | Action |
| --- | --- |
| D-pad single direction | Arrow key, on release |
| A / B / Y | Enter / Escape / Tab, on release |
| X | Immediate Backspace; repeat while held |
| L2, left trigger | Hold Shift |
| R2, right trigger | Hold Ctrl |
| L1 / R1 | Previous / next workspace, on release |
| L2 + bumper | Send focused window to adjacent workspace without following it |
| Left stick | Focus window in that direction |
| L2 + left stick | Move window in that direction |
| Right stick | Resize, or extend text selection in selection mode |
| R3 | Toggle right-stick Resize / Select text mode, on release |
| Start | Open terminal, on release |
| Select | Window picker, on release |
| Menu / Xbox | Application launcher, on release |
| L3 | Show / dismiss shortcut legend, on release |
| L4 / R4 | Unassigned |

Workspaces cycle through 1–4. Stick directions repeat after a short hold; dead zones prevent small movements from generating actions. Trigger hysteresis stabilizes held modifiers. Ordinary release actions use the modifiers held when released. X acts on press and uses normal keyboard repeat while held; R2+X deletes words where Ctrl+Backspace is supported.

## Shortcut table

D-pad + Y/A/B execute the [24 named shortcuts](gamepad-chord-layout.md): editing, text navigation and desktop operations. Up+A closes the focused window, Left+A toggles fullscreen, Down+A toggles tiled/tabbed, and Right+A toggles floating. X is excluded from all chords. Inputs may be pressed in either order; the action runs once all participating controls are released, consuming their single actions. Invalid, unassigned and rolling gestures emit nothing. Single D-pad directions wait for release and do not repeat.

Copy/paste are terminal-aware. Editing actions ignore held triggers for their shortcut and restore them afterward; navigation shortcuts accept Shift/Ctrl. Application support determines Find, Save, Redo and search-match behavior. See the table for details.

## Right-stick modes and legend

Right-stick left/right shrink/grow window width; up/down shrink/grow height. R3 switches to Select text: left/right emit Shift+Left/Right, and up/down Shift+Up/Down. Hold R2 to add Ctrl for word selection horizontally. Selection works where the application supports keyboard text selection. It does not provide a universal pointer-drag selection.

The stick must return to neutral before a mode switch takes effect. The bar continuously shows `R: Resize` or `R: Select text`. `minion-gamepad --status` reports `right_stick_mode` and `right_stick_pending`. Toggling the mode alone leaves no keyboard modifier held. Locking, leaving the active desktop, disconnecting, input resynchronization, restarting the service or entering passthrough restores Resize.

L3 opens a persistent Fuzzel legend derived from the active shortcut profile. D-pad up/down browse, typing filters the list, and B/Escape, Enter or another L3 tap dismisses it. It remains visible until dismissed. While open, shortcut chords and stick window actions are suppressed. The legend closes when mapping is suspended or reset.

The window picker lists windows across workspaces, with the current window first. D-pad up/down selects, A focuses the selected window, and B cancels. Typing filters by application, title or workspace. The launcher uses the same navigation keys. Optional buttons missing from a controller are reported in status.

## Switch to normal gamepad input

Hold Start+Select together for at least 0.75 seconds, then release both, or press Super+Ctrl+G. A notification shows the mode. Any overlapping Start/Select press consumes their individual actions, including a short overlap. In passthrough the mapper releases its controller grab and all keyboard keys so games receive normal input. The toggle gesture also reaches games; use the keyboard shortcut if it conflicts.

```bash
minion-gamepad --toggle
minion-gamepad --status
```

Passthrough mode survives service restart while the user's runtime directory exists; cold boot starts in desktop mode. Reconnect/resume/restart requires buttons, triggers and sticks to return to neutral. Disconnecting or leaving the active desktop releases held keys. The lock command pauses mapping until unlock.

## Personal profile

The [default profile](../setup/desktop/gamepad.json) is installed as `/etc/minion/gamepad.json`. Create a personal copy as your normal desktop user:

```bash
mkdir -p ~/.config/minion
test -e ~/.config/minion/gamepad.json || cp /etc/minion/gamepad.json ~/.config/minion/gamepad.json
# Edit the personal file, then apply:
systemctl --user restart minion-gamepad.service
minion-gamepad --status
```

Setup preserves this file. Top-level settings override the defaults; a nested object replaces that entire object. Chord values are named actions such as `copy`, `close`, `home` and `equalize`, as shown in the default JSON. `actions` assigns named actions to buttons, including `legend` and `selection`. X must remain Backspace and cannot appear in a chord. Set `chords` to `{}` to disable shortcuts and restore held D-pad arrows. Thresholds, repeat timing, workspace numbers and resize increments are configurable.

Old character-typing profiles and the old `super` action are incompatible with this layout. On a fresh install use the new default; if retaining a personal copy during development, replace its old `chords` and `actions` objects before restarting. No profile migration is performed.

One compatible controller is selected automatically. If several match, set `device` to an exact name or integer USB vendor/product IDs, such as `{"name": "Your controller's exact name"}`. Status reports selection, axis ranges, grab state and recent Sway commands. Inspect failures with `journalctl --user -u minion-gamepad.service -b`.

## Implementation and tested scope

[minion-gamepad](../setup/desktop/minion-gamepad) runs as the logged-in user, reads evdev events, emits keys through the virtual keyboard, and sends desktop operations through Sway IPC. Setup installs Ubuntu's `python3-evdev`, loads uinput and grants the active local user access through a uaccess rule; it does not add the account to the input group.

The mapping follows Xbox/xpad labels: X is Linux BTN_NORTH (307), and Y is BTN_WEST (308). These historical directional aliases do not describe Xbox button positions. The host checker independently feeds driver codes through every assigned gesture, without creating a host input device.

The [VM mapping suite](testing.md#gamepad-tests) covers real applications, shortcuts and lifecycle behavior with a synthetic controller. See recorded results for what has actually run on this revision. Physical controls, suspend and comfort need WIN Mini validation. Rear buttons, gyro and rumble have no added mappings.
