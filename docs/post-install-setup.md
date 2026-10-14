# Minion setup on Ubuntu

Install Ubuntu 24.04 Server amd64 manually or with the [installation helper](install.md), create your normal user, and boot into that installed system. Then run the standalone setup to add Sway, greetd, Foot, Firefox, Chromium, desktop services, development toolchains, Docker, coding CLIs, Bash with ble.sh and local Atuin history. It also installs Ubuntu's supported HWE kernel, firmware, AMD microcode, Mesa graphics/video packages and ALSA device profiles. The setup uses your existing account and password and activates the configured environment on your next reboot.

Partition selection and LUKS encryption happen during Ubuntu installation. The optional helper creates a separate Ubuntu ESP in free space; when installing manually, choose the intended Linux space and preserve Windows, Recovery and their existing EFI files. The setup does not create encryption or partition disks. Core behavior has been checked on the WIN Mini; use the [current validation status](validation-plan.md) to distinguish completed device checks from remaining coverage.

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

Normal setup downloads Ubuntu packages through the target's existing APT sources and installs Firefox and [Canonical's Chromium](https://snapcraft.io/chromium) from the Snap Store's stable channel. Snap handles their signed runtime dependencies. Chromium opens from the application launcher (Super+D) or the `chromium` command; Super+B continues to open Firefox. Atuin and ble.sh are downloaded to temporary directories from the URLs in `setup/shell/artifacts.json` and must match the recorded SHA-256 checksums before installation. Mihomo uses the version/checksum manifest in `setup/proxy/artifacts.json`; a matching installed binary is retained. The ble.sh nightly URL can change upstream: a checksum mismatch stops setup; update and test the version/checksum manifest before accepting a different release.

Setup seeds `~/.chromium-browser.init` with `--no-first-run --no-default-browser-check`, preventing Chromium's unbranded first-run terms placeholder from blocking normal windows or external links. Existing personal startup settings are preserved. The proxy launcher also passes these flags explicitly.

Setup seeds Firefox first, with Chromium as the fallback, for HTTP/HTTPS links and HTML files in `~/.config/mimeapps.list`. Existing explicit defaults are preserved on reruns. The proxy dashboard opens Chromium directly, independently of this preference.

The Chromium Snap includes a matching driver at `/snap/bin/chromium.chromedriver`. For WebDriver, set the browser binary to `/snap/chromium/current/usr/lib/chromium-browser/chrome`; launching `/snap/bin/chromium` from inside the confined driver failed in the device check. Use a separate automation profile under `~/snap/chromium/common/` and `--headless=new` when no window is needed. This combination passed page navigation and JavaScript execution with the browser sandbox enabled. Direct `chromium --headless=new --dump-dom URL` also works. Ordinary desktop launches continue to use `chromium`.

Working internet connectivity is required for normal setup. No application bundle is transferred with the clone. APT sources are retained, and setup does not embed a VM host address.

On the WIN Mini 2023 (`GPD` / `G1617-01`), setup also supplies `bmi260-init-data.fw` if Ubuntu's firmware package has not supplied it. The in-tree `bmi270_i2c` driver requires this file for the gyro/accelerometer. The firmware and its BSD license are downloaded from a pinned linux-firmware revision and verified against `setup/desktop/firmware.json` before installation. Existing plain or compressed firmware is retained. This conditional download is independent of the shell/browser cache; `--check` reports whether it is needed without downloading. Normal setup leaves driver activation to the next boot and does not enable gyro controls or automatic screen rotation.

Setup also installs and enables [Handheld Daemon power controls](power-controls.md), with verified, pinned daemon and UI releases. Open **Handheld Daemon** from Super+D or run `minion-hhd-ui`. Initial power overrides are disabled until explicitly enabled in its interface; Minion's controller mapper remains in charge of input. Startup, signing-key enrollment, module loading and selected AC/battery power profiles passed on the 2023/7840U handheld; not every GPU or power-control combination has been tested.

After reboot, enter your LUKS passphrase if you configured encryption, then log in using your existing account password. Super+Enter opens Foot, Super+D opens the application launcher, Super+B opens Firefox, Super+E opens Thunar, Super+1 through Super+4 switch workspaces, and Super+L locks the session. The configuration uses Bash and local-only Atuin without requiring an account.

Work through the [device checklist](device-checklist.md) after installation. It includes touchscreen mapping, HHD and temperature checks, controller behavior, suspend, networking, proxy access and development tools.

## Memory and swap

When no swap is already active or configured in `/etc/fstab`, setup creates a
private `0600` swapfile at `/var/lib/minion/swapfile` and adds its boot entry.
Its size is half physical RAM, with a 1 GiB minimum and an 8 GiB cap; the WIN
Mini uses 8 GiB. This supplies a disk-backed fallback during memory pressure.
On the device's LUKS root filesystem, the file is encrypted with the rest of root.

Existing swap policies and sizes are retained. Automatic file creation supports
ext4/XFS and leaves at least 2 GiB free; other filesystems or insufficient space
are reported without allocating a file. An unexpected existing file is refused.
Reruns retain the file and boot entry. This does not configure hibernation or
change swappiness, lid-close behavior or kernel resume parameters.

Check with `swapon --show`, `free -h` and
`systemctl status var-lib-minion-swapfile.swap`. To apply only this component,
run `sudo /usr/bin/python3 setup/base/swap.py`; add `--check` for a read-only plan.
The implementation follows util-linux's [swapfile guidance](https://man7.org/linux/man-pages/man8/swapon.8.html#NOTES), using fully written blocks rather than a sparse file.

## Clock and night light

Setup enables network time synchronization. When the existing timezone is UTC,
it selects `Europe/Minsk` (UTC+3); an existing non-UTC timezone is retained. Change
it later with `sudo timedatectl set-timezone REGION/CITY`. The status bar picks
up timezone changes automatically. The hardware clock remains in UTC.

Open **Night light** from Super+D to choose **Automatic (sunset to sunrise)**,
**Warm now**, or **Off**. Automatic is the default: Gammastep gradually changes
from 6500K during the day to 4500K at night using Minsk's sun position. It works
locally without a location service. The chosen mode persists across logins.
The same controls are available as `minion-night-light auto`,
`minion-night-light on`, and `minion-night-light off`; `status` prints the mode.

Edit `~/.config/gammastep/config.ini` to change temperatures, latitude/longitude
when travelling, or set explicit `dawn-time` and `dusk-time` intervals instead
of solar timing. Run `systemctl --user restart minion-night-light.service` after
editing. Setup seeds the configuration when absent and preserves it on reruns.
The service follows the graphical session; Off releases the screen's color
adjustment. Backlight brightness remains controlled by the brightness keys.

## Authentication caching

Sudo remembers successful authentication for **15 minutes**, shared across the
selected desktop account's terminals and processes. Setup installs a validated,
account-specific `/etc/sudoers.d/60-minion-auth-USERNAME` policy; it changes cache
scope and lifetime while retaining the account's existing command permissions.
Run `sudo -k` to invalidate the shared cache immediately.

The desktop runs one OpenSSH agent through `minion-ssh-agent.service`. On first
SSH/Git use, unlock the key normally; `AddKeysToAgent 1h` keeps it in the agent
for **one hour from loading**, after which the next use needs the passphrase
again. Using a key does not restart that hour. Logout/reboot stops the desktop
agent and clears its loaded keys. No passphrase is written into the configuration.

Setup appends a `Host *` include to `~/.ssh/config` and seeds `~/.ssh/minion.conf`.
Earlier personal host options take precedence; an edited Minion SSH defaults
file is retained on reruns. `IdentityAgent` points SSH/Git to the shared socket,
including from already running terminals without `SSH_AUTH_SOCK`. New shells
also export that socket for `ssh-add`. In an existing shell, run:

```bash
export SSH_AUTH_SOCK="/run/user/$UID/minion-ssh-agent/socket"
ssh-add -l                    # List loaded keys
ssh-add -D                    # Clear loaded keys when desired
```

The service's default key lifetime is one hour as well. To inspect it, run
`systemctl --user status minion-ssh-agent.service`. These defaults follow
[sudo's timestamp controls](https://www.sudo.ws/docs/man/sudoers.man/) and
[OpenSSH's agent settings](https://man.openbsd.org/ssh_config.5#AddKeysToAgent).

## Coding CLIs

Ordinary `sudo ./setup.sh` installs **Codex** (`codex`), **Claude Code** (`claude`) and **Cursor Agent** (`agent`) for the selected desktop account. Their official native installers run as that user, with the correct home directory and no root credentials or tool settings inherited. Their native installers are independent of the development Node.js/npm installation. Setup installs Git, curl, certificates, ripgrep, `xdg-utils` for opening browser sign-in links, bubblewrap for Linux sandboxing, and socat for Claude's optional Linux sandbox; it leaves tool permissions and sandbox settings at upstream defaults.

On Ubuntu 24.04, setup also installs `apparmor-profiles` and `apparmor-utils`, copies Ubuntu's `bwrap-userns-restrict` profile into `/etc/apparmor.d/` if absent, and loads it immediately when AppArmor is active. Existing profile edits are retained; the system restriction on unprivileged user namespaces remains enabled. This follows the [official Codex sandbox prerequisites](https://learn.chatgpt.com/docs/sandboxing#prerequisites) and fixes `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. The profile loads on later boots without needing the checkout. A basic diagnostic is `codex sandbox -- /bin/true`; it should exit successfully without a model request or sign-in.

These tools follow their publishers' current release channels: Codex's latest release, Claude's stable channel and Cursor's current CLI release. Their HTTPS bootstrap scripts are downloaded completely before execution; these are upstream installers, not Minion-pinned artifacts. Upstream installers handle their payload downloads and integrity checks where provided. Executable commands already found in `~/.local/bin` or the standard system binary directories are retained without launching them, because even a version check can rewrite upstream settings. Newly installed commands are checked with `--version`. Minion does not reset account or personal tool settings.

Open a new Foot terminal after setup. Minion's Bash integration adds `~/.local/bin` to PATH. Check installation with:

```bash
codex --version
claude --version
agent --version
```

Launch `codex`, `claude` or `agent` as your normal user and follow that tool's sign-in prompts. Setup does not sign in, transfer credentials or start model sessions. Each tool needs its own supported account or API access. Native installations can update through their upstream mechanisms; rerunning Minion setup retains an existing installation.

Setup disables automatic commit and pull-request attribution for Claude Code and Cursor Agent. It merges `attribution.commit = ""` and `attribution.pr = ""` into `~/.claude/settings.json`, and sets `attribution.attributeCommitsToAgent` and `attribution.attributePRsToAgent` to `false` in `~/.cursor/cli-config.json`. Reruns reapply these attribution preferences while retaining unrelated settings; the setup configuration backup includes both files. Restart existing CLI sessions after changing them. See [Claude attribution settings](https://code.claude.com/docs/en/settings-reference#attribution) and [Cursor CLI configuration](https://cursor.com/docs/cli/reference/configuration). Claude project or managed settings can override the user-level preference.

Minion's interactive Bash profile exports `CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT=1`. With Foot 1.16.2, extended keyboard events caused duplicate Enter, gamepad A and Backspace actions in Codex; disabling enhancement resolved them on the device and survived reboot. Codex uses ordinary terminal input with this workaround, so some extended key combinations may be unavailable. After upgrading the terminal or Codex, test without it using `env -u CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT codex`. A fresh terminal picks up the default after setup or a rerun.

Official installation instructions: [Codex](https://learn.chatgpt.com/docs/codex/cli), [Claude Code](https://code.claude.com/docs/en/setup), [Cursor Agent](https://cursor.com/docs/cli/installation).

Setup seeds `/etc/codex/config.toml` from `setup/agents/codex.toml` with `tui.mouse_scroll_speed = 3.0`, tested with Codex CLI 0.162.1 to make controller scrolling comfortable on the WIN Mini. Existing system configuration is retained on reruns. Personal settings in `~/.codex/config.toml` take precedence over these defaults, following [Codex's configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic#configuration-precedence). Restart Codex after changing the setting.

Claude Code gets `env.CLAUDE_CODE_SCROLL_SPEED = "3"` in `~/.claude/settings.json`, the same setting its `/scroll-speed` command saves. This triples the base wheel distance in its fullscreen renderer. Setup preserves a subsequently chosen multiplier and other environment settings. Restart Claude to load the default, or use `/scroll-speed` to tune it interactively; see [Claude mouse wheel scrolling](https://code.claude.com/docs/en/fullscreen#mouse-wheel-scrolling).

Cursor Agent 2026.10.01 uses the terminal's normal scrollback and exposes no wheel-speed setting. Minion's Foot defaults set `[scrollback] multiplier=9.0`, up from Foot 1.16.2's default `3.0`, to triple wheel scrolling in Cursor and ordinary terminal history. Applications handling mouse events in the alternate screen, including Codex and fullscreen Claude, keep their own wheel speed. Open a new terminal to load the Foot setting. Setup seeds `~/.config/foot/foot.ini` on fresh installations and preserves existing personal configuration on reruns.

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
| Neovim | File tree, fuzzy file/text search, code navigation and normal editing | Pinned nvim-tree, mini.nvim and nvim-lspconfig plugins; Ubuntu ripgrep |
| Audio development | SuperCollider language/server, VST3 hosting extension, JUCE SDK and editable synth example | Ubuntu SuperCollider/PipeWire JACK; pinned user-owned source builds |
| Additional language servers | Bash, JSON/HTML/CSS, YAML, TOML and C/C++ | mise for bash-language-server, vscode-langservers-extracted, yaml-language-server and Taplo; Ubuntu for clangd |
| Containers | Docker Engine/CLI, containerd, Buildx, Compose plugin | Docker's signed Ubuntu stable repository |

Ubuntu packages provide the native build prerequisites (`build-essential`, Make, pkg-config, OpenSSL/libffi and common Python build headers), GDB, strace, tmux, rsync and archive utilities. These OS dependencies follow Ubuntu's supported package versions; the Go, Rust, Node and Python toolchains above are installed separately from Ubuntu's runtime packages. Ubuntu's `/usr/bin/python3` is retained for OS services; the development `python` and `python3` commands live in your account. Conda/Miniforge is optional and is not installed by default alongside uv.

Open a new terminal after setup. Bash activates mise automatically, includes Cargo's commands and uses uv's user-local Python. All per-user downloads, installers and builds run without root privileges. HTTPS bootstrap scripts for mise, uv and rustup are downloaded completely before execution. These follow upstream channels rather than the project's pinned desktop artifact manifest. mise uses its registry/backends and their upstream integrity checks.

Run `nvim .` inside a project, `nvim /path/to/project` to browse a directory, or `nvim path/to/file` to open a file. Choose **Neovim** in the application launcher to start at home. The default `~/.config/nvim/init.lua` provides the file tree, search and language servers. Files support normal editing: `i` enters insert mode, Esc returns to normal mode, `:w` saves and `:q`/`:qa` quits a window/all windows. The editor checks for external LLM changes when focused or idle and reloads unmodified buffers.

Press **F1** for the controls: **F2** toggles the file tree, **F3/Ctrl+P** finds files, **F4/Ctrl+F** searches project text, **F5** lists file symbols, **F6** searches project symbols as you type, **Enter** or `gd` follows a definition, `gr` lists references and `K` shows documentation. A single definition opens directly; multiple definitions open a searchable picker with file paths, positions and code lines. Choose with Enter or cancel with Esc; no bottom results split opens. Project-symbol search requires a nonempty query; availability depends on the language server. **Alt+Left/Right** (gamepad B+Left/Right) moves back/forward through jump history. In normal mode, **Esc/Backspace** returns to the previous code location and **Tab** cycles open files. In the tree, D-pad arrows browse, Enter opens a file or folder, Backspace browses the parent directory and Esc closes the tree. Mouse-wheel and gamepad stick scrolling work in code windows. Picker queries use the physical keyboard, with arrows/Enter/Esc for selection.

Language servers cover Go, Rust, JavaScript/TypeScript, Python, shell, JSON, YAML, TOML and C/C++. JavaScript/TypeScript uses TypeScript 7's native language server (`tsc --lsp`). Native syntax highlighting also works for other Neovim-supported file types. Servers attach according to their project/filetype rules; Rust projects need `Cargo.toml`, and accurate C/C++ navigation benefits from the project's `compile_commands.json`. Plugins and language servers are downloaded during setup rather than first launch. The plugin manifest records exact revisions. Personal `~/.config/nvim/init.lua` settings survive setup reruns. To update only the pinned plugins and seed the default configuration after the language tools are installed, run `/usr/bin/python3 setup/development/nvim.py` as your normal user.

Audio development uses SuperCollider 3.13 from Ubuntu, the VSTPlugin 0.6.2 extension for native Linux VST3 instruments/effects, and JUCE 9.0.4 for building your own plugins with CMake/Ninja. [The manifest](../setup/development/audio-sources.json) pins the user-owned SDK sources and VST3 interfaces by commit. Setup builds the extension under `~/.local/share/SuperCollider/Extensions/VSTPlugin` and puts JUCE under `~/.local/share/minion/audio`. Downloads and builds run as the desktop user. The graphical SuperCollider IDE and Wine plugin bridge are not installed.

The editable `~/Projects/synth-lab` starter contains a real C++ VST3 instrument with MIDI, 16 voices, an envelope, Gain/Brightness parameters and host-state persistence. Its SuperCollider script loads the compiled plugin, sequences a melody/chord, changes a parameter and records the synth output. Run:

```bash
cd ~/Projects/synth-lab
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --target SynthLab_VST3 --parallel 2
pw-jack sclang -D play.scd
pw-play demo.wav
```

`pw-jack` uses the existing PipeWire session. For a terminal without a display connection, prefix the SuperCollider command with `QT_QPA_PLATFORM=offscreen`. Edit `Synth.cpp` for the instrument and `play.scd` for sequencing; stop the host before rebuilding. See the [starter README](../setup/development/synth-lab/README.md) for the VST3 bundle path and installation in other hosts. Setup retains an existing starter project, refuses modified managed SDKs/extensions and skips rebuilding an unchanged extension. To install only the user-owned tools after their Ubuntu dependencies are present, run `/usr/bin/python3 setup/development/audio.py` as your normal user.

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

**Gamepad Start** and **Super+Enter** open a new Foot terminal in the focused
Foot window's shell directory. This also works while a command or coding agent
is running in that shell. When another application is focused, or the shell's
directory cannot be determined, the new terminal starts in home. The shared
`minion-terminal` launcher passes paths directly to Foot, including spaces and
Unicode. It supports the normal standalone Foot windows installed by setup;
ambiguous shared-server clients fall back to home. Sway's focus policy is unchanged.

DejaVu Sans Mono is the terminal's main font. Noto Core provides fallback fonts
for additional scripts, symbols and musical notation; Noto Color Emoji supplies
emoji. Foot and desktop applications use Fontconfig to select these fallbacks.
After installing fonts in an existing session, open a new terminal or restart an
affected application so it can discover them. Private-use icons from Nerd Fonts
and CJK fonts are not included in this fallback set.

The WIN Mini's built-in keyboard supports English (US) and Russian typing. Press **Ctrl+Space** to switch; the bar shows **US** or **RU**. Select remains the gamepad window picker. Menus and system messages remain English. Desktop shortcuts keep the same physical keys in either layout. The physical keyboard and gamepad share a keymap so L2/R2 modifiers also work with physical typing; hold R2 and press the spacebar to switch languages. Personal layout overrides in `~/.config/sway/minion.conf` still take precedence.

Click the **Wi-Fi** text in the bar, or choose **Wi-Fi networks** from Super+D, to open the graphical network chooser. It lists nearby networks and signal strengths; select one to connect. Saved profiles are reused, and NetworkManager's existing applet handles password prompts. Refresh scans for networks; Enable Wi-Fi turns the radio on. **Saved / hidden networks** opens the connection editor for hidden networks and enterprise authentication. Right-clicking the bar's Wi-Fi text shows the current SSID. Opening the chooser alone does not change your connection.

On the GPD WIN Mini 2023 (`G1617-01`), setup seeds the internal microphone at **10% input volume**, which selects **0 dB Capture and 0 dB Internal Mic Boost** on its ALC245 codec. The initial 100% level selected +30 dB for each control and badly distorted speech during the device check. Setup writes only this internal-microphone route in `~/.local/state/wireplumber/default-routes` before the first desktop login; other audio devices and any saved microphone level are preserved. Later volume changes persist normally, and setup reruns retain them. To apply the tested level manually in an existing session, run `pactl set-source-volume alsa_input.pci-0000_63_00.6.analog-stereo 10%`, or adjust the internal microphone in `pavucontrol`.

On external power, the desktop stays on and does not lock or blank automatically while the lid is open. On battery, idle locking occurs after five minutes and displays turn off after ten. Closing the lid locks and suspends on either power source, including when docked. Plugging or unplugging is detected within about two seconds; unplugging starts fresh battery idle timers. Super+L still locks on either power source, and explicit suspend still locks before sleeping. Connecting a charger does not unlock an already locked session. Setup installs the lid policy through `/etc/systemd/logind.conf.d/60-minion-power.conf`; reboot after setup to activate it.

The WIN Mini's **L4** rear button toggles display power without locking or suspending; another L4 press or ordinary input restores the display. **R4** toggles Keep awake, suppressing automatic idle locking/display-off while background work runs. Both act once after release, including after a hold. The bar shows `Awake ON`/`Awake OFF`; click it to toggle. The override survives charger changes and service restarts and resets at reboot. Closing the lid and explicit suspend still lock and sleep. Super+L remains lock-only, and the power button is unchanged. See [rear-button controls](gamepad-controls.md) for device matching and the background-agent workflow.

These controls are also available as `minion-idle-controls off`, `on`, `toggle-awake` and `status`. The independent `minion-display-wake.service` restores display power on input and resume, including on AC and with Keep awake enabled. Display-off fails before blanking if the wake listener cannot be signaled. Normal idle policy changes are detected within about two seconds.

`minion-rear-buttons.service` reads only the dedicated WIN Mini rear keyboard and debounces its firmware macro sequences. Setup installs `/etc/udev/rules.d/60-minion-rear-buttons.rules` to grant that device to the active local user. The reader does not grab or hide the physical keyboard or controller, and ignores actions while its graphical session is inactive.

Routine notification popups expire after five seconds by default; Keep awake messages expire after 2.5 seconds. Critical alerts remain until dismissed unless the sender requests an explicit timeout. Applications' explicit timeout requests are honored. Setup seeds `~/.config/mako/config` when absent and preserves existing settings on reruns. After editing that file, run `makoctl reload`; right-click or tap a popup to dismiss it manually.

The bottom bar shows the HHD power target, available temperatures, Wi-Fi signal, output volume/mute, proxy service state, battery, both stick modes (for example `L:Scroll R:Windows`) and date/time. Click Wi-Fi to see the connected network name. A keyboard layout indicator appears when multiple layouts are configured; it prefers physical keyboards over the gamepad's virtual keyboard. The compact battery display uses `73% ↑` for charging, `↓` for discharging, `Full` for a full battery and `Idle` when connected but not charging. The battery indicator is hidden when no readable system battery is detected; peripheral batteries are excluded.

Battery, audio, layout and stick mode refresh every second; power, temperatures, Wi-Fi and proxy state refresh every five seconds. Wi-Fi uses cached readings without requesting scans. `Proxy ON` means the system service is active, rather than proving internet connectivity. Unavailable Wi-Fi/audio/proxy readings show `?` without stopping the bar. These indicators use the packages already installed by setup.

The power block shows `Auto` with HHD TDP overrides disabled, or a configured target such as `Limit 15W`; this is not measured power consumption or hardware readback. `Power ?` means HHD cannot be queried or its backend is not ready. Click it to open HHD; right-click for an explanation. Temperature summaries can show `CPU65° GPU58° SSD40° Bat32°`, omitting missing measurements. `Ctl` identifies the CPU cooling-control reading when die temperature is unavailable. Click temperatures for every readable channel, including GPU junction, SSD internal and other kernel sensors. All temperatures are Celsius. See [power and temperature details](power-controls.md#bottom-bar).

## Process and battery monitoring

Setup installs **Power Statistics** (`gnome-power-statistics`, Ubuntu package
`gnome-power-manager`) and **PowerTOP**. Power Statistics is a standalone GTK
application using the existing UPower service; it does not install a GNOME
desktop. Click the battery percentage in the bottom bar to open it with that
battery selected, or launch it from Super+D. Clicking again brings its existing
window forward, including from another workspace. Use **History**
with graph type **Rate** for power over time. Details include the estimated
time to empty while discharging, or time to full while charging. Charge graphs
and other history types are also available.

Run `sudo powertop` in a terminal for process activity, wakeups, CPU/device
statistics and power estimates. Tab/Shift+Tab switch pages; Escape quits.
Per-process/device watts are model estimates and need enough battery-only
measurements; a fresh install or charging session may show activity without
power attribution. Battery discharge rate represents total device draw;
charging rate is net power entering the battery. Runtime estimates follow the
recent workload and can change quickly. `htop`, when installed, remains useful
for ordinary CPU/memory process inspection.

Setup also installs [gamepad desktop navigation](gamepad-controls.md): triggers hold Shift/Ctrl and bumpers change workspaces. D-pad first sends arrows immediately and accelerates while held; hold A/B first, then choose a D-pad direction for a named shortcut, or hold Select before a face button for a layout toggle. Start opens a terminal; Select opens the window picker; Menu opens the launcher. X/Y provide immediate, holdable Backspace/Space; A/B singles and other discrete controls act on release. [A/B + D-pad and Select + face shortcuts](gamepad-chord-layout.md) perform editing, text navigation and desktop actions; use the physical QWERTY keyboard for typing. Hold Start+Select together, then release both, or press Super+Ctrl+G to toggle normal gamepad input for games. Personal overrides in `~/.config/minion/gamepad.json` are preserved across setup reruns. The mapping has [VM acceptance tests](testing.md#gamepad-tests); actual WIN Mini controls still need verification.

The default layout uses left-stick scrolling and right-stick window focus/move together. Sway centers the pointer in a newly selected window only when it is outside that window (`mouse_warping container`), so scrolling follows selection while preserving an existing in-window pointer position. L3 switches the left stick between scrolling and text navigation; R3 independently switches the right stick between window focus/move and resize. Each change waits only for its own stick to return to neutral; the bar shows both behaviors. L2 adds Shift for text selection and R2 adds Ctrl. Hold Menu for 0.75 seconds to open a persistent shortcut legend; a short Menu tap, B/Escape or Enter dismisses it. Menu taps otherwise toggle the launcher. Hold B then Up to close the focused window. Hold Select then A for fullscreen, B for floating, Y for tiled/tabbed, or X for split orientation. A+D-pad carries editing shortcuts; B+Left/Right navigates back/forward. X holds Backspace and Y holds Space, both with immediate press and normal repeat. Editing shortcuts include terminal-aware copy/paste. Old character-typing personal profiles must be replaced with the new shortcut layout; setup performs no migration.

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

Setup also installs the proxy runtime and a local MetaCubeXD dashboard. To use it, privately configure your subscription with `sudo python3 setup/proxy/manage.py configure` from the repository, then explicitly enable its service. Click **Proxy** in the bar or choose **Proxy dashboard** from the launcher to select servers, restore Automatic selection and test latency. Graphical selections persist across proxy restarts. Rerunning ordinary setup updates it and preserves its configuration, dashboard identity and activation state. See [proxy setup](proxy.md).

Every applied run saves `setup.log`, `result.json` and `configuration-before.tar.gz` under `/var/lib/minion/setup/TIMESTAMP/`. These directories are private to root. `/var/lib/minion/setup/last-success.json` identifies the last successful run. A failure prints the log path and returns nonzero; inspect the log, resolve the problem and rerun the same command.

Reruns preserve existing Atuin and Foot user settings and avoid duplicating the Bash include. Existing Firefox and Chromium installations retain their revisions, selected channels and browser profiles. System configuration owned by this setup is reapplied; a backup records its prior contents. Existing personal Sway configuration is honored. Add layouts, scaling and output preferences in `~/.config/sway/minion.conf`; this file is not generated or overwritten by setup. For example:

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
