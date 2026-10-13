# Testing setup and desktop behavior

Tests run independently of device setup. Host checks use isolated commands or mapper frames. VM checks exercise the installed system through guest SSH and real keyboard/controller events. All runtime images, credentials, reports and screenshots remain under ignored `.local/`.

Firefox-first browser preferences were applied on the WIN Mini: `xdg-settings get default-web-browser` and `xdg-mime query default` for HTTP, HTTPS, HTML and XHTML all resolve to `firefox_firefox.desktop`. Chromium remains the fallback. An isolated execution of the setup's preference-seeding block verified repeat installation and retention of explicit browser choices and unrelated file associations; setup staging and `git diff --check` passed.

## Host checks

On 2026-10-13, faster wheel scrolling was configured for Claude Code 2.1.287 and Cursor Agent 2026.10.01. Claude's supported `env.CLAUDE_CODE_SCROLL_SPEED = "3"` was merged locally and added as a setup default, preserving existing personal multipliers on reruns. Cursor uses normal terminal history; Foot's scrollback multiplier was raised from its implicit default 3.0 to 9.0 locally and in the fresh-setup template. Foot 1.16.2 configuration validation passed for both files. The coding-CLI and setup-layout checks passed, including retained unrelated environment settings and personal speed overrides. Ubuntu's Foot source confirms the multiplier applies to the normal buffer; alternate-screen apps reporting mouse events retain their own speed. No live CLI session was restarted and physical scrolling comfort remains unconfirmed. [Private settings report](../.local/device-checks/cli-scroll-result.json).

On 2026-10-13, CLI provisioning gained user-level commit/PR attribution preferences for Claude Code and Cursor Agent, applied on fresh setup and reruns. Isolated checks passed fresh config creation, preservation of unrelated model/plugin/permission settings and unknown attribution keys, user ownership, unchanged matching reruns, invalid-file refusal and read-only preflight. On the WIN Mini, Claude already had empty commit/PR attribution; Cursor's two enabled switches were disabled. A local backup was saved and JSON comparisons confirmed all unrelated settings survived; a second application left both files unchanged. No model request, commit or PR was generated for verification. [Private settings report](../.local/device-checks/attribution-defaults-result.json).

On 2026-10-13, the WIN Mini lacked `pipewire-alsa`, leaving plain ALSA clients without default-device routing through PipeWire. Installing that package fixed normal-user capture: `arecord -D default -d 1 -f S16_LE -r 16000 /dev/null` returned zero without ALSA errors, without restarting services or rebooting. The desktop package list now includes it. Setup-layout and diff checks passed. This verifies device opening and capture; voice-mode behavior in individual applications has not been retested. [Private capture report](../.local/device-checks/pipewire-alsa-result.json).

The sensor firmware check uses isolated targets to verify model matching, pinned download URLs, checksum refusal before installation, retention of existing plain/compressed firmware and installation of the accompanying license. It does not probe host hardware. Normal setup enables the sensor driver but leaves gyro input mapping and automatic rotation unconfigured.

Run from the repository root:

```bash
python3 tests/check-setup-layout.py
python3 tests/check-microphone-defaults.py
python3 tests/check-sensor-firmware.py
python3 tests/check-network-picker.py
python3 tests/check-browser-download-mode.py
python3 tests/check-chord-recognizer.py
python3 tests/check-status-bar.py
python3 tests/check-idle-policy.py
python3 tests/check-install-plan.py
python3 tests/check-install-launch.py
python3 tests/check-proxy.py
python3 tests/check-proxy-bypass.py
python3 tests/check-proxy-selection.py
python3 tests/check-hhd-artifacts.py
python3 tests/check-coding-clis.py
python3 tests/check-development.py
```

