#!/usr/bin/env python3
"""Test install.sh in a disposable UEFI VM; never attach host block devices.

Fixture SSH access is granted through the VM console. Storage and installation
are initiated later by the actual staged install.sh in the live shell.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from qmp import Monitor
import vm
from gui import key, type_text
from PIL import Image


def command(*args, **kwargs):
    kwargs.setdefault('check', True)
    kwargs.setdefault('text', True)
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    return subprocess.run([str(a) for a in args], **kwargs)


def prepare():
    if vm.digest(vm.ISO) != vm.ISO_SHA256:
        raise ValueError('Verified project Ubuntu ISO required')
    vm.ROOT.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='storage-install-', dir=vm.ROOT))
    directory.chmod(0o700)
    command('/usr/bin/qemu-img', 'create', '-f', 'qcow2', directory / 'disk.qcow2', '48G')
    vm.initialize_firmware(directory, True)
    command('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', directory / 'ssh-key')
    credentials = dict(username='vmuser', hostname='ubuntu-mini-vm',
                       login_password=secrets.token_hex(12), luks_passphrase=secrets.token_hex(16),
                       ssh_authorized_keys=[(directory / 'ssh-key.pub').read_text().strip()])
    (directory / 'credentials.json').write_text(json.dumps(credentials, indent=2) + '\n')
    (directory / 'credentials.json').chmod(0o600)
    print(directory)


def launch(directory, boot=False):
    vm.require_stopped(directory)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    phase = 'boot' if boot else 'install'
    argv = ['/usr/bin/qemu-system-x86_64', '-machine', 'q35,accel=kvm,smm=on',
            '-cpu', 'host', '-m', '6144', '-smp', '4', '-display', 'none',
            '-drive', 'if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.ms.fd',
            '-drive', f'if=pflash,format=raw,unit=1,file={directory}/OVMF_VARS.fd',
            '-global', 'driver=cfi.pflash01,property=secure,value=on',
            '-drive', f'if=none,id=fixture,format=qcow2,file={directory}/disk.qcow2',
            '-device', 'virtio-blk-pci,drive=fixture,serial=MINIOS-INSTALL-TEST',
            '-device', 'VGA', '-monitor', 'none',
            '-chardev', f'socket,id=serial,path={directory}/serial.sock,server=on,wait=off,logfile={directory}/{phase}-serial.log',
            '-serial', 'chardev:serial', '-qmp', f'unix:{directory}/qmp.sock,server=on,wait=off',
            '-no-reboot', '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22',
            '-device', 'virtio-net-pci,netdev=net0']
    if not boot:
        argv += ['-drive', f'file={vm.ISO},media=cdrom,readonly=on', '-boot', 'order=d']
    with (directory / f'{phase}-qemu.log').open('ab') as file:
        process = subprocess.Popen(argv, stdout=file, stderr=file, start_new_session=True)
    (directory / 'state.json').write_text(json.dumps(dict(pid=process.pid, ssh_port=port,
        phase=phase, secure_boot=True, command=argv), indent=2) + '\n')
    print(json.dumps(dict(directory=str(directory), pid=process.pid, ssh_port=port, phase=phase)))


def ssh(directory, script, user='ubuntu-server', **kwargs):
    state = json.loads((directory / 'state.json').read_text())
    authentication = ['-o', 'BatchMode=yes']
    if user != 'ubuntu-server' and (directory / 'interactive.json').exists():
        askpass = directory / 'askpass.py'
        if not askpass.exists():
            askpass.write_text('#!/usr/bin/python3\nimport json\nprint(json.load(open(' +
                              repr(str(directory / 'credentials.json')) + '))["login_password"])\n')
            askpass.chmod(0o700)
        kwargs['env'] = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE='force', DISPLAY=':0')
        authentication = ['-o', 'BatchMode=no', '-o', 'PreferredAuthentications=password', '-o', 'PubkeyAuthentication=no']
    return command('ssh', '-i', directory / 'ssh-key', '-p', state['ssh_port'],
        '-o', 'StrictHostKeyChecking=accept-new', '-o', f'UserKnownHostsFile={directory}/known_hosts',
        *authentication, '-o', 'ConnectTimeout=5', f'{user}@127.0.0.1', script, **kwargs)


def wait_live(directory):
    for _ in range(90):
        result = ssh(directory, 'sudo cat /run/subiquity/server-state', check=False)
        if result.returncode == 0 and result.stdout.strip() in ('WAITING', 'NEEDS_CONFIRMATION'):
            print('Live Ubuntu installer ready over SSH')
            return
        time.sleep(2)
    raise TimeoutError('Live installer SSH/state did not become ready')


def stage(directory):
    state = json.loads((directory / 'state.json').read_text())
    ssh(directory, 'sudo rm -f /tmp/install-credentials.json')
    for source, target in ((vm.PROJECT / 'install.sh', '/tmp/install.sh'),
                           (directory / 'credentials.json', '/tmp/install-credentials.json')):
        command('scp', '-i', directory / 'ssh-key', '-P', state['ssh_port'],
            '-o', 'StrictHostKeyChecking=accept-new', '-o', f'UserKnownHostsFile={directory}/known_hosts',
            str(source), f'ubuntu-server@127.0.0.1:{target}')
    ssh(directory, 'sudo chown root:root /tmp/install-credentials.json && '
        'sudo chmod 600 /tmp/install-credentials.json && chmod 755 /tmp/install.sh')


def fixture(directory):
    script = r'''import hashlib,json,subprocess
def run(*a,**kw): return subprocess.run(a,check=True,text=True,stdout=subprocess.PIPE,**kw).stdout
assert run('lsblk','-dn','-o','SERIAL','/dev/vda').strip()=='MINIOS-INSTALL-TEST'
assert subprocess.run(['sfdisk','--json','/dev/vda'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
layout=''' + repr('label: gpt\nunit: sectors\n\n/dev/vda1: start=2048, size=204800, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="preserved-efi"\n/dev/vda2: start=206848, size=32768, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, name="reserved"\n/dev/vda3: start=239616, size=8388608, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name="existing-data"\n/dev/vda4: start=98564096, size=2097152, type=DE94BBA4-06D1-4D40-A16A-BFD50179D6AC, name="recovery-at-end", attrs="RequiredPartition GUID:63"\n') + r'''
run('sfdisk','/dev/vda',input=layout)
run('udevadm','settle')
run('mkfs.vfat','-F','32','/dev/vda1')
table=json.loads(run('sfdisk','--json','/dev/vda'))['partitiontable']
for p in table['partitions']:
 with open(p['node'],'r+b',buffering=0) as f:
  # Leave FAT boot sector intact; test recognizable data inside each partition.
  f.seek(2*1024*1024 if p['size']*512>2*1024*1024 else 1024*1024)
  f.write(hashlib.sha256(p['node'].encode()).digest()*128)
hashes={p['node']:run('sha256sum',p['node']).split()[0] for p in table['partitions']}
print(json.dumps(dict(table=table,hashes=hashes)))
'''
    result = ssh(directory, 'sudo python3 -', input=script)
    baseline = json.loads(result.stdout)
    (directory / 'preservation-baseline.json').write_text(json.dumps(baseline, indent=2) + '\n')
    print('Four existing partitions created; whole-partition SHA-256 baseline recorded')


def reclaim(directory):
    stage(directory)
    baseline = json.loads((directory / 'preservation-baseline.json').read_text())
    # The previous 20 GiB install is occupied space; a 42 GiB request must fail
    # before explicitly freeing those three fixture-owned partitions.
    result = ssh(directory, 'sudo sh /tmp/install.sh --disk /dev/vda --size 42G --check', check=False)
    assert result.returncode != 0 and 'Insufficient contiguous free space' in result.stderr
    script = '''import json,subprocess\ndef run(*a): return subprocess.check_output(a,text=True)\n'''
    script += 'baseline=' + repr(baseline) + '\n'
    script += '''assert run('lsblk','-dn','-o','SERIAL','/dev/vda').strip()=='MINIOS-INSTALL-TEST'
table=json.loads(run('sfdisk','--json','/dev/vda'))['partitiontable']
assert len(table['partitions'])==7
tree=json.loads(run('lsblk','--json','-o','TYPE,MOUNTPOINTS','/dev/vda'))['blockdevices']
def walk(n):
 yield n
 for c in n.get('children',[]): yield from walk(c)
assert all(n['type'] in ('disk','part') and not any(n.get('mountpoints') or []) for n in walk(tree[0]))
for p in baseline['table']['partitions']:
 assert p in table['partitions']
 assert run('sha256sum',p['node']).split()[0]==baseline['hashes'][p['node']]
assert [p['name'] for p in table['partitions'][4:]] in ([
 'mini-os-efi','mini-os-boot','mini-os-root'], ['ubuntu-mini-efi','ubuntu-mini-boot','ubuntu-mini-root'])
run('sfdisk','--delete','/dev/vda','5','6','7')
run('udevadm','settle')
assert json.loads(run('sfdisk','--json','/dev/vda'))['partitiontable']==baseline['table']
print('Explicit fixture cleanup removed only the three Ubuntu partitions; original GPT entries intact')
'''
    result = ssh(directory, 'sudo python3 -', input=script)
    print(result.stdout.strip())


def install(directory, size):
    (directory / 'interactive.json').unlink(missing_ok=True)
    stage(directory)
    mirror = json.loads((vm.PROJECT / '.local/mirror/server.json').read_text())['guest_url']
    check = ssh(directory, 'sudo /tmp/install.sh --disk /dev/vda --check' +
                (' --size ' + shlex.quote(size) if size else ''))
    (directory / 'storage-plan.json').write_text(check.stdout)
    oversized = ssh(directory, 'sudo /tmp/install.sh --disk /dev/vda --size 250G --check', check=False)
    if oversized.returncode == 0:
        raise AssertionError('Oversized allocation was accepted')
    cmd = 'sudo /tmp/install.sh --disk /dev/vda --no-follow --yes --credentials-file /tmp/install-credentials.json'
    cmd += ' --mirror ' + shlex.quote(mirror + '/ubuntu')
    cmd += ' --security-mirror ' + shlex.quote(mirror + '/ubuntu-security')
    if size:
        cmd += ' --size ' + shlex.quote(size)
    result = ssh(directory, cmd, check=False)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Installation helper failed')


def status(directory):
    result = ssh(directory, 'sudo sh /tmp/install.sh --status; '
                 'sudo cat /run/subiquity/server-state; '
                 'sudo journalctl -u ubuntu-mini-install --no-pager -n 6; '
                 'sudo tail -n 12 /var/log/installer/curtin-install.log; '
                 'if test "$(sudo cat /run/subiquity/server-state)" = ERROR; then '
                 'sudo journalctl --no-pager --grep="Installation refused/failed|FileNotFoundError|KeyError" -n 10; fi; '
                 'ps -eo comm,etimes | tail -n 12', check=False)
    print(result.stdout)
    print(result.stderr, file=sys.stderr)


def reset_preflight(directory):
    result = ssh(directory, 'sudo sfdisk --json /dev/vda')
    table = result.stdout
    assert len(json.loads(table)['partitiontable']['partitions']) == 4
    ssh(directory, 'sudo systemctl stop ubuntu-mini-install.service', check=False)
    ssh(directory, 'if ! test -d /run/subiquity; then sudo mv /run/ubuntu-mini-install/previous-session /run/subiquity; fi')
    ssh(directory, 'sudo rm -rf /run/ubuntu-mini-install; sudo rm -f /autoinstall.yaml')
    ssh(directory, 'sudo systemctl reset-failed ubuntu-mini-install.service; '
        'sudo systemctl start snap.subiquity.subiquity-server.service snap.subiquity.subiquity-service.service', check=False)
    print('Removed failed preflight configuration in the disposable VM; no partitions were created')


def finish(directory):
    stage(directory)
    result = ssh(directory, 'sudo env SNAP=/snap/subiquity/current '
        'PYTHON=/snap/subiquity/current/usr/bin/python3.10 '
        'PY3OR2_PYTHON=/snap/subiquity/current/usr/bin/python3.10 '
        'PYTHONPATH=/snap/subiquity/current/lib/python3.10/site-packages '
        'PATH=/snap/subiquity/current/bin:/usr/sbin:/usr/bin:/sbin:/bin '
        'sh /tmp/install.sh --finish-plan /run/ubuntu-mini-install/plan.json', check=False)
    print(result.stdout)
    if result.returncode:
        print(result.stderr)
        raise RuntimeError('Finishing checks failed')
    ssh(directory, 'sudo poweroff', check=False)


def capture(directory):
    client = Monitor(directory / 'qmp.sock')
    try:
        client.execute('screendump', {'filename': str(directory / 'screen.ppm')})
    finally:
        client.close()
    Image.open(directory / 'screen.ppm').save(directory / 'screen.png')
    print(directory / 'screen.png')


def unlock(directory, correct_only=False):
    creds = json.loads((directory / 'credentials.json').read_text())
    client = Monitor(directory / 'qmp.sock')
    try:
        client.execute('screendump', {'filename': str(directory / 'luks-before.ppm')})
        if not correct_only:
            type_text(client, 'intentionally-wrong-passphrase\n')
            # Argon2 rejection can take longer under concurrent VM load.
            time.sleep(12)
            assert ssh(directory, 'true', user=creds['username'], check=False).returncode != 0
            client.execute('screendump', {'filename': str(directory / 'luks-wrong.ppm')})
        type_text(client, creds['luks_passphrase'] + '\n')
    finally:
        client.close()
    for _ in range(45):
        if ssh(directory, 'true', user=creds['username'], check=False).returncode == 0:
            print('Correct LUKS passphrase booted to guest SSH; wrong-passphrase screen retained when tested')
            for name in ('luks-before', 'luks-wrong'):
                if (directory / (name + '.ppm')).exists():
                    Image.open(directory / (name + '.ppm')).save(directory / (name + '.png'))
            return
        time.sleep(2)
    raise TimeoutError('Guest did not boot after the correct LUKS passphrase')


def shutdown(directory):
    creds = json.loads((directory / 'credentials.json').read_text())
    ssh(directory, "sudo -S -p '' poweroff", user=creds['username'],
        input=creds['login_password'] + '\n', check=False)
    print('Shutdown requested for the disposable installed VM')


def next_usb(directory):
    creds = json.loads((directory / 'credentials.json').read_text())
    script = '''import re,subprocess
efi=subprocess.check_output(['efibootmgr','-v'],text=True)
entry=re.search(r'^Boot([0-9A-Fa-f]{4})\\*? UEFI QEMU DVD-ROM',efi,re.M).group(1)
subprocess.run(['efibootmgr','-n',entry],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['poweroff'],check=True)
'''
    ssh(directory, "sudo -S -p '' python3 -", user=creds['username'],
        input=creds['login_password'] + '\n' + script, check=False)
    print('Selected the fixture USB/CD boot entry for the next boot, then requested shutdown')


def fresh_usb(directory):
    vm.require_stopped(directory)
    shutil.copy2(directory / 'OVMF_VARS.fd', directory / 'previous-firmware.fd')
    vm.initialize_firmware(directory, True)
    launch(directory)


def console(directory):
    client = Monitor(directory / 'qmp.sock')
    try:
        deadline = time.monotonic() + 120
        while True:
            client.execute('screendump', {'filename': str(directory / 'console-ready.ppm')})
            frame = Image.open(directory / 'console-ready.ppm').convert('RGB')
            orange = sum(count for count, color in (frame.getcolors(frame.width*frame.height) or [])
                         if color == (233, 84, 32))
            if orange > frame.width * 4:
                break
            if time.monotonic() > deadline:
                raise TimeoutError('Wait for the ordinary installer language screen before opening its shell')
            time.sleep(1)
        key(client, ['ctrl', 'alt', 'f2'])
        time.sleep(2)
        pubkey = (directory / 'ssh-key.pub').read_text().strip()
        type_text(client, 'mkdir -p ~/.ssh; chmod 700 ~/.ssh; printf ' + shlex.quote(pubkey + '\n') +
                  ' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys\n')
    finally:
        client.close()


def enter(directory):
    client = Monitor(directory / 'qmp.sock')
    try:
        key(client, ['ret'])
    finally:
        client.close()


def interactive(directory, cancel_only=False):
    import pexpect
    stage(directory)
    before = ssh(directory, 'sudo sfdisk --json /dev/vda').stdout
    state = json.loads((directory / 'state.json').read_text())
    creds = json.loads((directory / 'credentials.json').read_text())
    mirror = json.loads((vm.PROJECT / '.local/mirror/server.json').read_text())['guest_url']
    cmd = 'sudo sh /tmp/install.sh --disk /dev/vda --no-follow --mirror ' + shlex.quote(mirror + '/ubuntu')
    cmd += ' --security-mirror ' + shlex.quote(mirror + '/ubuntu-security')
    child = pexpect.spawn('ssh', ['-tt','-i',str(directory/'ssh-key'),'-p',str(state['ssh_port']),
        '-o','StrictHostKeyChecking=accept-new','-o',f'UserKnownHostsFile={directory}/known_hosts',
        '-o','BatchMode=yes',f'ubuntu-server@127.0.0.1',cmd], encoding='utf-8', timeout=90)
    # No pexpect transcript/logfile: the fixture passwords stay private.
    try:
        for prompt, answer in (
            ('Hostname [koolaid]: ',creds['hostname']),('Username [andy]: ',creds['username']),
            ('Account password: ',creds['login_password']),('Repeat account password: ',creds['login_password']),
            ('Encryption passphrase: ',creds['luks_passphrase']),('Repeat encryption passphrase: ',creds['luks_passphrase'])):
            child.expect_exact(prompt)
            child.sendline(answer)
        child.expect_exact('? Type INSTALL: ')
        child.sendline('CANCEL' if cancel_only else 'INSTALL')
        child.expect_exact('Installation cancelled; no disk changes made' if cancel_only else 'Ubuntu installer launched in an independent service.')
        child.expect(pexpect.EOF)
    finally:
        child.close()
    if cancel_only:
        assert ssh(directory, 'sudo sfdisk --json /dev/vda').stdout == before
        assert ssh(directory, 'test ! -e /run/ubuntu-mini-install && test ! -e /autoinstall.yaml', check=False).returncode == 0
        print('Real terminal prompts reached confirmation; cancellation left disk and installation state untouched')
    else:
        (directory/'interactive.json').write_text(json.dumps(dict(started=True,confirmation='INSTALL'))+'\n')
        print('Interactive credentials and INSTALL confirmation launched the official installer')


def console_install(directory, size):
    """Launch through tty2/QMP, rather than an SSH session's cgroup."""
    started_at = time.time()
    (directory / 'interactive.json').unlink(missing_ok=True)
    stage(directory)
    mirror = json.loads((vm.PROJECT / '.local/mirror/server.json').read_text())['guest_url']
    cmd = 'sudo sh /tmp/install.sh --disk /dev/vda --yes --credentials-file /tmp/install-credentials.json'
    cmd += ' --mirror ' + shlex.quote(mirror + '/ubuntu')
    cmd += ' --security-mirror ' + shlex.quote(mirror + '/ubuntu-security')
    if size:
        cmd += ' --size ' + shlex.quote(size)
    client = Monitor(directory / 'qmp.sock')
    try:
        key(client, ['ctrl', 'alt', 'f2'])
        time.sleep(1)
        type_text(client, 'cat /proc/self/cgroup > /tmp/console-cgroup.txt\n')
        type_text(client, cmd + '\n')
    finally:
        client.close()
    for _ in range(45):
        result = ssh(directory, 'sudo cat /run/ubuntu-mini-install/status.json', check=False)
        if result.returncode == 0:
            record = json.loads(result.stdout)
            if record['stage'] == 'failed':
                raise RuntimeError(record['message'])
            if record['stage'] in ('starting', 'installing', 'verified', 'complete'):
                print('Installer launched from the actual live console; progress is on tty3')
                report = dict(started_at=started_at, helper_sha256=vm.digest(vm.PROJECT/'install.sh'),
                    console_cgroup=ssh(directory, 'cat /tmp/console-cgroup.txt').stdout.strip(),
                    worker_cgroup=ssh(directory, 'sudo systemctl show ubuntu-mini-install -p ControlGroup --value').stdout.strip(),
                    progress_console=json.loads(ssh(directory,
                        'sudo cat /run/ubuntu-mini-install/plan.json').stdout)['progress_console'], status=record)
                assert report['worker_cgroup'] and report['worker_cgroup'] not in report['console_cgroup']
                assert report['progress_console'] == 3
                (directory / 'console-launch-report.json').write_text(json.dumps(report, indent=2)+'\n')
                capture(directory)
                return
        time.sleep(2)
    raise TimeoutError('Local-console launch did not reach the independent installer; inspect the framebuffer')


