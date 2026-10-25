# Gamepad desktop controls

Post-install setup installs desktop and REAPER mappings plus normal gamepad passthrough. Hold Start+Select for 0.75 seconds, then release both, to cycle **Desktop → REAPER → Gamepad → Desktop**. Super+Ctrl+G and `minion-gamepad --toggle` use the same cycle. The hardware mouse mode and trackpad remain independently available. Use the physical QWERTY keyboard for typing. The following table describes Desktop mode.

| Control | Action |
| --- | --- |
| D-pad first | Arrow immediately; hold to accelerate |
| A / B | Enter / Escape, on release |
| Y | Immediate Space; repeat while held |
| X | Immediate Backspace; repeat while held |
| L2, left trigger | Hold Shift |
| R2, right trigger | Hold Ctrl |
| L1 / R1 | Previous / next numbered workspace, on release; wrap in both directions |
| L2 + bumper | Send focused window to adjacent workspace without following it |
| R3 | Switch right stick between window focus/move / resize, on release |
| Start | Tap: terminal in the focused Foot shell's directory; hold 0.75 s then release: file manager |
| Select | Toggle window picker, on release |
| Menu / Xbox | Tap: toggle launcher; hold 0.75 s: toggle shortcut legend |
| L3 | Switch left stick between scroll / text navigation, on release |
| L4 | Unassigned |
| R4 | Tap: start/stop dictation; hold 0.75 s: cancel |
| Fn+F3 | Toggle display power, without locking or suspending |
| Fn+F4 | Toggle Keep awake |
| Fn+F5 | Toggle internal display between 60 and 120 Hz; remember the selection |
| Fn+F6 | Unassigned |

The left stick starts in **Scroll**, and the right in **Windows** (focus/move). L3 and R3 switch their own stick independently; all four combinations are available:

| Control | Primary behavior | Secondary behavior |
| --- | --- | --- |
| Left stick | Scroll vertically/horizontally | Move the caret with arrows |
| L2 + left stick | Scroll | Select text with Shift+arrows |
| R2 + left stick | Scroll | Ctrl+arrows; words horizontally |
| L2 + R2 + left stick | Scroll | Ctrl+Shift+arrows; select words horizontally |
| Right stick | Focus window | Resize window |
| L2 + right stick | Move window | Resize window |

On the WIN Mini 2023, L4 and R4 emit Print Screen and Pause on the separate `12068:309:Mouse_for_Windows` keyboard. A session reader coalesces R4's ordinary repeats and firmware macro repetitions, allowing a 75 ms gap between sequences within a hold. A short tap starts recording or stops it and inserts the transcription. Holding for 0.75 seconds cancels once and consumes the release; L4 is ignored. Dictation follows the physical US/RU layout selected when recording starts. The Mic bar block shows recording/transcription state; Super+V and Super+Shift+V remain keyboard alternatives. Sway consumes both rear keys while preserving the physical keyboard's Print Screen shortcut. A device-specific uaccess rule grants the active local user access to this rear keyboard, without adding the user to the input group. No firmware remapping is needed. Other devices or firmware mappings need their own matching and input handling.

Fn+F3 toggles display power while applications continue running. A second press restores the display and leaves it on. Ordinary keyboard, touchpad, touchscreen and controller input leaves an explicitly blanked display off; only Fn+F3 restores it. Automatic idle blanking still wakes on input; this does not unlock a session that was already locked. Fn+F3 also works while locked. Fn+F4 toggles the explicit **Keep awake** override while unlocked; the bar shows `Awake ON` or `Awake OFF` and can be clicked to toggle it. The override suppresses automatic idle locking and display-off on either power source, survives idle-service restarts and charger changes, and resets at reboot. Turning it off restores fresh battery timers when unplugged; AC already disables those timers. These Fn overrides apply to the built-in keyboard; Fn+F5 toggles 60/120 Hz once per press and saves the selected mode for later sessions; Fn+F6 is consumed without an action. Plain function keys remain available to applications.

For a background agent, enable Keep awake with Fn+F4, then turn the display off with Fn+F3. Keep awake does not unlock an existing lock. Super+L still locks only, and explicit suspend still locks and suspends. Closing the lid disables the built-in keyboard until reopening, preserving its previous event setting. It also suppresses gamepad buttons, sticks, scrolling, window/workspace commands and rear-button dictation. The mapper consumes controller events even in passthrough, releases held virtual keys and waits for neutral controls after reopening. With Keep awake enabled, closing the lid blanks the display without locking or suspending; reopening it restores the display unless Fn+F3 manually blanked it. With Keep awake off, lid close locks and suspends on AC and battery. Without Keep awake, the normal five-minute battery idle lock still applies after manually turning the display off. These bindings do not change the power button.

