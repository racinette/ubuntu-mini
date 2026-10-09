# Gamepad desktop controls

Post-install setup installs this profile automatically. In the WIN Mini's gamepad mode, the controller navigates applications and the Sway desktop. The hardware mouse mode and trackpad remain available independently.

| Control | Action |
| --- | --- |
| D-pad single direction | Arrow key, on release |
| A / B / X / Y | Enter / Escape / Backspace / Tab, on release |
| L2, left trigger | Hold Shift |
| R2, right trigger | Hold Ctrl |
| L1, left bumper | Previous workspace, on release |
| R1, right bumper | Next workspace, on release |
| Left stick | Focus the window in that direction |
| Shift + left stick | Move the window in that direction |
| Right stick | Resize the window: right/down grow width/height; left/up shrink |
| Shift + bumper | Send the focused window to the adjacent workspace, keeping the current workspace selected |
| Start | Open a terminal, on release |
| Select | Open the window picker, on release |
| Menu / Xbox | Open the application launcher, on release |
| Left stick click, L3 | Arm commands / Super chords; tap again to cancel, on release |
| Right stick click, R3 | Toggle fullscreen, on release |
| L4 / R4 | Unassigned |

Workspaces cycle through 1–4. Stick actions repeat after a short hold; dead zones prevent small movements from generating actions. Triggers use separate press/release thresholds to keep a held modifier stable.

Discrete button actions wait for release and do not repeat while held. The modifier state at release determines the action, so you can press a face button or bumper first, hold a trigger, and then release the button to perform the combination. Shift/Ctrl remain held modifiers; stick directions retain their hold/repeat behavior.

D-pad and face buttons also support the [V1 typing chords](gamepad-chord-layout.md). Single inputs keep the actions above. Overlapping inputs form one gesture and emit one key after every participating D-pad direction and face button has been released. A chord consumes its constituent actions, so typing does not also move the cursor or press Enter. D-pad directions now wait for release and do not repeat while held. No typing mode or onscreen keyboard is required.

The window picker lists open windows across workspaces, with the current window first. Use D-pad up/down to select, A to focus that window, and B to cancel. Typing filters the list by application, window title or workspace. The application launcher uses the same navigation keys. The Menu/L3/R3 actions are optional capabilities; if a controller does not expose one of these buttons on its gamepad event device, status reports the unavailable action while the main navigation controls remain usable.

The face buttons are keyboard keys, so applications determine their behavior. For example, Shift + D-pad selects text; Ctrl + left/right moves by words; Ctrl + X emits Ctrl+Backspace to delete a word. Shift + Y reverses application focus. In Firefox, Ctrl + Y changes tabs and Ctrl + Shift + Y changes them in reverse.

## L3 commands and one-shot Super

Tap and release **L3**, then press and release one control from this table. Each command exits the layer. A brief notification shows the legend; arming alone emits no keyboard key and does not affect the physical keyboard. `mini-os-gamepad --status` reports `super_armed` while the layer is waiting.

| After tapping L3 | Command |
| --- | --- |
| X | Close the focused window |
| Y | Toggle tabbed / tiled layout |
| A | Open a terminal |
| B | Cancel, without sending Escape |
| Up | Copy |
| Down | Paste |
| Left | Undo in graphical applications |
| Right | Redo in graphical applications |

Copy/paste use Ctrl+Shift+C/V in Foot, including Foot windows with custom application IDs, and Ctrl+C/V in graphical applications. Undo uses Ctrl+Z; redo uses Ctrl+Shift+Z, whose support depends on the application. Detected terminals receive neither undo nor redo, so this command does not suspend a shell job. Other detected terminal emulators receive no clipboard command either. If the focused client process cannot be identified, clipboard/editing commands are skipped with a notification. Application identifiers and the client executable identify common terminals; terminal sessions embedded inside graphical applications are treated as part of that application.

Commands ignore held Shift/Ctrl triggers for their shortcut, then restore those held modifiers. They fire once, after release. A second L3 tap or L3 followed by B cancels. Direct button actions (Start, Select, Menu, R3 and bumpers) also cancel the layer before doing their usual action. Stick navigation and trigger changes leave it armed.

**Typing chords retain one-shot Super.** Tap L3, then enter any assigned multi-input typing chord. The mapper presses Super immediately before the emitted key and releases it afterward, so both thumbs are free to enter the chord.

| After tapping L3 | Shortcut | Result |
| --- | --- | --- |
| Up+Y (`e`) | Super+E | Open the file manager |
| Right+Y (`d`) | Super+D | Open the application launcher |
| Right+A (`f`) | Super+F | Toggle fullscreen |

Shift/Ctrl triggers still combine with these typing chords: L3, hold L2, then Up+X+Y (`q`) emits Super+Shift+Q. Keep the trigger held until the chord finishes. Invalid/unassigned gestures leave the layer armed so you can retry. Single controls use the command table instead of emitting Super+arrows or Super+face keys.

