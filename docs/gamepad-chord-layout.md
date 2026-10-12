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

Hold Y/A/B first, then choose the D-pad direction. There is no deadline for completing the combo. Release all participating controls to execute once. A diagonal is one physical D-pad position. Constituent arrows, Enter, Escape and Tab are consumed. Holding a shortcut does not repeat it. A new press after release has begun cancels the gesture; finish releasing before starting another. Unassigned combinations do nothing. The table and profile names identify the participating controls; the face button always goes first.

Single A/B/Y inputs produce Enter/Escape/Tab on release. D-pad first sends arrows immediately, then repeats after 400 ms and accelerates while held. All directions ramp from 12 to 25 steps per second over another 300 ms, reaching the default keyboard repeat rate used by held X. Release stops immediately; direction changes restart the ramp. Adding A/B/Y during navigation stops it and consumes the remaining gesture instead of executing a combo. Simultaneous face/direction starts are suppressed. L2/R2 add Shift/Ctrl to navigation. X presses Backspace immediately, remains held for application key repeat, and releases immediately. R2+X gives Ctrl+Backspace. X never participates in shortcut recognition.

## Terminal controls

| Gesture | Action |
| --- | --- |
| A+B | Interrupt / cancel (Ctrl+C) |
| Hold A+B, then Up | Suspend the foreground job (Ctrl+Z) |
| Hold A+B, then Down | End input (Ctrl+D) |

Both face buttons must be held before adding a direction. They may be pressed in either order or together, with no deadline. Release every participating control to execute once; holding does not repeat. Adding the second face button alongside or after the direction suppresses the gesture. Unassigned directions do nothing rather than falling back to interruption.

These controls send literal Ctrl+C/Z/D only in recognized terminal windows, including Foot with custom application IDs. They are skipped in graphical applications and when the client cannot be identified. Held triggers do not change their modifiers. Terminal applications determine the result: Ctrl+C normally interrupts a foreground command, Ctrl+Z normally suspends it (use `fg` to resume), and Ctrl+D ends input rather than sending a signal; at an empty shell prompt it can exit the shell. No Enter/Escape or arrow leaks from these gestures.

## Modifiers and application behavior

Copy/paste use Ctrl+C/V in graphical applications and Ctrl+Shift+C/V in Foot, including Foot windows with custom application IDs. Other detected terminals receive no editing shortcut. Cut, undo, redo, select all, find, save and search-match commands are skipped in detected terminals; this prevents shell interrupts, suspension or prefix commands. If the client cannot be identified, these actions are skipped with a notification.

Editing shortcuts have fixed modifiers and restore any held triggers afterward. Redo uses Ctrl+Shift+Z; search matches use Shift+F3/F3. Their behavior depends on the focused application. Home/End, Page Up/Down and document boundaries accept held Shift/Ctrl triggers. For example L2+Right+B selects to the end of the line.

Desktop actions call Sway directly. Equalize balances tiled siblings recursively within the focused workspace, retains layout/focus, and leaves floating windows alone. Application size constraints can limit balancing. Screenshot copies the whole display image to the clipboard, like Print Screen.

## Legend and right stick

Tap L3 to open a persistent, searchable legend generated from the active profile. Browse it with D-pad up/down; B/Escape, Enter or another L3 tap dismisses it. Shortcut chords and stick window actions are suppressed while it is open.

R3 switches both sticks between Window and Workspace controls. Window is the default: left scrolls, right navigates text; L2 adds Shift for selection and R2 adds Ctrl for word movement horizontally. Both triggers select words where supported. Text navigation and scrolling speed increase with stick deflection; up/down text movement runs more slowly than left/right. Workspace uses left-stick focus, L2+left-stick move and right-stick resize, with the existing repeat timing.

Switching waits for both sticks to return to neutral and suppresses both until then. The bar shows `Window` or `Workspace`; status reports `stick_mode` and `stick_pending`. The legend closes and the context returns to Window on lock, inactive session, disconnect, input resynchronization, passthrough or service restart. Entering Window mode alone holds no keyboard modifiers; L2 and R2 control Shift and Ctrl. The [control reference](gamepad-controls.md#stick-contexts-and-legend) describes scrolling target and application behavior.

## Verification

`python3 tests/check-chord-recognizer.py` checks all 27 assignments in 196 face-first press/release orders, unlimited prefix holds, terminal-only Ctrl+C/Z/D, complete A+B prefixes, wrong-order/simultaneous suppression, immediate and accelerated D-pad navigation, single keys, immediate Backspace holds, modifier restoration, terminal guards, invalid/rolling gestures, neutral mode transitions, stick selection/repeat, legend capture, profile validation and lifecycle cleanup. It creates no input device. Real application and Sway checks are recorded in [testing](testing.md); physical controller comfort and suspend behavior still need device QA.