Numbered workspaces form a dynamic ring. If N is the highest occupied workspace, the bumpers cycle through 1 to N+1; N+1 is an extra empty workspace. R1 from N+1 wraps to 1, and L1 from 1 wraps directly to the last occupied workspace N, skipping the extra empty slot. Opening or moving a window into the extra workspace grows the ring. Sway removes empty workspaces when they are left; a session service immediately renumbers the remaining numbered workspaces consecutively, preserving window contents, focus and any name suffix. For example, when 2 disappears from 1, 2, 3, the former 3 becomes 2. Closing the highest workspace shrinks the ring. L2+bumper sends the focused window to the adjacent workspace without following it, using the same wraparound. From an unnumbered workspace, either bumper starts at 1. Super+1–4 remain direct keyboard shortcuts.

Window focus and resize actions repeat after a short hold; text movement and scrolling run continuously at a speed based on deflection. Dead zones prevent small movements from generating actions. Trigger hysteresis stabilizes held modifiers. Ordinary release actions use the modifiers held when released. X and Y act on press and use normal keyboard repeat while held. R2+X deletes words where Ctrl+Backspace is supported; R2+Y sends Ctrl+Space to switch US/RU.

## Shortcut table

Hold A/B first, then use the D-pad for the [editing/navigation shortcuts](gamepad-chord-layout.md). A provides copy/paste, undo/redo, cut, select all, find and save. B provides close, equalize, navigation back/forward, document boundaries and search matches. Hold Select first, then A for fullscreen, B for floating, Y for tiled/tabbed or X for split orientation. Prefixes have no timeout; release all participating controls to execute once. Select alone toggles the window picker; Select+face consumes both individual actions. X and Y otherwise act immediately and repeat while held. Invalid, unassigned and rolling combos emit no shortcut.

D-pad first sends an arrow immediately. Holding it starts repetition after 400 ms, increasing from 12 to 25 steps per second in all directions over another 300 ms. The sustained rate matches Sway's default keyboard repeat used by held X; personal keyboard repeat settings can differ. A diagonal sends both arrows at the vertical rate. Changing direction restarts the delay and acceleration; releasing stops immediately without an extra step. L2/R2 add Shift/Ctrl, including changes during a hold. Adding A/B during navigation stops repetition and suppresses the gesture until all those controls are released; it cannot become a combo. A face and direction first observed in the same input frame are also suppressed. To make a combo, press the face button first.

Copy/paste are terminal-aware. Editing actions ignore held triggers for their shortcut and restore them afterward; navigation shortcuts accept Shift/Ctrl. Application support determines Find, Save, Redo and search-match behavior. B+Left/Right send Alt+Left/Right for navigation history, including the configured Neovim jump list. See the table for details.

