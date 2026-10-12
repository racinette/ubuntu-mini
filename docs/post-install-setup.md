# Minion setup on Ubuntu

Install Ubuntu 24.04 Server amd64 manually or with the [installation helper](install.md), create your normal user, and boot into that installed system. Then run the standalone setup to add Sway, greetd, Foot, Firefox, desktop services, development toolchains, Docker, coding CLIs, Bash with ble.sh and local Atuin history. It also installs Ubuntu's supported HWE kernel, firmware, AMD microcode, Mesa graphics/video packages and ALSA device profiles. The setup uses your existing account and password and activates the configured environment on your next reboot.

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

Normal setup downloads Ubuntu packages through the target's existing APT sources and installs Firefox from the Snap Store's stable channel. Snap handles its signed runtime dependencies. Atuin and ble.sh are downloaded to temporary directories from the URLs in `setup/shell/artifacts.json` and must match the recorded SHA-256 checksums before installation. Mihomo uses the version/checksum manifest in `setup/proxy/artifacts.json`; a matching installed binary is retained. The ble.sh nightly URL can change upstream: a checksum mismatch stops setup; update and test the version/checksum manifest before accepting a different release.

Working internet connectivity is required for normal setup. No application bundle is transferred with the clone. APT sources are retained, and setup does not embed a VM host address.

Setup also installs and enables [Handheld Daemon power controls](power-controls.md), with verified, pinned daemon and UI releases. Open **Handheld Daemon** from Super+D or run `minion-hhd-ui`. Initial power overrides are disabled until explicitly enabled in its interface; Minion's controller mapper remains in charge of input. Actual TDP/GPU controls, kernel-module signing and suspend behavior need testing on the 2023/7840U handheld.

After reboot, enter your LUKS passphrase if you configured encryption, then log in using your existing account password. Super+Enter opens Foot, Super+D opens the application launcher, Super+B opens Firefox, Super+E opens Thunar, Super+1 through Super+4 switch workspaces, and Super+L locks the session. The configuration uses Bash and local-only Atuin without requiring an account.

Work through the [device checklist](device-checklist.md) after installation. It includes touchscreen mapping, HHD and temperature checks, controller behavior, suspend, networking, proxy access and development tools.

## Coding CLIs

Ordinary `sudo ./setup.sh` installs **Codex** (`codex`), **Claude Code** (`claude`) and **Cursor Agent** (`agent`) for the selected desktop account. Their official native installers run as that user, with the correct home directory and no root credentials or tool settings inherited. Their native installers are independent of the development Node.js/npm installation. Setup installs Git, curl, certificates, ripgrep, `xdg-utils` for opening browser sign-in links, and the bubblewrap/socat packages used by Claude's optional Linux sandbox; it leaves tool permissions and sandbox settings at upstream defaults.

These tools follow their publishers' current release channels: Codex's latest release, Claude's stable channel and Cursor's current CLI release. Their HTTPS bootstrap scripts are downloaded completely before execution; these are upstream installers, not Minion-pinned artifacts. Upstream installers handle their payload downloads and integrity checks where provided. Executable commands already found in `~/.local/bin` or the standard system binary directories are retained without launching them, because even a version check can rewrite upstream settings. Newly installed commands are checked with `--version`. Minion does not reset account or personal tool settings.

Open a new Foot terminal after setup. Minion's Bash integration adds `~/.local/bin` to PATH. Check installation with:

```bash
codex --version
claude --version
agent --version
```

Launch `codex`, `claude` or `agent` as your normal user and follow that tool's sign-in prompts. Setup does not sign in, transfer credentials or start model sessions. Each tool needs its own supported account or API access. Native installations can update through their upstream mechanisms; rerunning Minion setup retains an existing installation.

Minion's interactive Bash profile exports `CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT=1`. With Foot 1.16.2, extended keyboard events caused duplicate Enter, gamepad A and Backspace actions in Codex; disabling enhancement resolved them on the device and survived reboot. Codex uses ordinary terminal input with this workaround, so some extended key combinations may be unavailable. After upgrading the terminal or Codex, test without it using `env -u CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT codex`. A fresh terminal picks up the default after setup or a rerun.

