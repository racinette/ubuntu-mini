# Testing setup and desktop behavior

Tests run independently of device setup. Host checks use isolated commands or mapper frames. VM checks exercise the installed system through guest SSH and real keyboard/controller events. All runtime images, credentials, reports and screenshots remain under ignored `.local/`.

For the current completed/deferred split, read [validation status](validation-plan.md).
Dated entries below retain their original scope and limitations; a pending item
in an older experiment may have been completed or superseded by a later entry.

Firefox-first browser preferences were applied on the WIN Mini: `xdg-settings get default-web-browser` and `xdg-mime query default` for HTTP, HTTPS, HTML and XHTML all resolve to `firefox_firefox.desktop`. Chromium remains the fallback. An isolated execution of the setup's preference-seeding block verified repeat installation and retention of explicit browser choices and unrelated file associations; setup staging and `git diff --check` passed.

## Recent device checks

On 2026-10-25, L3 area selection gained actual Toolbar, Tracks, Timeline and
Transport panels. The left stick/D-pad choose spatial neighbors; A/L3 enters,
B cancels, and holding L3 retains the action menu. FX stays within track controls.
The pinned js_ReaScriptAPI extension discovers native panels; exact theme-image
matching locates visible buttons without generating mouse input. Host checks
cover image decoding, missing/ambiguous matches, generations, customized-toolbar
refusal and preservation of personal REAPER settings. A private muted JACK
project on an isolated Xvfb display found 13 toolbar and seven transport buttons
with Reapertips. Mapper-to-native-action tests passed New, Open/Cancel, Save,
Play/Pause/Stop, start/end, spatial navigation, menu/cancel isolation and no mouse
events. The controller resumes after a native file dialog remains open, and panel
resizing refreshes the discovered button positions. Xvfb is only a temporary test
tool, not an installed product dependency. Live installation completed with REAPER
closed; installed mapper, profile, bar command and scripts match the repository.
Physical navigation comfort remains pending.
[Private workflow report](../.local/device-checks/realearn/native-buttons-result.json),
[private installation report](../.local/device-checks/realearn/native-buttons-install-result.json).

On 2026-10-25, numeric Mixer controls and FX parameters gained absolute
right-stick angle control over a clockwise 270-degree sweep. Centering retains
the value; the bottom gap is inactive. A new target requires neutral before
engagement. Mapper checks passed angle values, stationary hold, release, focus
return and target-change gating. MIDI tests verified full 14-bit MSB/LSB pairs,
including zero, without a release reset. A private muted JACK project confirmed
pan endpoints/intermediate values, volume ordering, FX values, release/gap hold,
neutral gating, retained switch controls and no pointer events. Installation
completed with the existing project open.
[Private workflow report](../.local/device-checks/realearn/rotary-result.json),
[private installation report](../.local/device-checks/realearn/rotary-install-result.json).

On 2026-10-25, Mixer left-stick navigation became spatial within the current
track. It uses native control rectangles to choose a neighbor in each direction,
prefers aligned controls, skips hidden controls and stays put at edges. D-pad
up/down retains track selection. Forty-three Lua geometry fixtures passed,
including translated/scaled layouts, hidden controls, cosmetic row offsets and
edges. A private muted JACK project confirmed horizontal navigation, Mute/Solo
up/down without changing tracks, held edge behavior and the existing adjustment,
switch and FX-entry workflow. The live update installed without restarting
REAPER. [Private workflow report](../.local/device-checks/realearn/spatial-result.json),
[private installation report](../.local/device-checks/realearn/spatial-install-result.json).

On 2026-10-25, the Mixer left stick changed from viewport scrolling to navigation
between tracks (up/down) and outlined track controls (left/right). A nudge moves
once, with a 350 ms delay and 160 ms repeat interval when held. Mapper-frame
checks passed all four directions, repeat timing, neutral stop/re-engagement and
independent right-stick adjustment. The private muted JACK project passed actual
left-stick track/control selection and delayed repeat alongside volume, pan,
switches and FX entry. The live update installed successfully without restarting
REAPER. [Private workflow report](../.local/device-checks/realearn/mixer-stick-result.json),
[private installation report](../.local/device-checks/realearn/mixer-stick-install-result.json).

On 2026-10-25, Mixer gained vertical track selection and left/right selection of
native track controls. A click-through cyan outline follows the selected TCP
widget using REAPER's reported positions; controls hidden by the theme are
skipped. A muted, input-disabled private JACK project passed mapper-frame tests
for independent volume/pan adjustment, vertical tracks, mute/solo/arm, hidden
Monitoring skip and FX entry. Native X11 readback verified four child borders,
empty input regions, exact alignment before/after resizing and focus hide/restore.
The outline was also visually inspected. This prototype covers track controls,
not send widgets or arbitrary plugin interfaces. Physical comfort still needs
user testing. The normal session installation passed after correcting an absent
temporary-service check and waiting for mapper readiness after restart; REAPER
and its project stayed open. [Private installation report](../.local/device-checks/realearn/outline-install-result.json),
[private control report](../.local/device-checks/realearn/outline-result.json),
[private drawing report](../.local/device-checks/realearn/outline-drawing-result.json).

On 2026-10-25, the next REAPER controller batch added native item navigation,
R2+D-pad grid cursor movement, item selection at the cursor, A+D-pad native
editing, and B+D-pad recording/project actions. B now uses the actual Stop action
instead of Go to project start. Stick rates increase only in the REAPER profile.
A disposable three-track MIDI project running the real PipeWire/JACK backend
passed mapper-frame-to-MIDI checks for track/item navigation, cursor movement,
split, undo/redo, copy/paste/cut, duplicate/delete, track-item selection and zoom,
arming/monitoring, recording/stop, markers, track insertion, FX entry/back,
menu cancellation without stopping playback, empty split feedback and saving.
Recording inputs were disabled and master output muted; this did not test a
physical instrument or input latency. No mouse or shortcut-key events were
emitted (only held Ctrl for the R2 test). Native ReaLearn state replacement and
restarting only the owned control display also passed in that isolated resource.
Host chord, installer preservation/explicit update, MIDI routing, status,
development and setup-layout checks passed. Physical usability remains to be
assessed. [Private workflow report](../.local/device-checks/realearn/batch-result.json).

On 2026-10-25, the initial REAPER keyboard profile was extended with ReaLearn
2.18.4 and direct MIDI control. JACK routing resolves PipeWire MIDI ports through authenticated client PIDs;
the ALSA fallback resolves virtual RawMIDI clients by PID. It needs no network
listener or separate MIDI-routing service. A disposable project using dummy audio passed Arrange navigation and
zoom, one-shot transport, Mixer level/pan with finer trigger adjustment,
mute/solo, action-menu record arming, FX/parameter navigation and adjustment,
bypass, stock-effect insertion, three-page wraparound and saving. The native
controller display starts from the saved monitoring-FX preset. These automated
checks do not establish physical-controller ergonomics or guitar-interface
latency. [Private ReaLearn report](../.local/device-checks/realearn/live-result.json).

The first device install exposed an audio-backend gap: dummy-audio checks had
used an ALSA virtual input, while the real session used JACK. A muted disposable
JACK project with recording inputs disabled passed the complete page workflow
after adding native JACK output and PipeWire port-ID linking. Regression checks
cover duplicate JACK client names, authenticated-PID selection, retained links,
reset recovery, rerouting and backend-specific input-cache setup. ReaLearn's
large settings window and an undocked controller panel are explicitly tiled.
The same workflow also passed using a copy of the user's existing JACK device
cache. That cache had left the originally selected MIDI slot unavailable; setup
now reserves an unused numbered JACK input while retaining other devices and
the user's controller state. The installed normal REAPER session confirmed a
MIDI page change and return to its original page. Its controller FX was bypassed
and was re-enabled. Native Sway readback confirmed the monitoring-FX settings
window tiled at 320×517 logical pixels with fullscreen disabled. Temporary MIDI
producers and test instances were stopped. Installer migration/bypass recovery,
MIDI routing, chord, status, development and setup-layout checks passed.
[Private installed-session report](../.local/device-checks/realearn/installed-jack-result.json).

The following initial-profile report records the earlier keyboard implementation,
which the ReaLearn profile supersedes:

On 2026-10-24, a REAPER editing profile was added to the existing mapper.
Start+Select hold/release and the keyboard/CLI toggle now cycle Desktop, REAPER
and raw gamepad passthrough. The bar and Menu-hold legend identify the profile.
Isolated checks passed mode persistence, neutral gating, modifier cleanup,
Select-prefix consumption, one-shot transport, guarded save/mixer/zoom,
accelerated track navigation, stick modes, lid suppression and status labels;
existing desktop chord, idle-policy and setup staging/hash checks also passed.
A temporary uinput keyboard fed the prepared mapper into a disposable REAPER
project with dummy audio. REAPER confirmed play/stop without hold repeats,
track/cursor navigation, horizontal zoom, track-height adjustment, mixer toggle,
project saving and vertical scrolling without changing zoom. The live check
caught unreliable modified-wheel handling, so REAPER scrolling instead uses its
stock Alt+arrow viewport actions; no REAPER keymap change or extension is needed.
The test did not record the microphone or play audio. Local installation passed
source comparisons, an active mapper check and the complete REAPER → passthrough
→ Desktop cycle with grab/neutral/key-state checks. The running bar command was
restarted to load the profile labels. Physical controller feedback is pending.
No VM/reboot or guitar-interface test was run. [Private REAPER input report](../.local/device-checks/reaper-gamepad/live-result.json).

On 2026-10-24, REAPER 7.83 was added to the development setup using Cockos's
official Linux x86_64 archive and published SHA-256 checksum. An isolated fresh
installation through the upstream installer created the executable, application
launcher, icons, MIME registrations, uninstaller and user-local `reaper` command.
The installed executable matched the archive and had no missing linked
libraries. A second run required no archive and retained personal settings and
all installed files. The live user's existing `~/opt/REAPER` installation was
detected and retained without modification. `tests/check-reaper.py` passed
checksum/size checks, unsafe archive refusal, fresh installation, existing and
incomplete installation handling, settings retention, user-only installation
and read-only preflight. Development integration, setup staging/hash and diff
checks passed. No full setup, GUI/audio validation or theme change was performed.
[Private REAPER report](../.local/device-checks/reaper/result.json).

On 2026-10-22, a real closed-lid check showed the physical keyboard blocked
while the gamepad mapper remained ready and continued window/workspace actions.
The mapper now observes the same lid marker, releases virtual keys and pending
gestures, and consumes the physical controller while closed, including in
passthrough. Reopening waits for neutral controls. The rear-button reader also
suppresses dictation actions and drops gestures spanning lid transitions.
Isolated chord and idle-policy checks passed closed-lid suppression, held-key
release, sticks, workspace/window actions, passthrough grabbing, neutral
recovery and rear-action refusal; setup staging and diff checks passed.
Local installation passed source comparisons, active mapper/rear-reader checks,
closed-lid grabbing with no keys or commands. During the user’s real lid-close
test, ACPI reported closed and the mapper remained grabbed, not ready, with no
held keys. Physical retest feedback and live neutral recovery are pending.
[Private gamepad report](../.local/device-checks/lid-gamepad/result.json).

On 2026-10-22, lid-close also began disabling the WIN Mini's built-in keyboard
through Sway. Lid-open restores the saved event setting, including a keyboard
that was already disabled; the lid switch and other inputs remain active.
Isolated checks passed repeated close events, setting preservation, missing
hardware and retry after a failed restore. Live input readback confirmed only
the built-in keyboard was disabled and restored. The installed Awake lid-close/
open handler passed the same readback and matches the repository source.
A physical close/open typing check remains unconfirmed.
[Private keyboard report](../.local/device-checks/lid-keyboard/result.json).

On 2026-10-22, lid handling became Awake-aware and explicit Fn+F3 blanking
became persistent. The existing idle service holds a low-level logind lid
inhibitor while Sway handles close/open events; outside the session, logind's
suspend fallback remains. Awake lid-close blanks without locking or sleeping;
normal lid-close locks before suspend. Automatic wake paths respect manual
blanking, while ordinary idle blanking still wakes on activity. Select now
toggles its owned window picker, including child-overlay cleanup. Isolated
idle-policy, chord, picker-process, status-bar and setup-layout checks passed,
as did native Sway configuration validation. Local installation passed source
comparisons, active service/inhibitor checks, manual blanking through synthetic
Shift input, Fn+F3 command toggling, simulated Awake lid-close/open, preserved
manual blanking after reopening, and automatic idle wake. A live Sway picker
opened and closed without leaving its overlay. The user confirmed all three physical checks: Select opens/closes its picker,
Fn+F3 blanking survives ordinary input until the next Fn+F3 press, and Awake
lid-close/open stays running and returns without unlocking. No real suspend or
reboot was performed for these changes.
[Private installation report](../.local/device-checks/lid-display-picker/result.json).

