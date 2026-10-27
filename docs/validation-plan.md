# Validation status

Current device status as of **2026-10-27** for the **GPD WIN Mini 2023 / Ryzen 7 7840U**. The installed system is in everyday use. This summary supersedes the earlier pre-device backlog; dated experiments and their limits remain in [test history](testing-history.md). The [device checklist](device-checklist.md) is a reusable checklist for another installation and deliberately stays unchecked.

## Completed on this device

| Area | Observed result |
| --- | --- |
| Boot and access | Installed Ubuntu boots and unlocks; password-authenticated login, locking and suspend/wake were exercised. Additional reboot cycles were deferred at the user's request. |
| Touch and display | Explicit touchscreen-to-eDP-1 mapping fixed missed taps. Center/four-corner taps passed, including after reboot. Desktop scaling, brightness and everyday keyboard/touchpad use were accepted. |
| Power backend | HHD starts and its UI works. The existing DKMS signing key was enrolled with Secure Boot enabled; `acpi_call` loaded. Power targets were exercised on AC and battery. |
| Cooling/background work | A 12-minute CPU workload continued on battery with Keep awake enabled and the panel truly off. Cooling remained stable, CPU peaked at 52.5°C, and the fan responded. Separate OpenGL load also passed. |
| Low-battery protection | UPower is enabled with 20% low / 10% critical / 5% clean-shutdown policy. The session warning service is active; isolated D-Bus escalation and charger reset passed. A real low-battery shutdown has not been tested. |
| GPU and sensors | Hardware-accelerated OpenGL completed the full glmark2 suite with no observed corruption or recorded GPU errors. RADV enumerates the GPU. Missing BMI260 firmware was supplied and all six sensor channels changed. |
| Audio and Bluetooth | Speakers and volume/mute were accepted. Reducing internal-mic capture/boost to 0 dB fixed audible distortion; plain ALSA capture works through PipeWire. soundcore AeroClip paired and the user confirmed it worked. Local English/Russian Voxtype dictation was also accepted; R4 tap/hold activation and cancellation were accepted. |
| Controller | Current defaults combine left-stick scrolling and right-stick window selection; L3/R3 switch independently. Held Space/Backspace/D-pad, face-first chords, terminal signals, workspace compaction/wraparound and the Menu legend have isolated and live checks. Physical diagonal/edge cases are not exhaustively certified. |
| Display/idle controls | The user accepted sticky Fn+F3 blanking, Awake lid-close without sleep/lock, and Select picker toggling. Built-in keyboard suppression passed live readback; a real closed-lid check confirmed the gamepad stayed grabbed and not ready. Full input recovery/edge cases remain separate checks. R4 dictation and cancellation were accepted. |
| Network and browsers | Wi-Fi chooser and Chromium were accepted; Chromium headless/WebDriver checks passed with its sandbox. Firefox is the default browser. Proxy dashboard, connectivity and Russian direct-routing rules were checked. |
| Coding and navigation | Codex sandbox execution was repaired. CLI attribution preferences and scroll defaults are configured. Neovim navigation was checked across 17 file types and 11 language servers, including cross-file TypeScript and multiple-definition picking. |
| Audio development | A native JUCE VST3 synth compiled, loaded in SuperCollider, received MIDI/parameter changes and produced a valid recording. LSP, Dragonfly, BYOD and AIDA-X provide 184 discovered VST3 effects; nine selected effects passed generated-audio recording. |
| REAPER | Installation/rerun checks passed. Gamepad editing, spatial Mixer controls and rotary knobs received user feedback and iterative fixes. Private live tests cover native FX controls (including ReaPitch), BYOD/AIDA-X generic parameters, full-size tabs and window ownership. Visible tab order and direct FX-chain arrow navigation have regression checks and are installed; physical acceptance of the latest changes is pending. External-interface latency remains untested. |
| Blender | Blender 5.2.2 LTS launched on the Radeon 780M OpenGL viewport; the Python API, a small Cycles CPU render and project save/reopen passed. GPU compute rendering remains untested. |
| Additional desktop apps | Telegram 7.3.1 launched; GIMP 3.2.6 opened a generated PNG; qBittorrent 4.6.3 launched natively on Wayland with torrent/magnet handlers registered. Account messaging and torrent transfers were not exercised. |
| Recent desktop fixes | Minsk timezone/NTP and 4500K night colors passed; the user accepted the warm palette. Noto fallbacks fixed missing characters. Start/Super+Enter inherit the focused Foot shell directory; native focus behavior is unchanged. |
| Swap | An 8 GiB private swapfile is active on encrypted root and configured for boot. A bounded cgroup test forced real swap use and passed readback; a setup rerun preserved the file and boot configuration. |
| Authentication caching | Sudo authentication carries across terminals for 15 minutes. Ubuntu's packaged OpenSSH agent runs with a one-hour timeout; live disposable-key signing passed after migration. Real Git reuse and isolated expiry passed before migration. Logout/login remains deferred. |

