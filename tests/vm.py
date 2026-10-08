#!/usr/bin/env python3
"""Create and control disposable VMs for manual Ubuntu installation and setup tests.

Only generated image directories under .local/vm are accepted. No physical disk
or automated partitioning workflow is exposed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess
import tempfile
import time

from qmp import Monitor

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / '.local/vm'
ISO = PROJECT / 'ubuntu-24.04.5-live-server-amd64.iso'
ISO_SHA256 = '97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8'
MIB = 1024**2


def run(*command, **kwargs):
    kwargs.setdefault("check", True)
    return subprocess.run([str(s) for s in command], **kwargs)


def digest(path, offset=0, size=None):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        source.seek(offset)
        remaining = size if size is not None else Path(path).stat().st_size - offset
        while remaining:
            data = source.read(min(8 * MIB, remaining))
            if not data:
                raise EOFError(path)
            result.update(data)
            remaining -= len(data)
    return result.hexdigest()


def initialize_firmware(directory, secure_boot=False):
    """Give a new VM its own variable store, with enrolled keys when requested."""
    suffix = '.ms' if secure_boot else ''
    code = Path(f'/usr/share/OVMF/OVMF_CODE_4M{suffix}.fd')
    template = Path(f'/usr/share/OVMF/OVMF_VARS_4M{suffix}.fd')
    shutil.copyfile(template, directory / 'OVMF_VARS.fd')
    (directory / 'firmware.json').write_text(json.dumps({
        'secure_boot': secure_boot, 'code': str(code), 'vars_template': str(template),
        'code_sha256': digest(code), 'vars_template_sha256': digest(template),
    }, indent=2) + '\n')


def prepare(secure_boot=False):
    """Create a blank virtual disk; install Ubuntu manually in its GUI."""
    if not ISO.is_file() or ISO.is_symlink() or digest(ISO) != ISO_SHA256:
        raise ValueError('The verified Ubuntu ISO must be a regular project file')
    ROOT.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='storage-server-', dir=ROOT))
    directory.chmod(0o700)
    run('/usr/bin/qemu-img', 'create', '-f', 'qcow2', directory / 'disk.qcow2', '80G',
        stdout=subprocess.DEVNULL)
    initialize_firmware(directory, secure_boot)
    (directory / 'credentials.json').write_text(json.dumps({
        'username': 'vmuser', 'login_password': secrets.token_hex(12),
        'luks_passphrase': secrets.token_hex(16)}, indent=2) + '\n')
    (directory / 'credentials.json').chmod(0o600)
    run('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', directory / 'ssh-key')
    (directory / 'fixture.json').write_text(json.dumps({
        'kind': 'manual-ubuntu-server', 'iso_sha256': ISO_SHA256,
        'hostname': 'ubuntu-mini-vm', 'username': 'vmuser'}, indent=2) + '\n')
    print(directory)


def select_directory(value):
    directory = Path(value).resolve()
    if directory.parent != ROOT or not directory.name.startswith("storage-"):
        raise ValueError("Only a generated project VM directory is accepted")
    return directory


def require_stopped(directory):
    monitor = directory / "qmp.sock"
    if not monitor.exists():
        return
    try:
        client = Monitor(monitor)
    except (FileNotFoundError, ConnectionRefusedError):
        monitor.unlink(missing_ok=True)
        (directory / "serial.sock").unlink(missing_ok=True)
    else:
        client.close()
        raise ValueError("VM is running; stop it before this operation")


def branch(directory, secure_boot=False):
    """Keep the verified installed disk immutable while testing provisioning."""
    require_stopped(directory)
    destination = Path(tempfile.mkdtemp(prefix="storage-desktop-", dir=ROOT))
    destination.chmod(0o700)
    run("/usr/bin/qemu-img", "check", directory / "disk.qcow2", stdout=subprocess.DEVNULL)
    (directory / "disk.qcow2").chmod(0o444)
    run("/usr/bin/qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b",
        directory / "disk.qcow2", destination / "disk.qcow2", stdout=subprocess.DEVNULL)
    for name in ("OVMF_VARS.fd", "credentials.json", "ssh-key", "ssh-key.pub"):
        shutil.copy2(directory / name, destination / name)
    if secure_boot:
        initialize_firmware(destination, True)
    elif (directory / 'firmware.json').exists():
        shutil.copy2(directory / 'firmware.json', destination / 'firmware.json')
    if (directory / 'fixture.json').exists():
        shutil.copy2(directory / 'fixture.json', destination / 'fixture.json')
    (destination / "baseline.json").write_text(json.dumps({"directory": str(directory)}, indent=2) + "\n")
    print(destination)


def launch(directory, stage, audio=False, window=False, setup_assets=False):
    monitor = directory / "qmp.sock"
    require_stopped(directory)
    if stage == 'install' and digest(ISO) != ISO_SHA256:
        raise ValueError('ISO does not match the verified Ubuntu release checksum')
    for file in ("disk.qcow2", "OVMF_VARS.fd"):
        if not (directory / file).is_file() or (directory / file).is_symlink():
            raise ValueError(f"VM resource must be a regular file: {file}")
    for suffix in ("serial.log", "qemu.log"):
        previous = directory / f"{stage}-{suffix}"
        if previous.exists():
            index = 1
            while (directory / f"{stage}-{index}-{suffix}").exists():
                index += 1
            previous.rename(directory / f"{stage}-{index}-{suffix}")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    firmware_path = directory / 'firmware.json'
    firmware = json.loads(firmware_path.read_text()) if firmware_path.exists() else {}
    secure_boot = firmware.get('secure_boot', False)
    code = '/usr/share/OVMF/OVMF_CODE_4M.ms.fd' if secure_boot else '/usr/share/OVMF/OVMF_CODE_4M.fd'
    flash = [
        '-drive', f'if=pflash,format=raw,unit=0,readonly=on,file={code}',
        '-drive', f"if=pflash,format=raw,unit=1,file={directory / 'OVMF_VARS.fd'}"]
    command = ["/usr/bin/qemu-system-x86_64", "-machine", "q35,accel=kvm" + (",smm=on" if secure_boot else ""), "-cpu", "host", "-m", "6144", "-smp", "4"] + flash + [
               "-drive", f"if=none,id=fixture,format=qcow2,file={directory / 'disk.qcow2'}",
               "-device", "virtio-blk-pci,drive=fixture,serial=MINIOS-FIXTURE-001",
               "-device", "VGA", "-display", "gtk" if window else "none", "-monitor", "none",
               "-chardev", f"socket,id=serial,path={directory / 'serial.sock'},server=on,wait=off,logfile={directory / (stage + '-serial.log')}",
               "-serial", "chardev:serial",
               "-qmp", f"unix:{monitor},server=on,wait=off", "-no-reboot",
               "-netdev", f"user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22", "-device", "virtio-net-pci,netdev=net0"]
    if secure_boot:
        command.extend(['-global', 'driver=cfi.pflash01,property=secure,value=on'])
    if window:
        command.extend(['-name', 'ubuntu-mini preview'])
    if audio:
        command.extend(['-audiodev', f'wav,id=audio,path={directory / "audio.wav"}',
                        '-device', 'ich9-intel-hda', '-device', 'hda-duplex,audiodev=audio'])
    if setup_assets:
        # Simulate a USB artifact directory without duplicating its large Snaps.
        # Only the fixed project cache is shared, and the guest cannot write it.
        cache = PROJECT / '.local/mirror/assets'
        if not cache.is_dir() or cache.is_symlink():
            raise ValueError('The generated setup artifact cache is required')
        command.extend(['-virtfs', f'local,path={cache},mount_tag=setup_assets,security_model=none,readonly=on'])
    if stage == 'install':
        # The ordinary signed ISO boots into the interactive Ubuntu installer.
        command.extend(['-drive', f'file={ISO},media=cdrom,readonly=on', '-boot', 'order=d'])
    logfile = directory / (stage + "-qemu.log")
    with logfile.open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
    state = {"pid": process.pid, "ssh_port": port, "stage": stage, "command": command,
             'secure_boot': secure_boot}
    (directory / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    deadline = time.monotonic() + 15
    while True:
        if process.poll() is not None:
            monitor.unlink(missing_ok=True)
            raise RuntimeError(logfile.read_text())
        try:
            client = Monitor(monitor)
            break
        except (FileNotFoundError, ConnectionRefusedError):
            pass
        if time.monotonic() > deadline:
            process.terminate()
            raise TimeoutError("QMP socket did not appear")
        time.sleep(0.1)
    try:
        print(json.dumps({"pid": process.pid, "ssh_port": port, "stage": stage,
                          "kvm": client.execute("query-kvm")}, indent=2))
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    prep = subs.add_parser('prepare', help='Create a blank VM for manual installation')
    prep.add_argument('--secure-boot', action='store_true')
    clone = subs.add_parser('branch', help='Create a writable overlay over a stopped VM')
    clone.add_argument('directory')
    clone.add_argument('--secure-boot', action='store_true')
    start = subs.add_parser('launch')
    start.add_argument('directory')
    start.add_argument('stage', choices=['install', 'boot'])
    start.add_argument('--audio', action='store_true')
    start.add_argument('--window', action='store_true')
    start.add_argument('--setup-assets', action='store_true', help='Share only the fixed cache read-only')
    qmp = subs.add_parser('qmp')
    qmp.add_argument('directory')
    qmp.add_argument('command')
    qmp.add_argument('arguments', nargs='?', default='{}')
    ssh = subs.add_parser('ssh')
    ssh.add_argument('directory')
    ssh.add_argument('user', choices=['root', 'vmuser'])
    ssh.add_argument('command')
    ssh.add_argument('--sudo', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.secure_boot)
        return
    directory = select_directory(args.directory)
    if args.action == 'branch':
        branch(directory, args.secure_boot)
    elif args.action == 'launch':
        launch(directory, args.stage, args.audio, args.window, args.setup_assets)
    elif args.action == 'ssh':
        state = json.loads((directory / 'state.json').read_text())
        command, options = args.command, {}
        if args.sudo:
            if args.user != 'vmuser':
                raise ValueError('Password sudo is only supported for the fixture user')
            credentials = json.loads((directory / 'credentials.json').read_text())
            options = {'input': credentials['login_password'] + '\n', 'text': True}
            command = 'sudo -S -p "" -- sh -c ' + shlex.quote(command)
        run('ssh', '-i', directory / 'ssh-key', '-p', state['ssh_port'],
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f"UserKnownHostsFile={directory / 'known_hosts'}", f'{args.user}@127.0.0.1', command, **options)
    else:
        client = Monitor(directory / 'qmp.sock')
        try:
            print(json.dumps(client.execute(args.command, json.loads(args.arguments)), indent=2))
        finally:
            client.close()
        if args.command == 'quit':
            (directory / 'qmp.sock').unlink(missing_ok=True)
            (directory / 'serial.sock').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
