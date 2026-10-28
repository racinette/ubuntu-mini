# Agent handoff

Updated **2026-10-28**, after committing the installed REAPER slider changes.
This is a snapshot for the next agent, not a replacement for source inspection.
Check Git status, running processes and installed files before making changes.

## Start here

This repository, **Minion** (`ubuntu-mini`), provisions an Ubuntu desktop for a
**GPD WIN Mini 2023 / Ryzen 7 7840U**. We are working on the user's daily-use
device, not a disposable VM. User: `andy`; checkout: `/home/andy/ubuntu-mini`;
timezone: `Europe/Minsk`. Ubuntu 24.04, Sway, Foot, PipeWire and native Linux
REAPER are central to the current work. The desktop is approximately 960×540
logical pixels at 2× scale.

The active work is making REAPER usable from the gamepad without turning the
gamepad into a mouse. The user wants visible, spatial control navigation,
window-local regions, angle control of knobs, and relative, orientation-aware
slider control with hold acceleration and precise R2 steps. A generic exposed
parameter list is accepted for opaque plugin interfaces. They explicitly do
not want an endless collection of plugin-specific adapters.

Read these first:

- [README](../README.md): repository layout and entry points.
- [Gamepad controls](gamepad-controls.md), especially the REAPER section:
  current interaction contract.
- [Testing](testing.md): host/VM procedures; [test history](testing-history.md):
  dated observations and private evidence links.
- [Post-install setup](post-install-setup.md): installed software and policies.
- [Validation status](validation-plan.md): current coverage and remaining gaps.
  The unchecked [device checklist](device-checklist.md) is a reusable checklist,
  not a list of failures on this device.

## Exact handoff state

Latest implementation commit: **`89b33b4 Improve REAPER slider gestures, acceleration and fine adjustment`**.
Previous related commit: **`b33be38 Improve REAPER window controls, dialog focus and native sliders`**.
Use `git log -1` and `git status --short` for the current documentation revision
and any subsequent changes. Do not push unless asked.

The latest code is installed. Read-only comparison confirmed the mapper and both
Lua scripts match the repository. The live controller preset contains the
128-value acceleration parameter 16, driven by MIDI CC 51. The saved preset includes
ReaLearn's serialization defaults and retained mapping IDs, so it is not
byte-identical to generated source; preserve it rather than replacing personal mappings to normalize JSON.

At the final status check, REAPER was **closed**, the mapper was active in
**Desktop** mode, grabbed and ready, with no held keys. Both private test services
were inactive. REAPER had been reopened after installation but was no longer
running at this check. Do not reopen it merely to review this handoff.

There is no new feature request queued. The next useful step is physical
acceptance of the latest slider fix when the user resumes REAPER: adjust with
R2 + right stick, release R2, then use normal right-stick adjustment. Repeat on
horizontal and vertical sliders, including short nudges. Automated checks passed;
the user has not yet confirmed this installed fix physically.

### Current slider behavior and latest correction

