# Testing setup and desktop behavior

Tests run independently of device setup. Host checks use isolated commands or mapper frames. VM checks exercise the installed system through guest SSH and real keyboard/controller events. All runtime images, credentials, reports and screenshots remain under ignored `.local/`.

## Host checks

Run from the repository root:

```bash
python3 tests/check-setup-layout.py
python3 tests/check-browser-download-mode.py
python3 tests/check-chord-recognizer.py
python3 tests/check-install-plan.py
python3 tests/check-install-launch.py
```

The setup check verifies the root entry point, source staging and coordinator paths without installing packages. The browser check isolates Snap command selection and existing-browser retention. The chord check feeds independent Xbox face codes through all 960 press/release orders, both normally and with one-shot Super, and checks late Shift/Ctrl combinations, release-only arming, cancellation, single-use behavior, modifier ordering, invalid/reserved/rolling gestures, lifecycle cleanup and held-arrow compatibility. It creates no host input device and reads Linux key codes from `/usr/include/linux/input-event-codes.h`.

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

Preparation creates a blank 80 GiB virtual disk, private firmware variables, an SSH key and `credentials.json`. Read that private file locally and use its account password and disk passphrase during manual Ubuntu installation. Set the hostname to `ubuntu-mini-vm`, the account to `vmuser`, choose encryption, and install OpenSSH. Use the local archive mirror URL from [mirror instructions](local-mirror.md). The launcher supplies no Autoinstall configuration and does not choose partitions.

After installation, boot without the ISO using `launch ... boot --window`. In the guest, add the host fixture's `ssh-key.pub` contents to `/home/vmuser/.ssh/authorized_keys`; set the directory to mode 700 and the file to 600. Use `tests/vm.py ssh "$VM_DIR" vmuser 'true'` to verify access. Guest SSH uses a loopback port recorded in `state.json`.

Cold-boot tests require disk unlock and login prompts on the serial console. Inside this test VM, add:

