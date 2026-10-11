# Gamepad shortcuts

The default profile uses D-pad + Y/A/B for named actions. X is reserved for immediate, holdable Backspace. The physical QWERTY keyboard handles typing. The profile is [setup/desktop/gamepad.json](../setup/desktop/gamepad.json); see [controls](gamepad-controls.md) for sticks, single buttons and customization.

| D-pad | + Y: editing | + A: desktop | + B: navigation |
| --- | --- | --- | --- |
| Up | Copy | Close focused window | Page Up |
| Down | Paste | Toggle tiled/tabbed | Page Down |
| Left | Undo | Toggle fullscreen | Beginning of line (Home) |
| Right | Redo | Toggle floating | End of line (End) |
| Up-left | Cut | Open file manager | Beginning of document (Ctrl+Home) |
| Up-right | Select all | Horizontal/vertical split for the next window | End of document (Ctrl+End) |
| Down-left | Find | Equalize tiled window sizes | Previous search match (Shift+F3) |
| Down-right | Save | Screenshot to clipboard | Next search match (F3) |

## Enter a shortcut

Hold the D-pad direction and face button so they overlap, in either order. Release all participating controls to execute once. A diagonal is one physical D-pad position. Constituent arrows, Enter, Escape and Tab are consumed. Holding a shortcut does not repeat it. A new press after release has begun cancels the gesture; finish releasing before starting another. Unassigned combinations do nothing.

Single A/B/Y inputs produce Enter/Escape/Tab on release. Single D-pad directions produce arrows on release. X presses Backspace immediately, remains held for application key repeat, and releases immediately. R2+X gives Ctrl+Backspace. X never participates in shortcut recognition.

## Modifiers and application behavior

Copy/paste use Ctrl+C/V in graphical applications and Ctrl+Shift+C/V in Foot, including Foot windows with custom application IDs. Other detected terminals receive no editing shortcut. Cut, undo, redo, select all, find, save and search-match commands are skipped in detected terminals; this prevents shell interrupts, suspension or prefix commands. If the client cannot be identified, these actions are skipped with a notification.

Editing shortcuts have fixed modifiers and restore any held triggers afterward. Redo uses Ctrl+Shift+Z; search matches use Shift+F3/F3. Their behavior depends on the focused application. Home/End, Page Up/Down and document boundaries accept held Shift/Ctrl triggers. For example L2+Right+B selects to the end of the line.

Desktop actions call Sway directly. Equalize balances tiled siblings recursively within the focused workspace, retains layout/focus, and leaves floating windows alone. Application size constraints can limit balancing. Screenshot copies the whole display image to the clipboard, like Print Screen.

## Legend and right stick

Tap L3 to open a persistent, searchable legend generated from the active profile. Browse it with D-pad up/down; B/Escape, Enter or another L3 tap dismisses it. Shortcut chords and stick window actions are suppressed while it is open.

R3 toggles the right stick between resizing and text selection. Selection sends Shift+arrows; R2 adds Ctrl for word selection horizontally where supported. Both modes repeat while held. Switching waits for neutral and suspends stick actions until then. The bar shows `R: Resize` or `R: Select text`; status also reports a pending switch. Selection uses the focused application's keyboard behavior, so editors/text fields work best and terminal scrollback or arbitrary displayed text may require application-specific controls.

The legend closes and the right stick returns to Resize on lock, inactive session, disconnect, input resynchronization, passthrough or service restart. No Shift modifier remains held just because selection mode is enabled.

## Verification

`python3 tests/check-chord-recognizer.py` checks all 24 assignments in 480 press/release orders, single keys, immediate Backspace holds, modifier restoration, terminal guards, invalid/rolling gestures, neutral mode transitions, stick selection/repeat, legend capture, profile validation and lifecycle cleanup. It creates no input device. Real application and Sway checks are recorded in [testing](testing.md); physical controller comfort and suspend behavior still need device QA.
