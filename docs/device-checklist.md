# Minion device checks after installation

Use this checklist on the **GPD WIN Mini 2023 / Ryzen 7 7840U** after `setup.sh` completes and the machine has rebooted. Start with access, touchscreen mapping and handheld power controls, then check the remaining desktop and development workflows. Mark an item complete only after observing it on the device; container and VM results are recorded separately in [testing](testing.md).

Keep results in a private local copy, for example `.local/device-checks/notes.md`, with the date, tested Git revision, pass/fail or not applicable, and reproduction steps for failures. Leave this shared checklist unchecked. Subscription URLs, credentials and HHD API tokens should stay out of reports committed to Git.

## First boot and system identity

- [ ] Ubuntu boots from its installed disk with the USB installer removed. Disk unlock, the login greeter and the desktop have usable orientation and text size.
- [ ] If disk encryption was selected, a wrong passphrase is rejected and the correct one unlocks the disk. Login still requires the separate account password.
- [ ] If Windows was retained, it also boots through the firmware boot menu and its data/recovery partitions remain available. Do not repartition as part of these checks.
- [ ] Record the device, firmware, running kernel and source revision. Confirm Secure Boot has the intended state; inspect kernel lockdown when its file is available.
- [ ] Review failed system/user units and the setup result. Investigate failures belonging to Minion or its required services.

Run in Foot as your normal user, with the repository as the current directory:

```bash
git rev-parse HEAD
uname -r
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/bios_version
systemctl --failed
systemctl --user --failed
systemctl --user status minion-session.target minion-gamepad.service
sudo cat /var/lib/minion/setup/last-success.json
```

`last-success.json` points to the successful run directory containing `setup.log` and `result.json`. For Secure Boot, use `mokutil --sb-state` if `mokutil` is installed; inspect `/sys/kernel/security/lockdown` if present. Record missing diagnostics rather than treating a missing command as a hardware failure.

## Network and access for debugging

- [ ] Connect to Wi-Fi through the network applet or `nmtui`; confirm both Firefox and a terminal can reach the internet. Reconnect after reboot.
- [ ] Establish the intended on-device coding workflow: the agent can read this checkout, run commands and collect device diagnostics. Complete any required sign-in before starting hardware debugging.
- [ ] If remote access is being used, confirm it works over the intended local network. Default setup does not install or configure an SSH server.

```bash
nmcli device status
nmcli connection show --active
curl -I https://www.gstatic.com/generate_204
```

## Touchscreen coordinates

**Known issue:** Firefox scrolls with touch, single taps appear ineffective, and double taps select text at the wrong screen position. Check coordinate mapping before changing gesture settings.

- [ ] Save output and input descriptions. Identify the physical touchscreen, its associated output, the output transform and scale.
- [ ] Tap controls at the center and all four corners in Firefox and another native Wayland application. The activated control must match the touched position.
- [ ] Check single-tap activation, double-tap text selection, scrolling and dragging separately. Record where a touch lands relative to the intended point, including any offset, swapped axes or reversed direction.
- [ ] Compare raw touchscreen events with desktop coordinates if the mismatch persists. Optional diagnostic packages are `libinput-tools` and `evtest`; select the touchscreen device when recording events.
- [ ] Repeat the same checks after suspend/wake and with an external display if used. Record whether changing output layout or scaling changes the error.

```bash
swaymsg -t get_outputs
swaymsg -t get_inputs
```

