#!/usr/bin/env python3
"""Install pinned HHD power controls and UI, retaining Minion's input mapper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
PREFIX = Path('/usr/local/lib/minion-hhd')
CACHE = Path('/var/cache/minion/hhd')
MOK_CERTIFICATE = Path('/var/lib/shim-signed/mok/MOK.der')


def check_acpi_module():
    """Check the running kernel; offer enrollment of its matching local key."""
    def probe(*command):
        return subprocess.run(command, text=True, capture_output=True, timeout=30)

    loaded = probe('modprobe', 'acpi_call')
    if loaded.returncode == 0:
        print('acpi_call loads successfully on the running kernel.', flush=True)
        return
    print('acpi_call could not load: ' + (loaded.stderr.strip() or loaded.stdout.strip()), flush=True)
    print('HHD power controls need a working module; desktop setup can continue.', flush=True)
    secure_boot = probe('mokutil', '--sb-state')
    if secure_boot.returncode or 'SecureBoot enabled' not in secure_boot.stdout or not MOK_CERTIFICATE.is_file():
        print('Check matching kernel headers, DKMS and module signing after reboot.', flush=True)
        return

    # Only offer the certificate which actually signed this kernel's module.
    signature = probe('modinfo', '-F', 'sig_key', 'acpi_call')
    certificate = probe('openssl', 'x509', '-inform', 'DER', '-in', str(MOK_CERTIFICATE),
                        '-noout', '-serial', '-ext', 'subjectKeyIdentifier')
    key_id = signature.stdout.strip().replace(':', '').lower()
    lines = certificate.stdout.splitlines()
    # PKCS#7 signer identifiers may use issuer/serial or a subject key ID.
    cert_ids = {line.split('=', 1)[1].strip().lower() for line in lines if line.startswith('serial=')}
    if lines:
        cert_ids.add(lines[-1].strip().replace(':', '').lower())
    if (signature.returncode or certificate.returncode or not key_id or key_id not in cert_ids):
        print('The local certificate does not match the module signing key; investigate before enrollment.', flush=True)
        return
    enrolled = probe('mokutil', '--test-key', str(MOK_CERTIFICATE))
    # mokutil can report enrollment but return 1 when its additional trusted
    # kernel-keyring lookup is unavailable. Do not requeue an enrolled key.
    if enrolled.returncode == 0 or str(MOK_CERTIFICATE) + ' is already enrolled' in enrolled.stdout:
        print('The signing key is enrolled. Reboot and retry modprobe; inspect the kernel log if it still fails.', flush=True)
        return
    if str(MOK_CERTIFICATE) + ' is not enrolled' not in enrolled.stdout:
        print('Could not determine signing-key enrollment. Inspect mokutil --test-key before importing it.', flush=True)
        return
    pending = probe('mokutil', '--list-new')
    pending_ids = ''.join(pending.stdout.lower().replace(':', '').split())
    if pending.returncode == 0 and key_id in pending_ids:
        print('Signing-key enrollment is already queued. Complete Enroll MOK on the next boot.', flush=True)
        return

    print('Secure Boot needs enrollment of the local acpi_call signing key.', flush=True)
    print('Enrollment trusts kernel modules signed by this key and keeps Secure Boot enabled.', flush=True)
    if not sys.stdin.isatty():
        print('No interactive terminal. Run this command yourself before reboot:', flush=True)
        print('sudo mokutil --import ' + str(MOK_CERTIFICATE), flush=True)
        return
    print('Choose a temporary password below, then after reboot use the physical keyboard:', flush=True)
    print('Enroll MOK -> Continue -> Yes -> temporary password -> Reboot.', flush=True)
    # mokutil reads the password from the terminal without echo. Never generate,
    # pass on the command line, capture or log an enrollment password ourselves.
    requested = subprocess.run(['mokutil', '--import', str(MOK_CERTIFICATE)])
    if requested.returncode == 0:
        print('Enrollment queued; confirm Enroll MOK on reboot, then retry sudo modprobe acpi_call.', flush=True)
    else:
        print('Enrollment was not queued. Retry sudo mokutil --import ' + str(MOK_CERTIFICATE), flush=True)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(artifact):
    """Reuse only verified cache entries; never execute an unchecked download."""
    target = CACHE / artifact['filename']
    if target.is_file() and digest(target) == artifact['sha256']:
        return target
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=CACHE, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            print('Downloading ' + artifact['filename'], flush=True)
            with urllib.request.urlopen(artifact['url'], timeout=120) as response:
                shutil.copyfileobj(response, stream)
            stream.close()
            if digest(temporary) != artifact['sha256']:
                raise ValueError('Artifact checksum mismatch: ' + artifact['filename'])
            temporary.chmod(0o644)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def install_file(source, target, mode=0o644):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.read_bytes() == source.read_bytes():
        target.chmod(mode)
        return False
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(source.read_bytes())
            stream.close()
            temporary.chmod(mode)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return True


def preflight():
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') != '24.04':
        raise ValueError('HHD setup supports Ubuntu 24.04 only')
    if platform.machine() != 'x86_64' or not Path('/run/systemd/system').is_dir():
        raise ValueError('HHD setup requires a booted amd64 system with systemd')
    artifacts = json.loads((HERE / 'artifacts.json').read_text())
    for artifact in artifacts.values():
        if (Path(artifact['filename']).name != artifact['filename']
                or len(artifact['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in artifact['sha256'])
                or not artifact['url'].startswith('https://')):
            raise ValueError('Invalid HHD artifact manifest')
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check target and manifests without changes or downloads')
    args = parser.parse_args()
    artifacts = preflight()
    if args.check:
        print('HHD prerequisites checked; hardware controls need on-device validation.')
        return
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo inside the installed target')
    os.umask(0o022)
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')

    def run(*command):
        subprocess.run([str(v) for v in command], check=True, env=env)

    run('apt-get', 'install', '-y', '--no-install-recommends', *(HERE / 'packages.txt').read_text().split())
    check_acpi_module()
    PREFIX.mkdir(parents=True, exist_ok=True)
    marker = PREFIX / 'artifacts.json'
    previous = json.loads(marker.read_text()) if marker.is_file() else {}
    changed = False
    runtime = PREFIX / 'runtime'
    if previous.get('daemon') != artifacts['daemon'] or not (runtime / 'bin/hhd').is_file():
        archive = fetch(artifacts['daemon'])
        # The path deliberately omits "venv": HHD hides its unmanaged self-update
        # actions outside paths with that name. Versions belong to this installer.
        run('python3', '-m', 'venv', '--system-site-packages', runtime)
        # Ubuntu supplies the native Python dependencies, including GI and D-Bus.
        # No unpinned dependency/build downloads and no system-wide pip install.
        run(runtime / 'bin/pip', 'install', '--no-deps', '--no-build-isolation', archive)
        changed = True
    run(runtime / 'bin/pip', 'check')
    ui = PREFIX / 'ui'
    if previous.get('ui') != artifacts['ui'] or not (ui / 'hhd-ui').is_file():
        image = fetch(artifacts['ui'])
        with tempfile.TemporaryDirectory(prefix='.ui-', dir=PREFIX) as scratch:
            extracted = Path(scratch) / 'squashfs-root'
            # This verified release's filesystem starts at the pinned offset.
            # Extract without executing its AppImage runtime or requiring FUSE.
            subprocess.run(['unsquashfs', '-no-progress', '-d', str(extracted),
                            '-offset', str(artifacts['ui']['squashfs_offset']), str(image)],
                           stdout=subprocess.DEVNULL, check=True, env=env)
            sandbox = extracted / 'chrome-sandbox'
            if not sandbox.is_file():
                raise ValueError('HHD UI release is missing the Chromium sandbox helper')
            # Standard Chromium setuid sandbox, in a root-owned, unwritable tree.
            os.chown(sandbox, 0, 0)
            sandbox.chmod(0o4755)
            old = PREFIX / 'ui.previous'
            if old.exists():
                shutil.rmtree(old)
            if ui.exists():
                ui.rename(old)
            extracted.rename(ui)
            if old.exists():
                shutil.rmtree(old)
        changed = True
    install_file(HERE / 'minion-hhd-ui', Path('/usr/local/bin/minion-hhd-ui'), 0o755)
    install_file(HERE / 'minion-hhd.desktop', Path('/usr/local/share/applications/minion-hhd.desktop'))
    state = Path('/etc/hhd/state.yml')
    if not state.exists():
        install_file(HERE / 'state.yml', state)
    changed |= install_file(HERE / 'minion-hhd.service', Path('/etc/systemd/system/minion-hhd.service'))
    install_file(HERE / 'artifacts.json', marker)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'minion-hhd.service')
    run('systemctl', 'restart' if changed else 'start', 'minion-hhd.service')
    print('HHD installed and enabled. Open Handheld Daemon from the launcher. Hardware checks remain queued.', flush=True)


if __name__ == '__main__':
    main()
