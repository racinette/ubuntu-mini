# Remaining validation

The supported workflow is manual Ubuntu installation followed by source-only post-install setup. Earlier VM runs validated setup, reruns, signed boot, desktop use and synthetic gamepad input. [Testing instructions](testing.md) distinguish those recorded results from checks of the current source tree. The current chord assignments still need a fresh VM run and physical comfort testing.

## Software checks

- Repeat setup from a clean Ubuntu Server VM, then rerun it with personal settings and an active desktop. Confirm settings and partition geometry are preserved.
- Cold boot, reject a wrong disk passphrase, unlock with the correct one, and require a separate account password. Check graphical login, logout, explicit/idle locking and suspend locking.
- Exercise terminal editing, local history before/after reboot, browser input/clipboard/file chooser, notifications, networking, audio and desktop authorization.
- Run the current gamepad mapping suite, including chords, late modifiers, window/workspace actions, passthrough and reconnect/session behavior.
- Verify Secure Boot state, signed shim/GRUB/kernel and kernel lockdown after maintenance. A transition to a different kernel version remains open; earlier maintenance retained the same kernel version.
- Verify a fresh default Firefox installation from the Snap Store and screen sharing. Prior source-clone tests retained an existing Firefox; fresh Store command selection was tested in isolation, and real signed installation was tested through the cache.

## Before installing on the WIN Mini

Back up important data and retain Windows/disk-encryption recovery information. Review the actual partition map in the Ubuntu installer: identify unallocated Linux space, preserve Windows and Recovery, and reuse the EFI system partition without formatting it. Verify the official ISO boots under the device's Secure Boot policy and that the screen/keyboard are usable for installation and disk unlock.

After installation, boot Ubuntu and Windows independently. Confirm the chosen encryption and boot layout. Generic post-install setup does not partition the device or configure encryption.

## Physical hardware acceptance

| Area | Required observation |
| --- | --- |
| Display | Console, disk unlock, greeter and Sway have usable orientation/scaling; check external display if used |
| Touch | All corners map correctly after scaling, rotation and wake |
| Keyboard and touchpad | Keys, modifiers, language switching, click, tap and scroll work |
| Controller | Both hardware modes, trigger/button event codes, diagonal/adjacent chords, reconnect and wake work without duplicate input |
| Wireless | Wi-Fi and Bluetooth pairing/reconnection survive repeated suspend |
| Audio | Speakers, headphones, jack detection, microphone and volume/mute work before and after suspend |
| Suspend | Manual/lid suspend locks first; wake restores display, input, networking and audio; measure overnight battery loss |
| Battery and brightness | Charging/readings are plausible; brightness range and wake persistence work |
| GPU | AMD acceleration and video/3D rendering work; check reset/resume errors |
| Cooling and power | Firmware cooling behaves under load; measure matched workloads before changing power policy |
| Maintenance | Package/kernel updates preserve Ubuntu unlock/session behavior and Windows bootability |

## On-device backlog

These items are deliberately queued until we have shell access to the actual **WIN Mini 2023 / Ryzen 7 7840U**. Installation of HHD is part of default setup; resolving these hardware issues is not a prerequisite for installing it.

- **Touchscreen coordinates:** scrolling works in Firefox, single taps appear ineffective, and double taps select text at the wrong screen position. Record `swaymsg -t get_outputs` and `swaymsg -t get_inputs`; compare raw evdev/libinput coordinates with the output transform, 2× scaling and touch-to-output mapping. Test a tap grid across all corners in Firefox and another native Wayland application, then repeat after suspend. Establish the transform before adding calibration overrides.
- **HHD startup and interface:** record DMI model, BIOS, kernel and Secure Boot state. Check `minion-hhd.service`, launch the desktop UI and confirm local authentication. Verify only the Adjustor provider loads and that Minion's existing controller shortcuts, passthrough and text selection still work.
- **Power/temperature bar:** inventory actual hwmon and battery temperature channels; check CPU die/control, GPU, NVMe and battery labels and units against their kernel files. Confirm the bar fits at 2× scaling, sensor details open on click, the power block opens HHD, and its displayed target matches HHD's configuration. Confirm missing sensors/HHD do not freeze the bar, readings recover after suspend, and distinct channels on the shared APU are not mistaken for separate physical chips.
- **Power backend and signing:** verify the HWE headers match the running kernel, inspect `dkms status`, load `acpi_call` and check its signing/acceptance with Secure Boot. Resolve any required MOK enrollment on the device. Confirm HHD detects the actual model and exposes appropriate firmware limits before enabling TDP control.
- **TDP and GPU behavior:** first record the firmware baseline, then enable one control at a time. Compare requested limits with readback, temperatures and a repeatable CPU/GPU workload; test clock auto/manual transitions, AC versus battery and shared APU power behavior. Return controls to their defaults afterward.
- **Cooling and resume:** identify available fan/RPM interfaces and whether the running kernel provides a suitable GPD driver. Keep automatic firmware cooling for the initial tests. Check repeated lid/manual suspend, wake and cold boot both with default settings and with an explicitly selected power profile; watch for lost settings, stuck clocks/fan modes or duplicate controller input.
- **Development environment:** after a fresh login, check Go/Rust/Node/TypeScript/Python versions in Foot, a small compile/test cycle, and mise project switching alongside ble.sh/Atuin. Confirm `/usr/bin/python3` still serves Minion/Ubuntu services. Check Docker group access, Buildx and a Compose build/run/cleanup using the device’s normal storage/network configuration; repeat after reboot and with the proxy enabled. Local component checks used native ARM64 containers and a test-only Docker storage setting.
- **Coding CLIs:** sign in to `codex`, `claude` and Cursor's `agent` as the normal user in Foot. Check browser sign-in, proxy connectivity, terminal rendering at 2× scaling and a small repository task with each tool. Check their sandbox diagnostics on the actual Ubuntu kernel before relying on sandboxed commands; installation/version checks do not establish sandbox operation.

Record device identity, firmware/kernel versions, reproduction steps and logs for failures. Hardware overrides should match the observed device and include a rollback procedure. Rear buttons, gyro and custom fan curves remain optional extensions.
