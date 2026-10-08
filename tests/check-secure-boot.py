#!/usr/bin/env python3
"""Record live Secure Boot enforcement and the installed signed boot chain."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

from gui import experiment
from session import ssh

GUEST = r'''
import hashlib, json, platform, struct, subprocess
from pathlib import Path

def variable(name):
    files = list(Path('/sys/firmware/efi/efivars').glob(name + '-*'))
    return files[0].read_bytes()[4:].hex() if len(files) == 1 else None

def image(path):
    data = Path(path).read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0', 'Expected PE image'
    optional = pe + 24
    magic = struct.unpack_from('<H', data, optional)[0]
    directory = optional + (112 if magic == 0x20b else 96)
    offset, size = struct.unpack_from('<II', data, directory + 8 * 4)
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
            'certificate_offset': offset, 'certificate_size': size,
            'certificate_present': bool(offset and size and offset + size <= len(data))}

kernel = platform.release()
report = {'kernel': kernel, 'cmdline': Path('/proc/cmdline').read_text().strip(),
          'secure_boot_variable': variable('SecureBoot'),
          'setup_mode_variable': variable('SetupMode'),
          'shim_validation_disabled': variable('MokSBStateRT'),
          'lockdown': Path('/sys/kernel/security/lockdown').read_text().strip(),
          'mokutil': subprocess.check_output(['mokutil', '--sb-state'], text=True).strip(),
          'efi_entries': subprocess.check_output(['efibootmgr', '-v'], text=True),
          'boot_messages': '\n'.join(line for line in subprocess.check_output(['dmesg'], text=True).splitlines()
                                    if 'secure boot' in line.lower() or 'locked down' in line.lower()),
          'packages': subprocess.check_output(['dpkg-query', '-W', '-f=${Package} ${Version}\n',
                    'shim-signed', 'grub-efi-amd64-signed', 'linux-image-' + kernel], text=True),
          'images': {}, 'kernel_components': {}}
for name, path in {'shim': '/boot/efi/EFI/ubuntu/shimx64.efi',
                   'grub': '/boot/efi/EFI/ubuntu/grubx64.efi',
                   'fallback': '/boot/efi/EFI/BOOT/BOOTX64.EFI',
                   'kernel': '/boot/vmlinuz-' + kernel}.items():
    report['images'][name] = image(path)
shim_hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/usr/lib/shim').glob('shimx64.efi*') if p.is_file()}
report['shim_matches_packaged_binary'] = report['images']['shim']['sha256'] in shim_hashes
report['grub_matches_packaged_binary'] = report['images']['grub']['sha256'] == image('/usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed')['sha256']
for name in ('virtio_blk', 'virtio_net', 'dm_crypt', 'ext4'):
    result = subprocess.run(['modinfo', '-F', 'signer', name], text=True, capture_output=True)
    filename = subprocess.check_output(['modinfo', '-F', 'filename', name], text=True).strip()
    report['kernel_components'][name] = {'filename': filename, 'signer': result.stdout.strip(),
                                       'built_in': filename == '(builtin)'}
report['passed'] = (report['secure_boot_variable'] == '01' and report['setup_mode_variable'] == '00'
    and report['shim_validation_disabled'] in (None, '00') and '[integrity]' in report['lockdown']
    and report['mokutil'] == 'SecureBoot enabled' and report['shim_matches_packaged_binary']
    and report['grub_matches_packaged_binary'] and all(i['certificate_present'] for i in report['images'].values())
    and all(item['built_in'] or item['signer'] for item in report['kernel_components'].values()))
print(json.dumps(report, indent=2))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('--label', default='boot', choices=['boot', 'post-upgrade', 'post-refusal'])
    args = parser.parse_args()
    directory = experiment.select_directory(args.directory)
    state = json.loads((directory / 'state.json').read_text())
    if not state.get('secure_boot') or '-kernel' in state['command']:
        raise ValueError('Launch the VM through the enrolled Secure Boot firmware first')
    credentials = json.loads((directory / 'credentials.json').read_text())
    report = json.loads(ssh(directory, 'sudo -k -S -p "" python3 -c ' + shlex.quote(GUEST),
                            credentials['login_password'] + '\n'))
    report['qemu_command'] = state['command']
    report['firmware'] = json.loads((directory / 'firmware.json').read_text())
    # Inspect signatures with the host tool without adding test packages to the guest.
    report['signature_listings'] = {}
    images = directory / 'secure-boot-images'
    images.mkdir(exist_ok=True)
    for name, metadata in report['images'].items():
        command = ['ssh', '-i', str(directory / 'ssh-key'), '-p', str(state['ssh_port']),
                   '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=accept-new',
                   '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'), 'vmuser@127.0.0.1',
                   'sudo -k -S -p "" cat -- ' + shlex.quote(metadata['path'])]
        result = subprocess.run(command, input=(credentials['login_password'] + '\n').encode(), capture_output=True, check=True)
        path = images / (args.label + '-' + name + '.efi')
        path.write_bytes(result.stdout)
        if experiment.digest(path) != metadata['sha256']:
            raise ValueError('Image hash changed in transit')
        listing = subprocess.run(['sbverify', '--list', str(path)], text=True, capture_output=True)
        report['signature_listings'][name] = listing.stdout + listing.stderr
        report['passed'] &= listing.returncode == 0 and 'signature 1' in listing.stdout
    (directory / ('secure-boot-' + args.label + '-report.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('kernel', 'mokutil', 'lockdown', 'passed')}, indent=2))
    if not report['passed']:
        raise SystemExit('Secure Boot acceptance failed; inspect the report')


if __name__ == '__main__':
    main()
