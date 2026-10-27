# Agent handoff

Updated **2026-10-27**, after installing the REAPER FX-chain arrow-navigation fix.
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
window-local regions, and right-stick angle control of knobs. A generic exposed
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

Baseline before this handoff batch: **`0ec359b Improve REAPER FX controls and tab navigation`**.
Use `git log -1` for the current commit.
That commit includes native FX improvements, generic parameter fallback,
full-size REAPER tabs and navigation in visible tab order.

This handoff batch includes the subsequent FX-chain navigation fix in:

```text
docs/gamepad-controls.md
docs/testing-history.md
setup/development/reaper-gamepad.lua
setup/development/reaper-ui.lua
tests/check-reaper-hierarchy.py
```

The documentation cleanup also merged the shortcut reference into
`gamepad-controls.md`, separated test history from procedures, removed the
obsolete pre-install handoff, and corrected current validation/setup guidance.
The user requested committing this batch. Use `git status --short` to identify
any later changes; the list above is not a claim that those files remain dirty.
Do not push unless asked.

The FX-chain fix is already installed in
`~/.config/REAPER/Scripts/Device/`, and normal REAPER was reopened afterward.
Do not launch a duplicate instance or reinstall just because a delayed answer
to an earlier close-REAPER question arrives. Recheck the process state.
Physical gamepad acceptance of this last fix is still pending; automated live
testing passed. There is no further feature request queued at handoff.

### Latest bug and correction

The user reported that the FX stack behaved like one block: the left stick
could not traverse its entries, while the right stick bounced between effects.

The current [Effects list controls](gamepad-controls.md#reaper-editing-profile)
use immediate Up/Down selection, A to enter the editor, and boundary navigation
to Add/Remove. The right stick no longer changes chain selection.

Implementation is in `ui.fx_move`, `ui.fx_step`, `ui.fx_activate` and the region
selection initialization in `reaper-ui.lua`. A separate snap-back bug was fixed
in `reaper-gamepad.lua`: the loop observes native FX selection rather than
calling `TrackFX_Show` again whenever its local index changes. That redundant
call could overwrite a selection which was still being applied. Keep explicit
navigation responsible for changing selection.

Four relevant host checks passed, plus `git diff --check`:

```bash
/usr/bin/python3 tests/check-reaper-hierarchy.py
/usr/bin/python3 tests/check-reaper-windows.py
/usr/bin/python3 tests/check-reaper-fx-ui.py
/usr/bin/python3 tests/check-realearn.py
```

A private live test used actual mapper-generated MIDI and a muted four-effect
chain (ReaEQ, ReaComp, ReaVerb, ReaPitch). It checked all rows, native selection
agreement, disabled right-stick selection, boundary buttons, editor entry,
selection changed outside the controller, and a shorter chain.

Local evidence, ignored by Git:

```text
.local/device-checks/realearn/chain-arrows-result.json
.local/device-checks/realearn/chain-arrows-install-result.json
.local/device-checks/realearn/chain-arrows-reopen.log
.local/device-checks/realearn/chain-arrows-backup-20261027-221010/
```

Installed hashes recorded at handoff:

```text
reaper-ui.lua       5a36ec026e602a7efa55da3f8cf4e630c27bf9ec1fb0157e260e5f8bc4a38246
reaper-gamepad.lua  19a388d99692104e2d48bad9c735912586cb8b1033852ab1fbd0f6029baa3ab3
```

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
.local/device-checks/realearn/run-chain-check.py
.local/device-checks/realearn/test-chain-arrows.py
.local/device-checks/realearn/test-hierarchy.py
```

Read them before reuse. `run-chain-check.py` expects the private display to
already exist and its captured environment to be current. `start-batch-test.py`
creates an isolated profile from current source. Older live fixtures may assert
the superseded A-to-enter FX-list behavior; distinguish stale tests from bugs.

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
scripts normally do not. Ask the user to save and close REAPER before replacing
its scripts or configuration, then verify it is closed. REAPER can overwrite
configuration on exit. Preserve audio settings, themes, license, projects,
unrelated monitoring FX, MIDI inputs and personal mappings.

`/usr/bin/python3 setup/development/realearn.py` is the supported component
installer, run as the normal user with REAPER closed. `--update-controller`
explicitly replaces managed mappings; ordinary reruns preserve them. Read its
current behavior before invoking it for a narrow fix.

The latest local installer is `apply-chain-arrows.py` beside its reports. It
checked previous hashes, backed up both scripts, atomically replaced them and
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

For a continuation, inspect current status and ask for physical acceptance of
the FX-list behavior only if relevant. Do not reinstall or launch another test
DAW merely to review or commit documentation.
