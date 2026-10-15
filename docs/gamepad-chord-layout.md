# Gamepad shortcuts

The default profile uses A/B + D-pad for editing and navigation, and Select + face buttons for layout toggles. X is immediate, holdable Backspace; Y is immediate, holdable Space. The physical QWERTY keyboard handles typing. The profile is [setup/desktop/gamepad.json](../setup/desktop/gamepad.json); see [controls](gamepad-controls.md) for sticks, single buttons and customization.

| D-pad | + A: editing | + B: navigation/actions |
| --- | --- | --- |
| Up | Copy | Close focused window |
| Down | Paste | Equalize tiled window sizes |
| Left | Undo | Navigation back (Alt+Left) |
| Right | Redo | Navigation forward (Alt+Right) |
| Up-left | Cut | Beginning of document (Ctrl+Home) |
| Up-right | Select all | End of document (Ctrl+End) |
| Down-left | Find | Previous search match (Shift+F3) |
| Down-right | Save | Next search match (F3) |

| Hold Select, then press | Layout action |
| --- | --- |
| A | Toggle fullscreen |
| B | Toggle floating |
| Y | Toggle tiled/tabbed |
| X | Toggle horizontal/vertical split for the next window |

## Enter a shortcut

Hold A/B first, then choose the D-pad direction, or hold Select first, then press one face button. Neither prefix has a timeout. Release all participating controls to execute once. A diagonal is one physical D-pad position. Holding a shortcut does not repeat it. A new press after release has begun cancels the gesture; finish releasing before starting another. Unassigned combinations do nothing.

Single A/B inputs produce Enter/Escape on release. X and Y act immediately and remain held for normal application key repeat. R2+X gives Ctrl+Backspace, and R2+Y gives Ctrl+Space (US/RU switching). Select alone opens the window picker on release. Select+face consumes the picker and face actions, including Space/Backspace. Face-before-Select and simultaneous starts cannot become layout shortcuts. Select+D-pad and multi-face Select gestures are suppressed until all participating controls are released.

D-pad first sends arrows immediately, then repeats after 400 ms and accelerates from 12 to 25 steps per second over another 300 ms. Release stops immediately; direction changes restart the ramp. Adding A/B during navigation stops it and consumes the remaining gesture. Simultaneous face/direction starts are suppressed. L2/R2 add Shift/Ctrl to navigation. X/Y do not prefix D-pad shortcuts.

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

Editing shortcuts have fixed modifiers and restore any held triggers afterward. Redo uses Ctrl+Shift+Z; search matches use Shift+F3/F3. Their behavior depends on the focused application. Document boundaries accept held Shift/Ctrl triggers. For example L2+Up-right+B selects to the end of the document. Navigation history sends fixed Alt+Left/Right, ignoring trigger modifiers; browsers and file managers use their own history, and the default Neovim configuration maps these keys to its jump list.

Desktop actions call Sway directly. Equalize balances tiled siblings recursively within the focused workspace, retains layout/focus, and leaves floating windows alone. Application size constraints can limit balancing.

## Legend and sticks

Hold Menu/Xbox for 0.75 seconds to open a persistent, searchable legend generated from the active profile. It opens once during the hold and consumes the release. Browse it with D-pad up/down; B/Escape, Enter, a short Menu tap or another Menu hold dismisses it. Shortcut chords and stick actions are suppressed while it is open. Short Menu taps otherwise toggle the launcher.

L3 switches only the left stick between Scroll and Text. R3 switches only the right stick between Windows (focus, or move with L2) and Resize. Scroll/Windows are the defaults, and all four combinations work independently. In Text, L2 adds Shift for selection and R2 adds Ctrl for word movement horizontally; both triggers select words where supported. Text navigation and scrolling speed increase with stick deflection; up/down text movement runs more slowly than left/right. Focus, move and resize retain the existing repeat timing.

Switching waits only for the affected stick to return to neutral and suppresses only that stick until then. The bar abbreviates both behaviors, such as `L:T R:W` for Text/Windows; status reports `stick_modes` and `stick_pending` with separate left/right entries. Owned overlays close and both sticks return to Scroll/Windows on lock, inactive session, disconnect, input resynchronization, passthrough or service restart. Switching alone holds no keyboard modifiers; L2 and R2 control Shift and Ctrl. The [control reference](gamepad-controls.md#stick-contexts-and-legend) describes scrolling target and application behavior.

## Verification

`python3 tests/check-chord-recognizer.py` checks all 23 assignments in 148 valid press/release orders, unlimited prefix holds, terminal-only Ctrl+C/Z/D, complete A+B prefixes, wrong-order/simultaneous suppression, immediate and accelerated D-pad navigation, single keys, immediate Backspace/Space holds, Select-first layout shortcuts and invalid ordering, modifier restoration, terminal guards, invalid/rolling gestures, neutral mode transitions, stick selection/repeat, legend capture, profile validation and lifecycle cleanup. It creates no input device. Real application and Sway checks are recorded in [testing](testing.md); physical controller comfort and suspend behavior still need device QA.
