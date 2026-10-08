# Ubuntu 24.04 + Windows 11 dual-boot installation: problem report and automation handoff

**Status:** Storage partitions prepared; Ubuntu **not installed**. A candidate autoinstall YAML exists, but its execution is **not validated**. No further partitioning should be necessary for the current disk layout.

## Objective

Build a **repeatable, preferably automated installation procedure** for **Ubuntu 24.04** alongside **Windows 11** on a **GPD WIN Mini** (single 512 GB NVMe SSD), with these requirements:

- Retain both operating systems on the same SSD, each with approximately half the capacity.
- **Encrypt Ubuntu root with LUKS**, ideally using a straightforward layout without LVM unless there is a compelling reason for it.
- Preserve the Windows installation and BitLocker data when possible. Reinstalling Windows is acceptable if it substantially simplifies a *repeatable* procedure, but not the preferred first step.
- Make **Ubuntu the default boot target**, with a usable choice to boot Windows (via GRUB or UEFI menu).
- Use **Ubuntu 24.04**, because compatibility with Ubuntu-specific development/build tooling (e.g., Chromium's Ubuntu-targeted instructions) matters. Do **not** solve the installer problem by silently switching to Debian or a different Ubuntu flavor.
- Start from an **Ubuntu Server installation**, then apply the intended lightweight GUI setup through the existing installation scripts. Desktop choice, DAW, autocomplete, and other unrelated system tooling are **out of scope** for this handoff.
- Automate enough that subsequent reinstalls do **not** require manually recreating partitions or improvising installer steps.
- Hostname: `koolaid`; username: `andy`. Credentials and LUKS passphrase must be supplied **locally**, never pasted into public logs or committed to source control.

## Actual disk state (observed, not proposed)

Device reported by Linux: `/dev/nvme0n1` (KBG50ZNS512GB, ~476.9 GiB / 512 GB decimal), GPT, logical sector size 512 bytes.

`sfdisk -d` output supplied by the user:

```text
label: gpt
label-id: 8EC9B0D8-D58F-4C28-B392-1B57D3D1179A
device: /dev/nvme0n1
unit: sectors
first-lba: 34
last-lba: 1000215182
sector-size: 512

/dev/nvme0n1p1 : start=        2048, size=      204800, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid=E6D1E3A6-3448-405C-98D9-5EC4C840600D, name="EFI system partition"
/dev/nvme0n1p2 : start=      206848, size=      262144, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, uuid=57A2C51A-7969-4EAB-8BD0-8EFE33683F20, name="Microsoft reserved partition"
/dev/nvme0n1p3 : start=      468992, size=   524288000, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=14B15D4B-5E65-4E81-8531-FE64DADE4869, name="Basic data partition"
/dev/nvme0n1p4 : start=   966660096, size=    33554432, type=DE94BBA4-06D1-4D40-A16A-BFD50179D6AC, uuid=B93FFBBE-56D6-4F15-AD0E-22E28823127D, name="Basic data partition", attrs="RequiredPartition GUID:63"
/dev/nvme0n1p5 : start=   524759040, size=     2097152, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid=8B5402CA-C795-48EA-B926-A3A56267E330, name="ubuntu-efi"
/dev/nvme0n1p6 : start=   526856192, size=     4194304, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=BC7744BB-51C1-4BCF-909A-0EC73B2BAAD8, name="ubuntu-boot"
/dev/nvme0n1p7 : start=   531050496, size=   433559552, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=7B5D0C97-56A6-4607-83E6-56239821781C, name="ubuntu-root"
```

`lsblk` summary at that point:

| Partition | Size | Detected filesystem | Intended role / handling |
|---|---:|---|---|
| p1 | 100 MiB | vfat | Existing **Windows ESP**, preserve unchanged |
| p2 | 128 MiB | none | Microsoft Reserved (MSR), preserve |
| p3 | 250 GiB | BitLocker | Windows system, preserve |
| p4 | 16 GiB | NTFS | Windows recovery/OEM partition, preserve |
| p5 | 1 GiB | vfat | **Ubuntu ESP**, already formatted; use for `/boot/efi` |
| p6 | 2 GiB | none | Format ext4, mount `/boot` |
| p7 | ~206.7 GiB | none | Create LUKS container, format ext4 inside, mount `/` |

**Important geometry detail:** Partition **p4 is at the end of the disk**, while p5–p7 occupy space between Windows p3 and recovery p4. Partition *numbers* are therefore not in physical disk order. The original free region was displayed by `parted unit MiB print free` as approximately **256229–472002 MiB**. We manually created p5–p7 there. Do not assume that p4 precedes p5 physically.

The new p5 ESP was initially misidentified as `msftdata`; after setting `esp` flag and formatting FAT32, Subiquity reported **"existing, unused ESP, already formatted as vfat"**. p6 and p7 remain unformatted. No Ubuntu installation or LUKS volume creation is reported as completed.

## Problems observed in Ubuntu Server's interactive installer (Subiquity)

1. **Unallocated space was not selectable.** The installer showed only existing partitions and no usable free-space row, even though `parted ... print free` confirmed ~226 GB decimal free between the Windows system and the recovery partition. Clicking the disk offered `Info`, `Reformat`, and `Use As Boot Device`, but not an option to create a partition in that gap. We created p5–p7 from the installer shell using `parted`.
2. **Creating a GPT partition is not formatting it.** `parted mkpart ... ext4/fat32` set up entries/types or hints, but did not create filesystems. The installer displayed them as `existing, unused` until formatted.
3. **The new ESP was not initially recognized.** p5 showed GPT flag `msftdata`, unlike p1's `boot, esp`. Manually setting p5 `esp` and creating a FAT32 filesystem caused the installer to recognize p5 as an ESP.
4. **Normal partition editor did not offer FAT32.** For p5, its format choices were ext4, XFS, Btrfs, and swap. EFI partition setup was not exposed like an ordinary filesystem creation step.
5. **`Use As Boot Device` selected the Windows ESP (p1), not Ubuntu's (p5).** Even after p5 was a recognized, formatted ESP, Subiquity chose p1 for `/boot/efi`. The p1 editor showed an unavailable `Unmount` action; there was no demonstrated method to select p5 instead. It has **not** been proved that the installer intrinsically requires one ESP, only that this UI/workflow selected the wrong one.
6. **No straightforward interactive path was identified to create LUKS on an existing p7 while preserving Windows.** Guided encrypted storage appears oriented toward whole-disk workflows; whether this particular installed Subiquity build can consume a manually opened LUKS mapping remains **unverified**.

The disk itself is valid GPT, Linux supports two ESPs, and separate ESPs can be independently referenced by UEFI boot entries. These observed failures are **installer-interface/workflow limitations**, not a fundamental limitation of LUKS or UEFI.

## Approaches considered and why they were not selected

- **Reinstall Windows:** Acceptable if genuinely necessary, but does not by itself solve Subiquity's LUKS/custom-ESP UI limitations.
- **Guided encrypted Ubuntu on the entire disk, then shrink to install Windows:** Technically conceivable, but shrinking an encrypted root (especially LUKS + LVM + filesystem) is operationally risky and makes future reinstalls more complex. Not recommended as a shortcut.
- **Ubuntu Desktop 24.04 installer:** More accessible ordinary dual-boot UI, but manual partitioning + LUKS support is uncertain/limited; not a confirmed solution.
- **Lubuntu / Calamares:** A possible more flexible installer, but Calamares installations install the flavor they're packaged for. User does **not** want to install an unwanted desktop and uninstall it afterward. Do not treat flavor-switching as equivalent to installing the requested clean Ubuntu Server target.
- **Debian installer:** More direct manual-encryption support, but the requirement is Ubuntu 24.04 because of target development ecosystem compatibility.
- **Manually `debootstrap` the OS from an ISO shell:** Feasible but laborious and not a pleasant repeatable default.
- **Temporarily change Windows ESP's GPT flag to hide it from the installer:** Raised as a possibility but **not performed** and undesirable due to avoidable Windows boot risk.
- **Curtin/Subiquity autoinstall (current preferred avenue):** Machine-readable declarative storage actions may permit preserving p1–p4, mounting p5 explicitly and creating LUKS on p7 while allowing the official Ubuntu installer to install the OS. This is **not yet verified end-to-end**.

## Existing candidate autoinstall artifact — treat as unverified

An earlier assistant generated `koolaid-autoinstall.yaml` (if provided to the new environment, inspect the actual contents). It is an **experimental candidate, not validated installation instructions**. Its proposed essentials:

- Cloud-init `#cloud-config` → `autoinstall: { version: 1, ... }`.
- Hostname `koolaid`, username `andy`, password hash placeholder.
- Curtin storage `version: 2`; disk `path: /dev/nvme0n1`, `ptable: gpt`, `preserve: true`.
- Seven explicitly represented partitions, each `preserve: true`, using the exact byte offsets/sizes derived from the sectors above.
- Windows p1–p4 receive **no format, mount, or wipe actions**.
- p5 preserved FAT32 (`fstype: fat32`, `preserve: true`), mounted `/boot/efi`, with `grub_device: true` on partition p5.
- p6 formatted ext4 and mounted `/boot`.
- p7 passed to `type: dm_crypt`, mapping name `cryptroot`, formatted ext4 inside, mounted `/`.
- `cryptsetup-initramfs` in packages; swap disabled.
- Placeholders for account hash and LUKS secret.

**Known unknowns / reasons NOT to execute this draft as-is:**

1. **Curtin preserve semantics:** Confirm accepted partition properties, exact offset/size rules, partition ordering (p4 physically after p5–p7), and what storage config v2 does to omitted/preserved objects. GPT **partition GUIDs** and Windows recovery **attributes** should remain unchanged; a configuration declaring only `preserve: true` must not be assumed safe without verifying the actual storage plan.
2. **Two-ESP GRUB behavior:** Confirm `grub_device: true` on **p5** is honored by the exact version of Subiquity/Curtin/GRUB being used. `grub_device` alone is **not proof** p1 won't be used or modified. Account for Secure Boot if enabled.
3. **LUKS boot integration:** Check that the installed system has the correct `crypttab`, initramfs hooks, kernel/GRUB configuration, and passphrase prompt, not merely a formatted `dm_crypt` mapping.
4. **Secret handling:** Previous YAML uses a *literal passphrase placeholder in `dm_crypt.key`*, not a secure key provisioning mechanism. Do not post a real passphrase publicly, commit it, or leave it stored in installation logs/config files. Work out a supported local-secret strategy, possible key rotation, and clean-up.
5. **Validation:** A YAML parser and simple checks (partition entries, sector alignment) were run on the earlier draft, but there is **no recorded successful version-matched Subiquity validation and no installation test**. Run local syntax/schema validation with the actual Ubuntu 24.04 environment; also reason about side effects and ideally test on a VM with a synthetic copy of the partition layout before touching the real SSD.
6. **Interactive deployment method:** Supplying an autoinstall file to an already running interactive installer versus boot-time NoCloud `user-data` are different procedures; choose and document a reproducible method. Confirm confirmation prompts and failure behavior for the chosen approach. Do not assume a seed image can simply be copied to any filesystem and auto-discovered.
7. **Scope:** Define whether future reinstall wipes p7, reuses/reformats p6, preserves p5 and UEFI entries, and always retains Windows p1–p4. Prefer idempotent, declarative preflight checks. Do not rely only on hard-coded `/dev/nvme0n1` if device naming might change; validate model, capacity, GPT identifiers and partition identity before writing.

## What the automation should deliver

1. **One supported, preferably unattended or low-touch Ubuntu 24.04 installation flow** that respects the existing GPT layout and leaves Windows intact, with local prompts for credentials and LUKS passphrase. Existing setup scripts may supply tooling that makes this easier.
2. **Preflight:** print planned destructive actions and refuse to proceed unless disk/partition identity, geometry, partition types, mounted state, UEFI mode, and required prerequisites match expectations. Strongly guard against accidentally formatting p1, p3 or p4.
3. **Create/refresh Ubuntu data only:** p5 EFI (reuse without formatting unless explicitly intended), p6 `/boot`, p7 encrypted root. Support clean reinstalls without changing Windows partitions.
4. **Boot setup:** Target p5 for Ubuntu EFI bootloader files; keep Windows bootability via its p1 ESP; set Ubuntu default and make Windows selectable, including an explicit recovery/rollback path if the boot entry changes.
5. **Validation:** version-specific schema checks, dry-run/preflight where actually supported, and preferably disposable VM testing before running on physical hardware. Never claim schema validation proves preservation of Windows.
6. **Postinstall verification:** check `findmnt / /boot /boot/efi`, `lsblk -f`, `/etc/crypttab`, `/etc/fstab`, EFI boot entries via `efibootmgr -v`, successful encrypted Ubuntu boot, and Windows boot. Retain BitLocker recovery key because firmware/boot-path changes may trigger Windows recovery.
7. **Deliverables:** a reusable installation script/config plus precise usage instructions, secret-management guidance, emergency recovery steps, and a documented reinstall workflow. Favor simple, auditable scripts over fragile manual UI sequences.

## Key constraints / safety boundary

- **Do not run `Reformat` on the disk** in Subiquity; that can overwrite Windows partitioning.
- **Never format `/dev/nvme0n1p1`** (Windows ESP) or p2–p4. The prepared Ubuntu ESP is **p5**, not p1.
- **p4 is physically at the end of the disk**; don't infer safe ranges from partition numbers.
- No BitLocker recovery key or encryption passphrase is in this document.
- The existing Windows partition may trigger BitLocker recovery on changes to the boot environment; obtain/save recovery credentials and back up data before executing the actual install.
- **No storage changes should be made solely because a YAML file parses successfully.**

## Useful commands for the new environment

Read-only inventory (ensure matching machine and current installation state):

```bash
lsblk -o NAME,SIZE,FSTYPE,PARTTYPE,PARTUUID,PARTLABEL /dev/nvme0n1
sudo sfdisk -d /dev/nvme0n1
sudo parted /dev/nvme0n1 unit MiB print free
test -d /sys/firmware/efi && echo 'UEFI booted'
```

**Requested from the next agent:** First inspect the actual installed automation tools/scripts and the Ubuntu 24.04 installer capabilities, then propose the **simplest verifiable repeatable installation**. Challenge assumptions in the previous autoinstall draft instead of treating them as facts. The end goal is avoiding this entire manual investigation during the next reinstall.
