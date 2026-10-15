# Minion device checks after installation

Use this checklist on the **GPD WIN Mini 2023 / Ryzen 7 7840U** after `setup.sh` completes and the machine has rebooted. Start with access, touchscreen mapping and handheld power controls, then check the remaining desktop and development workflows. Mark an item complete only after observing it on the device; container and VM results are recorded separately in [testing](testing.md).

Keep results in a private local copy, for example `.local/device-checks/notes.md`, with the date, tested Git revision, pass/fail or not applicable, and reproduction steps for failures. Leave this shared checklist unchecked. Subscription URLs, credentials and HHD API tokens should stay out of reports committed to Git.

The original WIN Mini has already passed the core checks summarized in the
[current validation status](validation-plan.md). Unchecked items here are a
template for a new installation, not a list of outstanding failures on that device.

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

## Memory and swap

- [ ] `swapon --show` reports the intended swap. On a fresh ext4/XFS setup without an existing swap policy, Minion supplies `/var/lib/minion/swapfile`, up to 8 GiB, with `0600` permissions and a boot entry.
- [ ] Confirm an existing swap configuration survives setup reruns. Inspect any message about skipped allocation on unsupported filesystems or low disk space.
- [ ] At the next planned boot, confirm swap activates again. Under ordinary coding/browser workloads, observe memory pressure and any further OOM exits. Swap availability is not proof that arbitrary workloads cannot exhaust memory.

```bash
swapon --show
free -h
systemctl status var-lib-minion-swapfile.swap
```

## Network and access for debugging

- [ ] Initialize a passphrase-protected `pass` store privately. A disposable entry reaches the requested command using the shell example in the setup guide, consecutive lookups reuse the unlock, and a missing entry never starts the command. Check a graphical unlock prompt after `gpgconf --reload gpg-agent`. Back up the vault and encryption key separately; keep tokens out of reports.
- [ ] One sudo authentication is reused across terminals for 15 minutes; `sudo -k` invalidates it. SSH/Git unlock a key on first use and reuse it through the shared agent for one hour. Confirm agent removal/activation after logout/login at the next planned session restart.
- [ ] Connect to Wi-Fi through the network applet or `nmtui`; confirm both Firefox and a terminal can reach the internet. Reconnect after reboot.
- [ ] Establish the intended on-device coding workflow: the agent can read this checkout, run commands and collect device diagnostics. Complete any required sign-in before starting hardware debugging.
- [ ] If remote access is being used, confirm it works over the intended local network. Default setup does not install or configure an SSH server.

```bash
nmcli device status
nmcli connection show --active
curl -I https://www.gstatic.com/generate_204
```

## Touchscreen coordinates

**Observed fix:** Firefox taps missed controls until the WIN Mini touchscreen was explicitly associated with `eDP-1`. Setup now supplies this mapping; verify it on your installation before changing gesture settings. Center and four-corner single taps passed on the device, including after reboot; other gestures and suspend/wake still need checks.

- [ ] Save output and input descriptions. Identify the physical touchscreen, its associated output, the output transform and scale.
- [ ] Tap controls at the center and all four corners in Firefox and another native Wayland application. The activated control must match the touched position.
- [ ] Check single-tap activation, double-tap text selection, scrolling and dragging separately. Record where a touch lands relative to the intended point, including any offset, swapped axes or reversed direction.
- [ ] Compare raw touchscreen events with desktop coordinates if the mismatch persists. Optional diagnostic packages are `libinput-tools` and `evtest`; select the touchscreen device when recording events.
- [ ] Repeat the same checks after suspend/wake and with an external display if used. Record whether changing output layout or scaling changes the error.

```bash
swaymsg -t get_outputs
swaymsg -t get_inputs
```