The [control reference](gamepad-controls.md#reaper-editing-profile) owns the
bindings. Implementation details relevant to continuing work:

- Native slider class determines axis: horizontal uses left/right; vertical uses
  up/down, with up increasing. Perpendicular motion is ignored. Knobs and opaque
  generic parameter lists retain absolute-angle control.
- `Mapper.rotary_frame` in the mapper starts acceleration after 0.2 s and reaches
  full speed at 1 s. Cadence ramps 4→16 requests/s and normal step multiplier 1→4.
  R2 retains its step size while cadence accelerates. Neutral, reversal, context
  changes and scheduling gaps reset the ramp.
- MIDI CC 51 carries acceleration to ReaLearn parameter 16. Like CC 22 and 26,
  it is continuous: do not append the synthetic zero-release used for buttons.
- `ui.fx_step` prefers the smallest positive declared parameter step for R2,
  in **raw parameter units**, not normalized percentages. A JS integer range
  0–100 reported step 1; tested ReaEQ/ReaVerb/ReaPitch returned no step metadata.
- Without metadata, a unique adjacent writable numeric field supplies precision:
  `1000.0` changes by `0.1`. No metadata/usable field means a visible unavailable
  message, not an arbitrary percentage. This rule concerns relative sliders.
- The latest regression came from mixing native numeric edits in fine mode with
  host parameter setters in normal mode. ReaVerb then ignored normal updates.
  **Keep both modes on the native field path when fine precision comes from that
  field.** Host formatting converts normal range-based increments into matching
  numeric units; unusable/mismatched formatting retains native numeric stepping.
  Plugins with declared steps retain the host/API path in both modes.
- Do not restore the abandoned completion-notification workaround. It rounded
  vertical values and could drop the first normal nudge. The final source has no
  delayed callbacks, synthetic end-scroll notifications or pending-edit state.

Five relevant host checks passed immediately before the implementation commit:

```bash
/usr/bin/python3 tests/check-chord-recognizer.py
/usr/bin/python3 tests/check-midi-routing.py
/usr/bin/python3 tests/check-realearn.py
/usr/bin/python3 tests/check-reaper-hierarchy.py
/usr/bin/python3 tests/check-reaper-fx-ui.py
```

Private live tests used actual mapper-generated MIDI and a muted isolated REAPER.
They covered acceleration, axes, native/declared fine steps, repeated transitions
and three single-nudge fine→normal cycles. These tests do not establish physical
comfort, every plugin's behavior, or real guitar latency.

Latest ignored evidence under `.local/device-checks/realearn/`:

```text
slider-acceleration-result.json
slider-acceleration-install-result.json
slider-minimum-step-result.json
slider-minimum-step-install-result.json
fine-transition-result.json
fine-transition-nudge-result.json
fine-transition-install-result.json
fine-transition-backup-20261028-220938/
```

Installed SHA-256 values verified at handoff:

```text
minion-gamepad      cea54fcb925dfcca98980e28d33c5365a81fb67bcb5456c317ec32828e97cddc
reaper-ui.lua       1d0451296e01159a4b6b5980263de75dcabe7a09264b36c6593d92fafeb1374d
reaper-gamepad.lua  431ae856febeea895f03fd9562a8e4c6e58cb62dd2ecda28a551a5af409955bb
```

Earlier FX-chain selection, unnamed-track windows, A+B close-window and modal
cyan-outline fixes remain in the source. Historical rationale belongs in
[test history](testing-history.md), not another parallel handoff document.

## Code map

| Source | Responsibility |
| --- | --- |
| `setup.sh`, `setup/base/setup.py` | Full provisioning entry/coordinator; not a routine live-patch command |
| `setup/desktop/minion-gamepad`, `gamepad.json` | Physical input, modes, chords, neutral gating, keyboard/MIDI output |
| `setup/development/realearn.py` | ReaLearn installation, controller preset, MIDI integration and script installation |
| `setup/development/reaper-gamepad.lua` | REAPER controller loop, action dispatch, display and parameter state |
| `setup/development/reaper-ui.lua` | Native FX discovery, window/region/control model and activation |
| `setup/development/reaper-control-navigation.lua` | Spatial navigation |
| `setup/development/reaper-control-outline.py` | Click-through X11 outlines, Sway window identities/order and focus requests |
| `setup/development/reaper-dialog-focus.cpp` | Native SWELL focus reader for dialog outlines, including modal loops; built by `realearn.py` |
| `setup/development/reaper-transport.lua` | Transport controls |
| `setup/development/reaper-ui.py`, `reaper.py` | REAPER UI setup and application installation |
| `setup/desktop/minion-workspaces` | Workspace compaction, launch origin placement and REAPER tabbing |
| `tests/check-reaper-*.py`, `check-reaper-navigation.lua`, `check-realearn.py` | Committed REAPER regression checks |
| `setup/desktop/minion-idle*`, `minion-rear-buttons` | Lid, display, Keep awake and rear controls |
| `setup/development/nvim.lua`, `nvim.py` | Neovim configuration and language support |
| `setup/proxy/`, `setup/agents/`, `setup/shell/` | Proxy, agent integration and shell/auth defaults |

## REAPER architecture and boundaries

The mapper sends MIDI control changes through a verified, PID-matched REAPER
input (JACK under PipeWire, ALSA virtual input for other backends). ReaLearn and
the controller script translate these into REAPER actions. Do not replace this
with cursor movement or send actions to an unfocused background DAW.

The [REAPER control reference](gamepad-controls.md#reaper-editing-profile)
owns the window → region → control bindings, dialog layer and plugin support
boundary. Keep operating instructions there instead of duplicating them here.

Implementation invariants: require neutral after context/target changes; suppress
DAW actions in modal dialogs; preserve native window ownership and background
focus. Tabbing happens after origin placement. Visible order comes from Sway
tree traversal, never window IDs, creation time or focus history.

Native FX controls are discovered through JS_ReaScriptAPI/SWELL child windows.
Scope IDs to the correct parent: plugin-internal IDs can collide with host
chain IDs (ReaVerb exposed this). Skip hidden, disabled and offscreen widgets.
Unique labels can match host automation parameters; ambiguity must not bind
an unrelated parameter. Existing ReaEQ/ReaComp/ReaPitch adapters remain.

ReaPitch has nine sliders per shifter. Its visible shifter must be prepared
before values are adjusted. Native tab-change notifications invalidate cached
targets; discovery alone must not repeatedly change native tabs. Inspect the
existing adapter and tests before changing this synchronization.

If an editor exposes no navigable native controls, offer **Plugin parameters**:
named host automation parameters, selected with left stick/D-pad, adjusted with
right stick, with name/value in the controller panel. Do not pretend to highlight
custom-painted knobs. Blank/unused entries, synthetic MIDI CC parameters and
host-owned Wet/Bypass/Delta entries are filtered. Original parameter indices
remain intact. ReaLearn parameter 2 and the Lua conversion now cover **65536**
indices, not 256; BYOD's plugin bypass is at index 509.

This fallback was checked with BYOD and AIDA-X, plus native ReaEQ regression.
It does not add/connect BYOD pedals or expose arbitrary custom UI operations;
those still require touch/touchpad. This is an agreed boundary. Partially
discoverable native editors do not automatically receive this fallback.

## Testing without disturbing the user

Use `/usr/bin/python3` for device tests. The default `python3` can be a different
toolchain and lack `evdev`. Start with relevant committed checks; do not rerun
the entire VM/hardware suite for every small change.

For real UI tests, previous work used a separate headless Sway/Xwayland display,
a separate REAPER profile, muted audio and mapper-generated MIDI. Local scripts
are diagnostic fixtures, not installed services or portable acceptance tests:

```text
.local/device-checks/reaper-fx/sway.conf
.local/device-checks/reaper-fx/environment.json
.local/device-checks/realearn/start-batch-test.py
.local/device-checks/realearn/prepare-private-display.py
.local/device-checks/realearn/run-reaverb-probe.py
.local/device-checks/realearn/test-slider-minimum-step.py
.local/device-checks/realearn/test-fine-transition.py
.local/device-checks/realearn/test-fine-transition-nudge.py
```

Read them before reuse. `run-reaverb-probe.py` expects the private display to
already exist and its captured environment to be current. `start-batch-test.py`
creates an isolated profile from current source. Older live fixtures may assert
superseded FX-list, slider-axis, deflection-speed or percentage-fine behavior;
distinguish stale tests from bugs. Run live fixtures sequentially: they share
one profile, display and command RPC. Re-select the intended FX before a test;
the minimum-step test ends with the disposable JS effect selected.

Private units are `realearn-device-check.service` and `reaper-fx-sway.service`;
both were stopped at handoff. Stop only test-owned units, and tolerate an absent
unit during cleanup. Never kill every REAPER process to clean a test.

The fixture's `command.lua`/`command-result` RPC runs in a different Lua VM from
the controller script. Monkeypatching a REAPER API function in the RPC script
does not trace controller calls. A syntax error in an RPC command can terminate
its loop. Wait for asynchronous native selection/focus changes before asserting.
Check that a requested plugin loaded before interpreting widget dumps.

Sandbox process/GUI visibility may differ from the host. Use scoped escalation
when required to inspect or operate the actual session. Import only the needed
session variables (`DISPLAY`, `WAYLAND_DISPLAY`, `SWAYSOCK`, `XDG_RUNTIME_DIR`,
`DBUS_SESSION_BUS_ADDRESS`); do not print the whole environment. Never mix the
private test display into the user's session.

## Installing and preserving local changes

Edit repository sources first, test them, then install the smallest relevant
change locally. Root-owned mapper/service files require sudo; user-owned REAPER
scripts normally do not. If REAPER is running, ask the user to save and close it
before replacing its scripts or configuration, then verify it is closed. If it
is already closed, continue the authorized installation without another
confirmation. REAPER can overwrite configuration on exit. Preserve audio settings, themes, license, projects,
unrelated monitoring FX, MIDI inputs and personal mappings.

`/usr/bin/python3 setup/development/realearn.py` is the supported component
installer, run as the normal user with REAPER closed. `--update-controller`
explicitly replaces managed mappings; ordinary reruns preserve them. Read its
current behavior before invoking it for a narrow fix.

The latest local installer is `apply-fine-transition.py` beside its reports. It
checked the previous hash, backed up `reaper-ui.lua`, atomically replaced it and
provided rollback. **It is a one-time installer:** its expected pre-install
hashes are now obsolete. Do not rerun it unchanged. Back up and verify current
files for the next update instead.

The normal launcher is `~/.local/bin/reaper`, wrapping the installed binary
under `~/opt/REAPER/` with PipeWire JACK settings. Reopen through that launcher,
once, after checking for existing instances. Keep diagnostic output in ignored
local files. Never reopen a private test profile as the user's working session.

## Broader device context and user preferences

- The user uses this system extensively and declined reinstalling or repeated
  reboot cycles. Make incremental changes, and keep reproducible defaults in
  the repository as well as applying the agreed change locally.
- Prefer standard upstream tools over redundant `minion-*` wrappers/services.
  Custom helpers are justified where they implement device-specific behavior.
- Current display/lid/dictation bindings are in [desktop controls](post-install-setup.md#desktop-controls)
  and the gamepad reference. In particular, Awake lid-close must not suspend,
  and manual blanking must not wake on ordinary input. Preserve these intentional
  exceptions when touching idle handling.
- Flicker became rare at 60 Hz, but the root cause is unresolved. Do not call it
  fixed. Hibernation/kernel/Secure Boot changes were declined; swap does not imply
  hibernation support.
- Firefox is the default browser; Chromium is available for automation. Proxy
  rules include Russian bypass and Belarusian domain/IP bypass. Keep tokens and
  subscription URLs out of Git and diagnostic output.
- Use standard `pass` for secrets. The user explicitly rejected a custom secret
  execution wrapper. SSH uses Ubuntu's packaged agent, not the old custom
  `minion-ssh-agent`; key cache is one hour, shared sudo cache 15 minutes.
- Guitar effects and tooling are installed, but the external USB interface was
  unavailable: real guitar routing/latency remains untested. Do not infer that
  generated-audio checks prove live input performance.
- Past freezes involved heavy workloads and memory pressure. Avoid leaving
  background test servers/renderers running. Use bounded diagnostics, clean up
  only what you started, and distinguish measured temperatures/load from guesses.
- Commit when requested, with only the intended files. Do not silently include
  unrelated work, secrets, generated binaries or `.local/` test evidence.

For a continuation, inspect current status and use the latest slider retest
above when the user is ready. Do not reinstall or launch another test
DAW merely to review or commit documentation.