def check_viewer(directory):
    assert ssh(directory, 'cat /sys/class/tty/tty0/active').stdout.strip() == 'tty3'
    assert ssh(directory, 'systemctl is-active ubuntu-mini-install-console').stdout.strip() == 'active'
    client = Monitor(directory / 'qmp.sock')
    try:
        client.execute('screendump', {'filename': str(directory/'progress-before-close.ppm')})
        key(client, ['ctrl', 'c'])
        time.sleep(1)
        assert ssh(directory, 'systemctl is-active ubuntu-mini-install').stdout.strip() == 'active'
        assert ssh(directory, 'systemctl is-active ubuntu-mini-install-console', check=False).stdout.strip() == 'inactive'
        client.execute('screendump', {'filename': str(directory/'progress-closed.ppm')})
        key(client, ['ctrl', 'alt', 'f2'])
        time.sleep(1)
        key(client, ['ctrl', 'c'])
        time.sleep(1)
        type_text(client, 'sudo sh /tmp/install.sh --follow\n')
        time.sleep(2)
        assert ssh(directory, 'systemctl is-active ubuntu-mini-install').stdout.strip() == 'active'
        client.execute('screendump', {'filename': str(directory/'progress-reconnected.ppm')})
    finally:
        client.close()
    for name in ('progress-before-close','progress-closed','progress-reconnected'):
        Image.open(directory/(name+'.ppm')).save(directory/(name+'.png'))
    (directory/'viewer-check.json').write_text(json.dumps(dict(
        passed=True,ctrl_c_leaves_installer_running=True,follow_reconnected=True))+'\n')
    print('Ctrl+C closed both viewers without stopping installation; --follow reconnected from the live console')