After installing the optional diagnostic packages, `sudo libinput debug-events` and `sudo evtest` can help distinguish device events from compositor mapping. Keep device-specific adjustments to the default display/touch mapping in the personal configuration described in [setup](post-install-setup.md#screen-size-and-fn-keys), with the original setting and a way to revert it recorded.

## Handheld power controls and temperatures

See [power controls](power-controls.md) for the installed HHD configuration and its limits.

- [ ] `minion-hhd.service` starts after boot, identifies this device and exposes the power backend. Open **Handheld Daemon** from Super+D or run `minion-hhd-ui`; local authentication and the UI must work.
- [ ] On a fresh installation, TDP and AMD energy overrides remain disabled. HHD's controller emulation stays disabled; Minion's controller mapper remains responsible for desktop input.
- [ ] The running kernel has matching headers and a successfully built `acpi_call` module. Check module signing and loading under the device's actual Secure Boot policy; record any required MOK enrollment.
- [ ] The bar's power block opens HHD and shows `Auto` with overrides disabled. When testing an enabled target, its label follows HHD's configuration. A configured target is not measured power consumption or proof that firmware accepted it.
- [ ] Inventory readable CPU/control, GPU, NVMe and battery temperatures. Compare the bar and its click details with the corresponding kernel channels. Missing channels are omitted; CPU and integrated GPU channels may describe the same APU.
- [ ] Check the BMI260 motion sensor: `bmi270_i2c` binds and `/sys/bus/iio/devices/iio:device*/` exposes accelerometer and angular-velocity channels. Confirm readings respond to tilting the device. Setup supplies missing initialization firmware on this model; gyro input mapping and automatic rotation remain optional.
- [ ] Record the firmware baseline before changing power controls. Test one supported TDP/GPU control at a time and compare requested settings with available readback, temperatures and the same repeatable workload, on AC and battery.
- [ ] Identify any available fan/RPM readings and confirm firmware cooling behaves normally under load. Keep automatic cooling for initial checks; custom fan curves, rear buttons and gyro are separate optional work.
- [ ] Disable test overrides and reboot to restore the baseline. Repeat a selected power profile across suspend/wake and cold boot; check for lost settings, stuck clocks or fan behavior.

```bash
systemctl status minion-hhd.service
sudo journalctl -u minion-hhd.service -b
dkms status
modinfo -F signer acpi_call
```

When checking module acceptance, `sudo modprobe acpi_call` should succeed. If it fails, capture the error and relevant kernel log before making changes. For `Key was rejected by service`, check the signing certificate and follow [Secure Boot enrollment](power-controls.md#secure-boot-module-enrollment) if needed. Do not include HHD's local API token in diagnostic notes.

## Controller navigation and shortcuts

Use the [control reference](gamepad-controls.md) and [shortcut tables](gamepad-chord-layout.md) while checking these items.

- [ ] In hardware gamepad mode, A/B produce Enter/Escape on release; X produces immediate, repeatable Backspace and Y produces immediate, repeatable Space. Confirm X and Y are not swapped. R2+X deletes words where supported; R2+Y switches US/RU.
- [ ] The default layout scrolls with the left stick and focuses windows with the right; L2+right stick moves windows. Select another window with the right stick, then scroll it with the left without touching the touchpad. Focus changes center the pointer only when it is outside the selected window; verify an off-center point inside the selected window stays put, including while scrolling. L3 changes the left stick to text navigation; R3 changes the right stick to resize. Bumpers change workspaces; L2+bumper moves the focused window without following it. Check dead zones, repeat rate and diagonal handling for comfort.
- [ ] With N the highest occupied workspace, R1 visits the extra empty N+1, then wraps to 1; L1 from 1 wraps directly to the last occupied workspace N, skipping the extra empty slot. Opening a window there grows the ring. When an empty workspace disappears, remaining numbered workspaces renumber consecutively without changing their contents or focus. L2+bumper moves a disposable window without following it and uses the same wraparound. Each bumper acts once on release, including after a hold.
- [ ] Start and Super+Enter open Foot in the focused Foot shell's directory, including while a command is running; from another app they start in home. Select opens the window picker, and a short Menu/Xbox tap toggles the launcher. A second Menu tap closes it; holding Menu replaces it with the legend. D-pad and A/B can operate and dismiss the picker/launcher.
- [ ] Test all 20 editing/navigation/layout shortcuts, including physical diagonals: hold A/B before a D-pad direction, or Select before A/B/X/Y. Try long prefix holds; each action fires once after release and does not leak arrows or face-button actions. Hold B then Up to close only the focused test window. Check Select alone opens the picker and every Select+face layout shortcut consumes its individual actions without leaking Space/Backspace. D-pad first sends arrows immediately and accelerates while held; adding A/B afterward must not execute a combo or leak Enter/Escape. Check release stop, direction changes and Shift/Ctrl modifiers during a hold.
- [ ] Copy/paste work in both a GUI text field and Foot. Other guarded editing commands do not interrupt or suspend the shell. Use disposable text and windows for destructive editing/close tests.
- [ ] In a disposable Foot terminal, A+B interrupts `sleep 600`; hold both before Up to suspend another `sleep 600`, then use `fg` and interrupt it. Hold both before Down to end an empty `cat` input. Every action fires once after release, consumes Enter/Escape/arrows, ignores trigger modifiers and appears in the Menu-hold legend. Wrong-order, rolling and unassigned A+B gestures do nothing; GUI windows receive no Ctrl+C/Z/D from these terminal controls.
- [ ] Holding Menu for 0.75 seconds shows a persistent searchable legend once, without opening the launcher on release. D-pad browsing and B/Escape/Enter/Menu-tap dismissal work; underlying windows do not receive suppressed shortcuts or stick operations while it is open.
- [ ] L3 and R3 switch their own sticks independently, with the bar showing both behaviors. Test all four combinations. Switching while a stick is deflected waits only for that stick to return to neutral and suppresses only it meanwhile; the other stick keeps working. A second click cancels a pending change. Left Scroll behavior sends vertical/horizontal wheel events to the pane under the existing pointer without moving it; check split-editor panes and ordinary scrolling with triggers held. In Text mode, the left stick moves the caret; L2 selects, R2 moves by words horizontally, and both select words. Check changing triggers while the stick stays deflected. For both sticks, a nudge acts once, light deflection acts slowly and full deflection acts rapidly; up/down text movement stays slower than left/right, including during selection. Returning to neutral stops immediately; no modifier stays held after trigger release or a mode change.
- [ ] Start+Select held for at least 0.75 seconds toggles passthrough after release. A game receives ordinary controller input without duplicate virtual keyboard actions; toggling back restores navigation.
- [ ] Hardware mouse mode and the physical touchpad remain usable. Lock/unlock, mode changes and suspend/wake release held keys, require neutral controls and restore Scroll/Windows controls. Cold boot starts in desktop mode with left Scroll and right Windows.

```bash
minion-gamepad --status
journalctl --user -u minion-gamepad.service -b
```

## Display and everyday desktop use

- [ ] The 2× desktop scale is comfortable and the bottom bar fits. Check console/unlock/greeter separately; desktop scaling does not apply to those screens. Test any external display's orientation, scaling and touch association.
- [ ] Date/time uses the intended timezone and network time is synchronized. Night light offers Automatic/Warm now/Off and preserves the chosen mode; check comfortable night colors and return to daytime colors.
- [ ] Noto fallbacks display the scripts, symbols and emoji used in your apps. Open a new terminal after installing fonts; test CJK or private-use icons separately if needed.
- [ ] AMD graphics acceleration works for video and a repeatable 3D workload. Inspect `glxinfo -B` for the Xwayland renderer and check the kernel log for GPU reset/resume errors; distinguish software rendering from the intended AMD renderer.
- [ ] Physical QWERTY keys, modifiers, touchpad click/tap/scroll and any configured language switching work. The layout indicator follows the physical keyboard when multiple layouts are configured.
- [ ] On the built-in keyboard, Ctrl+Space switches English/Russian once per press and the bar follows US/RU. Russian typing works while desktop shortcuts keep their physical key positions. R2+physical Space also switches layouts, L2 modifies physical typing, gamepad editing shortcuts work under Russian, and Select still opens the window picker. Check switching at the lock screen as well.
- [ ] Fn brightness keys and `brightnessctl -c backlight set +5%` work without sudo. Check the minimum/maximum range, locked-screen behavior and wake persistence.
- [ ] Speakers, headphones, jack detection and microphone work. Volume/mute keys, media keys and the bar agree with actual playback; repeat after waking.
- [ ] Plain ALSA clients record through PipeWire: `arecord -D default -d 1 -f S16_LE -r 16000 /dev/null` succeeds without ALSA errors as the desktop user. Setup installs `pipewire-alsa` to provide default-device routing.
- [ ] On the WIN Mini 2023, a fresh setup seeds internal-microphone input at 10% (Capture and Internal Mic Boost both 0 dB). Record and replay speech to check clarity. Setup reruns preserve a subsequently chosen level and other audio routes; see [microphone defaults](post-install-setup.md#desktop-controls).
- [ ] Pair a Bluetooth device if used, then test reconnect after reboot and suspend.
- [ ] Clicking the bar's Wi-Fi text opens the nearby-network chooser; selecting a saved network reuses its profile, and a new secured network prompts for its password. Refresh, hidden/enterprise profile editing and enabling a disabled radio work. Opening/closing the chooser alone leaves the connection unchanged.
- [ ] Test any dock, external storage and card reader you intend to use, including reconnection after suspend.
- [ ] Firefox opens, accepts keyboard/touchpad input, and can copy/paste, upload a file and open a download in the file manager. Test screen sharing and its chooser in the application you intend to use.
- [ ] Chromium is installed alongside Firefox, opens from Super+D or `chromium`, and can run a headless browser automation check with its sandbox enabled. Setup reruns retain both browsers' revisions/channels and profiles.
- [ ] Notifications and desktop authorization prompts appear and can be answered. Print Screen and the screenshot shortcut put a usable image on the clipboard.
- [ ] Battery percentage and charging/full/discharging states follow AC connection changes. Wi-Fi signal, audio/mute, proxy state and both stick modes match actual state. Missing sensors do not stall the bar; click details and HHD launching work.
- [ ] Clicking the battery percentage opens Power Statistics with the laptop battery selected. Clicking again brings the existing window forward without duplication, including from another workspace.
- [ ] Routine notifications without an explicit sender timeout disappear after five seconds; Keep awake popups disappear after 2.5 seconds. Critical alerts remain available for dismissal. Tapping or right-clicking dismisses a popup, and existing personal Mako settings survive setup reruns.

## Development tools and coding agents

See [development setup](post-install-setup.md#development-environment) for managers, project versions and update commands.

- [ ] In a new Foot terminal, all requested runtimes are available without a first-use compiler download. Record their installed versions; fresh setup should have selected the latest stable versions available to its upstream installers.
- [ ] Build and run a small Go program; run a Rust project's tests, formatting and Clippy; compile TypeScript and run a Node/pnpm script; create a uv environment and run Python tests. Check gopls, Delve, rust-analyzer, Ruff and Pyright in the editor or workflow you will actually use.
- [ ] In a disposable project, choose a different Node version with `mise use`. Entering/leaving the project automatically switches versions. Repeat in a new terminal alongside ble.sh and Atuin; verify normal editing and history still work.
- [ ] `/usr/bin/python3` remains Ubuntu's interpreter, independently of the development `python`/`python3`. Minion's desktop services and HHD continue to start.
- [ ] After the fresh login, `id -nG` includes `docker`. Docker works without sudo; Buildx can build an image and Compose can start, inspect and remove a disposable service with the device's normal storage/network configuration.
- [ ] Sign in to Codex, Claude Code and Cursor Agent, test browser handoff and rendering at 2× scaling, and complete a small repository task with each. Check each tool's available sandbox diagnostics on the actual kernel; a version command alone does not establish sandbox operation.
- [ ] In Neovim insert mode, one physical Enter/Backspace or gamepad A/X tap performs one action; holding X still repeats. Check the same controls in the file tree/pickers, and repeat after reopening the editor.
- [ ] Open Neovim from the launcher and a project with `nvim .`. Check tree navigation, fuzzy lookup, project text search, definitions/references, return navigation, normal file editing/saving and external LLM edits appearing on focus/idle without overwriting unsaved work. Check Go, Rust, JS/TS, Python, shell, JSON, YAML, TOML and C/C++ language-server attachment and on-device D-pad/stick usability.

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
codex sandbox -- /bin/true
claude --version
agent --version
```

Conda/Miniforge is optional and is not part of default installation. Local development acceptance used ARM64 containers, and its nested Docker test needed a QA-only storage override; the handheld must pass with its own normal Docker configuration.

## Proxy connectivity

Configure a subscription privately using [proxy setup](proxy.md), only if proxy access is wanted. A fresh installation leaves the service disabled until explicitly enabled.

- [ ] The subscription fetch and `manage.py test` succeed after configuration. Confirm the expected TUN or explicit-proxy mode; an explicit-proxy test alone does not establish system-wide capture.
- [ ] Clicking Proxy in the bar and choosing Proxy dashboard in the launcher open the local MetaCubeXD interface. PROXY lists subscription servers and Automatic; latency tests respond and a graphical server choice survives a proxy restart. Check readability at the device scale. On upgrade, the previous choice migrates once and later dashboard selections stay authoritative; dashboard credentials and subscription URLs stay private.
- [ ] With TUN enabled, Firefox, ordinary terminal requests and coding agents work without application proxy settings. Confirm DNS, local/private network access and the expected public egress route.
- [ ] `.by` and `.бел` domains, including `hoster.by` and subdomains, route DIRECT. Similar-looking names such as `hoster.by.example.com` still follow the proxy; earlier personal exceptions retain priority. Russian bypass settings and the chosen proxy server remain unchanged.
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

- [ ] Super+L locks the session and requires authentication on AC and battery. On battery, the idle path locks after five minutes and powers off displays after ten; waking restores the display without bypassing the lock. On AC, idle locking/display-off are disabled. Unplugging restores the battery timers; plugging in does not bypass an existing lock.
- [ ] Fn+F3 turns displays off without locking or suspending; pressing it again leaves the display on, and ordinary input also wakes it. If already locked, waking still requires authentication. Fn+F4 toggles Keep awake once per press/hold; its bar indicator follows and can also be clicked. With Keep awake enabled, background work continues through manual display-off and battery idle timers remain disabled across charger changes. Turning it off restores fresh battery timers. Fn+F5/F6 and L4 have no assigned action. Physical-keyboard Print Screen still takes a screenshot; the rear keys do not leak into applications. Power-button behavior is unchanged.
- [ ] R4 tap starts/stops dictation. A 0.75-second hold cancels once, and releasing it does not start another recording. Dictation follows US/RU at recording start. Super+V and Super+Shift+V, plus the Mic bar controls, also work.
- [ ] Ctrl+Space and gamepad R2+Y switch US/RU and show a readable centered language popup. Repeated switching updates one popup, which disappears after one second without changing application focus.
- [ ] Closing the lid and manual suspend lock before sleeping on both AC and battery, including when docked. Repeat several cycles, including a cycle after using HHD controls and one with the proxy active.
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