On 2026-10-17, coding CLI setup gained completion popups and workspace urgency:
Codex uses its UI's native BEL signal for completion/approval/questions, while
Claude and Cursor use a one-shot hook. Claude permission/question hooks are also
configured. Host checks passed event/status filtering, focused-terminal
suppression, unambiguous origin selection, scratchpad/shared-server refusal,
JSON/TOML/Foot preference preservation, hook idempotence and invalid-config
refusal; CLI provisioning and 100-source setup staging passed too. The installed
Codex accepts the configuration and installed Cursor source confirms `stop`
dispatch. A live terminal fixture checks hook payloads and Foot's native BEL,
workspace urgency, focus preservation, clearing urgency on focus, focused
suppression and three-second popup expiry. These checks inject events; an actual
completed turn in each restarted CLI remains a normal-use check. The corrected
installed fixture passed Claude/Cursor completion and Claude permission hooks,
Codex's native terminal signal, correct workspace urgency, three-second popup
expiry, focus preservation and clearing on focus.
[Private installed notification report](../.local/device-checks/agent-notifications/installed-result.json).

The user identified an important live exception: this conversation was on
workspace 4 although tool ancestry led through workspace 2. Inspection confirmed
that Codex clients on multiple workspaces share an `app-server` daemon originally
launched from workspace 2. The workspace mapper now stops before following that
shared backend to its original terminal, leaving ambiguous launches to Sway's
normal placement. Codex's completion hook was replaced with UI terminal signals
for the same reason. Regression checks cover the shared-backend boundary and
ordinary direct CLI ancestry. The installed mapper was updated/restarted without
reloading Sway. [Private installation correction](../.local/device-checks/agent-notifications/shared-backend-result.json).

On 2026-10-17, Bluetooth and night-light startup moved to the packaged
`blueman-applet.service` and `gammastep.service` with session drop-ins. The
Gammastep indicator is disabled/masked to avoid a second adjustment process.
Isolated checks passed old-unit removal, retained personal overrides, unchanged
reruns, all saved night-light modes and setup staging (98 sources). The existing
mode picker remains; its service target now uses the packaged unit.
Live installation verified the Blueman D-Bus owner belongs to the packaged
service, exercised Automatic/Warm/Off with a single Gammastep process (none
while Off), restored the original mode/configuration, and confirmed the old
units are removed. The Warm-mode check was corrected to account for Gammastep
splitting its temperature argument in the running process; unsuccessful checks
restored the previous installation before retrying. Installed files match the
repository. New Bluetooth pairing/audio and a logout/login cycle were not
repeated.
[Private desktop-service report](../.local/device-checks/packaged-desktop-services/result.json).

On 2026-10-17, SSH setup switched from the custom agent service to Ubuntu's
packaged `ssh-agent.service`, using its native launcher/socket and a drop-in
for the one-hour lifetime and desktop-session teardown. Migration removes the
old managed `IdentityAgent` override and both legacy unit paths while retaining
personal SSH settings. Isolated checks passed fresh setup, migration/reruns,
user precedence, parse-failure rollback, stale-socket recovery, alias
canonicalization and preservation of forwarded agents. Setup staging and
shell/Python syntax checks passed. Live installation verified the vendor unit
and native socket, actual `ssh-agent -t 1h` process, manager environment,
removal of the forced agent setting, and signing with a disposable key through
both the standard socket and a temporary legacy alias. The test key was removed;
real keys were not read or loaded and no remote login was attempted. Installed
session/shell sources match the repository. Next logout/login lifecycle remains
for the next planned session restart.
[Private packaged-agent report](../.local/device-checks/packaged-ssh-agent/result.json).

On 2026-10-17, the workspace service gained process-ancestry placement for newly
opened child windows. A live terminal fixture reproduced the original bug with
the installed service, then verified the new watcher kept agent-like child
terminals with their source on a background workspace while preserving the
viewed workspace and focused window. Moving the source changed the destination
for the next child; manual child moves persisted, and independent Sway launches
kept native placement. Temporary windows were closed and focus restored. Unit
checks cover renaming, floating windows, shared-process ambiguity, scratchpad,
malformed/disappearing processes, account boundaries and safe command quoting.
The installed workspace script/unit match the tested sources and the service
is active. This does not infer origins across detached/shared processes such
as D-Bus application activation.
[Private window-origin report](../.local/device-checks/window-origins/result.json).

On 2026-10-17, a TCP/22 probe to the user's Belarusian server was observed
matching the proxy fallback and using the selected German node; it timed out.
MetaCubeX's downloaded Belarus list contained 772 prefixes and classified that
address within `87.232.64.0/21`. The new optional `bypass-by` configuration
adds a cached, daily refreshed IP rule while preserving existing suffix rules,
Russian bypasses and personal settings. Isolated native Mihomo checks passed
Belarusian and Russian IP routing, suffix/IDNA routing, unmatched proxy traffic,
earlier personal exceptions, enable/disable idempotence, provider conflicts and
failed-download preservation. Live installation verified the server connection
matched `minion-by-ips` with a DIRECT chain and returned an SSH greeting;
GitHub remained proxied and the selected node was preserved. No SSH login or
remote command was attempted. Proxy supervision/dashboard, setup staging,
Python syntax and diff checks also passed.
[Private Belarus IP report](../.local/device-checks/belarus-ip-bypass/result.json).

On 2026-10-17, setup gained a Thunar **Copy File Contents** custom action for
one text or miscellaneous file. The installed action command copied exact
UTF-8 text through the live Wayland clipboard, including Russian and a trailing
newline; a filename with spaces, a quote and literal shell syntax remained
literal. Isolated checks passed fresh configuration, private file mode,
preservation of personal actions/edits, unchanged reruns and rejection of
malformed XML without overwriting it. Setup staging (97 sources), Python syntax
and diff checks passed. Existing Thunar windows were left open; restart Thunar
to load the action before checking the context-menu interaction physically.
[Private clipboard report](../.local/device-checks/file-contents/result.json).

On 2026-10-17, Print Screen and the mapper's named screenshot action were routed
through `minion-screenshot`. Captures now save uniquely named, mode-0600 PNGs
under `~/Pictures/screenshots`, retain the clipboard copy and report success
with a one-second `Screenshot taken.` notification, without the filename.
Isolated checks passed unique paths, capture-failure cleanup and retaining saved
files if clipboard copying fails.
A live capture produced a 1920×1080 PNG; clipboard bytes matched the file and
the notification appeared and expired. Sway validation/reload preserved panel
mode, rotation and scale; the mapper restarted and became ready. Existing
personal Sway differences were retained. Recognizer, idle-policy, setup-staging,
syntax and diff checks passed; setup now stages 96 sources. A physical Print
Screen retest and fresh full setup remain pending.
[Private screenshot report](../.local/device-checks/screenshots/result.json).

On 2026-10-17, holding Start for 0.75 seconds then releasing gained a file-manager
action; short presses still open a terminal. Start's hold waits for release so
any overlap with Select retains passthrough priority, even after a long solo
hold. Recognizer checks passed threshold boundaries, stalled-frame release,
one-shot behavior, both overlap/release orders, cancellation and existing Menu
holds. Installed mapper/profile matched the previous committed baseline before
replacement; the restarted service selected the controller and became ready.
Synthetic frames through the installed mapper opened exactly one new Foot or
Thunar window through live Sway commands, with no launch before release.
The generated legend includes the configured Start hold automatically.
Setup-staging, syntax and diff checks passed. The physical Start retest and the
extended virtual-controller VM acceptance check remain pending.
[Private Start-hold report](../.local/device-checks/start-file-manager/result.json).