def verify(directory):
    baseline = json.loads((directory / 'preservation-baseline.json').read_text())
    creds = json.loads((directory / 'credentials.json').read_text())
    script = '''import json,re,subprocess\nfrom pathlib import Path\ndef run(*a): return subprocess.check_output(a,text=True)\n'''
    script += 'baseline=' + repr(baseline) + '\n'
    script += 'secrets_to_check=' + repr([creds['login_password'], creds['luks_passphrase']]) + '\n'
    script += '''table=json.loads(run('sfdisk','--json','/dev/vda'))['partitiontable']
for p in baseline['table']['partitions']:
 assert p in table['partitions'], p['node']
 assert run('sha256sum',p['node']).split()[0]==baseline['hashes'][p['node']], p['node']
assert len(table['partitions'])==7
assert 'SecureBoot enabled' in run('mokutil','--sb-state')
lockdown=Path('/sys/kernel/security/lockdown').read_text().strip()
assert '[integrity]' in lockdown or '[confidentiality]' in lockdown
assert 'cryptroot' in run('findmnt','-n','-o','SOURCE','/')
assert 'none' in Path('/etc/crypttab').read_text()
assert Path('/boot/efi/EFI/ubuntu/shimx64.efi').is_file()
for directory in ('/var/log/installer','/etc/cloud'):
 for p in Path(directory).rglob('*'):
  if p.is_file():
   contents=p.read_bytes()
   assert all(s.encode() not in contents for s in secrets_to_check), 'Plaintext secret retained'
efi=run('efibootmgr','-v')
assert ('HD(5,GPT,'+table['partitions'][4]['uuid']).lower() in efi.lower()
assert re.search(r'^BootCurrent: (\\w+)',efi,re.M).group(1)==re.search(r'^BootOrder: (\\w+)',efi,re.M).group(1)
plan=json.loads(Path('/var/log/installer/ubuntu-mini-storage-plan.json').read_text())
print(json.dumps(dict(passed=True,whole_existing_partition_hashes_unchanged=True,
 original_gpt_entries_preserved=True,secure_boot=True,kernel_lockdown=lockdown,
 plaintext_secrets_absent_from_installed_logs=True,
 helper_sha256=plan.get('helper_sha256'),allocation=plan['allocation'],
 mounts={p:run('findmnt','-n','-o','SOURCE',p).strip() for p in ('/','/boot','/boot/efi')},efi=efi)))
'''
    result = ssh(directory, "sudo -S -p '' python3 -", user=creds['username'],
                 input=creds['login_password'] + '\n' + script)
    report = json.loads(result.stdout)
    (directory / 'install-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k!='efi'}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch', 'fresh-usb', 'wait', 'fixture', 'reclaim', 'install', 'interactive-install', 'console-install', 'check-viewer', 'status', 'reset-preflight', 'finish', 'capture', 'console', 'enter', 'cancel', 'boot', 'unlock', 'unlock-correct', 'verify', 'shutdown', 'next-usb'])
    parser.add_argument('directory', nargs='?')
    parser.add_argument('--size')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
        return
    directory = vm.select_directory(args.directory)
    if not directory.name.startswith('storage-install-'):
        raise ValueError('Only disposable installation-test fixtures accepted')
    if args.action in ('launch', 'boot'):
        launch(directory, boot=args.action == 'boot')
    elif args.action == 'install':
        install(directory, args.size)
    elif args.action == 'console-install':
        console_install(directory, args.size)
    elif args.action == 'unlock-correct':
        unlock(directory, correct_only=True)
    elif args.action == 'cancel':
        interactive(directory, cancel_only=True)
    elif args.action == 'interactive-install':
        interactive(directory)
    else:
        {'fresh-usb': fresh_usb, 'wait': wait_live, 'fixture': fixture, 'reclaim': reclaim, 'status': status,
         'reset-preflight': reset_preflight, 'finish': finish, 'capture': capture, 'console': console, 'enter': enter,
         'check-viewer': check_viewer, 'unlock': unlock, 'verify': verify, 'shutdown': shutdown, 'next-usb': next_usb}[args.action](directory)


if __name__ == '__main__':
    main()