The microphone-default check covers WIN Mini model matching, the tested 10% input level, user ownership, fresh state creation, merging other routes and retaining saved levels byte-for-byte on reruns. It changes no host audio settings. The format follows [WirePlumber 0.4's per-route volume storage](https://github.com/PipeWire/wireplumber/blob/0.4.17/src/scripts/policy-device-routes.lua).

The Wi-Fi picker check uses fake NetworkManager objects to check AP grouping, literal SSID handling, saved-profile reuse, new-connection delegation to the secret agent and enterprise-profile handling. It never changes host connections. The browser-download check covers independent Firefox/Chromium retention, complete cached dependencies, local artifact transport and rejection of damaged Chromium files before installation. Live new-network authentication still needs an actual network/password test.

The setup check verifies the root entry point, source staging and coordinator paths without installing packages. The browser check isolates Snap command selection and existing-browser retention. The chord check feeds independent Xbox face codes through all 27 named shortcuts in 196 face-first press/release orders, and checks unlimited face-prefix holds, terminal-only Ctrl+C/Z/D with complete A+B prefixes, suppression of wrong-order and simultaneous inputs, immediate D-pad arrows with hold acceleration, polling-rate consistency, direction changes, neutral stop and bounded repeats after scheduling gaps, immediate Backspace holds, fixed versus trigger-modified shortcuts, terminal guards, invalid/rolling gestures, selection/neutral transitions, persistent legend capture, profile validation, lifecycle cleanup and held-arrow compatibility with shortcuts disabled. Stick-context checks cover Window startup/reset, both-stick neutral switching, focused-window wheel targeting, full 120-unit detents and legacy equivalents, batch magnitude, direction/speed, ordered modifier frames, modifier suppression/restoration, failure handling, simultaneous scrolling/selection, plain arrows, all Shift/Ctrl trigger combinations in all four directions, changing modifiers during continuous movement, the earlier profile action alias, speed by deflection, consistency across polling rates, slower vertical movement, single-step nudges, neutral stop, reversal, immediate slowdown and bounded repeats after scheduling gaps. It creates no host input device and reads Linux key codes from `/usr/include/linux/input-event-codes.h`.

The status bar check uses battery/hwmon fixtures and isolated command/API providers to check signal/network details, volume/mute, proxy service states, keyboard layout selection, power targets and safe click notifications. It checks HHD authentication, bounded read-only requests and failures, sensor units/labels, preferred channels, duplicate aliases, invalid/faulted/disabled sensors, live updates, disappearance and recovery. It does not query or change host hardware or services.

The HHD artifact check refuses corrupted downloads and altered cache entries, checks temporary-file cleanup, and verifies that matching cached releases need no network access. It also checks module-loading and enrollment decisions with isolated command responses: working modules, disabled Secure Boot, mismatched certificates, enrolled/pending keys, unattended instructions and interactive import success/failure. It changes no host modules or EFI variables. The setup-layout check includes default HHD installation, its read-only preflight and all component source hashes. Actual power controls require the [on-device checks](validation-plan.md#on-device-backlog).

The coding CLI check verifies that installers and initial version checks drop root privileges, use the selected user's home and groups, and exclude root credentials/settings from their environment. It also checks that existing commands are retained without execution, failed downloads are cleaned up before shell execution, missing installed commands fail setup, interactive Bash sets PATH without duplication and preflight is read-only. Bubblewrap checks cover ordinary provisioning dependencies, initial AppArmor profile installation, preservation and reloading on reruns, inactive AppArmor, missing packaged profiles and load failures; these use isolated files and mocked parser calls. The setup-layout check includes these tools in ordinary provisioning and source staging. These checks do not download releases or start model sessions.

The development check verifies user privilege/environment isolation, immediate latest-version installation for missing defaults, retention of selected mise/Rust/Python versions, refusal of conflicting Docker runtimes/repositories and read-only preflight. It downloads no runtimes and changes no host services.

The proxy selection check verifies selection by number, exact name, unique case-insensitive substring or prompt, ambiguous-match refusal, automatic selection, default restart/save-only behavior, private configuration and preservation on invalid choices or failed validation. It checks HTTPS status/timeout handling, latency ordering with original selection numbers, the unchecked `list --all` mode, uplink selection with an active TUN and unchanged selections during list checks. With `python3 tests/check-proxy-selection.py --mihomo /PATH/TO/NATIVE/MIHOMO`, it also exercises the real engine against synthetic URI/base64/VMess subscriptions. It checks exact Unicode/emoji/punctuation matching, rejection when a pinned node disappears and temporary-process cleanup. The native check uses OpenSSL to generate a temporary trusted test certificate, local HTTPS/CONNECT servers and private Unix sockets to verify successful HTTPS, stalled/unreachable connections, unsuccessful HTTP responses and rejection of an untrusted destination certificate. It needs no subscription account, external network, routes or system services; service restart calls are mocked.

The idle policy check verifies lid-close suspend on every power source and uses power-supply fixtures and isolated processes to verify charger detection, removal and restoration of battery timers, display wake on AC, child cleanup and unexpected exit handling. It covers Keep awake across charger changes, restoration of battery timers, runtime-state toggles, display-off without locking, and refusal to blank when the wake listener cannot be signaled. It feeds ordinary repeats and up to 100 repeated firmware macros through the rear-button reader, verifies one action after release, separate subsequent taps, and the display-wake action for L4. It checks rear-device key consumption and unchanged Super+L/power-button policy. The status check covers the Keep awake indicator, click action and live refresh. These checks change no host settings. Physical rear-button, lid and idle behavior still require the device checklist.

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

On 2026-10-11, normal setup gained mise-managed Go, Node/npm, pnpm, TypeScript and supporting tools; rustup stable with its development components; uv-managed current CPython and Ruff; and Docker CE/Buildx/Compose from Docker's signed repository. Host checks passed target-user isolation, partial-download refusal, immediate latest installs, stable CPython selection excluding prereleases/free-threaded variants, retained defaults, repository/runtime conflict refusal, read-only preflight, source staging and syntax.

A disposable native ARM64 Ubuntu 24.04 container installed all requested tools from upstream. Real Go, Rust and TypeScript compile/run checks passed, along with pnpm scripts, uv isolated dependency installation, pytest, Ruff, Pyright and a CMake/Ninja C++ build. Ubuntu's system Python remained 3.12. Automatic Node switching between global current and project Node 24 passed both plain interactive Bash and the actual Minion Bash/ble.sh/Atuin integration in a PTY. A newly populated mise config installed both runtime/tool batches successfully. Rerunning retained a deliberately selected Node 24 global default, custom Rust default, Python executable link, mise configuration, Docker configuration and daemon PID. A home Python pin also retained the user's selection while the newest stable interpreter remained installed. [Private development report](../.local/development-qa/report.json), [rerun report](../.local/development-qa/rerun-report.json).

Docker Compose built a local image from the Go executable, ran it successfully without sudo as the selected user, and removed its service/network/image. Nested overlay mounts failed in this Podman environment; this check used a **QA-only vfs/legacy image-store configuration**, with no production Docker configuration override. These component tests ran on ARM64, not the handheld's amd64 hardware. Full desktop setup, native amd64 toolchains and Docker's default storage/network behavior on the WIN Mini still require a device check.

On 2026-10-11, ordinary setup gained the official native Codex, Claude Code and Cursor Agent installers for the selected user, with Bash PATH integration and retention of existing executables without launching them. Host CLI isolation/failure/PATH checks, setup-layout checks and syntax checks passed. In Ubuntu 24.04 amd64 under QEMU, Codex 0.162.1 and Cursor Agent 2026.10.01-e373342 passed installation, unprivileged version/help commands, ownership, unchanged binaries/settings on rerun without download connectivity, and execution with the checkout unavailable. The test caught Cursor rewriting settings during `--version`; setup now skips execution of retained commands. [Private amd64 report](../.local/cli-qa/amd64-report.json).

Codex and Claude test payloads were cached after comparison with published SHA-256 checksums to avoid this environment's download rate limits; Cursor downloaded through its normal installer. Claude's bundled Bun runtime aborted with `MemoryExhaustion` under x86 user emulation. Its verified 2.1.287 ARM64 binary passed version/help checks in native Ubuntu Linux, but its upstream installer remained blocked by the test network's MITM certificate validation. No certificate bypass or test relay is included in device setup. Claude's complete amd64 installation, account sign-in, authenticated model sessions and all three tools' sandbox behavior remain device checks. [Private native report](../.local/cli-qa/native-report.json).

On 2026-10-11, the bar gained an authenticated read-only HHD target display and conditional CPU/control, GPU, NVMe and battery temperature summaries, with a full sensor notification and an HHD launcher action. The status-bar suite passed target versus quick-slider precedence, unavailable/unready controls, API authentication/bounded responses/timeouts, Celsius conversion, preferred channel selection, duplicate aliases, invalid/faulted/disabled sensors, safe clicks and live sensor/API loss and recovery. Setup-layout and syntax checks passed. These isolated tests do not establish which sensors the WIN Mini exports, physical readback accuracy, bar fit at 2× scaling, native UI launch or suspend behavior; those checks are queued for the device.

On 2026-10-11, default setup gained HHD 4.1.12 and HHD UI 3.4.2 with verified release downloads, Ubuntu-managed Python dependencies and a power-only boot service. An amd64 Ubuntu 24.04 container with synthetic WIN Mini `G1617-01` DMI passed real package installation, ACPI DKMS compilation against the current HWE headers, Python dependency checks, UI library resolution and sandbox-helper permissions, authenticated localhost API access, provider filtering, disabled initial TDP/energy overrides, retained settings and an uninterrupted rerun. Boot with the checkout unavailable retained settings and kept overrides disabled. The test caught and corrected a separate upstream one-shot TDP-enable action default. [Private HHD report](../.local/hhd-qa/installed-report.json).

Host setup-layout, artifact refusal/cache and syntax checks passed. Electron's sandbox failed to launch under Mac-hosted x86 QEMU user emulation with `clone: Invalid argument`; native Wayland UI operation remains unverified. The container has no physical AMD power/GPU/fan hardware and cannot establish Secure Boot module acceptance. These checks do not replace the [queued handheld tests](validation-plan.md#on-device-backlog), and a complete desktop provisioning run has not been repeated for this addition.

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

These records describe the sources installed at the time of each run. The reorganized setup source tree and simplified manual-install launcher have host checks; a fresh complete desktop setup run has not been repeated after restructuring. Fresh Snap Store installation, a different-kernel update, screen sharing and physical hardware acceptance remain in the [validation plan](validation-plan.md).
