# Gamepad desktop controls

Post-install setup installs this profile automatically. In the WIN Mini's gamepad mode, the controller navigates applications and the Sway desktop. The hardware mouse mode and trackpad remain independently available. Use the physical QWERTY keyboard for typing.

| Control | Action |
| --- | --- |
| D-pad first | Arrow immediately; hold to accelerate |
| A / B / Y | Enter / Escape / Tab, on release |
| X | Immediate Backspace; repeat while held |
| L2, left trigger | Hold Shift |
| R2, right trigger | Hold Ctrl |
| L1 / R1 | Previous / next numbered workspace, on release; stop at 1, no upper cap |
| L2 + bumper | Send focused window to adjacent workspace without following it |
| R3 | Switch both sticks between Window / Workspace controls, on release |
| Start | Open terminal, on release |
| Select | Window picker, on release |
| Menu / Xbox | Application launcher, on release |
| L3 | Show / dismiss shortcut legend, on release |
| L4 | Toggle display power, without locking or suspending |
| R4 | Toggle Keep awake |

The sticks start in **Window** mode. R3 switches both sticks together:

| Control | Window | Workspace |
| --- | --- | --- |
| Left stick | Scroll vertically/horizontally | Focus window |
| L2 + left stick | Scroll | Move window |
| Right stick | Move the caret with arrows | Resize window |
| L2 + right stick | Select text with Shift+arrows | Resize window |
| R2 + right stick | Ctrl+arrows; words horizontally | Resize window |
| L2 + R2 + right stick | Ctrl+Shift+arrows; select words horizontally | Resize window |

On the WIN Mini 2023, L4 and R4 emit Print Screen and Pause on the separate `12068:309:Mouse_for_Windows` keyboard. A session reader coalesces both ordinary key-repeat events and firmware macro repetitions into one action on release, allowing a 75 ms gap between sequences within a hold. Sway consumes the rear keys while preserving the physical keyboard's Print Screen screenshot shortcut. A device-specific uaccess rule grants the active local user access to this rear keyboard, without adding the user to the input group. No firmware remapping is needed. Other devices or firmware mappings need their own matching and input handling.

L4 toggles display power while applications continue running. A second L4 press restores the display and leaves it on. Keyboard, touchpad, touchscreen or mapped controller input also restores it; this does not unlock a session that was already locked. L4 also works while locked. R4 toggles the explicit **Keep awake** override while unlocked; the bar shows `Awake ON` or `Awake OFF` and can be clicked to toggle it. The override suppresses automatic idle locking and display-off on either power source, survives idle-service restarts and charger changes, and resets at reboot. Turning it off restores fresh battery timers when unplugged; AC already disables those timers.

For a background agent, enable Keep awake with R4, then turn the display off with L4. Keep awake does not unlock an existing lock. Super+L still locks only, and closing the lid or explicitly suspending still locks and suspends. Without Keep awake, the normal five-minute battery idle lock still applies after manually turning the display off. These bindings do not change the power button.

Workspace navigation is open-ended: R1 advances from 4 to 5, 5 to 6 and onward, creating the numbered workspace when needed. L1 moves back one number and stops at 1. L2+bumper sends the focused window to that adjacent number without following it, creating the destination when needed. Empty workspaces disappear when left; returning to their number recreates them. From an unnumbered workspace, either bumper starts at 1. Super+1–4 remain direct keyboard shortcuts.

Window focus and resize actions repeat after a short hold; Window mode uses continuous text movement and scrolling at a speed based on deflection. Dead zones prevent small movements from generating actions. Trigger hysteresis stabilizes held modifiers. Ordinary release actions use the modifiers held when released. X acts on press and uses normal keyboard repeat while held; R2+X deletes words where Ctrl+Backspace is supported.

## Shortcut table

Hold Y/A/B first, then use the D-pad to choose one of the [24 named shortcuts](gamepad-chord-layout.md): editing, text navigation and desktop operations. For example, hold A then Up to close the focused window, Left to toggle fullscreen, Down to toggle tiled/tabbed, or Right to toggle floating. The face prefix has no timeout. The action runs once all participating controls are released, consuming their single actions. X is excluded from all chords. Invalid, unassigned and rolling combos emit nothing.

D-pad first sends an arrow immediately. Holding it starts repetition after 400 ms, increasing from 12 to 25 steps per second in all directions over another 300 ms. The sustained rate matches Sway's default keyboard repeat used by held X; personal keyboard repeat settings can differ. A diagonal sends both arrows at the vertical rate. Changing direction restarts the delay and acceleration; releasing stops immediately without an extra step. L2/R2 add Shift/Ctrl, including changes during a hold. Adding Y/A/B during navigation stops repetition and suppresses the gesture until all those controls are released; it cannot become a combo. A face and direction first observed in the same input frame are also suppressed. To make a combo, press the face button first.

Copy/paste are terminal-aware. Editing actions ignore held triggers for their shortcut and restore them afterward; navigation shortcuts accept Shift/Ctrl. Application support determines Find, Save, Redo and search-match behavior. See the table for details.

