# Testing setup and desktop behavior

Tests run independently of device setup. Host checks use isolated commands or
mapper frames; VM checks exercise an installed disposable system through SSH
and real keyboard/controller events. Runtime images, credentials, reports and
screenshots stay under ignored `.local/`.

Read [validation status](validation-plan.md) for completed and deferred checks,
[test history](testing-history.md) for dated evidence, and the
[agent handoff](agent-handoff.md) for the active development state. Historical
results do not certify the current source revision.

Use `/usr/bin/python3` on the device: another `python3` on PATH may lack the
Ubuntu packages used by these checks. Run the checks relevant to your change;
the list below is not a request to run the entire suite on the live device.

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
python3 tests/check-reaper-dialog-focus.py
python3 tests/check-reaper-hierarchy.py
python3 tests/check-reaper-fx-ui.py
python3 tests/check-reaper-windows.py
python3 tests/check-realearn.py
python3 tests/check-midi-routing.py
python3 tests/check-audio-tooling.py
python3 tests/check-audio-effects.py
```

For slider changes, run the chord-recognizer, MIDI-routing, ReaLearn, hierarchy
and FX-widget checks. Together they cover axis/neutral gating, hold acceleration,
continuous speed CCs, preset persistence, fine precision and alternating native
fine/normal edits. These fixtures do not replace a live plugin check.

For a physical retest, use a disposable project with a muted track and ReaVerb.
Select Width and verify left/right movement; select Wet and verify up/down.
For each, nudge normally, hold R2 and nudge, release R2, then nudge normally again.
Repeat several times: neither direction nor mode should stop responding. Check
that the fine value advances by one displayed unit and stays when centered;
normal hold should accelerate after 0.2 s and reach full speed at 1 s. Keep R2
held until the fine gesture has settled when measuring its exact step. Repeat on
an unautomated numeric slider and a plugin exposing explicit step metadata when
changing either path. Use the isolated-display workflow in
[the handoff](agent-handoff.md#testing-without-disturbing-the-user) for automation;
never drive these checks into the user's working project.

The REAPER dialog-focus check covers foreground window identity, stale/missing
samples, profile gating, clipping and independence from the paused Lua state.
For a live check after installing the controller, open Add FX in REAPER mode:
the cyan border should follow the filter, lists and buttons with the left stick
or L1/R1. The D-pad moves the native selection within a list. Also open a tempo
or time-signature value editor and move between its fields; the border must
keep updating while that modal dialog is open. Leaving REAPER or switching to
Desktop mode must hide it, and closing the dialog must restore normal controls.

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

See [test history](testing-history.md) for the preserved device/VM reports and
[validation status](validation-plan.md#remaining-checks) for remaining coverage.
