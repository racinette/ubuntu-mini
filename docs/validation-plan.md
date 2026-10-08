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

Record device identity, firmware/kernel versions, reproduction steps and logs for failures. Hardware overrides should match the observed device and include a rollback procedure. Rear buttons, gyro, fan overrides and TDP tuning remain optional extensions.