```bash
sudo mkdir -p /etc/default/grub.d
sudo tee /etc/default/grub.d/99-ubuntu-mini-vm.cfg >/dev/null <<'CONFIG'
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
sudo tee /etc/mini-os/vm-environment >/dev/null <<'CONFIG'
export WLR_RENDERER=pixman
export WLR_NO_HARDWARE_CURSORS=1
CONFIG
mkdir -p ~/.config/sway
cat > ~/.config/sway/mini-os.conf <<'CONFIG'
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

The synthetic controller is created inside the guest. Mapping tests exercise real Firefox input, all assigned chords with normal/Shift output, constituent suppression, late modifiers, Sway focus/move/resize/workspaces, picker/launcher, passthrough, reconnect, lock, inactive-console and restart behavior. The test removes its controller and HTTP service afterward. Physical trigger axes, adjacent presses and comfort remain device checks.

## Recorded results and current limits

On 2026-10-09, L3 was changed to arm/cancel one-shot Super. Host checks passed all 960 chord press/release orders both normally and with Super, all 48 late Shift/Ctrl combinations with Super, single-key shortcuts, modifier ordering, cancellation, pending-state cleanup across disconnect/lock/inactive-session/passthrough/reset, and held-arrow compatibility when chords are disabled. The setup-layout check passed. The VM harness now checks actual Super+Enter, Super+F, Super+D and Super+Shift+Q shortcuts, but has not been rerun for this change; physical L3 comfort and shortcut dispatch need device QA.

On 2026-10-09, physical WIN Mini QA reported that Y produced Backspace, X produced Tab, and Y+B/X+A produced nothing. Feeding Xbox/xpad event codes into the mapper reproduced all four symptoms. The X/Y translation and single-button defaults were corrected. The host chord checker now feeds independent Xbox face codes rather than deriving input from the mapper's own configuration; it failed on the previous source and passed after the correction, including all four single actions, 960 chord press/release orders and 48 late-modifier cases. The setup-layout check also passed. The browser VM harness was corrected to use the same driver codes, but has not been rerun; the device still needs a retest after applying the updated setup.

On 2026-10-09, physical-device QA reported tiny desktop elements and a permission error from `brightnessctl -c backlight set +5%`. The desktop defaults now use 2× scaling, explicitly install Ubuntu's `brightness-udev` rules, add the selected account to `video`, and include playback/Print Screen bindings. Ubuntu Sway 1.9 accepted the full configuration; an isolated headless session confirmed a 960×540 logical workspace at 1920×1080/2× and a 1280×720 workspace with a 1.5× override. Isolated provisioning verified account selection, package selection, group setup, backlight-rule refresh and deferred activation; the existing setup-layout check passed. [Private scaling report](../.local/desktop-qa/scaling-report.json). These checks do not verify physical backlight writes, Fn key codes, audio/media playback or comfort on the device; retest those after updating and logging in again. No full desktop VM setup run was repeated for this patch.

On 2026-10-09, the observable helper passed a complete 20 GiB installation launched through the actual live Ctrl+Alt+F2 console. It automatically switched to the dedicated F3 progress viewer, ran the handoff in an independent service, and installed helper SHA-256 `4d7933e44515b6efd49fcf0da07a391850231bffc85abcda56b0fd0040a3afac`. Ctrl+C closed both the dedicated viewer and original console viewer without stopping installation; `--follow` reopened progress. Cancellation still left disk and configuration unchanged. The run required no installer diagnostic intervention and rebooted automatically.

Cold boot without the ISO passed wrong-passphrase rejection, correct unlock, Secure Boot and integrity lockdown, account access, the new ESP/default firmware entry, unchanged original GPT entries and whole-partition hashes, and absence of plaintext credentials in installed logs. Ctrl+Alt+F1 was needed to reveal the text unlock prompt in this VM. The final run served 155 requests and approximately 291 MB from the package cache, with zero upstream mirror downloads. [Observable installation summary](../.local/vm/observable-install-summary.json), [current console installation](../.local/vm/storage-install-nkpl8nsn/install-report.json).

On 2026-10-08, the live-USB helper passed complete automatic installations with a 20 GiB explicit allocation and a 42.89 GiB maximum-space allocation. A reinstall passed after explicitly reclaiming only the previous Ubuntu partitions. The final maximum-space run used real terminal credential prompts and `INSTALL` confirmation, with cancellation tested first. It required no diagnostic intervention and installed helper SHA-256 `15b9053725debbd04fe53d4f31208d3e68d16713b665854c89eb850199432117`. The explicit-size run used the preceding revision; the subsequent helper change corrected terminal input handling.

Both installed systems passed cold boot without the ISO, wrong-passphrase rejection, successful unlock, Secure Boot, account access, Ubuntu's new ESP/default firmware entry, unchanged original GPT entries and whole-partition hashes, and absence of plaintext credentials in installer logs/cloud configuration. The final interactive run also confirmed kernel lockdown in integrity mode. Package downloads used the local mirror; the final run served its requests from cache. The fixtures contain synthetic partitions, so Windows boot and BitLocker recovery remain physical-device checks. [Installation summary](../.local/vm/install-summary.json), [20 GiB reinstall](../.local/vm/storage-install-dtuowdxy/install-report.json), [2026-10-08 interactive installation](../.local/vm/storage-install-nkpl8nsn/2026-10-08-interactive-report.json).

Previous standalone setup runs passed clean Server provisioning, reruns, personal-setting preservation, configuration backups, unchanged GPT geometry, cold boot, graphical login, desktop services, shell editing/local history and real signed Firefox installation through the cache. The source-clone rerun passed real upstream shell downloads while retaining an existing browser. [Standalone summary](../.local/vm/post-install-setup-summary.json), [source-clone report](../.local/vm/storage-desktop-69unztc4/source-setup-report.json).

Signed boot and kernel lockdown passed before/after maintenance; earlier experiments also observed rejection of unsigned EFI code and a signature-stripped kernel. Maintenance retained the same kernel version. Earlier automated installation/storage experiments were removed from the source tree; the current standalone helper was tested separately as described above. [Signed boot report](../.local/vm/storage-desktop-zm9c2afx/secure-boot-boot-report.json).

The retained chord VM passed 25 acceptance groups and 96 character cases covering 95 printable ASCII characters. Its layout predates the current frequency-based assignments. The current layout passed the host frame checker; its revised assignments still need a fresh VM run. [Gamepad acceptance summary](../.local/vm/gamepad-chords-summary.json), [mapping report](../.local/vm/storage-desktop-zm9c2afx/gamepad-mapping-report.json).

These records describe the sources installed at the time of each run. The reorganized setup source tree and simplified manual-install launcher have host checks; a fresh complete desktop setup run has not been repeated after restructuring. Fresh Snap Store installation, a different-kernel update, screen sharing and physical hardware acceptance remain in the [validation plan](validation-plan.md).
