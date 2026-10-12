# Handheld power controls

Ordinary `sudo ./setup.sh` installs [Handheld Daemon (HHD)](https://github.com/hhd-dev/hhd) and its desktop interface, then enables and starts `minion-hhd.service`. Open **Handheld Daemon** from the application launcher (Super+D), or run `minion-hhd-ui` in a terminal. This integration targets the GPD WIN Mini 2023 with Ryzen 7 7840U; actual hardware operation is still queued in the [device backlog](validation-plan.md#on-device-backlog).

Only HHD's bundled Adjustor power plugin is loaded. Minion's gamepad navigation, shortcuts and text selection continue to use its existing mapper; HHD controller emulation, input-hiding rules, gyro handling and Steam overlay integration are not installed or enabled by this component.

The first installation explicitly disables TDP overrides, AMD energy management and power-profiles-daemon emulation. Firmware cooling and the existing power policy remain in effect. Enable the relevant controls in HHD when testing on the handheld. Availability depends on the detected device, firmware and kernel drivers: installing the application does not establish that every Motion Assistant feature works. Fan controls and gyro support are separate hardware checks; no custom fan curve or experimental kernel driver is installed.

HHD stores settings and profiles under `/etc/hhd/`. Existing settings are preserved when setup is rerun, including any overrides you have subsequently enabled. The API listens on localhost port 5335 and requires a token; the desktop interface reads the local token automatically. Local desktop users can operate these privileged power controls.

The installer pins HHD 4.1.12 (including Adjustor) and HHD UI 3.4.2 in `setup/hhd/artifacts.json`, verifies downloads with SHA-256 and caches them in `/var/cache/minion/hhd/`. Native Python dependencies come from Ubuntu APT; HHD uses an isolated runtime with access to those packages. The UI is extracted once into a root-owned directory, with the standard Chromium sandbox helper, so launching needs no FUSE mount. Installed files live under `/usr/local/lib/minion-hhd/`, independently of the checkout. The shell/browser `--asset-dir` and `--asset-url` options do not redirect HHD downloads.

Ubuntu's `acpi-call-dkms` package and matching HWE headers are installed for the ACPI power backend. Setup tests loading `acpi_call` on the running kernel. If Secure Boot is enabled and the module's matching local signing certificate is not enrolled, interactive setup starts an enrollment password prompt. Unattended setup prints the enrollment command instead. Already enrolled or pending keys are retained; a mismatched certificate is not offered. Setup keeps Secure Boot enabled and leaves boot-screen confirmation and reboot to you. A module-load failure is reported without preventing desktop installation; a newly installed kernel may need a reboot before the module is available. Fan-driver availability also remains an on-device check.

## Secure Boot module enrollment

On the WIN Mini, `sudo modprobe acpi_call` initially failed with `Key was rejected by service`: DKMS had signed the module, but the local signing certificate was not enrolled. Enrolling the existing certificate allowed the module to load with Secure Boot still enabled. Check your own device before requesting enrollment:

```bash
mokutil --sb-state
modinfo -F signer acpi_call
mokutil --test-key /var/lib/shim-signed/mok/MOK.der
sudo modprobe acpi_call
```

If setup already queued enrollment, continue with the reboot instructions below. Otherwise, if the module is signed with the local Ubuntu DKMS key and that certificate is not enrolled, request enrollment:

```bash
sudo mokutil --import /var/lib/shim-signed/mok/MOK.der
```

Enter your sudo password if prompted, then choose and confirm a temporary enrollment password. Save your work and reboot. At the blue MOK screen, press a key if a countdown appears, then use the physical keyboard to choose **Enroll MOK → Continue → Yes**, enter the temporary password and choose **Reboot**. Verify the certificate identity when offered. Enrollment trusts modules signed by this key; setup can queue the request, but boot-screen confirmation requires your physical approval. See [Ubuntu's Secure Boot guidance](https://documentation.ubuntu.com/security/security-features/platform-protections/secure-boot/).

After returning to Ubuntu, repeat `mokutil --test-key` and `sudo modprobe acpi_call`, then check `lsmod | rg '^acpi_call '`. Enrollment and loading establish module acceptance; testing requested power limits against hardware readback remains a separate check. Missing certificate files or a different module signer need investigation before following this procedure. Keep signing keys and enrollment passwords private.

To inspect or stop the service:

```bash
systemctl status minion-hhd.service
journalctl -u minion-hhd.service -b
sudo systemctl disable --now minion-hhd.service
```

Stopping HHD prevents further overrides; it does not promise to restore every firmware value already written. For a clean baseline, disable the relevant controls in HHD and reboot. Rerunning setup enables the service again and retains its settings.

## Bottom bar

The power block reads HHD's authenticated localhost API every five seconds, without sudo or configuration writes. `Auto` means its TDP override is disabled; `Limit 15W` is its configured steady APU target, not measured consumption or confirmation that the firmware applied it. The detailed skin/STAPM target takes precedence over the quick-access slider. An unavailable daemon or unready backend shows `Power ?`; enabled controls without a supported target show `Limit ?`. Left-click opens HHD; right-click explains the current power label.

The adjacent temperature block reads kernel sensor files independently of HHD, so readings can remain available when the daemon is stopped. A fully populated example is `CPU65° GPU58° SSD40° Bat32°`. Missing categories disappear; with no usable sensors, the whole temperature block disappears. A short CPU/control-temperature form is available when Sway needs to fit the bar into less space.

CPU summaries prefer `Tdie`; `Ctl` identifies the `Tctl` cooling-control reading when only that is available. GPU summaries prefer the edge channel, and SSD summaries prefer the NVMe composite channel. For several devices, the summary uses the hottest preferred channel. Battery temperature is included only when the system battery exports it. These labels follow the kernel's [AMD CPU sensor documentation](https://docs.kernel.org/hwmon/k10temp.html), [AMD GPU interfaces](https://docs.kernel.org/gpu/amdgpu/thermal.html) and [power-supply ABI](https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-class-power).

Click the temperature block to list all readable hwmon channels with their original driver/channel labels and temperatures to one decimal place. This includes additional CPU, GPU junction/memory, SSD internal, ACPI, wireless or board channels if exported. Unknown channels retain their actual labels rather than being assigned to a guessed component; if there are only unknown channels, the bar shows the hottest as `Temp`. Equal values from distinct channels are retained, while duplicate sysfs aliases are removed. CPU and integrated GPU readings can describe the same APU package; the display does not imply separate physical chips.

Readings refresh every five seconds. Disabled/faulted sensors, unreadable or malformed files and implausible handheld temperatures are omitted; class paths are rediscovered to handle driver changes and resume. The implementation uses the kernel's [hwmon units and labels](https://docs.kernel.org/hwmon/sysfs-interface.html), converting millidegrees for hwmon and tenths of a degree for battery readings. No probing, calibration, fan control or additional sensor package is installed. Available channels and their behavior after suspend still need confirmation on the handheld.