After installing the optional diagnostic packages, `sudo libinput debug-events` and `sudo evtest` can help distinguish device events from compositor mapping. Keep any eventual display/touch override in the personal configuration described in [setup](post-install-setup.md#screen-size-and-fn-keys), with the original setting and a way to revert it recorded.

## Handheld power controls and temperatures

See [power controls](power-controls.md) for the installed HHD configuration and its limits.

- [ ] `minion-hhd.service` starts after boot, identifies this device and exposes the power backend. Open **Handheld Daemon** from Super+D or run `minion-hhd-ui`; local authentication and the UI must work.
- [ ] On a fresh installation, TDP and AMD energy overrides remain disabled. HHD's controller emulation stays disabled; Minion's controller mapper remains responsible for desktop input.
- [ ] The running kernel has matching headers and a successfully built `acpi_call` module. Check module signing and loading under the device's actual Secure Boot policy; record any required MOK enrollment.
- [ ] The bar's power block opens HHD and shows `Auto` with overrides disabled. When testing an enabled target, its label follows HHD's configuration. A configured target is not measured power consumption or proof that firmware accepted it.
- [ ] Inventory readable CPU/control, GPU, NVMe and battery temperatures. Compare the bar and its click details with the corresponding kernel channels. Missing channels are omitted; CPU and integrated GPU channels may describe the same APU.
- [ ] Record the firmware baseline before changing power controls. Test one supported TDP/GPU control at a time and compare requested settings with available readback, temperatures and the same repeatable workload, on AC and battery.
- [ ] Identify any available fan/RPM readings and confirm firmware cooling behaves normally under load. Keep automatic cooling for initial checks; custom fan curves, rear buttons and gyro are separate optional work.
- [ ] Disable test overrides and reboot to restore the baseline. Repeat a selected power profile across suspend/wake and cold boot; check for lost settings, stuck clocks or fan behavior.

```bash
systemctl status minion-hhd.service
sudo journalctl -u minion-hhd.service -b
dkms status
modinfo -F signer acpi_call
```

When checking module acceptance, `sudo modprobe acpi_call` should succeed. If it fails, capture the error and relevant kernel log before making changes. Do not include HHD's local API token in diagnostic notes.

## Controller navigation and shortcuts

Use the [control reference](gamepad-controls.md) and [24-shortcut table](gamepad-chord-layout.md) while checking these items.

- [ ] In hardware gamepad mode, A/B/Y produce Enter/Escape/Tab and X produces Backspace. Confirm X and Y are not swapped. X acts immediately and repeats while held; R2+X deletes words where supported.
- [ ] Left stick focuses windows; L2+left stick moves them. Bumpers change workspaces; L2+bumper moves the focused window without following it. Check dead zones, repeat rate and diagonal handling for comfort.
- [ ] Start opens Foot, Select opens the window picker, and Menu/Xbox opens the launcher. D-pad and A/B can operate and dismiss the picker/launcher.
- [ ] Test all 24 shortcuts, including physical diagonals. Try both press orders; each action fires once after release and does not leak arrows or face-button actions. Up+A closes only the focused test window.
- [ ] Copy/paste work in both a GUI text field and Foot. Other guarded editing commands do not interrupt or suspend the shell. Use disposable text and windows for destructive editing/close tests.
- [ ] L3 shows a persistent searchable legend. D-pad browsing and B/Escape/Enter/L3 dismissal work; underlying windows do not receive suppressed shortcuts or stick operations while it is open.
- [ ] R3 switches right-stick Resize/Select text mode, with the bar matching the mode. Switching while deflected waits for neutral. In an editor, selection extends with Shift+arrows and R2 adds Ctrl; no modifier stays held after release or a mode change.
- [ ] Start+Select held for at least 0.75 seconds toggles passthrough after release. A game receives ordinary controller input without duplicate virtual keyboard actions; toggling back restores navigation.
- [ ] Hardware mouse mode and the physical touchpad remain usable. Lock/unlock, mode changes and suspend/wake release held keys, require neutral controls and restore the expected right-stick state. Cold boot starts in desktop/Resize mode.

```bash
minion-gamepad --status
journalctl --user -u minion-gamepad.service -b
```

## Display and everyday desktop use

- [ ] The 2× desktop scale is comfortable and the bottom bar fits. Check console/unlock/greeter separately; desktop scaling does not apply to those screens. Test any external display's orientation, scaling and touch association.
- [ ] AMD graphics acceleration works for video and a repeatable 3D workload. Inspect `glxinfo -B` for the Xwayland renderer and check the kernel log for GPU reset/resume errors; distinguish software rendering from the intended AMD renderer.
- [ ] Physical QWERTY keys, modifiers, touchpad click/tap/scroll and any configured language switching work. The layout indicator follows the physical keyboard when multiple layouts are configured.
- [ ] Fn brightness keys and `brightnessctl -c backlight set +5%` work without sudo. Check the minimum/maximum range, locked-screen behavior and wake persistence.
- [ ] Speakers, headphones, jack detection and microphone work. Volume/mute keys, media keys and the bar agree with actual playback; repeat after waking.
- [ ] Pair a Bluetooth device if used, then test reconnect after reboot and suspend.
- [ ] Test any dock, external storage and card reader you intend to use, including reconnection after suspend.
- [ ] Firefox opens, accepts keyboard/touchpad input, and can copy/paste, upload a file and open a download in the file manager. Test screen sharing and its chooser in the application you intend to use.
- [ ] Notifications and desktop authorization prompts appear and can be answered. Print Screen and the screenshot shortcut put a usable image on the clipboard.
- [ ] Battery percentage and charging/full/discharging states follow AC connection changes. Wi-Fi signal, audio/mute, proxy state and right-stick mode match actual state. Missing sensors do not stall the bar; click details and HHD launching work.

## Development tools and coding agents

See [development setup](post-install-setup.md#development-environment) for managers, project versions and update commands.

- [ ] In a new Foot terminal, all requested runtimes are available without a first-use compiler download. Record their installed versions; fresh setup should have selected the latest stable versions available to its upstream installers.
- [ ] Build and run a small Go program; run a Rust project's tests, formatting and Clippy; compile TypeScript and run a Node/pnpm script; create a uv environment and run Python tests. Check gopls, Delve, rust-analyzer, Ruff and Pyright in the editor or workflow you will actually use.
- [ ] In a disposable project, choose a different Node version with `mise use`. Entering/leaving the project automatically switches versions. Repeat in a new terminal alongside ble.sh and Atuin; verify normal editing and history still work.
- [ ] `/usr/bin/python3` remains Ubuntu's interpreter, independently of the development `python`/`python3`. Minion's desktop services and HHD continue to start.
- [ ] After the fresh login, `id -nG` includes `docker`. Docker works without sudo; Buildx can build an image and Compose can start, inspect and remove a disposable service with the device's normal storage/network configuration.
- [ ] Sign in to Codex, Claude Code and Cursor Agent, test browser handoff and rendering at 2× scaling, and complete a small repository task with each. Check each tool's available sandbox diagnostics on the actual kernel; a version command alone does not establish sandbox operation.

```bash
go version
rustc --version
node --version
pnpm --version
tsc --version
python --version
uv --version
/usr/bin/python3 --version
mise ls --global
id -nG
docker info
docker buildx version
docker compose version
codex --version
claude --version
agent --version
```

Conda/Miniforge is optional and is not part of default installation. Local development acceptance used ARM64 containers, and its nested Docker test needed a QA-only storage override; the handheld must pass with its own normal Docker configuration.

## Proxy connectivity

Configure a subscription privately using [proxy setup](proxy.md), only if proxy access is wanted. A fresh installation leaves the service disabled until explicitly enabled.

- [ ] The subscription fetch and `manage.py test` succeed after configuration. Confirm the expected TUN or explicit-proxy mode; an explicit-proxy test alone does not establish system-wide capture.
- [ ] With TUN enabled, Firefox, ordinary terminal requests and coding agents work without application proxy settings. Confirm DNS, local/private network access and the expected public egress route.
- [ ] Stop the service and confirm direct connectivity/DNS return; start it again and check recovery. The bar tracks service state, while actual requests establish connectivity.
- [ ] Repeat after Wi-Fi changes, suspend/wake and reboot. Confirm the chosen boot activation state, retained configuration and device registration.
- [ ] If Docker builds/containers need proxy access, test an actual image pull, build dependency download and container request. Record any needed Docker-specific configuration; host connectivity alone does not prove container traffic is routed as intended.

From the repository:

```bash
systemctl status minion-proxy.service
sudo python3 setup/proxy/manage.py test
sudo journalctl -u minion-proxy.service -b
```

## Locking and repeated suspend

- [ ] Super+L locks the session and requires authentication. The idle path locks after five minutes and powers off displays after ten; waking restores the display without bypassing the lock.
- [ ] Closing the lid and manual suspend lock before sleeping. Repeat several cycles on AC and battery, including a cycle after using HHD controls and one with the proxy active.
- [ ] After each wake, recheck display, touch coordinates, physical keyboard/touchpad, controller, Wi-Fi, Bluetooth, audio, brightness, power controls and bar readings. No stale modifier, duplicate input or frozen reading remains.
- [ ] Record battery percentage, elapsed time and approximate charge loss during a longer battery suspend. Compare with your intended daily use rather than assuming a fixed acceptable loss.
- [ ] After a cold boot, confirm the same essential services and workflows recover. If later applying Ubuntu/kernel updates, repeat boot/unlock, module acceptance, suspend and Windows boot checks.

## Record failures for the debugging session

For each failure, record the checklist item, expected and observed behavior, exact reproduction steps, AC/battery and proxy state, scale/transform, and whether a reboot or wake triggered it. Attach the relevant service log and a screenshot when useful. Preserve the baseline and record how to revert any test override.

Useful starting points:

```bash
sudo journalctl -b -p warning
sudo journalctl -k -b
journalctl --user -b
```

Keep raw logs private and review them before sharing; they can contain network details, application activity and connection destinations.