On 2026-10-17, Thunar reported a missing
`org.freedesktop.thumbnails.Thumbnailer1` service. Tumbler 4.18.1 and its extra
plugins were installed and added explicitly to the no-recommends package list.
Live D-Bus activation and generation of PNG/MP4 preview thumbnails passed;
a separate Thunar session browsed two folders without the missing-service
warning. Its `GFileInfo created without standard::size` critical remains.
A debugger run, deliberately configured to trap criticals, located that message
in the GTK cell-rendering path through `g_file_info_get_size`; ordinary browsing
continued without that debug setting. Upstream Thunar 4.18.8 uses this getter
without checking whether size exists; [4.20's source](https://github.com/xfce-mirror/thunar/blob/thunar-4.20.0/thunar/thunar-file.c#L2654)
handles missing size metadata for virtual locations. Ubuntu's configured sources
offer only 4.18.8, so no alternate build or warning suppression was installed.
Setup-staging and diff checks passed. Existing Thunar windows may need reopening
to refresh their supported thumbnail types.
[Private thumbnail report](../.local/device-checks/thunar-diagnostics/thumbnail-result.json)
and [browsing report](../.local/device-checks/thunar-diagnostics/browsing-result.json).

On 2026-10-17, imv 4.4.0 and mpv 0.37.0 were installed from Ubuntu packages
and added to ordinary desktop setup. Common image/video associations now use
their native desktop entries; existing browser and unrelated defaults were
preserved. `xdg-open` opened a generated PNG in imv and an H.264 MP4 in mpv
in the live Sway session. A separate one-second playback completed with VA-API
hardware decoding and GPU rendering. Ubuntu exposes the image command as
`imv-wayland`, rather than `imv`. Isolated provisioning checks retained personal
handlers and were idempotent; setup-staging, syntax and diff checks passed.
The video fixture was silent; audio, subtitles, other codecs and a fresh full
setup were not retested.
[Private media-viewer report](../.local/device-checks/media-viewers/result.json).

On 2026-10-16, Fn+F5 gained internal-panel 60/120 Hz switching, with the selected
mode saved for later sessions. The bar now reads the active rate and abbreviates
stick modes as `L:S/T R:W/R`. Native 60 → 120 → 60 Hz checks passed. Installation
exposed Sway resetting the panel's implicit 90° rotation on reload; landscape was
restored and the saved preference now includes current rotation and scale.
The corrected configuration reloaded successfully at 60 Hz, landscape and 2×
scaling. Installed scripts matched and a live bar stream showed `L:S R:W 60Hz`.
Isolated checks covered advertised/current-resolution modes, persistence, failed
switch/readback/write rollback, missing/inactive panel, personal/symlink refusal,
all compact labels and live refresh/error readings. Idle-policy, status-bar,
setup-staging, Sway validation and diff checks passed. The user confirmed that
Fn+F5 taps switch rates and a two-second hold switches only once. Next-login
persistence remains to be confirmed. In a subsequent observation on the same
day, the user reported that graphics flicker at 60 Hz had fallen to nearly zero,
with occasional recurrence. This is a qualitative report without a controlled
comparison or occurrence count; 60 Hz appears to mitigate the symptom, but does
not eliminate it or establish a root cause.
[Private refresh-controls report](../.local/device-checks/refresh-controls/result.json).

On 2026-10-16, the Neovim Back mapping reproduced `E19: Mark has invalid line
number` after an external edit shortened a loaded file and `checktime` reloaded
it. The saved jump still referred to line 90. Back/Forward now recover this
specific error using Neovim's selected history entry and `cursor()` clipping,
without clearing history or hiding unrelated errors. The previous config fails
the new regression with the reported E19. All 20 scope/navigation cases passed,
including Esc/Backspace/Alt+Left recovery, forward recovery, empty-file recovery,
repeat/reverse navigation and propagation of an unrelated autocmd failure.
The tested config was installed after an exact baseline comparison. Existing
editor instances need reopening. These are disposable headless checks; the
user's particular live editing sequence has not been replayed.
[Private stale-jump report](../.local/device-checks/neovim-stale-jumps/result.json).

On 2026-10-15, the WIN Mini's UPower policy changed from a 2% action threshold
to 20% low / 10% critical / 5% PowerOff. UPower was enabled for boot and restarted;
its live API confirmed PowerOff. The session warning service is active and part
of the graphical session, including the device's older target location. Installed
sources matched, unrelated UPower settings were preserved and a second policy
application made no changes. Isolated real-D-Bus warning transitions, policy,
idle/status-bar, setup-staging, service-unit, syntax and diff checks passed. No
real battery drain, shutdown or next-login cycle was performed.
[Private battery-protection report](../.local/device-checks/battery-protection/result.json).

`/usr/bin/python3 tests/check-battery-policy.py --integration` checks UPower policy
merging, retained unrelated settings, rerun stability, malformed-file/symlink
refusal, warning escalation/deduplication, charger reset and delivery retry. Its
real watcher runs against a private D-Bus with simulated UPower and notification
services; it checks notification urgency, replacement IDs, expiry, peripheral
filtering and daemon-owner changes. It never changes host battery readings or
calls a power action. This does not test a real battery discharge or shutdown.

On 2026-10-15, native domain-suffix DIRECT rules for `.by` and IDNA `.бел` (`xn--90ais`) were added to proxy defaults and the live device. The installed configuration and selected proxy were preserved apart from those two rules. Live TLS connection inspection confirmed `hoster.by` matched the direct suffix rule while GitHub still used PROXY; the public Hoster.by page returned HTTP 200. A disposable native engine verified root/subdomain and IDNA matches, lookalikes staying proxied, earlier personal exceptions and retained Russian domain/IP bypasses. Proxy supervision/dashboard checks, setup staging, syntax and diff checks passed. No browser sign-in or account-specific page behavior was tested. [Private Belarus bypass report](../.local/device-checks/belarus-bypass/result.json).

On 2026-10-15, duplicate Neovim Enter/Backspace actions were reproduced in real Foot 1.16.2 windows with both a clean editor and the previous project config. A single synthetic Return inserted two newlines, and Backspace removed two characters. Keeping CSI-u disambiguation while disabling key-event reporting reduced each to one action. The correction runs on UI attachment/resume and replaces protocol flags rather than growing the terminal's mode stack. A disposable PTY regression passed startup, single actions, intentional repeat, the resume hook and clean-exit mode restoration; it rejects the previous config. All 14 project-scope/navigation checks passed again, installed/repository configs matched, and setup staging/syntax/diff checks passed. Physical keyboard/gamepad confirmation and a physical suspend/resume cycle were still pending at this point. [Private Neovim input report](../.local/device-checks/neovim-input/result.json).

On 2026-10-15, the custom Wi-Fi chooser and legacy proxy CLI server-list/selection checker were removed. NetworkManager's existing tray menu supplies nearby networks, while the bar's Wi-Fi text opens its connection editor; the user accepted the upstream GUI. The live proxy choice migrated to Mihomo's native selector, remained selected after the service restart, and the one-time migration record was consumed. Routing, subscription and credential settings were retained; a proxied GitHub HTTPS request succeeded. Disposable native-engine tests verified authenticated control, Unicode choices, later GUI selections persisting across restarts, missing-node fallback and domain/IP bypass routing. Installed sources matched, the bar reloaded and launch actions opened the upstream editor/dashboard. Setup staging, status-bar, proxy supervision/bypass/migration, syntax and diff checks passed. No new Wi-Fi password, network switch, next-login cycle or full setup was tested. [Private cleanup report](../.local/device-checks/helper-cleanup/result.json).

On 2026-10-15, Ubuntu pass 1.7.4 and graphical GPG pinentry were installed, and the user initialized a personal encryption key/store through private prompts. A disposable token decrypted successfully, a second lookup reused the unlock in 0.401 seconds, and the test entry was removed. Effective GPG settings matched the 15-minute idle/one-hour maximum cache defaults, with external passphrase caching disabled. The proposed custom command wrapper was subsequently removed from the device and setup at the user's request. The setup guide now uses ordinary shell syntax with a failed-lookup guard. Private config/store modes, preservation tests and setup staging passed. Actual cache expiry and next-login prompts were not timed, and the user still needs a separate backup of the vault and secret key. No real cloud token or API request was used. [Private pass report](../.local/device-checks/pass/result.json).

On 2026-10-15, a session watcher added a centered US/RU confirmation popup for actual keyboard-layout changes. The user accepted its readability and one-second expiry. Live checks exercised both languages through Sway, verified in-place replacement with one notification ID, automatic expiry, a stable watcher process and restoration of the original layout. An isolated real-Mako preview checked the style without modifying the active notification server. Unit checks cover physical-keyboard selection, quiet startup/hotplug, duplicate events, replacement IDs, notification failures, personal-style retention and monitor streams with or without a subscription acknowledgement. The installed script/service matched the repository, and setup source-staging, syntax and diff checks passed. Setup preserves unrelated Mako settings and existing personal `minion-layout` rules. No reboot or full setup was repeated; next-login activation remains untested. [Private popup report](../.local/device-checks/layout-popup/result.json).

On 2026-10-15, the user accepted the refined voice/power controls: R4 tap starts/stops dictation, a 0.75-second hold cancels once and consumes release, L4 is unassigned, and Fn+F3/F4 now control display power/Keep awake. Fn+F5/F6 are consumed without an action on the built-in keyboard. The reader passed ordinary-repeat and up-to-100-macro-repeat checks, short/long/boundary holds, release consumption, subsequent taps, ignored L4 and inactive/locked-session guards. Cancellation waits for an in-flight activation rather than being dropped. Display control snapshots the pre-wake state on press and acts on release, preserving on/off behavior after a long key hold. Idle-policy, voice-input, source-staging, syntax and diff checks passed; installed sources matched, Sway validated/reloaded and both services stayed active. The user confirmed R4 dictation/cancellation, Fn display/awake controls and ignored L4 in the physical retest. No reboot or full setup was repeated. [Private button report](../.local/device-checks/voice-buttons/result.json).

On 2026-10-15, checksum-pinned Voxtype 1.1.1 and the multilingual Whisper small Q5_1 model were installed with Ubuntu's wtype helper. An 11-second public English sample transcribed correctly in about two seconds using the Radeon 780M Vulkan backend. Native Wayland text injection passed English and Russian Unicode in a disposable GTK window; the user then confirmed live microphone dictation in both languages. Recognition was subsequently changed to follow the physical US/RU keyboard layout at recording start. Live checks selected each fixed language correctly, started capture in about 0.3 seconds and preserved the recognition language after switching layouts mid-recording; both captures were cancelled without text output. The session service, Sway configuration/reload and one-second ALSA capture checks passed. Isolated checks cover download hashes/sizes, failed-download retention, managed updates, symlink refusal, personal-setting retention, language selection/freeze, busy/lock guards, bar states/clicks and setup source staging. Screen-lock stop/restart ordering was validated through systemd's loaded dependency graph; a physical lock/unlock and next-login cycle remain untested. The device's existing personal scrolling include was preserved while adding voice shortcuts. The later R4/Fn binding checks are recorded above. No full setup or reboot was repeated. [Private voice-input report](../.local/device-checks/voice-input/result.json).

On 2026-10-15, a follow-up Neovim audit reproduced automatic tree/working-directory changes when opening an external file with the tree visible, plus inconsistent tree/search scope after browsing to a parent and reopening a project file. The configuration now changes scope only at startup or through deliberate directory/root navigation. Fourteen integration checks passed against both repository and installed configurations, including file/text searches after external navigation, a fresh launch using saved editor state, and simultaneous independent instances. The previous configuration fails the external-file regression check. All 17 language fixtures and five TypeScript definition-picker/history checks passed again. Read-only inspection also confirmed that the user's original editor was still running after closing a window: `:q` closes one window; `:qa` exits the whole editor. The previous matching config was backed up before local installation; existing sessions need reopening. Setup-staging/hash and diff checks passed. [Private audit report](../.local/device-checks/neovim-audit/result.json).

On 2026-10-15, Neovim's startup directory selection was corrected so explicit directories take precedence over ancestor project markers. Six disposable headless checks passed against both the repository and installed configuration: `nvim .` inside a parent project, relative and absolute directory arguments, a file argument that infers the parent project, a directory without markers, and startup without arguments. Directory cases also verified that opening a contained file preserves the working directory and tree root. The installed configuration matched the previous repository version before updating; its backup remains private. Setup-staging/hash and diff checks passed. Existing sessions need reopening. [Private directory-root report](../.local/device-checks/neovim-directory-root/result.json).

On 2026-10-14, GIMP 3.2.6 (official stable Snap revision 561) and qBittorrent 4.6.3 (Ubuntu package `4.6.3-1build2`) were installed and added to ordinary setup. Qt 6 Wayland support was installed after qBittorrent reported the missing plugin. GIMP opened a generated 64×64 PNG through its desktop launcher; qBittorrent opened natively in Sway with app ID `org.qbittorrent.qBittorrent` and no platform-plugin warning. Torrent files and magnet links resolve to its desktop handler. An interrupted GIMP download succeeded on retry; the Qt dependency downloads succeeded through the existing local proxy after direct mirror requests failed, without persistent network changes. The additional-app installer retained Telegram/GIMP on rerun. Setup-staging/hash, syntax, package-audit and diff checks passed. No torrent transfer, Web UI or full fresh setup was tested. [Private apps report](../.local/device-checks/gimp-qbittorrent/result.json).

On 2026-10-14, Telegram Desktop 7.3.1 (Snap revision 7169) was installed from Telegram's official `latest/stable` channel. Ordinary setup now installs it after the browsers, retaining an existing native installation or selected Snap revision/channel. A live installer rerun retained the app without reinstalling it. Launching the installed desktop entry created a Telegram window in Sway, and `tg:` links resolve to its desktop handler. Snap's desktop, Wayland/X11, network, graphics and audio interfaces are connected. Setup-staging/hash, Python syntax and diff checks passed; no full setup or reboot was repeated. Account sign-in, messaging, calls and notifications remain for normal signed-in use. [Private Telegram report](../.local/device-checks/telegram/result.json).

On 2026-10-14, Blender 5.2.2 LTS (Snap revision 7803) was installed from the Blender Foundation's official `5.2lts/stable` channel and added to development provisioning. Setup retains existing Blender installations and selected Snap channels. The embedded Python API modified the factory scene, saved a `.blend`, rendered a nonuniform 64×64 PNG with Cycles on two CPU threads and reopened the file with the edited object position intact. The GUI launched under native Wayland with the Radeon 780M/Mesa 25.2.8 OpenGL viewport, and the normal first-run setup screen displayed correctly. An unsupported option in the initial test launch was treated as a filename; relaunching with supported arguments removed that error. The desktop launcher is available through the session's Snap application directory. Development-isolation, setup-staging/hash, syntax and diff checks passed. Cycles GPU/HIP rendering and a full fresh setup remain untested. [Private Blender report](../.local/device-checks/blender/result.json).

On 2026-10-14, LSP 1.2.16 and Dragonfly Reverb 3.2.10 were installed as Ubuntu VST3 packages, with both LSP packages selected from noble-backports. Checksum-pinned official BYOD 1.3.0 and AIDA-X 1.1.0 Linux releases supplied user-owned native VST3 bundles. SuperCollider discovered 184 effects (178 LSP, four Dragonfly, BYOD and AIDA-X). The repository's generated-audio demo loaded nine selected effects and recorded each on private buses without microphone input or speaker output. All nine recordings contained finite, non-silent, unclipped stereo processing at 48 kHz; factory-flat EQ/compression matched the dry reference. AIDA-X loaded its embedded neural model and cabinet IR. Unchanged installer reruns skipped archives and preserved bundles. Checksum/archive, personal-file retention, user-only installation, existing audio-tooling/development, staging/hash and diff checks passed. No full setup or reboot was repeated. The server and AIDA-X logged realtime-priority fallback, so live low-latency behavior remains unverified. The external guitar interface was unavailable; input routing, physical guitar sound and latency remain deferred. [Private effects report](../.local/device-checks/guitar-effects/result.json).

On 2026-10-14, the battery percentage gained a left-click action opening Power Statistics with the clicked battery selected. Battery blocks carry their supply instance; unsafe instance strings fall back to the application's default selection. The launcher also explicitly focuses an existing Power Statistics window. Status-bar checks passed, including button routing, launch arguments and instance handling. A live check of the installed script opened/refocused a single BAT0 window and recovered it from another workspace without duplication, then restored the original workspace/focus. The installed script matches the repository; Sway was reloaded to activate it. Physical bar tapping remains for ordinary use. [Private battery-click report](../.local/device-checks/battery-click/result.json).

On 2026-10-14, PowerTOP 2.15 and GNOME Power Statistics 43.0 were installed on the WIN Mini and added to desktop provisioning. Power Statistics opened visibly on the battery device, and UPower returned power-rate history. PowerTOP detected RAPL/PowerCap, generated a five-second activity/process report and displayed its interactive Overview; the probe then exited. Its optional cpufreq_stats/Devfreq probes were unavailable, but collection completed successfully. The device was charging, and PowerTOP had no saved battery-only estimation model, so per-process watts and discharge runtime were not validated. No calibration or auto-tuning was applied. Package/version, configuration diff and report checks passed. [Private monitoring report](../.local/device-checks/power-monitors/result.json).

On 2026-10-14, the WIN Mini's shell lacked `SSH_AUTH_SOCK` while the user service manager advertised a GnuPG SSH socket. Setup gained a desktop-scoped OpenSSH agent with a one-hour default key lifetime, automatic key loading and a fixed `IdentityAgent` fallback for existing processes. A validated per-account sudoers drop-in sets a shared 15-minute cache. The live installer passed full sudoers validation, successful sudo reuse from a separate PTY, SSH key loading and a second real Git `ls-remote` with `BatchMode=yes`. Effective SSH settings report 3600 seconds and the shared socket. A separate disposable key/agent check verified automatic expiry with a one-second test lifetime; no user key was inspected for that check. Host tests passed personal SSH precedence, configuration retention, user-context validation, reruns, rollback, staging/hash, coding CLI integration, shell/Python syntax and diff checks. The desktop agent is active and connected to the user service environment; logout/reboot lifecycle has not been repeated. [Private authentication report](../.local/device-checks/auth-cache/result.json), [expiry report](../.local/device-checks/auth-cache/expiry-result.json).

On 2026-10-14, the WIN Mini had no active/configured swap and retained an October 13 Firefox scope exit attributed to the OOM killer. Setup now supplies swap when no existing policy is present. The device received an 8 GiB, root-owned `0600` file on its LUKS/ext4 root; it is active and `/etc/fstab` generates an active swap unit. An immediate rerun preserved the file inode and fstab bytes. `findmnt --verify` passed. A transient test allocated 144 MiB inside a 96 MiB memory/128 MiB swap cgroup, observed 64.3 MiB swapped out and verified page-marker readback; it exited successfully and was collected. Isolated allocation, existing-policy retention, rerun, rollback, setup-staging/hash, syntax, documentation-link and diff checks passed. The configuration is ready for boot, but no reboot or unrestricted whole-desktop memory stress was performed. [Private swap report](../.local/device-checks/swap/result.json).

On 2026-10-14, Gamepad Start and Super+Enter were changed to use `minion-terminal`, which inherits the focused standalone Foot client's shell directory. Isolated checks covered custom application IDs, paths containing spaces/Unicode/shell metacharacters, missing/deleted directories, ambiguous clients and home fallback. A real Foot parent/child check passed before and after local installation: the child opened in the parent's project directory and received focus through Sway's existing policy. The installed mapper matched the repository and remained active; the live Sway config changed only its terminal launch command. Chord-recognizer, setup-staging/hash, Python syntax, Sway configuration and diff checks passed. The user clarified that focus already worked, so no focus policy was changed. [Private terminal launch report](../.local/device-checks/terminal-launch/result.json), [installation report](../.local/device-checks/terminal-launch/install-result.json).

On 2026-10-14, the WIN Mini's DejaVu-only desktop font set lacked glyphs for media symbols, musical notation and many emoji. `fonts-noto-core` and `fonts-noto-color-emoji` were installed and added to ordinary setup. Fontconfig reported coverage for all 57 sample Latin/Cyrillic, border, arrow, media, Braille, musical and emoji characters. The primary monospace match remained DejaVu Sans Mono; the rocket matched Noto Color Emoji and the G clef matched Noto Music. Foot's configuration check passed. The user confirmed all sample characters displayed correctly and the original issue was fixed. This does not establish coverage for every Unicode character, CJK text or private-use icon sets. [Private font-coverage report](../.local/device-checks/font-coverage/result.json).

On 2026-10-14, the WIN Mini switched from UTC to `Europe/Minsk` while network time remained synchronized and the hardware clock remained in UTC. Gammastep 2.0.9 accepted the real Wayland gamma-control request without a protocol failure. Off released the client, Automatic ran with the Minsk solar configuration, and Warm now ran continuously at 4500K; mode persistence was verified from the saved state. Isolated night-light, status-bar, setup-staging/hash, syntax and diff checks passed. No reboot was required. [Private night-light report](../.local/device-checks/night-light/result.json).

On 2026-10-13, SuperCollider 3.13, PipeWire's JACK bridge and the native audio build dependencies were installed on the WIN Mini. Pinned user-owned builds installed VSTPlugin 0.6.2 (native Linux VST3 hosting) and JUCE 9.0.4 sources. The editable Synth Lab C++ instrument built as a VST3 and loaded in SuperCollider, exposed Gain/Brightness parameters and played an eight-note MIDI melody plus a three-note chord. The script changed Brightness and recorded 5.397 seconds of stereo 48 kHz PCM audio; the recording was non-silent and unclipped (peak 0.101, RMS 0.0239). SuperCollider shut down after the recording, PipeWire/WirePlumber remained active and no separate JACK server remained. An installation rerun retained the project and skipped extension rebuilding. Audio-tooling, development-isolation, setup-staging/hash, syntax and diff checks passed. No full fresh setup or reboot was repeated; external third-party plugins and Windows/Wine plugins were not tested. [Private audio-tooling report](../.local/device-checks/audio-tooling/result.json).

The 2026-10-13 Neovim navigation audit exercised 17 file types through all 11 configured language servers: Go, Rust, TypeScript/TSX, JavaScript/JSX, Python, shell, JSON, YAML, TOML, C/C++, HTML, CSS, SCSS and Less. Normal-mode Enter/gd and Alt+Left/Right history checks passed in the 12 code fixtures with definition targets. All 17 file-symbol picker callbacks returned selectable results; reference pickers passed in those 12 code fixtures. The audit found that Go returns no project symbols for the original empty query, so F6 now uses live symbol search. Searching for a known symbol passed in all 10 fixtures whose servers advertise workspace-symbol support; JSON/YAML/TOML/HTML/CSS/SCSS/Less do not advertise it. A separate cross-file TypeScript test passed Enter on an imported type and gd on its use. Tests used disposable files and headless Neovim; they do not establish navigation in every real project or dependency. The tested configuration was applied locally after an exact comparison with the previous repository version. Existing Neovim sessions need reopening for the F6 change. [Private navigation matrix](../.local/device-checks/navigation-matrix-verified-result.json), [imported-type report](../.local/device-checks/typescript-import-navigation/result.json).

A follow-up TypeScript check on 2026-10-13 verified the definition picker for Enter/gd: imported types with one definition jump directly, while a merged interface with two definitions opens the searchable picker instead of a bottom quickfix split. Filtering and choosing the second definition passed for both mappings, with Alt+Left/Right restoring the exact source and target positions. Cancelling preserved the source cursor and tag stack; no quickfix entries or extra windows remained. Setup-layout and diff checks passed. The tested config was installed locally after confirming no unrelated local changes; reopen Neovim to activate it. [Private definition-picker report](../.local/device-checks/definition-picker-result.json).

On 2026-10-13, the simplified gamepad layout made Y immediate, repeatable Space alongside X Backspace. Editing moved to A+D-pad, navigation to B+D-pad, and all four layout toggles to Select-first face-button chords. The isolated recognizer passed 23 assignments in 148 valid press/release orders, including invalid-order suppression, release gaps, lifecycle cleanup and existing passthrough controls. A live GTK probe received 14 spaces and 14 backspaces during separate holds, with repeat stopping on release; all eight layout-toggle commands succeeded without stray characters, and B+Left/Right delivered Alt+Left/Right. Native Neovim jump-history checks passed both directions. Status-bar, setup-layout, syntax and diff checks passed; the VM fixture was updated but not rerun. Local installation succeeded with the mapper active, grabbed and ready, no held keys, and installed files matching the repository. Physical comfort remains for the user to confirm; existing Neovim sessions need reopening for the new history bindings. [Private live report](../.local/device-checks/new-gamepad-layout-live-result.json), [private installation report](../.local/device-checks/new-gamepad-layout-apply-result.json).

On 2026-10-13, native Sway `mouse_warping container` was enabled so right-stick window selection also targets pointer-based scrolling. A live probe with two disposable GTK windows verified centering in a newly focused window, preserving an off-center pointer position already inside the target, actual mapper wheel delivery to that target, and no pointer movement during scrolling. The original workspace names and focus were restored. The preference was saved in the user's existing Sway include and the repository's default Sway config; both configs validated, reload succeeded, and setup-layout/diff checks passed. This also applies to keyboard-driven focus changes. Physical controller comfort remains for the user to confirm. [Private pointer/wheel probe](../.local/device-checks/focus-pointer-probe-result.json), [private apply report](../.local/device-checks/focus-pointer-apply-result.json).

The 2026-10-13 stick-layout refinement makes Scroll/Windows the startup and reset default: left stick scrolls, right stick focuses windows, and L2+right stick moves them. L3 selects left-stick Text navigation/selection; R3 selects right-stick Resize. Isolated checks passed simultaneous wheel scrolling and window movement, all four combinations, text speed/modifiers on the left axes, independent neutral transitions, lifecycle reset and the existing shortcut/overlay checks. Status-bar and setup-layout checks passed; VM fixture axes and assertions were updated but the full VM suite was not rerun. Local installation passed with the mapper active/grabbed/ready, no held keys or pending switches, and all three installed files matching the source. Physical default-layout confirmation remains pending. [Private apply report](../.local/device-checks/scroll-window-defaults-apply-result.json).

On 2026-10-13, L3/R3 became independent stick switches, refined to left Scroll/Text and right Windows/Resize. Scroll/Windows is the default, allowing scrolling and window selection together. Each pending change suppresses only its own stick until it returns to neutral. All four combinations, continued movement of the other stick, pending-change cancellation, modifier behavior and lifecycle reset passed the isolated mapper check, alongside the existing 27 shortcuts in 196 face-first orders. The bar check passed all four labels and live updates; setup-layout and syntax checks passed. Menu tap now toggles the mapper-owned launcher, and a 0.75-second Menu hold toggles the persistent legend once while consuming release. A short Menu tap also dismisses the legend. Actual Fuzzel windows passed launcher second-tap dismissal, once-only legend hold, release consumption and short Menu dismissal without injecting input into applications. The mapper, default profile and bar were installed on the WIN Mini; source comparisons matched, the mapper was active/grabbed/ready with no held keys; the later default-layout refinement is recorded separately below, and Sway reloaded successfully. The VM mapping suite was updated but not rerun; physical stick comfort and Menu behavior remain pending user confirmation. [Private overlay probe](../.local/device-checks/independent-sticks-probe-result.json), [private apply report](../.local/device-checks/independent-sticks-apply-result.json).

On 2026-10-13, faster wheel scrolling was configured for Claude Code 2.1.287 and Cursor Agent 2026.10.01. Claude's supported `env.CLAUDE_CODE_SCROLL_SPEED = "3"` was merged locally and added as a setup default, preserving existing personal multipliers on reruns. Cursor uses normal terminal history; Foot's scrollback multiplier was raised from its implicit default 3.0 to 9.0 locally and in the fresh-setup template. Foot 1.16.2 configuration validation passed for both files. The coding-CLI and setup-layout checks passed, including retained unrelated environment settings and personal speed overrides. Ubuntu's Foot source confirms the multiplier applies to the normal buffer; alternate-screen apps reporting mouse events retain their own speed. No live CLI session was restarted and physical scrolling comfort remains unconfirmed. [Private settings report](../.local/device-checks/cli-scroll-result.json).

On 2026-10-13, CLI provisioning gained user-level commit/PR attribution preferences for Claude Code and Cursor Agent, applied on fresh setup and reruns. Isolated checks passed fresh config creation, preservation of unrelated model/plugin/permission settings and unknown attribution keys, user ownership, unchanged matching reruns, invalid-file refusal and read-only preflight. On the WIN Mini, Claude already had empty commit/PR attribution; Cursor's two enabled switches were disabled. A local backup was saved and JSON comparisons confirmed all unrelated settings survived; a second application left both files unchanged. No model request, commit or PR was generated for verification. [Private settings report](../.local/device-checks/attribution-defaults-result.json).

On 2026-10-13, the WIN Mini lacked `pipewire-alsa`, leaving plain ALSA clients without default-device routing through PipeWire. Installing that package fixed normal-user capture: `arecord -D default -d 1 -f S16_LE -r 16000 /dev/null` returned zero without ALSA errors, without restarting services or rebooting. The desktop package list now includes it. Setup-layout and diff checks passed. This verifies device opening and capture; voice-mode behavior in individual applications has not been retested. [Private capture report](../.local/device-checks/pipewire-alsa-result.json).

The sensor firmware check uses isolated targets to verify model matching, pinned download URLs, checksum refusal before installation, retention of existing plain/compressed firmware and installation of the accompanying license. It does not probe host hardware. Normal setup enables the sensor driver but leaves gyro input mapping and automatic rotation unconfigured.

## Host checks

Run from the repository root:

```bash
python3 tests/check-setup-layout.py
python3 tests/check-swap.py
python3 tests/check-auth-cache.py
python3 tests/check-secret-store.py
python3 tests/check-microphone-defaults.py
python3 tests/check-voice-input.py
python3 tests/check-sensor-firmware.py
python3 tests/check-browser-download-mode.py
python3 tests/check-chord-recognizer.py
python3 tests/check-status-bar.py
python3 tests/check-layout-popup.py
python3 tests/check-night-light.py
python3 tests/check-terminal-launch.py
python3 tests/check-window-origins.py
python3 tests/check-neovim-input.py
python3 tests/check-idle-policy.py
python3 tests/check-install-plan.py
python3 tests/check-install-launch.py
python3 tests/check-proxy.py
python3 tests/check-proxy-bypass.py
python3 tests/check-hhd-artifacts.py
python3 tests/check-coding-clis.py
python3 tests/check-development.py
python3 tests/check-reaper.py
python3 tests/check-realearn.py
python3 tests/check-midi-routing.py
python3 tests/check-audio-tooling.py
python3 tests/check-audio-effects.py
```

The secret-store check verifies private settings, retention of personal configuration/keys/stores and symlink refusal. With `pass` and GnuPG installed, `python3 tests/check-secret-store.py --integration` additionally creates a disposable fixture key/store to check actual encryption and the documented standard shell example: command environment injection, literal argument preservation, child exit status and missing-entry blocking. It never opens the personal vault.

The Neovim input check runs the actual editor/config in a disposable PTY that emulates Foot's keyboard negotiation and its measured duplicate release bytes. It verifies single Enter/Backspace actions, intentional repeat, the resume hook and restoring the shell's keyboard mode on exit. It needs the installed Neovim/plugins and host PTY/local-socket access, but sends no desktop input and opens no project files. A separate live Foot check reproduced the same bug with the previous config and single actions with the corrected config.

The microphone-default check covers WIN Mini model matching, the tested 10% input level, user ownership, fresh state creation, merging other routes and retaining saved levels byte-for-byte on reruns. It changes no host audio settings. The format follows [WirePlumber 0.4's per-route volume storage](https://github.com/PipeWire/wireplumber/blob/0.4.17/src/scripts/policy-device-routes.lua).

The voice-input check uses small local payloads and mocked Sway/systemd commands. It verifies checksum/size failures, retained personal files, managed upgrades, US/RU selection, a fixed language for each recording, idle-only language changes and cancellation. It opens no microphone or desktop window; live recognition results are recorded above.

The browser-download check covers independent Firefox/Chromium retention, complete cached dependencies, local artifact transport and rejection of damaged Chromium files before installation. Live new-network authentication still needs an actual network/password test.

The setup check verifies the root entry point, source staging and coordinator paths without installing packages. The swap check uses isolated files and mocked system commands to verify private allocation, existing-policy retention, boot-entry preservation, reruns and rollback after allocation/format/activation failures. The browser check isolates Snap command selection and existing-browser retention. The chord check feeds independent Xbox face codes through all 23 named shortcuts in 148 face-first press/release orders, and checks unlimited face-prefix holds, terminal-only Ctrl+C/Z/D with complete A+B prefixes, suppression of wrong-order and simultaneous inputs, immediate D-pad arrows with hold acceleration, polling-rate consistency, direction changes, neutral stop and bounded repeats after scheduling gaps, immediate Backspace holds, fixed versus trigger-modified shortcuts, terminal guards, invalid/rolling gestures, selection/neutral transitions, persistent legend capture, profile validation, lifecycle cleanup and held-arrow compatibility with shortcuts disabled. Stick-context checks cover Scroll/Windows startup/reset, all four independent behavior combinations, per-stick neutral switching and pending-change cancellation, Menu hold threshold/once-only/release consumption, owned launcher toggling and short Menu dismissal of the legend, pointer-preserving wheel delivery, full 120-unit detents and legacy equivalents, batch magnitude, direction/speed, ordered modifier frames, modifier suppression/restoration, failure handling, simultaneous scrolling/window movement, plain arrows, all Shift/Ctrl trigger combinations in all four directions, changing modifiers during continuous movement, the earlier profile action alias, speed by deflection, consistency across polling rates, slower vertical movement, single-step nudges, neutral stop, reversal, immediate slowdown and bounded repeats after scheduling gaps. It creates no host input device and reads Linux key codes from `/usr/include/linux/input-event-codes.h`.

The status bar check uses battery/hwmon fixtures and isolated command/API providers to check signal/network details, volume/mute, proxy service states, keyboard layout selection, power targets and safe click notifications. It checks HHD authentication, bounded read-only requests and failures, sensor units/labels, preferred channels, duplicate aliases, invalid/faulted/disabled sensors, live updates, disappearance and recovery. It does not query or change host hardware or services. The night-light check verifies timezone and personal configuration retention, mode persistence, continuous Wayland control arguments and cancelling the chooser without changing the mode. It uses isolated files and mocked system commands.

The HHD artifact check refuses corrupted downloads and altered cache entries, checks temporary-file cleanup, and verifies that matching cached releases need no network access. It also checks module-loading and enrollment decisions with isolated command responses: working modules, disabled Secure Boot, mismatched certificates, enrolled/pending keys, unattended instructions and interactive import success/failure. It changes no host modules or EFI variables. The setup-layout check includes default HHD installation, its read-only preflight and all component source hashes. Selected real power-control tests and remaining coverage are summarized in [validation status](validation-plan.md).

The coding CLI check verifies that installers and initial version checks drop root privileges, use the selected user's home and groups, and exclude root credentials/settings from their environment. It also checks that existing commands are retained without execution, failed downloads are cleaned up before shell execution, missing installed commands fail setup, interactive Bash sets PATH without duplication and preflight is read-only. Bubblewrap checks cover ordinary provisioning dependencies, initial AppArmor profile installation, preservation and reloading on reruns, inactive AppArmor, missing packaged profiles and load failures; these use isolated files and mocked parser calls. The setup-layout check includes these tools in ordinary provisioning and source staging. These checks do not download releases or start model sessions.

The ReaLearn check verifies download checksums, native VST monitoring-state serialization, preservation of personal DAW/key bindings and MIDI device slots, exclusion of the controller from performance inputs, retained controller mappings on reruns, and refusal to rewrite a running instance or unrelated monitoring chain. It uses synthetic plugin payloads and a temporary resource directory.

The development check verifies user privilege/environment isolation, immediate latest-version installation for missing defaults, retention of selected mise/Rust/Python versions, refusal of conflicting Docker runtimes/repositories and read-only preflight. It downloads no runtimes and changes no host services. The audio-tooling check verifies refusal of modified/foreign SDKs, modified extension preservation, editable project retention, unchanged reruns without rebuilding and refusal to run user-owned builds as root. It uses an isolated home and mocked build/download operations. The audio-effects check uses synthetic archives and an isolated home to verify checksums, rejection of traversal/absolute paths and links, preservation of modified/unmanaged bundles, unchanged reruns without downloads or writes, and refusal to install user plugins as root.

After development setup, run `python3 tests/check-neovim.py` for a headless integration check with the installed Neovim/plugins. It uses disposable files and isolated editor state to check directory/file startup, dependency navigation and back/forward history, file/text search scope, deliberate parent/root changes, `:q` versus `:qa`, fresh launches with saved state, and independent simultaneous instances. It launches no language servers and changes no desktop session. Use `--config ~/.config/nvim/init.lua` to check the installed configuration instead of the repository default.

The proxy dashboard check covers safe asset extraction, the native selector, one-time migration of old exact server pins/automatic policies, preservation of newer active dashboard choices, retained routing/personal groups, failed-validation rollback and confirmation before migration cleanup. With `python3 tests/check-proxy-dashboard.py --mihomo /PATH/TO/NATIVE/MIHOMO`, it runs a disposable real engine to check authenticated control, Unicode selection persistence, missing-node fallback and later GUI choices surviving repeated restarts. It needs no real subscription, external network or host routing changes. The status-bar check verifies Wi-Fi clicks launch NetworkManager's own connection editor; its tray menu supplies nearby-network selection.

`python3 tests/check-proxy-bypass.py --mihomo /PATH/TO/NATIVE/MIHOMO` also verifies Belarusian `.by` and IDNA `.бел` suffixes against a disposable local HTTP server: root domains/subdomains route directly, suffix lookalikes remain proxied, and earlier personal reject rules keep priority. The same fixture retains Russian domain/IP routing checks. No real subscription, host routing change or external network is used.

The idle policy check verifies logind's lid-suspend fallback outside the desktop session and the session's low-level lid inhibitor. It checks Awake-aware lid blanking versus lock-before-suspend, lock-failure refusal, lid reopening, and manual Fn+F3 blanking that survives activity, charger changes and reopening. Automatic idle blanking still wakes on input. Power-supply fixtures and isolated processes cover charger detection, battery timers, child cleanup and unexpected exit handling. Rear-button checks cover R4 tap/hold cancellation, separate subsequent taps and ignored L4 input, and Fn+F3 press/release snapshots. The status check covers the Keep awake indicator and live refresh. These checks change no host settings; physical lid and key behavior still require the device checklist. The chord check also covers Select toggling its owned window picker and cleaning it up during mapper resets; `tests/check-window-picker.py` verifies that cancellation dismisses its child overlay without selecting a window.

`python3 tests/check-proxy-bypass.py --mihomo /PATH/TO/NATIVE/MIHOMO` also checks Russian bypass precedence, repeated enable/disable, retained personal settings and failed-download preservation. Its native checks use local HTTP fixtures to prove domain and IP rules connect directly while unmatched traffic follows the proxy fallback, without changing host routes or services.

## Optional proxy container test

With Podman running, create a private file containing only your HTTPS subscription URL. Keep it outside Git and use mode 600. This test registers one device with the provider; reuse the saved `device-id` file on later runs rather than consuming additional device slots.

```bash
python3 tests/test-proxy-container.py --subscription-file /PRIVATE/PATH/subscription-url
# Repeat with the device-id path printed in the private report directory:
python3 tests/test-proxy-container.py --subscription-file /PRIVATE/PATH/subscription-url \
  --device-id-file /PRIVATE/PATH/device-id
```

The harness builds a disposable Ubuntu 24.04 image, runs systemd in a privileged container with its own network namespace, downloads the pinned binary, and exercises real subscription requests and HTTPS connections. It checks read-only preflight, private files, disabled initial activation, configuration retention, uninterrupted reruns, TUN capture, DNS, LAN bypass, boot activation, stop cleanup and URL redaction. It mounts no host directories and removes its container afterward. Reports and raw logs remain private under ignored `.local/proxy-qa/`.

Use `--platform linux/arm64` for a native ARM64 Linux container on an Apple Silicon Podman machine. Use `--skip-tun` to test HTTP/SOCKS mode when cross-architecture syscall emulation cannot run TUN or systemd-resolved. A passing report with TUN skipped does not establish system-wide capture. The test exercises the component installer directly, without installing a whole desktop; the host setup-layout check verifies that ordinary `setup.sh` and its read-only preflight include the proxy component. It also checks that no global management command is installed and that the enabled boot service works without its source checkout. The test image uses a fixture resolver configuration; it does not change the host's DNS.

## VM host requirements

On an Ubuntu host:

```bash
sudo apt-get install --no-install-recommends \
  qemu-system-x86 qemu-system-gui qemu-utils ovmf \
  cpu-checker openssh-client python3-pil python3-pexpect sbsigntool
kvm-ok
test -r /dev/kvm && test -w /dev/kvm && echo 'KVM accessible'
python3 tests/probe-host.py
```

QEMU runs as the ordinary host user. That user needs read/write access to `/dev/kvm`. The probe launches a diskless KVM/UEFI guest and shuts it down after inspecting QMP. An agent running in a sandbox may also need approved host execution for KVM, network sockets and QMP; filesystem access alone is insufficient.

Place `ubuntu-24.04.5-live-server-amd64.iso` in the repository root. The launcher verifies SHA-256 `97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8`. Installation media is ignored by Git. Start the [local mirror](local-mirror.md) and prepare its caches before repeated setup runs.

## Test the live USB installation helper

The [standalone installer](install.md) has a separate disposable test harness. It boots the ordinary signed ISO with Secure Boot enabled. Once the language screen appears, `console` switches to the live shell and adds only a public fixture SSH key. The actual installation starts later by running `install.sh` in that live environment. `install` and `interactive-install` use SSH with `--no-follow`; `console-install` launches through the actual Ctrl+Alt+F2 console and checks the independent service and dedicated progress console.

```bash
python3 tests/test-install-vm.py prepare
# Set VM_DIR to the printed directory.
python3 tests/test-install-vm.py launch "$VM_DIR"
python3 tests/test-install-vm.py console "$VM_DIR"
python3 tests/test-install-vm.py wait "$VM_DIR"
python3 tests/test-install-vm.py fixture "$VM_DIR"
python3 tests/test-install-vm.py console-install "$VM_DIR" --size 20G
```

Omit `--size` to test taking the largest free region. The 48 GiB fixture contains a preserved 100 MiB ESP, a reserved partition, a 4 GiB data partition and a 1 GiB recovery partition physically at the end. Whole-partition hashes are recorded before installation. These are synthetic contents, not a Windows installation.

To test the normal terminal prompts instead of supplying a private credentials file, replace the `install` step with `cancel` followed by `interactive-install`. The harness answers the actual hostname, username, password and encryption prompts through a terminal, verifies cancellation leaves the GPT and installer configuration untouched, then confirms a maximum-space installation with `INSTALL`. Installed-system verification uses password authentication for this path.

`check-viewer` can run immediately after `console-install`: it closes the dedicated viewer and original console viewer with Ctrl+C, checks the worker remains active, then reconnects with `--follow`. Saved screenshots must show the closed and reopened viewers.

Installation uses the local mirror's current URL, including its separate security endpoint. Oversized allocation is rejected before installation. Inspect `status` for progress and `capture` for the actual progress console; the installer automatically reboots, and QEMU exits because the harness uses `-no-reboot`. After it exits:

```bash
python3 tests/test-install-vm.py boot "$VM_DIR"
# Wait for the encryption prompt; capture saves screen.png for inspection.
python3 tests/test-install-vm.py capture "$VM_DIR"
python3 tests/test-install-vm.py unlock "$VM_DIR"
python3 tests/test-install-vm.py verify "$VM_DIR"
python3 tests/test-install-vm.py shutdown "$VM_DIR"
```

`unlock` enters a wrong fixture passphrase before the correct one. The saved `luks-wrong.png` must show rejection; QMP typing requires the VM to be at the prompt; Ctrl+Alt+F1 can reveal the text prompt if the framebuffer is blank. `verify` checks Secure Boot and kernel lockdown, encrypted root, the new ESP and default firmware entry, account-password sudo, original GPT entries and full hashes, and absence of plaintext credentials in installed logs/cloud configuration. It records the installation helper's SHA-256 from the installed storage plan. Reports and screenshots are private files under the fixture directory.

For a reinstall test, boot a fresh USB session on the same stopped fixture. `fresh-usb` backs up and resets only the VM's private firmware variables so the USB boots reliably; it does not change the virtual disk. After `console` and `wait`, `reclaim` first proves a 42 GiB request is refused while the previous Ubuntu allocation occupies space, verifies preserved hashes, then explicitly deletes only fixture partitions 5–7. It verifies that the original table is restored. Run `cancel`, then `console-install ... --size 20G`, `install ... --size 20G` or `interactive-install` and repeat cold-boot verification. This cleanup exists only in the guarded VM harness; the device installer contains no deletion operation.

`reset-preflight` and `finish` are diagnostic harness operations for failed test runs. A successful acceptance run must complete automatically without either operation.

## Create a manual installation fixture

```bash
python3 tests/vm.py prepare --secure-boot
```

Set `VM_DIR` to the printed directory, then launch:

```bash
VM_DIR=.local/vm/storage-server-EXAMPLE
python3 tests/vm.py launch "$VM_DIR" install --window
```

Preparation creates a blank 80 GiB virtual disk, private firmware variables, an SSH key and `credentials.json`. Read that private file locally and use its account password and disk passphrase during manual Ubuntu installation. Set the hostname to `minion-vm`, the account to `vmuser`, choose encryption, and install OpenSSH. Use the local archive mirror URL from [mirror instructions](local-mirror.md). The launcher supplies no Autoinstall configuration and does not choose partitions.

After installation, boot without the ISO using `launch ... boot --window`. In the guest, add the host fixture's `ssh-key.pub` contents to `/home/vmuser/.ssh/authorized_keys`; set the directory to mode 700 and the file to 600. Use `tests/vm.py ssh "$VM_DIR" vmuser 'true'` to verify access. Guest SSH uses a loopback port recorded in `state.json`.

Cold-boot tests require disk unlock and login prompts on the serial console. Inside this test VM, add:

```bash
sudo mkdir -p /etc/default/grub.d
sudo tee /etc/default/grub.d/99-minion-vm.cfg >/dev/null <<'CONFIG'
GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX console=tty0 console=ttyS0,115200n8"
CONFIG
sudo update-grub
sudo apt-get install -y mokutil efibootmgr
```

Configure both APT archive/security URIs to use the local mirror, then shut down the guest normally. Keep this unconfigured Server image as the baseline. Existing project fixtures remain usable; their backing images and private runtime files must stay in place.

## Test setup from sources

Create a writable branch of a stopped Server baseline; the baseline is checked and made read-only:

```bash
python3 tests/vm.py branch "$SERVER_VM" --secure-boot
# Set VM_DIR to the new directory printed above.
python3 tests/vm.py launch "$VM_DIR" boot --setup-assets --window
python3 tests/check-boot-authentication.py "$VM_DIR"
python3 tests/check-post-install-setup.py "$VM_DIR"
```

`SERVER_VM` is the manually installed baseline directory. The setup checker copies the root `setup.sh` and `setup/` directly into the guest. It checks invalid-account/missing-cache refusals, read-only preflight, configuration backup, unchanged GPT geometry and deferred networking/login activation. It installs through the explicitly shared read-only cache. No source or binary archive is built.

Before graphical checks, add fixture-only settings inside the guest:

```bash
sudo tee /etc/minion/vm-environment >/dev/null <<'CONFIG'
export WLR_RENDERER=pixman
export WLR_NO_HARDWARE_CURSORS=1
CONFIG
mkdir -p ~/.config/sway
cat > ~/.config/sway/minion.conf <<'CONFIG'
input type:keyboard {
    xkb_layout us,ru
    xkb_options grp:alt_shift_toggle
}
CONFIG
sudo poweroff
```

These software-rendering and language settings support the GUI tests and are not device defaults. Launch again, then run:

```bash
python3 tests/vm.py launch "$VM_DIR" boot --setup-assets --audio
python3 tests/check-boot-authentication.py "$VM_DIR"
python3 tests/check-login.py "$VM_DIR"
python3 tests/check-desktop-state.py "$VM_DIR"
python3 tests/check-secure-boot.py "$VM_DIR"
python3 tests/check-shell-editing.py "$VM_DIR"
python3 tests/check-browser.py "$VM_DIR"
python3 tests/check-history.py "$VM_DIR"
python3 tests/check-lock.py "$VM_DIR"
python3 tests/check-idle.py "$VM_DIR"
python3 tests/check-suspend.py "$VM_DIR"
```

Run GUI checks while signed in and unlocked. The idle/suspend checks deliberately lock the desktop. History testing temporarily disconnects virtual networking and then restores it. Reports are written beside the VM disk. Shut down normally, run `qemu-img check` on the stopped disk, and retain the reports with that source revision.

For setup reruns, run `check-post-install-setup.py "$VM_DIR" --rerun`; it tests retained personal settings and forces a real signed browser reinstall in this disposable guest. A source-only Git-clone rerun is available through `check-source-setup.py` on a branch of a passed setup VM. That checker intentionally downloads shell assets from upstream, so it does not measure local-cache reuse. `check-history-after-boot.py` checks persistence of a passing history test across a later reboot.

## Gamepad tests

Use a new branch of a passed desktop setup VM:

```bash
python3 tests/vm.py branch "$DESKTOP_VM" --secure-boot
# Set VM_DIR to the printed branch directory.
python3 tests/vm.py launch "$VM_DIR" boot
python3 tests/check-boot-authentication.py "$VM_DIR"
python3 tests/check-gamepad-mapping.py "$VM_DIR" --prepare
```

Preparation reapplies current setup sources through the local mirror and checks preserved settings/GPT and source hashes. Shut down and cold boot before testing the installed revision, then run:

```bash
python3 tests/check-boot-authentication.py "$VM_DIR"
python3 tests/check-login.py "$VM_DIR"
python3 tests/check-virtual-gamepad.py "$VM_DIR"
python3 tests/check-gamepad-mapping.py "$VM_DIR"
```

The synthetic controller is created inside the guest. Mapping tests use a Firefox text-field fixture to exercise editing keys, immediate/held Backspace, shortcut editing, navigation and right-stick selection; no browser navigation shortcuts are assigned. They also check constituent suppression, Sway focus/move/resize/workspaces, window shortcuts, persistent legend, picker/launcher, passthrough, reconnect, lock, inactive console and restart behavior. Exhaustive shortcut orders and terminal guards are checked separately by the host checker. The test removes its controller and HTTP service afterward. Physical trigger axes, adjacent presses and comfort remain device checks.

## Recorded results and current limits

On 2026-10-12, proxy setup gained the checksum-pinned MetaCubeXD v1.273.1 static dashboard, a launcher and a Proxy bar click action. The existing Mihomo service serves its authenticated API and local panel only on loopback. A private generated runtime retains the saved CLI routing/subscription policy while adding Automatic and native manual selection; graphical choices persist in Mihomo's cache, and explicit CLI choices supersede them once on the next start. Isolated native Mihomo checks passed automatic/pinned migration, Unicode manual selection across restarts, missing-server fallback and explicit CLI overrides, including restoring Automatic when the saved CLI policy was already automatic. Authentication and local static serving passed. Existing real cached-provider/filter/TLS checks and setup/status-bar checks passed. A disposable Chromium run connected automatically to an isolated core and displayed its proxy list at 960×540; a screenshot was inspected. [Private browser preview](../.local/device-checks/dashboard-browser-preview-result.json). Local installation passed: the saved subscription/configuration were retained, a second provisioning run retained the dashboard identity and did not restart the service, activation produced an authenticated local selector, and both HTTPS checks succeeded. The first real app launch exposed Chromium’s unbranded first-run terms placeholder and snap confinement of the session bootstrap; the launcher now skips first-run prompts and uses a private directory under the snap’s common storage. The desktop seeds matching startup flags for ordinary external links. The live Chromium window now reports Overview – MetaCubeXD, and opening an ordinary external link produced an Example Domain browser window without the terms dialog. [Private installation report](../.local/device-checks/proxy-dashboard-install-result.json). Physical dashboard usability remains pending.

On 2026-10-13, workspace navigation changed to a dynamic ring from 1 through N+1, where N is the highest occupied numbered workspace. R1 wraps from the extra empty workspace to 1, and L1 wraps from 1 directly to the last occupied workspace N, skipping the empty slot. A session service uses Sway workspace events to renumber remaining workspaces consecutively after empty workspaces disappear; the native bar stays unchanged. Host checks passed compaction/name-suffix preservation, forward/reverse wraparound, empty-slot bounds, Shift moves, explicit-list compatibility, setup staging and idle-policy checks. A live check with disposable Foot windows passed middle-workspace removal with focused-window preservation, both wrap directions, growth after filling the extra slot and moving without following; it restored the original workspace names and focus. [Private live report](../.local/device-checks/workspace-ring-probe-result.json). A subsequent live check verified backward wrap from 1 directly to N, return from N+1 to N, and unchanged forward navigation. [Private backward-wrap report](../.local/device-checks/backward-workspace-wrap-probe-result.json), [successful local correction](../.local/device-checks/backward-workspace-wrap-apply-result.json). Local installation succeeded; the installed mapper/helper/service match the repository and both services are active. [Private installation report](../.local/device-checks/workspace-ring-apply-result.json). Physical bumper comfort checks remain pending.

On 2026-10-12, gamepad workspace navigation became open-ended by default (`workspace_numbers: null`): R1 advances to the next number without wrapping, L1 stops at 1, and L2+bumper sends the focused window without following. Explicit personal workspace lists retain their circular behavior. The host shortcut check passed release-only dispatch, late Shift, navigation beyond 4 and 1000, the lower boundary, unnumbered workspaces, explicit-list compatibility and invalid-profile checks; setup staging and diff checks also passed. A live Sway check with a disposable Foot window verified advancement beyond 4, empty-workspace removal/recreation and moving to a new destination without following, then restored the original focus. [Private workspace probe](../.local/device-checks/open-workspaces-probe-result.json). Local installation succeeded, both installed files match the repository, and the restarted mapper is active, grabbed and neutral-ready. [Private installation report](../.local/device-checks/open-workspaces-apply-result.json). Physical bumper checks are pending.

On 2026-10-12, setup gained English/Russian typing with Ctrl+Space switching once per press, including a binding enabled while locked. Physical and gamepad keyboards share the same keymap so their modifiers combine; the desktop's Super shortcuts use keycodes to retain their physical positions under Russian. Interface language remains English. The prepared configuration passed Sway validation, idle-policy, status-bar and setup-layout checks. Local installation and reload succeeded; the installed configuration matches the repository, and switching the physical keyboard between both layouts also switched the gamepad keyboard. The user confirmed physical Ctrl+Space, Russian typing, R2+physical Space and L2 with physical letters. An isolated native Wayland Chromium check verified Cyrillic input, gamepad Select all and Undo/Redo under Russian; a Foot check received the expected Ctrl+C, Ctrl+Z and Ctrl+D control bytes. The check restored the previous window and layout. [Private shortcut report](../.local/device-checks/russian-shortcuts-result.json), [private keyboard installation report](../.local/device-checks/russian-keyboard-install-result.json). Physical lock-screen switching remains untested.

On 2026-10-12, the WIN Mini passed the complete native Wayland glmark2 2023.01 suite on the Radeon 780M (radeonsi/Mesa 25.2.8), running fullscreen for 332 seconds. GPU utilization reached 99%; peak GPU/CPU temperatures were 51°C / 54.125°C, with the automatic fan reaching 5377 RPM. All scenes completed with exit status zero, and the kernel log recorded no GPU errors, resets or timeouts during the run. The user confirmed the animation looked correct. Ubuntu's verified test packages were extracted into the private test directory without installing system packages or changing power settings. [Private 3D report](../.local/device-checks/graphics-3d-result.json). This establishes OpenGL 3D operation under this workload; Vulkan rendering workloads and hardware video decoding were not tested.

On 2026-10-12, a driver audit on the WIN Mini 2023 confirmed hardware-accelerated OpenGL on the Radeon 780M (`amdgpu`, radeonsi/Mesa 25.2.8) and successful Vulkan enumeration through RADV. The motion sensor was unbound because `bmi260-init-data.fw` was absent. Setup now conditionally installs the pinned upstream firmware and license when this model lacks either plain or compressed firmware, while retaining existing package-provided copies. Firmware corruption/retention checks and setup staging/preflight checks passed. Local installation followed by a probe of only `i2c-BMI0160:00` successfully bound `bmi270_i2c` without reboot; the `bmi260` IIO device returned changing samples on all six acceleration/angular-velocity channels. [Private sensor report](../.local/device-checks/sensor-firmware-install-result.json). Deliberate tilt/orientation accuracy, calibration, gyro input mapping, sensor resume/reboot behavior and actual hardware video decoding remain untested.

On 2026-10-12, the WIN Mini's battery idle check locked successfully after five minutes, but the ten-minute display-off command failed with `Invalid output subcommand: Documents.` The unquoted output wildcard expanded into home-directory filenames when swayidle ran the command through the shell. Both display-off and resume commands now quote the full Sway command. A regression check executes both commands through `/bin/sh` with a stub IPC client in a populated directory and verifies that the wildcard survives. Idle-policy and setup-layout checks passed. After local installation and idle-service restart, a brief power cycle using the corrected commands reported Sway output power false and kernel DRM DPMS Off, followed by successful restoration to On. [Private panel report](../.local/device-checks/idle-display-fix-result.json). The user then repeated the idle check and confirmed that display-off now works.

Also on 2026-10-12, a physical rear-button capture identified L4 as `KEY_SYSRQ` and R4 as `KEY_PAUSE` on the separate `12068:309:Mouse_for_Windows` keyboard. Initial Sway-only bindings passed the automated display power/input wake check, but the user's physical hold test exposed repeated toggles, and L4 needed a toggle action to restore the display. The final session reader coalesces firmware macro sequences into one action after release and handles L4's own input waking the display before its action. A device-specific uaccess rule grants access only to the dedicated rear keyboard. The corrected controls passed isolated idle-policy and setup-layout checks, Sway configuration validation and installed service verification; the status-bar check also passed. The on-device check again reported panel power false / DRM DPMS Off, continuing background execution, successful wake from synthetic Shift input, and no lock created. All three idle/wake/rear-reader services remained active; the rear keyboard was readable and the power-button settings stayed unchanged. [Private refinement report](../.local/device-checks/rear-idle-controls-refinement-result.json). The user then confirmed that holding R4 for three seconds toggles once on release and that L4 turns the panel off and restores it on the next press. The full VM suite, reboot persistence, locked-screen L4 and separate touchpad/touch/controller wake checks have not been repeated for these changes.

The same device session exposed persistent routine popups because Mako had no configuration and its default timeout was zero. Setup now seeds a personal Mako configuration with a five-second default and a 2.5-second Keep awake timeout, preserving existing personal settings and honoring explicit sender timeouts. Critical alerts retain a zero default timeout. The configuration was installed locally and reloaded without restarting the desktop, and the two stale Keep awake popups were dismissed. A live D-Bus test verified that a Keep awake notification disappeared by three seconds, a normal notification remained at three seconds and disappeared by six, and a critical notification remained until test cleanup. [Private notification report](../.local/device-checks/notification-timeout-result.json). Setup source staging and diff checks passed; fresh-setup and reboot checks have not been repeated for this notification change.

On 2026-10-12, Codex sandbox startup on the WIN Mini failed before command execution with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. Kernel audit logs identified AppArmor `unprivileged_userns` capability denials. Installing Ubuntu's `apparmor-profiles`/`apparmor-utils` packages and loading the packaged `bwrap-userns-restrict` profile fixed startup. Both `codex sandbox -- /bin/true` and commands in the existing Codex session succeeded. Live boundary checks verified workspace write/read, denial of a write elsewhere in the user's home (`EROFS`), denial of a direct IPv4 TCP connection (`EPERM`), and a network namespace distinct from the host. The global `kernel.apparmor_restrict_unprivileged_userns` setting stayed at `1`; the profile matches Ubuntu's package, is installed in `/etc/apparmor.d/`, and AppArmor is active and enabled for boot. Coding CLI provisioning and setup-layout checks passed inside the repaired sandbox. [Private apply report](../.local/device-checks/sandbox-profile-apply-result.json), [private boundary probe](../.local/device-checks/sandbox-boundary-probe.json). A reboot and full clean-VM setup have not been repeated for this fix.

On 2026-10-13, the WIN Mini gained a separate Neovim project viewer (`minion-projects`, `NVIM_APPNAME=minion-view`) with a navigation-only file tree, fuzzy file lookup, project text search, language-server navigation and read-only source buffers. Native language checks initialized Go, Rust, TypeScript, Python, Bash, JSON, YAML, TOML and C/C++ servers; Go/Rust/TypeScript/Python/Bash/C++ returned definition locations, and JSON/YAML/TOML returned document symbols. The TypeScript check caught an incompatible legacy wrapper; the profile uses the installed TypeScript 7 native server. Ubuntu clangd 18.1.3 supplies C/C++ support. An external-change check verified reload on focus with read-only state preserved. Development isolation, setup staging and syntax checks passed. The user confirmed that on-device browsing, file lookup and search look usable. [Private language report](../.local/device-checks/project-viewer/language-results.json), [reload report](../.local/device-checks/project-viewer/reload-result.json). No full fresh setup or reboot was repeated for this addition.

Later in that session, the user requested ordinary editable Neovim instead of a separate read-only entry point. Setup now installs the same project tools into the default `~/.config/nvim` and `~/.local/share/nvim` locations, with a **Neovim** desktop entry. The installed `minion-projects` wrapper/menu entry was removed, and its retired profile was archived privately. Plain `nvim` passed all nine language checks with editable buffers. Native directory arguments (absolute and relative) opened the project tree, relative file arguments opened the intended source, and a disposable file could be edited and saved. A rerun retained the installed configuration and exact plugin revisions. [Private native language report](../.local/device-checks/project-viewer/default-nvim-language-results.json), [editing/directory report](../.local/device-checks/neovim-default-migration/default-result.json). No fresh setup or reboot was repeated for this simplification.

On 2026-10-11, normal setup gained mise-managed Go, Node/npm, pnpm, TypeScript and supporting tools; rustup stable with its development components; uv-managed current CPython and Ruff; and Docker CE/Buildx/Compose from Docker's signed repository. Host checks passed target-user isolation, partial-download refusal, immediate latest installs, stable CPython selection excluding prereleases/free-threaded variants, retained defaults, repository/runtime conflict refusal, read-only preflight, source staging and syntax.

A disposable native ARM64 Ubuntu 24.04 container installed all requested tools from upstream. Real Go, Rust and TypeScript compile/run checks passed, along with pnpm scripts, uv isolated dependency installation, pytest, Ruff, Pyright and a CMake/Ninja C++ build. Ubuntu's system Python remained 3.12. Automatic Node switching between global current and project Node 24 passed both plain interactive Bash and the actual Minion Bash/ble.sh/Atuin integration in a PTY. A newly populated mise config installed both runtime/tool batches successfully. Rerunning retained a deliberately selected Node 24 global default, custom Rust default, Python executable link, mise configuration, Docker configuration and daemon PID. A home Python pin also retained the user's selection while the newest stable interpreter remained installed. [Private development report](../.local/development-qa/report.json), [rerun report](../.local/development-qa/rerun-report.json).

Docker Compose built a local image from the Go executable, ran it successfully without sudo as the selected user, and removed its service/network/image. Nested overlay mounts failed in this Podman environment; this check used a **QA-only vfs/legacy image-store configuration**, with no production Docker configuration override. These component tests ran on ARM64, not the handheld's amd64 hardware. Full desktop setup, native amd64 toolchains and Docker's default storage/network behavior on the WIN Mini still require a device check.

On 2026-10-11, ordinary setup gained the official native Codex, Claude Code and Cursor Agent installers for the selected user, with Bash PATH integration and retention of existing executables without launching them. Host CLI isolation/failure/PATH checks, setup-layout checks and syntax checks passed. In Ubuntu 24.04 amd64 under QEMU, Codex 0.162.1 and Cursor Agent 2026.10.01-e373342 passed installation, unprivileged version/help commands, ownership, unchanged binaries/settings on rerun without download connectivity, and execution with the checkout unavailable. The test caught Cursor rewriting settings during `--version`; setup now skips execution of retained commands. [Private amd64 report](../.local/cli-qa/amd64-report.json).

Codex and Claude test payloads were cached after comparison with published SHA-256 checksums to avoid this environment's download rate limits; Cursor downloaded through its normal installer. Claude's bundled Bun runtime aborted with `MemoryExhaustion` under x86 user emulation. Its verified 2.1.287 ARM64 binary passed version/help checks in native Ubuntu Linux, but its upstream installer remained blocked by the test network's MITM certificate validation. No certificate bypass or test relay is included in device setup. Claude's complete amd64 installation, account sign-in, authenticated model sessions and all three tools' sandbox behavior remain device checks. [Private native report](../.local/cli-qa/native-report.json).

On 2026-10-11, the bar gained an authenticated read-only HHD target display and conditional CPU/control, GPU, NVMe and battery temperature summaries, with a full sensor notification and an HHD launcher action. The status-bar suite passed target versus quick-slider precedence, unavailable/unready controls, API authentication/bounded responses/timeouts, Celsius conversion, preferred channel selection, duplicate aliases, invalid/faulted/disabled sensors, safe clicks and live sensor/API loss and recovery. Setup-layout and syntax checks passed. These isolated tests do not establish which sensors the WIN Mini exports, physical readback accuracy, bar fit at 2× scaling, native UI launch or suspend behavior; those checks are queued for the device.

On 2026-10-11, default setup gained HHD 4.1.12 and HHD UI 3.4.2 with verified release downloads, Ubuntu-managed Python dependencies and a power-only boot service. An amd64 Ubuntu 24.04 container with synthetic WIN Mini `G1617-01` DMI passed real package installation, ACPI DKMS compilation against the current HWE headers, Python dependency checks, UI library resolution and sandbox-helper permissions, authenticated localhost API access, provider filtering, disabled initial TDP/energy overrides, retained settings and an uninterrupted rerun. Boot with the checkout unavailable retained settings and kept overrides disabled. The test caught and corrected a separate upstream one-shot TDP-enable action default. [Private HHD report](../.local/hhd-qa/installed-report.json).

Host setup-layout, artifact refusal/cache and syntax checks passed. Electron's sandbox failed to launch under Mac-hosted x86 QEMU user emulation with `clone: Invalid argument`; native Wayland UI operation remains unverified. The container has no physical AMD power/GPU/fan hardware and cannot establish Secure Boot module acceptance. These checks do not replace the [device results and remaining checks](validation-plan.md#remaining-checks), and a complete desktop provisioning run has not been repeated for this addition.

On 2026-10-11, the bar gained Wi-Fi signal/network details, volume/mute, proxy service state and a conditional keyboard layout indicator, with compact battery labels. The status bar checker passed fixtures, live state changes, protocol output and unavailable/timed-out providers; setup layout and Python syntax passed. These checks use isolated command providers, so physical Wi-Fi/audio/battery readings and the complete bar in a handheld session still need device verification.

On 2026-10-11, the status bar gained system battery percentage and charging status. Isolated power-supply fixtures passed charging/discharging/full states, changing readings, missing/invalid values, absent/peripheral battery filtering, multiple batteries and valid bar JSON while retaining the right-stick indicator. Shell syntax passed. Physical WIN Mini battery readings have not been checked.

On 2026-10-12, D-pad shortcuts became face-button-first with no prefix timeout. D-pad-first navigation now emits immediately, repeats after 400 ms and accelerates from 4 to 30 horizontal or 10 vertical steps per second over another 1.2 seconds. The Linux frame checker passed 168 valid face-first press/release orders across all 24 shortcuts, wrong-order and simultaneous suppression, unlimited prefix holds, polling-rate consistency, bounded scheduling gaps, direction changes, modifier handling, personal D-pad mappings, legend capture and lifecycle resets. Setup-layout and Python syntax checks passed. A local Firefox probe on the WIN Mini passed real arrow delivery, increasing horizontal movement from 5 to 28 steps per second, release stop, all four Shift/Ctrl combinations, delayed-prefix Home, wrong-order suppression and simultaneous-start suppression. [Private D-pad browser probe](../.local/device-checks/dpad-navigation-browser-probe.json). The full VM harness was updated but has not been rerun; physical controller comfort and diagonal shortcuts remain on-device checks.

On 2026-10-12, R3 became a shared Window/Workspace switch. Window starts by default and uses left-stick scrolling plus right-stick text navigation/selection; Workspace uses left-stick focus/move and right-stick resizing. The Linux frame checker passed both-stick neutral transitions, scrolling target/direction/speed/modifier/failure cases, simultaneous scrolling and selection, text modifier/speed/precision checks, lifecycle reset and the existing 480 shortcut press/release orders. Isolated status-bar tests passed Window/Workspace labels and setup-layout checks passed. A physical WIN Mini Firefox probe passed 16 real Sway wheel-delivery cases covering both axes/directions with each Shift/Ctrl combination; triggers did not change ordinary scrolling. [Private browser probe](../.local/device-checks/stick-scroll-browser-probe.json). The first synthetic Sway wheel path produced only about 1.2 vertical or 0.65 horizontal CSS pixels per step in Firefox. Replacing it with kernel wheel detents produced 144 vertical or 78 horizontal CSS pixels per step in the same fixture. The strengthened probe checks substantial scroll distance as well as direction and trigger suppression. [Private wheel-distance probe](../.local/device-checks/stick-scroll-wheel-probe.json). The full VM mapping suite was updated but has not been rerun for this change; physical controller comfort, split-pane behavior and other applications still require device checks.

On 2026-10-11, character chords and the L3 Super layer were replaced with 24 named D-pad + Y/A/B shortcuts, immediate holdable X/Backspace, R3 right-stick selection mode and an L3 shortcut legend. The Linux frame checker passed all 480 assigned press/release orders, independent Xbox button codes, modifier restoration, terminal guards, selection/repeat/neutral transitions, legend capture, profile validation and lifecycle resets. Setup layout, browser download mode, Python and shell syntax checks passed.

An isolated Ubuntu 24.04 ARM64 session with real Sway 1.9 and Foot confirmed close, split, layout, fullscreen and floating commands; equalizing three uneven tiles preserved focus. Real Fuzzel remained open until dismissed and closed with Escape or a second legend action. [Private desktop report](../.local/controller-qa/controller-desktop-report.json). Keyboard delivery in this session used a wtype bridge rather than kernel uinput. The GTK editor did not reliably process selection through that bridge, so application text selection remains unverified. The revised full VM mapping suite has not been run; physical controller behavior, Backspace repeat, text selection and suspend/resume still need device checks.

On 2026-10-11, the project codename and internal names changed to Minion, while repository URLs and the clone directory remained `ubuntu-mini`. This layout targets fresh installations and includes no migration from earlier names. Setup layout, browser download mode, installer planning, proxy preservation/supervision, Linux installer handoff and gamepad chord checks passed. Python and shell syntax checks passed. Isolated Ubuntu provisioning checks confirmed the generated command paths, session dependencies, device/network configuration and Bash include; real Sway 1.9 accepted the generated configuration and read the renamed personal include. Package/device commands and shell artifact installation were mocked in this layout check. [Private layout report](../.local/rename-qa/minion-layout-report.json).

The renamed proxy also passed the complete native ARM64 container test, including live subscription retrieval, explicit HTTPS proxy egress, TUN routing/DNS, configuration retention, startup without the source checkout and direct connectivity restoration after stop. [Private Minion proxy report](../.local/proxy-qa/container-1vk4jel9/report.json). A full OS installation, desktop login and physical handheld checks were not repeated for the rename. Earlier reports below predate the Minion names.

On 2026-10-11, proxy installation was included in ordinary setup and management moved to repo-based `setup/proxy/manage.py`, with a root-owned runtime copy used by systemd. Host checks passed default installation/preflight integration, source staging, configuration preservation and service supervision. Both the [updated amd64 explicit-proxy test](../.local/proxy-qa/container-c2iyxl7t/report.json) and [updated native ARM64 TUN test](../.local/proxy-qa/container-0c8lmvly/report.json) passed real component installation, retained state, service lifecycle and boot with the source checkout unavailable. Native routing/DNS/cleanup passed again. One earlier native run failed a live HTTPS probe; the complete repeat passed without code changes. A full desktop provisioning run was not repeated for this revision.

On 2026-10-11, the optional Mihomo component fetched a real HWID-protected subscription and passed native ARM64 Ubuntu 24.04 container checks for verified installation, HTTPS proxy egress, retained configuration/device registration across reruns, no service restart on installation rerun, ordinary HTTPS through TUN, DNS capture, private-network bypass, service activation after container reboot, tunnel removal, restored public routing/direct egress/DNS after stop, and subscription URL redaction. [Private native Linux report](../.local/proxy-qa/container-7hd90s_u/report.json). The amd64 coordinator and pinned amd64 core also passed installation/preflight, private configuration, real HTTPS proxy egress, uninterrupted reruns, enabled boot startup, stop/direct-egress restoration and URL redaction in explicit-proxy mode. [Private amd64 report](../.local/proxy-qa/container-tl9g7x8r/report.json). Host refusal/preservation/supervision checks, setup layout and Python syntax checks passed.

No IPv6 uplink was available, so IPv6 connectivity remains unverified. The amd64 core under emulation failed a TUN route syscall; native ARM64 routing tests do not verify the handheld's amd64 kernel, Wi-Fi changes, suspend/resume or physical LAN access. Provider device slots and endpoint availability also remain external dependencies.

On 2026-10-09, the L3 layer gained release-only command singles: X/Y/A/B close/toggle layout/open terminal/cancel, and Up/Down/Left/Right copy/paste/undo/redo. Host frame checks passed all eight singles, Foot versus GUI clipboard modifiers, blocked terminal undo/redo, unknown-focus rejection, trigger restoration, in-progress cancellation and lifecycle cleanup. All 960 normal and 960 Super chord orders still passed, including late modifiers and no-chords compatibility. The setup-layout and Python syntax checks passed. An isolated headless Ubuntu Sway 1.9 session identified a real GUI client, toggled tiled→tabbed→tiled and closed only the focused test window; all three IPC commands succeeded. These checks used cached software with zero downloads. [Private command-layer report](../.local/desktop-qa/command-layer-report.json). The VM harness includes the new commands and real browser clipboard/editing cases, but has not been rerun. Real Foot clipboard behavior and physical controller comfort remain device QA.

On 2026-10-09, L3 was changed to arm/cancel one-shot Super. Host checks passed all 960 chord press/release orders both normally and with Super, all 48 late Shift/Ctrl combinations with Super, single-key shortcuts, modifier ordering, cancellation, pending-state cleanup across disconnect/lock/inactive-session/passthrough/reset, and held-arrow compatibility when chords are disabled. The setup-layout check passed. The VM harness now checks actual Super+Enter, Super+F, Super+D and Super+Shift+Q shortcuts, but has not been rerun for this change; physical L3 comfort and shortcut dispatch need device QA.

On 2026-10-09, physical WIN Mini QA reported that Y produced Backspace, X produced Tab, and Y+B/X+A produced nothing. Feeding Xbox/xpad event codes into the mapper reproduced all four symptoms. The X/Y translation and single-button defaults were corrected. The host chord checker now feeds independent Xbox face codes rather than deriving input from the mapper's own configuration; it failed on the previous source and passed after the correction, including all four single actions, 960 chord press/release orders and 48 late-modifier cases. The setup-layout check also passed. The browser VM harness was corrected to use the same driver codes, but has not been rerun; the device still needs a retest after applying the updated setup.

On 2026-10-09, physical-device QA reported tiny desktop elements and a permission error from `brightnessctl -c backlight set +5%`. The desktop defaults now use 2× scaling, explicitly install Ubuntu's `brightness-udev` rules, add the selected account to `video`, and include playback/Print Screen bindings. Ubuntu Sway 1.9 accepted the full configuration; an isolated headless session confirmed a 960×540 logical workspace at 1920×1080/2× and a 1280×720 workspace with a 1.5× override. Isolated provisioning verified account selection, package selection, group setup, backlight-rule refresh and deferred activation; the existing setup-layout check passed. [Private scaling report](../.local/desktop-qa/scaling-report.json). These checks do not verify physical backlight writes, Fn key codes, audio/media playback or comfort on the device; retest those after updating and logging in again. No full desktop VM setup run was repeated for this patch.

On 2026-10-09, the observable helper passed a complete 20 GiB installation launched through the actual live Ctrl+Alt+F2 console. It automatically switched to the dedicated F3 progress viewer, ran the handoff in an independent service, and installed helper SHA-256 `4d7933e44515b6efd49fcf0da07a391850231bffc85abcda56b0fd0040a3afac`. Ctrl+C closed both the dedicated viewer and original console viewer without stopping installation; `--follow` reopened progress. Cancellation still left disk and configuration unchanged. The run required no installer diagnostic intervention and rebooted automatically.

Cold boot without the ISO passed wrong-passphrase rejection, correct unlock, Secure Boot and integrity lockdown, account access, the new ESP/default firmware entry, unchanged original GPT entries and whole-partition hashes, and absence of plaintext credentials in installed logs. Ctrl+Alt+F1 was needed to reveal the text unlock prompt in this VM. The final run served 155 requests and approximately 291 MB from the package cache, with zero upstream mirror downloads. [Observable installation summary](../.local/vm/observable-install-summary.json), [current console installation](../.local/vm/storage-install-nkpl8nsn/install-report.json).

On 2026-10-08, the live-USB helper passed complete automatic installations with a 20 GiB explicit allocation and a 42.89 GiB maximum-space allocation. A reinstall passed after explicitly reclaiming only the previous Ubuntu partitions. The final maximum-space run used real terminal credential prompts and `INSTALL` confirmation, with cancellation tested first. It required no diagnostic intervention and installed helper SHA-256 `15b9053725debbd04fe53d4f31208d3e68d16713b665854c89eb850199432117`. The explicit-size run used the preceding revision; the subsequent helper change corrected terminal input handling.

Both installed systems passed cold boot without the ISO, wrong-passphrase rejection, successful unlock, Secure Boot, account access, Ubuntu's new ESP/default firmware entry, unchanged original GPT entries and whole-partition hashes, and absence of plaintext credentials in installer logs/cloud configuration. The final interactive run also confirmed kernel lockdown in integrity mode. Package downloads used the local mirror; the final run served its requests from cache. The fixtures contain synthetic partitions, so Windows boot and BitLocker recovery remain physical-device checks. [Installation summary](../.local/vm/install-summary.json), [20 GiB reinstall](../.local/vm/storage-install-dtuowdxy/install-report.json), [2026-10-08 interactive installation](../.local/vm/storage-install-nkpl8nsn/2026-10-08-interactive-report.json).

Previous standalone setup runs passed clean Server provisioning, reruns, personal-setting preservation, configuration backups, unchanged GPT geometry, cold boot, graphical login, desktop services, shell editing/local history and real signed Firefox installation through the cache. The source-clone rerun passed real upstream shell downloads while retaining an existing browser. [Standalone summary](../.local/vm/post-install-setup-summary.json), [source-clone report](../.local/vm/storage-desktop-69unztc4/source-setup-report.json).

Signed boot and kernel lockdown passed before/after maintenance; earlier experiments also observed rejection of unsigned EFI code and a signature-stripped kernel. Maintenance retained the same kernel version. Earlier automated installation/storage experiments were removed from the source tree; the current standalone helper was tested separately as described above. [Signed boot report](../.local/vm/storage-desktop-zm9c2afx/secure-boot-boot-report.json).

The retained character-chord VM passed 25 acceptance groups and 96 character cases covering 95 printable ASCII characters. Its layout predates the named shortcuts above. [Gamepad acceptance summary](../.local/vm/gamepad-chords-summary.json), [mapping report](../.local/vm/storage-desktop-zm9c2afx/gamepad-mapping-report.json).

These records describe the sources installed at the time of each run. The reorganized setup source tree and simplified manual-install launcher have host checks; a fresh complete desktop setup run has not been repeated after restructuring. A full current-source clean installation, different-kernel maintenance and optional workflow/peripheral checks remain in [validation status](validation-plan.md); core physical acceptance has since been exercised on the device.