Terminal controls use the free A+B prefix: release A+B for Ctrl+C (interrupt), hold both before Up for Ctrl+Z (suspend job), or hold both before Down for Ctrl+D (end input). Release all participating controls to execute once, with no hold deadline or repeats. These actions work only in recognized terminal windows and ignore trigger modifiers. Ctrl+D can exit an empty shell; `fg` resumes a suspended job. The [terminal control reference](gamepad-chord-layout.md#terminal-controls) describes ordering and application behavior.

## Stick contexts and legend

The default Scroll/Windows combination lets the left stick scroll while the right stick selects windows. L3 changes the left stick to Text, where it navigates text like the D-pad. Hold L2 (Shift) to extend selection, R2 (Ctrl) for word movement horizontally, or both for word selection. Ctrl+up/down follows the application's own navigation behavior. Triggers can be pressed or released while the stick remains deflected to switch between movement and selection.

A quick nudge moves once. Holding the stick moves continuously, with light deflection for precision and full deflection for speed. Text movement ranges from 4 to 40 horizontal steps per second and 2 to 10 vertical steps per second. The same speeds apply while selecting. Scrolling ranges from 1 to 18 wheel steps per second in either axis; the dominant axis wins on diagonals. Returning to neutral stops immediately. Text navigation and selection use the focused application's keyboard behavior, such as in a browser text box or editor; they do not provide universal pointer-drag or terminal scrollback selection.

Scrolling sends full mouse-wheel detents through the virtual input device and leaves the pointer in place. Sway uses `mouse_warping container`: selecting a window with the right stick, keyboard or window picker moves the pointer to its center once if the pointer is outside it. If the pointer is already inside, its position is preserved. Left-stick scrolling then reaches the selected window without further pointer movement. Within split editors, use the touchpad to choose a pane; wheel events still follow that pointer position, even if another pane has keyboard focus. Each detent carries 120 high-resolution units plus its legacy wheel event, so applications receive normal wheel distances. Controller Shift/Ctrl are temporarily released around wheel events and restored afterward, so triggers keep ordinary scrolling rather than zooming or changing axes. Physical keyboard modifiers still follow the application's behavior. Wheel scrolling in terminals depends on the running program and its mouse/scrollback handling.

In Windows, the right stick focuses windows and L2+right stick moves them. R3 switches that stick to Resize, independently of whether the left stick scrolls or navigates text. Right-stick left/right shrink/grow width; up/down shrink/grow height. These actions retain their fixed repeat timing.

L3 requests a left-stick change; R3 requests a right-stick change. Only the affected stick must return to neutral before its change takes effect, and only that stick is suppressed while pending. The other stick continues operating. Another click cancels that stick's pending change. The bar abbreviates both behaviors: `L:S R:W` means Scroll/Windows; `T` means Text and `R` means Resize. The adjacent `60Hz`/`120Hz` indicator reads the active internal-panel mode. `minion-gamepad --status` reports `stick_modes` and `stick_pending` objects with `left` and `right` entries. Switching alone leaves no keyboard modifier held. Locking, leaving the active desktop, disconnecting, input resynchronization, restarting the service or entering passthrough restores Scroll/Windows.

Hold Menu/Xbox for at least 0.75 seconds to open a persistent Fuzzel legend derived from the active shortcut profile. It opens once at the hold threshold, stays visible until dismissed and consumes the release without opening the launcher. D-pad up/down browse and typing filters the list. A short Menu tap, another Menu hold, B/Escape or Enter dismisses it. A short Menu tap otherwise toggles the application launcher; a second tap closes the launcher opened by this mapper. Holding Menu while that launcher is open replaces it with the legend. While the legend is open, shortcut chords and both sticks are suppressed. Mapping suspension or reset closes owned overlays.

The window picker lists windows across workspaces, with the current window first. D-pad up/down selects, A focuses the selected window, and B cancels. Typing filters by application, title or workspace. The launcher uses the same navigation keys. Optional buttons missing from a controller are reported in status.

Hold Start alone for at least 0.75 seconds, then release it to open a new Thunar window. A shorter press opens a terminal on release. Start waits for release so adding Select at any point still consumes both individual actions. Holding does not open repeated windows.

## REAPER editing profile

This profile uses [ReaLearn](https://www.helgoboss.org/projects/realearn), installed
with REAPER by the development setup. It sends MIDI control changes to REAPER's numbered JACK input under PipeWire,
or to its ALSA virtual input with other Linux audio backends. Both routes verify
the focused application's PID; identical JACK client names cannot redirect input.
It generates no mouse movement, clicks or wheel events. The physical keyboard
keeps REAPER's ordinary shortcuts.

Select cycles **Arrange → Mixer → FX → Arrange**. The bottom bar shows
`RP:Arrange`, `RP:Mixer` or `RP:FX`; REAPER's docked control display shows the
selected track, current controls and relevant values. Start+Select still changes
the overall Desktop / REAPER / Gamepad profile.

The controller display normally stays docked inside REAPER. Its undocked window
and the ReaLearn monitoring-FX settings window follow Sway tiling, including on
the built-in screen.

| Control | Arrange | Mixer | FX |
| --- | --- | --- | --- |
| D-pad left/right | Previous/next item; hold R2 for cursor by grid | Previous/next visible track control | Previous/next parameter |
| D-pad up/down | Previous/next track | Previous/next track | Previous/next FX |
| Left stick | Scroll viewport | Move outline spatially within track | Previous/next track |
| Right stick | Timeline zoom / track height | Adjust outlined control | Adjust selected parameter |
| X | Split selected items at cursor | Mute/unmute track | Bypass/enable selected FX |
| R3 | Toggle loop | Solo/unsolo track | Show/hide FX window |
| L3 | Open/close the page's action menu | Same | Same |
| A | Select item at cursor on selected track | Toggle outlined switch / enter FX | Show/hide selected FX |
| B | Stop transport | Return to Arrange | Return to Arrange |

Hold A or B first, add a D-pad direction, then release both. These combos invoke
REAPER actions directly, including while a stock FX window has focus:

| D-pad | Hold A: editing | Hold B: project / recording |
| --- | --- | --- |
| Up | Copy items | Insert track |
| Down | Paste | Arm/disarm selected tracks |
| Left / Right | Undo / Redo | Previous / Next marker |
| Up-left | Cut items | Record |
| Up-right | Select all items on selected tracks | Input monitoring on/off |
| Down-left | Zoom to selected items | Duplicate items |
| Down-right | Save | Delete selected items |

Arrange shows the selected item count/name and whether the track is armed.
X splits only when the edit cursor is inside a selected item; otherwise the
display explains what to select. Select an item with D-pad left/right, hold R2
and move the cursor inside it, then press X. Stick rates are faster in REAPER
(scroll/adjustment 4–50 and zoom 3–14 steps/second) without changing Desktop rates.

Mixer follows the vertical track list in the arrange view. Up/down selects and
reveals a track; left/right chooses Volume, Pan, Mute, Solo, Arm, Monitoring or
FX, skipping controls hidden by the current theme/layout. A cyan outline marks
the real track control. The left stick navigates within that track in screen
space: up/down moves to a control above/below the current one, and left/right
moves to a control on that side. It prefers aligned controls and skips hidden
ones; at an edge the selection stays put. D-pad up/down still selects tracks,
and D-pad left/right retains ordered control selection. A nudge moves once; holding repeats after 350 ms
at about six moves per second, independently of the scrolling speed.
Right-stick up/right increases a value or enables a
switch; down/left decreases or disables it. A toggles a selected switch; on FX,
A enters the FX page and opens the track's effects. Volume and Pan need only
the stick. X and R3 retain their direct mute/solo actions.

The outline is a click-through X11 child of the REAPER project window. It uses
REAPER's reported control positions, follows resizing/scrolling and hides when
another application has focus, the action menu opens or the page/profile changes.
Its drawing process belongs to the controller script, exits when that script or
REAPER stops and requires no session service. This prototype covers native track
controls; sends and arbitrary plugin widgets do not have outline navigation.

In the action menu, use D-pad up/down, then A to run or B/L3 to cancel. Arrange
includes recording, insert track, copy/paste/cut, undo/redo, split/trim, markers,
metronome and item removal. Mixer includes record arming, input monitoring,
mute/solo, insert track, recording, level reset and pan centering. FX includes
inserting stock ReaEQ, ReaComp, ReaGate, ReaDelay and ReaVerbate. Plugin-specific
custom interfaces and dialogs are outside this layout's scope.

Y plays/stops once on release; holding never repeats. Start saves. Either
trigger makes level/pan/FX adjustments finer; triggers still emit Shift/Ctrl for
physical typing and ordinary keyboard shortcuts. L1/R1 navigate workspaces;
L2+bumper sends the window. Menu taps open the launcher and holding Menu shows
the full legend. Select+face layout toggles remain.
X is a discrete context action in REAPER; it remains holdable Backspace on Desktop.

MIDI controls require the genuine REAPER project, stock FX-chain/plugin window or the
controller display to be focused. Native dialogs retain ordinary D-pad arrows,
Enter and Escape; sticks are suppressed. Input to another application is never
routed to a background DAW. Disconnecting, changing profiles, locking or closing
the lid clears keyboard state and MIDI fine adjustment. Neutral controls are
required before mapping resumes.

The installer preserves existing REAPER audio/theme/license settings, other MIDI
inputs and an existing device controller preset. It excludes the controller's
controller input from **All MIDI Inputs**, so controller gestures are not recorded
as performance MIDI. A nonempty, unrelated monitoring-FX chain is preserved;
setup asks for manual integration rather than replacing it. Close REAPER before
running `/usr/bin/python3 setup/development/realearn.py` as your normal user.
Add `--update-controller` to explicitly replace this device's controller mappings
with the current repository layout; ordinary setup reruns retain custom mappings.

## Switch profiles and normal gamepad input

Hold Start+Select together for at least 0.75 seconds, then release both, or press Super+Ctrl+G. Each completed gesture advances once through Desktop, REAPER and Gamepad passthrough. A notification shows the mode; the bar shows `Pad` during passthrough. Any overlapping Start/Select press consumes their individual actions, including a short overlap. In passthrough the mapper releases its controller grab and all keyboard keys so games receive normal input. The toggle gesture also reaches games; use the keyboard shortcut if it conflicts.

```bash
minion-gamepad --toggle
minion-gamepad --status
```

The selected profile survives service restart while the user's runtime directory exists; cold boot starts in desktop mode. Reconnect/resume/restart requires buttons, triggers and sticks to return to neutral. Disconnecting or leaving the active desktop releases held keys. The lock command pauses mapping until unlock.

## Personal profile

The [default profile](../setup/desktop/gamepad.json) is installed as `/etc/minion/gamepad.json`. Create a personal copy as your normal desktop user:

```bash
mkdir -p ~/.config/minion
test -e ~/.config/minion/gamepad.json || cp /etc/minion/gamepad.json ~/.config/minion/gamepad.json
# Edit the personal file, then apply:
systemctl --user restart minion-gamepad.service
minion-gamepad --status
```

Setup preserves this file. Top-level settings override the defaults; a nested object replaces that entire object. Chord values are named actions such as `copy`, `close`, `home` and `equalize`, as shown in the default JSON. `actions` assigns named actions to buttons, including `legend`, `left_stick_context` and `right_stick_context`. `hold_actions` assigns alternate actions to the same buttons after `action_hold` seconds, consuming the short-press action. Hold actions on passthrough toggle buttons wait until release, so any overlap still consumes the individual action. Select is reserved for its release shortcuts and cannot have a hold action. The older `stick_context`, `selection` and `text_navigation` actions remain compatible and request changes to both sticks, each waiting for its own neutral position. X must remain Backspace and cannot appear in a chord. Set `chords` to `{}` to disable shortcuts and restore held D-pad arrows. D-pad acceleration uses `dpad_repeat_delay`, `dpad_acceleration_time`, `dpad_rate` and `dpad_line_rate`. Thresholds, repeat timing and resize increments are configurable. `workspace_numbers: null` selects the dynamic ring and automatic renumbering; an explicit list such as `"workspace_numbers": [1, 2, 3, 4]` retains circular navigation through that list. Existing personal lists are preserved and disable automatic renumbering.

Text navigation and selection speed is configurable with `selection_rate` (horizontal) and `selection_line_rate` (vertical), retaining the earlier setting names. Each is a pair of minimum and maximum steps per second, from 1 to 100. Scrolling speed uses `scroll_rate`, another minimum/maximum pair of wheel steps per second. Window focus and resizing retain their existing repeat timing.

`zoom_rate` controls REAPER right-stick zoom steps per second (default 1–6).
`profiles.reaper` overrides `buttons`, `actions`, `hold_actions` and `chords`
for that mapping; hardware assignments and timing are shared. A personal
`profiles` object replaces the whole default object, so retain its `reaper`
entry. X remains holdable Backspace; REAPER Y is the discrete
`reaper_play_stop` action. The selected profile is reported as `mode` in status.

Old character-typing profiles and the old `super` action are incompatible with this layout. On a fresh install use the new default; if retaining a personal copy during development, replace its old `chords` and `actions` objects before restarting. No profile migration is performed.

One compatible controller is selected automatically. If several match, set `device` to an exact name or integer USB vendor/product IDs, such as `{"name": "Your controller's exact name"}`. Status reports selection, axis ranges, grab state and recent Sway commands. Inspect failures with `journalctl --user -u minion-gamepad.service -b`.

## Implementation and tested scope

[minion-gamepad](../setup/desktop/minion-gamepad) runs as the logged-in user, reads evdev events, emits keys and wheel scrolling through a shared virtual input device, and sends desktop operations through Sway IPC. Setup installs Ubuntu's `python3-evdev`, loads uinput and grants the active local user access through a uaccess rule; it does not add the account to the input group.

The mapping follows Xbox/xpad labels: X is Linux BTN_NORTH (307), and Y is BTN_WEST (308). These historical directional aliases do not describe Xbox button positions. The host checker independently feeds driver codes through every assigned gesture, without creating a host input device.

The [VM mapping suite](testing.md#gamepad-tests) covers real applications, shortcuts and lifecycle behavior with a synthetic controller. See recorded results for what has actually run on this revision. Physical controls, suspend and comfort need WIN Mini validation. The rear buttons use their own session reader independently of the controller mapper, including in controller passthrough. Gyro and rumble have no added mappings.