See [test history](testing-history.md) for measurements, source revisions and links to private evidence. A successful observation applies to that workload and configuration, rather than every possible application or hardware state.

## Remaining checks

These are verification gaps, not known blockers to ordinary use:

- **REAPER latest changes:** physically retest visible tab-order cycling, generic parameter selection/adjustment and direct FX-chain Up/Down navigation. Private live checks use synthetic mapper input and do not establish comfort. Custom-painted plugin operations without exposed automation remain touch/touchpad workflows.
- **Closed-lid input recovery:** confirm held-control release/neutral recovery on the physical device in Desktop and passthrough modes; the closed-state readback passed.
- **Fresh installation and rerun:** run the current complete source-only setup in a clean Ubuntu Server VM, then rerun with edited personal settings. Component/staging checks and live device updates have passed, but the full latest setup has not been repeated end to end.
- **Current controller VM suite:** rerun the full synthetic gamepad suite with the current mapping. Host gesture tests and selected live Sway/Foot/browser probes passed; earlier full VM results use older layouts.
- **Maintenance:** after the next kernel update, verify boot/unlock, module signing/loading, essential services and suspend. Test retained Windows boot if it is part of the intended workflow. This is queued for maintenance rather than another immediate reboot cycle.
- **Network edge cases:** actual connection to a new password-protected Wi-Fi network, hidden/enterprise networks and Bluetooth automatic reconnection after sleep/reboot remain separate checks. Pairing and normal connectivity already passed.
- **Optional workflows:** screen sharing/portal chooser, external display/dock/storage/card reader and Vulkan rendering remain untested. A short generated H.264 MP4 passed VA-API hardware decoding and GPU playback in mpv; other codecs and sustained video playback remain separate checks. Test them when needed.
- **Guitar input:** the USB audio interface was unavailable. Verify its routing, input gain, live effects and latency when connected; generated-audio VST3 processing already passed. Realtime-priority fallback in the host/modeler logs needs evaluation during that latency check.
- **Specific refinements:** lock-screen language switching, sensor calibration/resume and real-project LSP edge cases are not exhaustively tested. Confirm the SSH agent lifecycle at the next planned logout/login; live key reuse already passed. Transient wrong-color graphics flicker has also been reported in the browser. At 60 Hz, the user reports nearly no occurrences, with occasional recurrence; this appears to mitigate the symptom, but no root cause is established.
- **Memory pressure:** observe sustained real workloads and confirm swap activation at the next planned boot. The bounded read/write check passed; the earlier Firefox out-of-memory exit motivates continued observation.
- **Low-battery policy:** real warning visibility during discharge, charger cancellation of a pending power action and a deliberate saved-work shutdown remain untested. Policy readback, active services and simulated warning transitions passed.

## Deliberate choices

- With Keep awake off, lid close locks and suspends on either power source. With it on, lid close blanks the panel and blocks built-in keyboard/gamepad input while work continues. Manual Fn+F3 blanking requires Fn+F3 to restore; ordinary input does not wake it. See [desktop controls](post-install-setup.md#desktop-controls). Hibernation/Secure Boot changes were declined; explicitly shut down before transport when suspend is unsuitable. Adding swap does not enable hibernation.
- Power-button behavior is unchanged. Keep awake/display-only controls use Fn+F4/F3. Fn+F5 switches 60/120 Hz and remembers the rate. R4 controls dictation; L4 and Fn+F6 are unassigned.
- Firmware cooling remains automatic. Custom fan curves and gyro input/automatic rotation are optional features.
- Additional reboot cycles and low-priority peripheral tests were deferred by the user.

## Reproducing results

For another installation, use the [installation instructions](install.md), [source setup](post-install-setup.md) and [device checklist](device-checklist.md). Record device identity, firmware/kernel, tested Git revision and reproduction steps privately under `.local/`; do not commit credentials, subscriptions or API tokens. Back up project data and recovery information separately: setup's configuration archives are not full-system or user-data backups.
