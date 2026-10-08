# Ubuntu post install setup

Manually install Ubuntu 24.04 Server amd64, create your normal user, and boot into that installed system. Then run the standalone setup to add Sway, greetd, Foot, Firefox, desktop services, Bash with ble.sh and local Atuin history. It also installs Ubuntu's supported HWE kernel, firmware, AMD microcode, Mesa graphics/video packages and ALSA device profiles. The setup uses your existing account and password and activates the configured environment on your next reboot.

Partition selection and LUKS encryption belong to your manual Ubuntu installation. Choose the intended Linux space, preserve Windows and Recovery, and reuse the existing EFI partition without formatting. The setup does not create encryption or partition disks. Physical screen orientation, touch mapping and hardware behavior still need validation on the WIN Mini.

## Clone and run

Publish the project sources to your GitHub repository. On the installed Ubuntu system, run from your normal account:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git mini-os
cd mini-os
sudo ./setup.sh --check
sudo ./setup.sh
sudo reboot
```

Replace the URL with your repository. The repository contains scripts, configuration and small version/checksum manifests. Application archives, binaries, ISO images, VM disks and private test state stay outside Git; `.gitignore` excludes them. Keep the root `setup.sh` and the complete `setup/` directory together, because the entry point reads its configuration relative to its own location. The `tests/` and `docs/` components are not read or installed by setup.

`sudo` supplies your existing username. When invoking from a root shell instead, pass `--user YOUR_USERNAME`. `--check` checks the target prerequisites without installing packages, downloading applications or writing configuration. It verifies a cache only when one is explicitly selected; an online check does not prove package or upstream connectivity.

Normal setup downloads Ubuntu packages through the target's existing APT sources and installs Firefox from the Snap Store's stable channel. Snap handles its signed runtime dependencies. Atuin and ble.sh are downloaded to temporary directories from the URLs in `setup/shell/artifacts.json` and must match the recorded SHA-256 checksums before installation. The ble.sh nightly URL can change upstream: a checksum mismatch stops setup; update and test the version/checksum manifest before accepting a different release.

Working internet connectivity is required for normal setup. No application bundle is transferred with the clone. APT sources are retained, and setup does not embed a VM host address.

After reboot, enter your LUKS passphrase if you configured encryption, then log in using your existing account password. Super+Enter opens Foot, Super+D opens the application launcher, Super+B opens Firefox, Super+E opens Thunar, Super+1 through Super+4 switch workspaces, and Super+L locks the session. The configuration uses Bash and local-only Atuin without requiring an account.

Setup also installs [gamepad desktop navigation](gamepad-controls.md): triggers hold Shift/Ctrl, bumpers change workspaces, the D-pad sends arrows, and sticks focus/move/resize windows. Start opens a terminal; Select opens the window picker; Menu opens the launcher. Button actions fire on release. [V1 typing chords](gamepad-chord-layout.md) combine the D-pad and face buttons to type US keyboard letters, digits and punctuation; release the whole combination to emit one key. D-pad arrows also wait for release. Hold Start+Select together, then release both, or press Super+Ctrl+G to toggle normal gamepad input for games. Personal overrides in `~/.config/mini-os/gamepad.json` are preserved across setup reruns. The mapping has [VM acceptance tests](testing.md#gamepad-tests); actual WIN Mini controls still need verification.

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