Terminal controls use the free A+B prefix: release A+B for Ctrl+C (interrupt), hold both before Up for Ctrl+Z (suspend job), or hold both before Down for Ctrl+D (end input). Release all participating controls to execute once, with no hold deadline or repeats. These actions work only in recognized terminal windows and ignore trigger modifiers. Ctrl+D can exit an empty shell; `fg` resumes a suspended job. The [terminal control reference](gamepad-chord-layout.md#terminal-controls) describes ordering and application behavior.

## Stick contexts and legend

In Window mode, the left stick scrolls and the right stick navigates text like the D-pad. Hold L2 (Shift) to extend selection, R2 (Ctrl) for word movement horizontally, or both for word selection. Ctrl+up/down follows the application's own navigation behavior. Triggers can be pressed or released while the stick remains deflected to switch between movement and selection.

A quick nudge moves once. Holding the stick moves continuously, with light deflection for precision and full deflection for speed. Text movement ranges from 4 to 40 horizontal steps per second and 2 to 10 vertical steps per second. The same speeds apply while selecting. Scrolling ranges from 1 to 18 wheel steps per second in either axis; the dominant axis wins on diagonals. Returning to neutral stops immediately. Text navigation and selection use the focused application's keyboard behavior, such as in a browser text box or editor; they do not provide universal pointer-drag or terminal scrollback selection.

A new scroll gesture positions the pointer at the center of the focused window, then sends full mouse-wheel detents through the virtual input device. Each detent carries 120 high-resolution units plus its legacy wheel event, so applications receive normal wheel distances. Held scrolling checks for a changed focused window or geometry every 200 ms and retargets it. Within an application, the pane under that center point receives the scroll; a split editor may therefore need touchpad positioning or an application-specific command to scroll another pane. Controller Shift/Ctrl are temporarily released around wheel events and restored afterward, so triggers keep ordinary scrolling rather than zooming or changing axes. Physical keyboard modifiers still follow the application's behavior. Wheel scrolling in terminals depends on the running program and its mouse/scrollback handling.

In Workspace mode, the left stick focuses windows, L2+left stick moves them, and the right stick resizes them. Right-stick left/right shrink/grow width; up/down shrink/grow height. These actions retain their fixed repeat timing.

R3 requests a context change. Both sticks must return to neutral before it takes effect; both are suppressed while a change is pending. The bar shows `Window` or `Workspace`. `minion-gamepad --status` reports `stick_mode` and `stick_pending`. Toggling the context alone leaves no keyboard modifier held. Locking, leaving the active desktop, disconnecting, input resynchronization, restarting the service or entering passthrough restores Window.

L3 opens a persistent Fuzzel legend derived from the active shortcut profile. D-pad up/down browse, typing filters the list, and B/Escape, Enter or another L3 tap dismisses it. It remains visible until dismissed. While open, shortcut chords and both sticks are suppressed. The legend closes when mapping is suspended or reset.

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

Setup preserves this file. Top-level settings override the defaults; a nested object replaces that entire object. Chord values are named actions such as `copy`, `close`, `home` and `equalize`, as shown in the default JSON. `actions` assigns named actions to buttons, including `legend` and `stick_context`. The earlier `selection` and `text_navigation` action names remain aliases for `stick_context`; both now switch the shared Window/Workspace context. X must remain Backspace and cannot appear in a chord. Set `chords` to `{}` to disable shortcuts and restore held D-pad arrows. D-pad acceleration uses `dpad_repeat_delay`, `dpad_acceleration_time`, `dpad_rate` and `dpad_line_rate`. Thresholds, repeat timing and resize increments are configurable. `workspace_numbers: null` selects open-ended navigation; an explicit list such as `"workspace_numbers": [1, 2, 3, 4]` retains circular navigation through that list. Existing personal lists are preserved.

Text navigation and selection speed is configurable with `selection_rate` (horizontal) and `selection_line_rate` (vertical), retaining the earlier setting names. Each is a pair of minimum and maximum steps per second, from 1 to 100. Scrolling speed uses `scroll_rate`, another minimum/maximum pair of wheel steps per second. Window focus and resizing retain their existing repeat timing.

Old character-typing profiles and the old `super` action are incompatible with this layout. On a fresh install use the new default; if retaining a personal copy during development, replace its old `chords` and `actions` objects before restarting. No profile migration is performed.

One compatible controller is selected automatically. If several match, set `device` to an exact name or integer USB vendor/product IDs, such as `{"name": "Your controller's exact name"}`. Status reports selection, axis ranges, grab state and recent Sway commands. Inspect failures with `journalctl --user -u minion-gamepad.service -b`.

## Implementation and tested scope

[minion-gamepad](../setup/desktop/minion-gamepad) runs as the logged-in user, reads evdev events, emits keys and wheel scrolling through a shared virtual input device, and sends desktop operations and cursor positioning through Sway IPC. Setup installs Ubuntu's `python3-evdev`, loads uinput and grants the active local user access through a uaccess rule; it does not add the account to the input group.

The mapping follows Xbox/xpad labels: X is Linux BTN_NORTH (307), and Y is BTN_WEST (308). These historical directional aliases do not describe Xbox button positions. The host checker independently feeds driver codes through every assigned gesture, without creating a host input device.

The [VM mapping suite](testing.md#gamepad-tests) covers real applications, shortcuts and lifecycle behavior with a synthetic controller. See recorded results for what has actually run on this revision. Physical controls, suspend and comfort need WIN Mini validation. The rear buttons use their own session reader independently of the controller mapper, including in controller passthrough. Gyro and rumble have no added mappings.