Locking, switching away from the graphical session, disconnecting, input resynchronization, service restart and switching to normal gamepad input clear the layer. It is never restored after reconnect/restart. With typing chords disabled in a personal profile, ordinary D-pad arrows retain their held/repeating behavior; armed commands still wait for release and consume their constituent input.

## Switch to normal gamepad input

Hold **Start + Select together for at least 0.75 seconds, then release both**, or press **Super+Ctrl+G**, to toggle between desktop navigation and passthrough. A notification shows the selected mode. Overlapping Start/Select presses consume both individual actions, even if released before the hold threshold: no terminal or picker opens. In passthrough, the mapper releases its exclusive controller grab and all mapped keyboard keys, allowing games to receive normal gamepad input. The Start/Select chord also reaches games in this mode; use the keyboard shortcut if that chord conflicts with a game.

The same commands work from a terminal in the graphical session:

```bash
mini-os-gamepad --toggle
mini-os-gamepad --status
```

The selected mode survives a service restart while the user's runtime directory exists. A cold boot starts in desktop mode. After reconnecting, resuming the session or restarting the service, release buttons and return sticks/triggers to neutral before navigation resumes. Disconnecting or leaving the active desktop releases held keys. The configured lock command pauses mapping before showing the password lock and resumes it after unlock.

## Personal profile

The repository default is [setup/desktop/gamepad.json](../setup/desktop/gamepad.json). Setup installs it as `/etc/mini-os/gamepad.json`. Create a personal copy as your normal desktop user:

```bash
mkdir -p ~/.config/mini-os
test -e ~/.config/mini-os/gamepad.json || cp /etc/mini-os/gamepad.json ~/.config/mini-os/gamepad.json
# Edit ~/.config/mini-os/gamepad.json, then apply it:
systemctl --user restart mini-os-gamepad.service
mini-os-gamepad --status
```

Setup reruns preserve this personal file. Its top-level settings override the default; a nested object replaces that entire object. Copying the complete default makes button edits straightforward. You can adjust workspace numbers, axis/button symbols, thresholds, repeat timing and resize increments. The `actions` object assigns desktop actions (`terminal`, `window_picker`, `launcher`, `layout`, `fullscreen`, `super`) to button symbols; set it to `{}` to disable these extra actions. The default assigns `super` to `BTN_THUMBL` (L3); personal action maps retain their own assignments. The `chords` object maps combinations to ordinary Linux keyboard codes; set it to `{}` to disable typing chords and restore held D-pad arrows/repeat. `chord_axes` lists the horizontal and vertical D-pad axes. Profiles copied before these settings were added inherit them from the current default.

The mapper automatically chooses one accessible controller with all configured controls. If several controllers match, it waits for an explicit selector. Set `device` to an exact name, or integer USB vendor/product IDs, for example `{"name": "Your controller's exact name"}`. Status reports the selected name, axis ranges, grab state and recent Sway commands. Inspect failures with `journalctl --user -u mini-os-gamepad.service -b`.

## Implementation and tested scope

[mini-os-gamepad](../setup/desktop/mini-os-gamepad) is a Python service running as the logged-in user. It reads Linux evdev controller events, emits keys through a virtual keyboard using [python-evdev/uinput](https://python-evdev.readthedocs.io/en/latest/tutorial.html), and sends window/workspace commands directly to Sway's IPC socket. Setup installs `python3-evdev` from Ubuntu. The source repository contains no controller binary or downloaded driver.

Setup loads the packaged `uinput` module and grants its device access to the active local user through a `uaccess` rule, following the pattern used by [AntiMicroX](https://github.com/AntiMicroX/antimicrox/blob/master/other/60-antimicrox-uinput.rules). It does not add the account to the input group. Controller access uses the existing session permissions.

The default face mapping follows Xbox/xpad button labels. Linux's historical aliases put Xbox X at `BTN_NORTH` (`BTN_X`, event code 307) and Y at `BTN_WEST` (`BTN_Y`, event code 308); those directional names do not describe their physical positions on an Xbox-layout controller. Physical WIN Mini QA confirmed that the earlier position-based assumption swapped Backspace/Tab and suppressed the Y+B and X+A chords. The corrected host checker feeds independent Xbox event codes into every chord case. It also checks all eight command singles, clipboard/editing shortcuts, terminal detection, trigger restoration and cancellation. These frame tests create no host input device.

The [VM mapping tests](testing.md#gamepad-tests) exercise real application keys, Sway actions and lifecycle behavior with a synthetic Linux controller. The previous recorded VM result used the old X/Y assumption; the corrected VM harness has not yet been rerun. Trigger axes, hardware switch and behavior after suspend still require physical validation. Rear buttons, gyro and rumble have no added mappings.
