# ubuntu-mini

Ubuntu installation and desktop setup for the GPD WIN Mini.

Install Ubuntu 24.04 Server amd64, then run `setup.sh` to configure Sway, Firefox, networking, desktop services and Bash with ble.sh and local Atuin history. The optional standalone [installation helper](docs/install.md) runs from the Server USB shell and instructs the official installer to use only unallocated GPT space. Hardware behavior still needs validation on the WIN Mini.

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/racinette/ubuntu-mini.git ubuntu-mini
cd ubuntu-mini
sudo ./setup.sh --check
sudo ./setup.sh
sudo reboot
```

Clone as your normal user and run setup through `sudo`. The repository contains source and configuration; Ubuntu packages and applications download during setup. See the [installation instructions](docs/post-install-setup.md) for prerequisites, logs, reruns and optional caching.

## Repository components

| Path | Purpose |
| --- | --- |
| `setup.sh` | Root entry point for device setup |
| `install.sh` | Optional live-USB installer for encrypted Ubuntu in free space |
| `setup/base/` | Setup coordinator and kernel/firmware package list |
| `setup/desktop/` | Desktop provisioning, services, gamepad mapper and configuration |
| `setup/shell/` | Shell provisioning, verified download manifest and user defaults |
| `tests/` | Host checks, disposable VM control, local mirror and acceptance tests |
| `tests/fixtures/` | Synthetic controller, browser pages and shell/input fixtures |
| `docs/` | Setup, controls, test instructions and remaining acceptance checks |

Installed desktop commands and configuration directories retain their `mini-os` names so setup reruns continue to use existing personal settings.

Only `setup.sh` and `setup/` are needed for post-install device setup. `install.sh` is a standalone file used earlier in the live USB environment. Tests run separately and are not installed by setup. `tests/vm.py` supports manual VM installation; `tests/test-install-vm.py` tests the optional installer helper on disposable virtual disks.

- [Gamepad navigation and customization](docs/gamepad-controls.md)
- [Gamepad chord typing layout](docs/gamepad-chord-layout.md)
- [Run tests and inspect validation results](docs/testing.md)
- [Reuse downloads through the local mirror](docs/local-mirror.md)
- [Remaining validation and hardware checks](docs/validation-plan.md)

ISO images, VM disks, firmware variables, credentials, mirror content and test reports stay under ignored local paths. Documentation links into `.local/` refer to private evidence unavailable in a fresh clone. Retained VM results describe the source revision tested; restructuring the repository does not update installed VM sources.
