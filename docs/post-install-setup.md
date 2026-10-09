# Ubuntu post install setup

Install Ubuntu 24.04 Server amd64 manually or with the [installation helper](install.md), create your normal user, and boot into that installed system. Then run the standalone setup to add Sway, greetd, Foot, Firefox, desktop services, Bash with ble.sh and local Atuin history. It also installs Ubuntu's supported HWE kernel, firmware, AMD microcode, Mesa graphics/video packages and ALSA device profiles. The setup uses your existing account and password and activates the configured environment on your next reboot.

Partition selection and LUKS encryption happen during Ubuntu installation. The optional helper creates a separate Ubuntu ESP in free space; when installing manually, choose the intended Linux space and preserve Windows, Recovery and their existing EFI files. The setup does not create encryption or partition disks. Physical screen orientation, touch mapping and hardware behavior still need validation on the WIN Mini.

## Clone and run

On the installed Ubuntu system, run from your normal account:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/racinette/ubuntu-mini.git ubuntu-mini
cd ubuntu-mini
sudo ./setup.sh --check
sudo ./setup.sh
sudo reboot
```

The repository contains scripts, configuration and small version/checksum manifests. Application archives, binaries, ISO images, VM disks and private test state stay outside Git; `.gitignore` excludes them. Keep the root `setup.sh` and the complete `setup/` directory together, because the entry point reads its configuration relative to its own location. The `tests/` and `docs/` components are not read or installed by setup.

`sudo` supplies your existing username. When invoking from a root shell instead, pass `--user YOUR_USERNAME`. `--check` checks the target prerequisites without installing packages, downloading applications or writing configuration. It verifies a cache only when one is explicitly selected; an online check does not prove package or upstream connectivity.

Normal setup downloads Ubuntu packages through the target's existing APT sources and installs Firefox from the Snap Store's stable channel. Snap handles its signed runtime dependencies. Atuin and ble.sh are downloaded to temporary directories from the URLs in `setup/shell/artifacts.json` and must match the recorded SHA-256 checksums before installation. The ble.sh nightly URL can change upstream: a checksum mismatch stops setup; update and test the version/checksum manifest before accepting a different release.

Working internet connectivity is required for normal setup. No application bundle is transferred with the clone. APT sources are retained, and setup does not embed a VM host address.

After reboot, enter your LUKS passphrase if you configured encryption, then log in using your existing account password. Super+Enter opens Foot, Super+D opens the application launcher, Super+B opens Firefox, Super+E opens Thunar, Super+1 through Super+4 switch workspaces, and Super+L locks the session. The configuration uses Bash and local-only Atuin without requiring an account.

Setup also installs [gamepad desktop navigation](gamepad-controls.md): triggers hold Shift/Ctrl, bumpers change workspaces, the D-pad sends arrows, and sticks focus/move/resize windows. Start opens a terminal; Select opens the window picker; Menu opens the launcher. Button actions fire on release. [V1 typing chords](gamepad-chord-layout.md) combine the D-pad and face buttons to type US keyboard letters, digits and punctuation; release the whole combination to emit one key. D-pad arrows also wait for release. Hold Start+Select together, then release both, or press Super+Ctrl+G to toggle normal gamepad input for games. Personal overrides in `~/.config/mini-os/gamepad.json` are preserved across setup reruns. The mapping has [VM acceptance tests](testing.md#gamepad-tests); actual WIN Mini controls still need verification.

L3 arms the [command layer](gamepad-controls.md#l3-commands-and-one-shot-super): X closes the focused window, Y toggles tabbed/tiled layout, A opens a terminal, B cancels, and Up/Down/Left/Right copy/paste/undo/redo. Undo/redo are disabled in detected terminals. Multi-input typing chords still emit one-shot Super shortcuts; for example, L3 then Up+Y emits Super+E to open the file manager. A second L3 tap cancels; Shift/Ctrl triggers can combine with typing shortcuts.

## Screen size and Fn keys

The desktop defaults to 2× output scaling for the WIN Mini's 7-inch 1920×1080 panel. This enlarges controls and text together, with a 960×540 logical workspace. It does not change the console, encryption prompt or text login greeter. For a smaller desktop UI, add `output * scale 1.5` to `~/.config/sway/mini-os.conf` and press Super+Shift+C. Personal output settings are loaded after the defaults. External monitors also inherit 2× unless overridden, for example `output HDMI-A-1 scale 1`; use `swaymsg -t get_outputs` to find the actual output name.

Fn+F1/F2 adjust the screen backlight. Setup explicitly installs `brightness-udev` and adds your account to the `video` group so `brightnessctl` can write to it without sudo. Brightness and volume controls also work while the screen is locked. Playback keys use `playerctl` with an active MPRIS-capable player: stop, previous, play/pause and next. Print Screen copies a screenshot to the clipboard. Insert and Scroll Lock are passed through to applications; ordinary F1–F12 remain available to applications.

To update only the desktop on an already configured device, from your normal account in the cloned repository:

```bash
git pull --ff-only
sudo python3 setup/desktop/provision.py --defer-activation
sudo reboot
```

This reapplies desktop configuration and installs any missing desktop packages without running shell or browser downloads. Personal Sway overrides are retained. Reboot or log out and back in to activate the new group membership. The full `setup.sh` also includes these changes.

For brightness troubleshooting, run `brightnessctl -c backlight set +5%` without sudo. A permission error means the rules or new group membership are not active; `id -nG` should include `video` after a fresh login. No backlight devices means a separate kernel/device issue. If this command works but Fn keys do not, check the active Sway configuration and the key events emitted by the device rather than remapping ordinary F1/F2.

## Logs and reruns

Every applied run saves `setup.log`, `result.json` and `configuration-before.tar.gz` under `/var/lib/mini-os/setup/TIMESTAMP/`. These directories are private to root. `/var/lib/mini-os/setup/last-success.json` identifies the last successful run. A failure prints the log path and returns nonzero; inspect the log, resolve the problem and rerun the same command.

Reruns preserve existing Atuin and Foot user settings and avoid duplicating the Bash include. An existing Firefox installation is retained instead of reverting its revision. System configuration owned by this setup is reapplied; a backup records its prior contents. Existing personal Sway configuration is honored. Add layouts, scaling and output preferences in `~/.config/sway/mini-os.conf`; this file is not generated or overwritten by setup. For example:

```text
input type:keyboard {
    xkb_layout us,ru
    xkb_options grp:alt_shift_toggle
}
```

Choose layouts for your own usage. Hardware adjustments follow observed behavior rather than VM display settings. Setup schedules NetworkManager and greetd for reboot and does not automatically reboot or restart your active greeter.

## Optional cache for repeated tests

VM tests can reuse the host's local mirror instead of fetching large downloads repeatedly. This is an explicit alternative to the default online workflow:

```bash
sudo ./setup.sh --asset-url http://YOUR_CACHE_HOST:PORT/assets
```

Alternatively, pass `--asset-dir /path/to/assets`. These options select the pinned shell archives and signed browser files described by the manifests. Checksums and Snap assertion validation remain mandatory. Cache configuration controls shell/browser artifacts only; APT continues using the target's configured package sources. See [local mirror instructions](local-mirror.md) for the host test cache.
