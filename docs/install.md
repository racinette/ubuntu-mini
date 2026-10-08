# Install Ubuntu Server into free disk space

`install.sh` runs from the shell of a UEFI-booted Ubuntu 24.04.5 Server USB. It calculates a layout inside unallocated GPT space and launches the USB's Subiquity/Curtin installer. After installation and reboot, run [post-install setup](post-install-setup.md) separately.

The helper preserves every existing partition without inspecting its operating system. It never shrinks, deletes or reuses one. A previously created but unformatted partition is occupied space. Free the intended space explicitly before starting; the helper contains no cleanup operation.

On the disk recorded in your dual-boot handoff, p5–p7 already occupy the intended Ubuntu region. They must be explicitly reclaimed before this free-space-only helper can use that region. The recorded region is approximately 210 GiB, so a `250G` request would be refused even after reclamation; omit `--size` or request a smaller allocation.

## Run from the live installer

Boot the Ubuntu Server USB, open another console with Ctrl+Alt+F2, and establish networking. Run the helper before confirming storage changes in the interactive installer. Download the standalone file or clone the repository:

```bash
curl -fL https://raw.githubusercontent.com/racinette/ubuntu-mini/main/install.sh -o install.sh
sudo sh ./install.sh --check
sudo sh ./install.sh
```

The file contains its own Python implementation; it needs no other repository files. The live Server environment supplies Python, YAML support and installer tools.

Without `--size`, it uses the largest suitable contiguous free region. With a size, it reserves exactly that total allocation, rounded down to a MiB, and leaves the rest free:

```bash
sudo sh ./install.sh --disk /dev/nvme0n1 --size 200G --check
sudo sh ./install.sh --disk /dev/nvme0n1 --size 200G
```

`G` and `GiB` mean 1024³ bytes; `GB` means 1000³ bytes. The minimum is 16 GiB. A region gets a 1 GiB FAT32 ESP, a 2 GiB ext4 `/boot`, and LUKS-encrypted ext4 root in the remainder. There is no LVM or swap allocation. Separate gaps are never added together to satisfy a request.

Automatic selection requires exactly one eligible disk. Use `--disk` if more than one qualifies. Read-only disks, removable/USB disks, mounted filesystems, active mappings and swap are excluded. Existing GPT is required; the helper does not initialize blank disks or convert MBR.

The script prompts for hostname (default `koolaid`), username (default `andy`), account password and encryption passphrase. It prints the disk identity, original partition table and new allocation, then requires `INSTALL` before launching. `--check` performs only inventory and planning, without collecting secrets or changing files or disks.

OpenSSH is installed with account-password login enabled. Supplying public keys through `--credentials-file` disables SSH password login; the account password still works locally and for `sudo`.

## Installer execution and logs

The helper validates its generated configuration with the bundled Subiquity schema and stages the complete launcher before handing control to an independent `ubuntu-mini-install` service. That service stops the idle interactive installer, saves its session under `/run/ubuntu-mini-install/previous-session`, and launches a fresh server with Curtin storage version 2 explicitly selected. The handoff continues even if the original shell closes. Curtin creates partitions and installs the standard Ubuntu Server system from the USB. Existing partition entries are included as preserved objects, including entries physically after the new partitions.

Version 24.04.5 of Subiquity is required. Installer refresh is disabled to keep execution consistent with the tested version. The preflight refuses an installer that has already begun installation. Do not use the interactive storage screen while the helper is running.

After confirmation, a local-console invocation opens a dedicated progress viewer on Ctrl+Alt+F3 (F4 when started from F3) and switches there automatically. SSH invocations show the viewer in the current terminal. The viewer prints stage changes, recent Curtin output and a heartbeat every 15 seconds during quiet steps. It reports a failed or unexpectedly stopped service explicitly. `--no-follow` is available for background automation.

Reconnect to progress or inspect status from another shell:

```bash
sudo sh ./install.sh --follow
sudo sh ./install.sh --status
sudo journalctl -b -u ubuntu-mini-install --no-pager -n 30
```

Ctrl+C leaves the viewer without stopping installation. The journal contains launch and service events; the viewer also reads `/var/log/installer/curtin-install.log`, because not all installer progress appears in the journal.

The installer configures `crypttab`, filesystem mounts, initramfs and signed Ubuntu EFI boot files on the new ESP. It registers Ubuntu's boot entry and leaves other operating systems available through the firmware boot menu. It does not mount other ESPs or generate operating-system-specific GRUB menu entries.

Successful installation triggers a reboot; remove the USB and unlock Ubuntu with the encryption passphrase. If the boot screen is blank, Ctrl+Alt+F1 can reveal the text unlock prompt. Installation verification and the storage plan are retained under `/var/log/installer/ubuntu-mini-*` on the installed system. If a step fails, inspect the logs and start a fresh USB session before retrying. A failure after disk writes may leave new partitions occupying the chosen region; inspect them and explicitly reclaim only the unwanted Ubuntu partitions before retrying. If the launch failed before partitioning, no reclamation is needed. The new version refuses leftover configuration from either the earlier helper or the current one; reboot into a fresh USB session and run `--check` before retrying.

## Local mirrors and unattended credentials

Use a mirror accessible from the live environment. QEMU's `10.0.2.2` address is for VM tests only; a physical device needs your host's LAN address.

The project test mirror binds to host loopback. A physical device needs a separately configured LAN-accessible mirror or a tunnel/forwarder to that service; substituting the LAN address alone does not expose it. The VM harness supplies both mirror flags automatically. A direct `install.sh` invocation without these flags uses Ubuntu's upstream repositories.

```bash
sudo sh ./install.sh --mirror http://MIRROR_HOST:43385/ubuntu \
  --security-mirror http://MIRROR_HOST:43385/ubuntu-security
```

For locally controlled automation, `--credentials-file` accepts a root-owned regular JSON file with mode 600. Fields are `hostname`, `username`, `login_password`, `luks_passphrase` and optionally `ssh_authorized_keys` (a list of public keys). `--yes` skips the final confirmation. Keep this file out of Git and delete your input copy when finished; the helper does not delete a file you supplied.

The encryption passphrase lives in a mode-600 key file inside a mode-700 directory under `/run`. Generated YAML contains its path rather than its contents. The target's `crypttab` uses `none`, requiring the passphrase at boot. Success and installer-error hooks remove the temporary key; reboot clears the live RAM filesystem. The account password is hashed locally before entering the configuration.

## Validation

Run `python3 tests/check-install-plan.py` for planner checks and `python3 tests/check-install-launch.py` for independent launch, progress and failure checks. See [VM testing](testing.md) for the installation harness and current results. A synthetic preservation test cannot establish Windows bootability or BitLocker behavior on physical firmware. Keep a backup and locally available recovery credentials for the operating systems already on the target disk.
