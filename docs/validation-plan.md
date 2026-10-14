# Validation status

Current device status as of **2026-10-14** for the **GPD WIN Mini 2023 / Ryzen 7 7840U**. The installed system is in everyday use. This summary supersedes the earlier pre-device backlog; dated experiments and their limits remain in [testing](testing.md). The [device checklist](device-checklist.md) is a reusable checklist for another installation and deliberately stays unchecked.

## Completed on this device

| Area | Observed result |
| --- | --- |
| Boot and access | Installed Ubuntu boots and unlocks; password-authenticated login, locking and suspend/wake were exercised. Additional reboot cycles were deferred at the user's request. |
| Touch and display | Explicit touchscreen-to-eDP-1 mapping fixed missed taps. Center/four-corner taps passed, including after reboot. Desktop scaling, brightness and everyday keyboard/touchpad use were accepted. |
| Power backend | HHD starts and its UI works. The existing DKMS signing key was enrolled with Secure Boot enabled; `acpi_call` loaded. Power targets were exercised on AC and battery. |
| Cooling/background work | A 12-minute CPU workload continued on battery with Keep awake enabled and the panel truly off. Cooling remained stable, CPU peaked at 52.5°C, and the fan responded. Separate OpenGL load also passed. |
| GPU and sensors | Hardware-accelerated OpenGL completed the full glmark2 suite with no observed corruption or recorded GPU errors. RADV enumerates the GPU. Missing BMI260 firmware was supplied and all six sensor channels changed. |
| Audio and Bluetooth | Speakers and volume/mute were accepted. Reducing internal-mic capture/boost to 0 dB fixed audible distortion; plain ALSA capture works through PipeWire. soundcore AeroClip paired and the user confirmed it worked. |
| Controller | Current defaults combine left-stick scrolling and right-stick window selection; L3/R3 switch independently. Held Space/Backspace/D-pad, face-first chords, terminal signals, workspace compaction/wraparound and the Menu legend have isolated and live checks. Physical diagonal/edge cases are not exhaustively certified. |
| Display/idle controls | L4 display-off/on and once-per-hold R4 Keep awake were physically accepted. Routine notifications expire. AC idle behavior and lid-close lock/suspend were exercised. |
| Network and browsers | Wi-Fi chooser and Chromium were accepted; Chromium headless/WebDriver checks passed with its sandbox. Firefox is the default browser. Proxy dashboard, connectivity and Russian direct-routing rules were checked. |
| Coding and navigation | Codex sandbox execution was repaired. CLI attribution preferences and scroll defaults are configured. Neovim navigation was checked across 17 file types and 11 language servers, including cross-file TypeScript and multiple-definition picking. |
| Audio development | A native JUCE VST3 synth compiled, loaded in SuperCollider, received MIDI/parameter changes and produced a valid recording. LSP, Dragonfly, BYOD and AIDA-X provide 184 discovered VST3 effects; nine selected effects passed generated-audio recording. |
| Blender | Blender 5.2.2 LTS launched on the Radeon 780M OpenGL viewport; the Python API, a small Cycles CPU render and project save/reopen passed. GPU compute rendering remains untested. |
| Recent desktop fixes | Minsk timezone/NTP and 4500K night colors passed; the user accepted the warm palette. Noto fallbacks fixed missing characters. Start/Super+Enter inherit the focused Foot shell directory; native focus behavior is unchanged. |
| Swap | An 8 GiB private swapfile is active on encrypted root and configured for boot. A bounded cgroup test forced real swap use and passed readback; a setup rerun preserved the file and boot configuration. |
| Authentication caching | Sudo authentication carries across terminals for 15 minutes. One shared SSH agent caches keys for an hour; a second real Git query passed without a prompt, and automatic key expiry passed in an isolated probe. |

See [testing](testing.md) for measurements, source revisions and links to private evidence. A successful observation applies to that workload and configuration, rather than every possible application or hardware state.

## Remaining checks

These are verification gaps, not known blockers to ordinary use:

- **Fresh installation and rerun:** run the current complete source-only setup in a clean Ubuntu Server VM, then rerun with edited personal settings. Component/staging checks and live device updates have passed, but the full latest setup has not been repeated end to end.
- **Current controller VM suite:** rerun the full synthetic gamepad suite with the current mapping. Host gesture tests and selected live Sway/Foot/browser probes passed; earlier full VM results use older layouts.
- **Maintenance:** after the next kernel update, verify boot/unlock, module signing/loading, essential services and suspend. Test retained Windows boot if it is part of the intended workflow. This is queued for maintenance rather than another immediate reboot cycle.
- **Network edge cases:** actual connection to a new password-protected Wi-Fi network, hidden/enterprise networks and Bluetooth automatic reconnection after sleep/reboot remain separate checks. Pairing and normal connectivity already passed.
- **Optional workflows:** screen sharing/portal chooser, external display/dock/storage/card reader, Vulkan rendering and hardware video decoding remain untested. Test them when needed.
- **Guitar input:** the USB audio interface was unavailable. Verify its routing, input gain, live effects and latency when connected; generated-audio VST3 processing already passed. Realtime-priority fallback in the host/modeler logs needs evaluation during that latency check.
- **Specific refinements:** lock-screen language switching, sensor calibration/resume and real-project LSP edge cases are not exhaustively tested. Confirm the SSH agent lifecycle at the next planned logout/login; live key reuse already passed. The intermittent Codex-only terminal redraw stripe was set aside after it stopped reproducing.
- **Memory pressure:** observe sustained real workloads and confirm swap activation at the next planned boot. The bounded read/write check passed; the earlier Firefox out-of-memory exit motivates continued observation.

## Deliberate choices

- Lid close still locks and suspends on either power source. Hibernation/Secure Boot changes were declined; explicitly shut down before transport when suspend is unsuitable. Adding swap does not enable hibernation.
- Power-button behavior is unchanged. Keep awake/display-only controls use R4/L4.
- Firmware cooling remains automatic. Custom fan curves and gyro input/automatic rotation are optional features.
- Additional reboot cycles and low-priority peripheral tests were deferred by the user.

## Reproducing results

For another installation, use the [installation instructions](install.md), [source setup](post-install-setup.md) and [device checklist](device-checklist.md). Record device identity, firmware/kernel, tested Git revision and reproduction steps privately under `.local/`; do not commit credentials, subscriptions or API tokens. Back up project data and recovery information separately: setup's configuration archives are not full-system or user-data backups.