Official installation instructions: [Codex](https://learn.chatgpt.com/docs/codex/cli), [Claude Code](https://code.claude.com/docs/en/setup), [Cursor Agent](https://cursor.com/docs/cli/installation).

Setup seeds `/etc/codex/config.toml` from `setup/agents/codex.toml` with `tui.mouse_scroll_speed = 3.0`, tested with Codex CLI 0.162.1 to make controller scrolling comfortable on the WIN Mini. Existing system configuration is retained on reruns. Personal settings in `~/.codex/config.toml` take precedence over these defaults, following [Codex's configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic#configuration-precedence). Restart Codex after changing the setting.

## Development environment

Ordinary `sudo ./setup.sh` preinstalls the following for your desktop account. Fresh installations resolve the **latest stable releases at setup time**, then install the actual runtimes and tools. There is no first-use compiler download. Node follows the current release rather than the older LTS branch; prereleases/nightlies are not requested.

| Area | Installed | Version manager / source |
| --- | --- | --- |
| Go | Go, gopls, Delve (`dlv`) | mise; official Go releases and Go modules |
| JavaScript / TypeScript | Node, bundled npm, pnpm, `tsc`, TypeScript language server | mise; official releases and npm |
| Rust | Stable rustc/Cargo, rustfmt, Clippy, rust-analyzer, rust-src | rustup |
| Python | Current CPython, uv/uvx, Ruff, Pyright | uv-managed Python and tools; mise for Pyright |
| Build tools | Current CMake and Ninja | mise |
| Other tools | Neovim, GitHub CLI, Git LFS, ShellCheck, shfmt, jq | mise |
| Containers | Docker Engine/CLI, containerd, Buildx, Compose plugin | Docker's signed Ubuntu stable repository |

Ubuntu packages provide the native build prerequisites (`build-essential`, Make, pkg-config, OpenSSL/libffi and common Python build headers), GDB, strace, tmux, rsync and archive utilities. These OS dependencies follow Ubuntu's supported package versions; the Go, Rust, Node and Python toolchains above are installed separately from Ubuntu's runtime packages. Ubuntu's `/usr/bin/python3` is retained for OS services; the development `python` and `python3` commands live in your account. Conda/Miniforge is optional and is not installed by default alongside uv.

Open a new terminal after setup. Bash activates mise automatically, includes Cargo's commands and uses uv's user-local Python. All per-user downloads, installers and builds run without root privileges. HTTPS bootstrap scripts for mise, uv and rustup are downloaded completely before execution. These follow upstream channels rather than the project's pinned desktop artifact manifest. mise uses its registry/backends and their upstream integrity checks.

```bash
go version
rustc --version
node --version
pnpm --version
tsc --version
python --version
uv --version
docker compose version
```

mise records exact initial versions in `~/.config/mise/config.toml`. To select a version for one project, run inside that project's directory:

```bash
mise use node@24          # installs it and writes mise.toml
mise use go@latest
mise ls                  # shows selected and installed versions
```

Bash switches when you enter a project with a trusted mise configuration. For an existing checkout, review its configuration, run `mise trust` if prompted, then `mise install`. Existing `.nvmrc`/`.node-version` support can be enabled with `mise settings add idiomatic_version_file_enable_tools node`. For scripts, CI and editor subprocesses that do not run interactive Bash, use `mise exec -- COMMAND`. Do not use sudo with mise, rustup, uv or project package managers.

Python projects should use isolated dependencies:

```bash
uv init
uv add --dev pytest debugpy
uv run python
# In an existing project requiring another interpreter:
uv python install 3.12
uv python pin 3.12
uv sync
```

The global TypeScript compiler and language tools work immediately. Add TypeScript, ESLint, Prettier and test runners as project development dependencies when a repository needs them, so its lockfile determines their versions. Rust projects can select a toolchain through `rust-toolchain.toml`; rustup downloads additional versions on request.

Docker starts at boot. Setup adds your account to the `docker` group; **log out and back in (or reboot)** before using it without sudo. This group grants root-equivalent access to the machine. Use `docker compose` rather than the legacy `docker-compose` executable. Setup retains daemon configuration, images, containers and volumes, and does not explicitly restart an already running Docker service. APT upgrades to Docker packages may restart it. An existing conflicting runtime package or different Docker APT source makes setup stop with an explanation rather than removing it automatically.

Reruns retain existing mise/uv/rustup installations and your global mise tool selections, installing missing defaults and any selected-but-missing tools. They ensure the stable Rust toolchain and latest uv-known stable Python are present without replacing an existing Rust default or user-local Python default. They retain an existing Ruff command. They do not upgrade every pinned mise tool automatically. To deliberately refresh the installed environment as your normal user:

```bash
mise self-update
mise upgrade
rustup update stable
uv self update
uv python install --default cpython  # deliberately select the newest Python as default
uv tool upgrade ruff
```

Docker updates come through APT. Project versions and lockfiles remain your responsibility. Initial installed mise versions and rustup state are recorded in the setup log. Development downloads are not covered by `--asset-dir`/`--asset-url`.

Upstream guides: [mise](https://mise.jdx.dev/getting-started.html), [rustup](https://rust-lang.org/tools/install/), [uv Python](https://docs.astral.sh/uv/guides/install-python/), [Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

## Desktop controls

On external power, the desktop stays on and does not lock or blank automatically while the lid is open. On battery, idle locking occurs after five minutes and displays turn off after ten. Closing the lid locks and suspends on either power source, including when docked. Plugging or unplugging is detected within about two seconds; unplugging starts fresh battery idle timers. Super+L still locks on either power source, and explicit suspend still locks before sleeping. Connecting a charger does not unlock an already locked session. Setup installs the lid policy through `/etc/systemd/logind.conf.d/60-minion-power.conf`; reboot after setup to activate it.

The bottom bar shows the HHD power target, available temperatures, Wi-Fi signal, output volume/mute, proxy service state, battery, Window/Workspace stick mode and date/time. Click Wi-Fi to see the connected network name. A keyboard layout indicator appears when multiple layouts are configured; it prefers physical keyboards over the gamepad's virtual keyboard. The compact battery display uses `73% ↑` for charging, `↓` for discharging, `Full` for a full battery and `Idle` when connected but not charging. The battery indicator is hidden when no readable system battery is detected; peripheral batteries are excluded.

Battery, audio, layout and stick mode refresh every second; power, temperatures, Wi-Fi and proxy state refresh every five seconds. Wi-Fi uses cached readings without requesting scans. `Proxy ON` means the system service is active, rather than proving internet connectivity. Unavailable Wi-Fi/audio/proxy readings show `?` without stopping the bar. These indicators use the packages already installed by setup.

The power block shows `Auto` with HHD TDP overrides disabled, or a configured target such as `Limit 15W`; this is not measured power consumption or hardware readback. `Power ?` means HHD cannot be queried or its backend is not ready. Click it to open HHD; right-click for an explanation. Temperature summaries can show `CPU65° GPU58° SSD40° Bat32°`, omitting missing measurements. `Ctl` identifies the CPU cooling-control reading when die temperature is unavailable. Click temperatures for every readable channel, including GPU junction, SSD internal and other kernel sensors. All temperatures are Celsius. See [power and temperature details](power-controls.md#bottom-bar).

Setup also installs [gamepad desktop navigation](gamepad-controls.md): triggers hold Shift/Ctrl, bumpers change workspaces, the D-pad sends arrows, and sticks focus/move/resize windows. Start opens a terminal; Select opens the window picker; Menu opens the launcher. X is immediate, holdable Backspace; other discrete controls act on release. [D-pad + Y/A/B shortcuts](gamepad-chord-layout.md) perform editing, text navigation and desktop actions; use the physical QWERTY keyboard for typing. Hold Start+Select together, then release both, or press Super+Ctrl+G to toggle normal gamepad input for games. Personal overrides in `~/.config/minion/gamepad.json` are preserved across setup reruns. The mapping has [VM acceptance tests](testing.md#gamepad-tests); actual WIN Mini controls still need verification.

L3 opens a persistent shortcut legend; B/Escape or another L3 tap dismisses it. R3 switches the right stick between resizing and text selection, waiting for neutral before switching. Selection sends Shift+arrows, with R2 adding Ctrl; the bar shows the current mode. Up+A closes the focused window, Left+A toggles fullscreen, and editing shortcuts include terminal-aware copy/paste. Old character-typing personal profiles must be replaced with the new shortcut layout; setup performs no migration.

## Screen size and Fn keys

The desktop defaults to 2× output scaling for the WIN Mini's 7-inch 1920×1080 panel. This enlarges controls and text together, with a 960×540 logical workspace. It does not change the console, encryption prompt or text login greeter. For a smaller desktop UI, add `output * scale 1.5` to `~/.config/sway/minion.conf` and press Super+Shift+C. Personal output settings are loaded after the defaults. External monitors also inherit 2× unless overridden, for example `output HDMI-A-1 scale 1`; use `swaymsg -t get_outputs` to find the actual output name.

The WIN Mini touchscreen (`8746:65521:ILTP7807:00_222A:FFF1`) is explicitly mapped to the built-in `eDP-1` output. On the device, missing this association caused Firefox taps to miss controls; the mapping restored single-tap activation at the center and all four corners, including after reboot. It leaves calibration and display rotation unchanged. If your hardware reports different identifiers, inspect `swaymsg -t get_inputs` and `swaymsg -t get_outputs`, then override the mapping in `~/.config/sway/minion.conf`.

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

Setup also installs the headless proxy runtime. To use it, privately configure your subscription with `sudo python3 setup/proxy/manage.py configure` from the repository, then explicitly enable its service. Rerunning ordinary setup updates it and preserves its configuration and activation state. See [proxy setup](proxy.md).

Every applied run saves `setup.log`, `result.json` and `configuration-before.tar.gz` under `/var/lib/minion/setup/TIMESTAMP/`. These directories are private to root. `/var/lib/minion/setup/last-success.json` identifies the last successful run. A failure prints the log path and returns nonzero; inspect the log, resolve the problem and rerun the same command.

Reruns preserve existing Atuin and Foot user settings and avoid duplicating the Bash include. An existing Firefox installation is retained instead of reverting its revision. System configuration owned by this setup is reapplied; a backup records its prior contents. Existing personal Sway configuration is honored. Add layouts, scaling and output preferences in `~/.config/sway/minion.conf`; this file is not generated or overwritten by setup. For example:

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
