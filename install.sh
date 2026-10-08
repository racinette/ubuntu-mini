#!/bin/sh
# Standalone live-USB installer. Keep the Python payload in this file so it
# can also be downloaded without cloning the repository.
set -eu
exec python3 - "$0" "$@" <<'MINI_OS_INSTALL_PYTHON'
import argparse
import getpass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import time
from decimal import Decimal

MIB = 1024**2
GIB = 1024**3
ESP = 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B'
LINUX = '0FC63DAF-8483-4772-8E79-3D69D8477DE4'
MINIMUM = 16 * GIB
WORK = Path('/run/ubuntu-mini-install')
UNIT = 'ubuntu-mini-install'
SUPPORTED = '24.04.5'


def run(*args, **kwargs):
    kwargs.setdefault('check', True)
    kwargs.setdefault('text', True)
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    return subprocess.run([str(a) for a in args], **kwargs)


def size_bytes(value):
    match = re.fullmatch(r'(\d+(?:\.\d+)?)(G|GiB|GB|M|MiB|MB|B)?', value)
    if not match:
        raise ValueError('Use a positive size such as 250G, 250GiB or 250GB')
    units = {None: GIB, 'G': GIB, 'GiB': GIB, 'GB': 10**9,
             'M': MIB, 'MiB': MIB, 'MB': 10**6, 'B': 1}
    size = int(Decimal(match[1]) * units[match[2]])
    return size // MIB * MIB


def descendants(node):
    yield node
    for child in node.get('children', []):
        yield from descendants(child)


def table_for(disk):
    run('sfdisk', '--verify', disk)
    table = json.loads(run('sfdisk', '--json', disk).stdout)['partitiontable']
    if table['label'] != 'gpt' or table['unit'] != 'sectors':
        raise ValueError('Only existing GPT disks are supported')
    sector = table['sectorsize']
    if sector not in (512, 4096):
        raise ValueError('Unsupported logical sector size')
    return table


def partition_number(node):
    match = re.search(r'(\d+)$', node)
    if not match:
        raise ValueError('Cannot determine partition number: ' + node)
    return int(match[1])


def make_plan(table, requested=None):
    """Pure planner: no filesystem probing or writes; all existing slots retained."""
    sector = table['sectorsize']
    first = table['firstlba'] * sector
    end = (table['lastlba'] + 1) * sector
    parts = sorted(table.get('partitions', []), key=lambda p: p['start'])
    gaps, cursor = [], first
    for part in parts:
        start, stop = part['start'] * sector, (part['start'] + part['size']) * sector
        if start < cursor or stop > end or part['size'] <= 0:
            raise ValueError('Invalid or overlapping GPT partition geometry')
        if start > cursor:
            gaps.append((cursor, start))
        cursor = stop
    if cursor < end:
        gaps.append((cursor, end))
    aligned = [(((start + MIB - 1) // MIB) * MIB, stop // MIB * MIB)
               for start, stop in gaps]
    usable = [(start, stop) for start, stop in aligned if stop > start]
    if requested is not None and requested < MINIMUM:
        raise ValueError('Installation allocation must be at least 16 GiB including EFI and /boot')
    needed = requested or MINIMUM
    eligible = [(start, stop) for start, stop in usable if stop - start >= needed]
    if not eligible:
        largest = max((stop - start for start, stop in usable), default=0)
        raise ValueError(f'Insufficient contiguous free space: largest region {largest/GIB:.2f} GiB; '
                         f'required {needed/GIB:.2f} GiB. Existing partitions are never reused.')
    start, stop = max(eligible, key=lambda gap: (gap[1] - gap[0], -gap[0]))
    allocation = requested or stop - start
    used_numbers = {partition_number(p['node']) for p in parts}
    numbers = [n for n in range(1, 129) if n not in used_numbers][:3]
    if len(numbers) != 3:
        raise ValueError('Not enough unused GPT partition slots')
    new = []
    for number, name, length, ptype in zip(numbers,
            ('ubuntu-mini-efi', 'ubuntu-mini-boot', 'ubuntu-mini-root'),
            (GIB, 2 * GIB, allocation - 3 * GIB), (ESP, LINUX, LINUX)):
        new.append(dict(number=number, name=name, offset=start, size=length, type=ptype))
        start += length
    return dict(disk=table['device'], original=table, allocation=allocation,
                new=new, remaining_in_gap=stop - start)


def inventory(disk=None, requested=None):
    tree = json.loads(run('lsblk', '--json', '--bytes', '--paths', '--output',
        'PATH,TYPE,RO,RM,TRAN,SIZE,MOUNTPOINTS,SERIAL,MODEL').stdout)['blockdevices']
    candidates = []
    for node in tree:
        if disk and os.path.realpath(node['path']) != os.path.realpath(disk):
            continue
        if node['type'] != 'disk' or node['ro'] or node['rm'] or node.get('tran') == 'usb':
            continue
        if any(any(n.get('mountpoints') or []) or n['type'] not in ('disk', 'part')
               or list((Path('/sys/class/block') / Path(n['path']).name / 'holders').glob('*'))
               for n in descendants(node)):
            if disk:
                raise ValueError('Target disk has mounted filesystems, swap, or active mappings')
            continue
        try:
            table = table_for(node['path'])
            plan = make_plan(table, requested)
        except (ValueError, subprocess.CalledProcessError) as error:
            if disk:
                raise ValueError(str(error)) from error
            continue
        plan['identity'] = {k: node.get(k) for k in ('path', 'size', 'serial', 'model')}
        candidates.append(plan)
    if len(candidates) != 1:
        raise ValueError(f'Found {len(candidates)} eligible unmounted GPT disks. '
                         'Specify --disk /dev/...; it must contain sufficient free space.')
    return candidates[0]


def storage_actions(plan, keyfile):
    sector = plan['original']['sectorsize']
    disk = dict(id='disk', type='disk', path=plan['disk'], ptable='gpt',
                preserve=True, grub_device=False)
    actions = [disk]
    for p in sorted(plan['original'].get('partitions', []), key=lambda p: partition_number(p['node'])):
        action = dict(id='existing-' + str(partition_number(p['node'])), type='partition',
                      device='disk', number=partition_number(p['node']),
                      offset=p['start'] * sector, size=p['size'] * sector,
                      partition_type=p['type'], preserve=True, grub_device=False)
        # Curtin v2 copies unspecified labels, GUIDs and GPT attributes from the
        # existing entries. Do not replace them through Subiquity's model.
        actions.append(action)
    for role, p in zip(('efi', 'boot', 'root'), plan['new']):
        action = dict(id=role, type='partition', device='disk', number=p['number'],
                      offset=p['offset'], size=p['size'], partition_type=p['type'],
                      partition_name=p['name'], preserve=False, grub_device=(role == 'efi'))
        if role == 'efi':
            action['flag'] = 'boot'
        actions.append(action)
    actions.extend([
        dict(id='efi-fs', type='format', volume='efi', fstype='fat32', preserve=False),
        dict(id='boot-fs', type='format', volume='boot', fstype='ext4', preserve=False),
        dict(id='crypt', type='dm_crypt', volume='root', dm_name='cryptroot', keyfile=keyfile,
             preserve=False, options=['luks']),
        dict(id='root-fs', type='format', volume='crypt', fstype='ext4', preserve=False),
        dict(id='root-mount', type='mount', device='root-fs', path='/'),
        dict(id='boot-mount', type='mount', device='boot-fs', path='/boot'),
        dict(id='efi-mount', type='mount', device='efi-fs', path='/boot/efi'),
    ])
    return actions


def verify_original(plan, after=False):
    current = table_for(plan['disk'])
    original = plan['original']
    for key in ('label', 'id', 'firstlba', 'lastlba', 'sectorsize'):
        if current.get(key) != original.get(key):
            raise ValueError('GPT metadata changed: ' + key)
    old = {partition_number(p['node']): p for p in original.get('partitions', [])}
    now = {partition_number(p['node']): p for p in current.get('partitions', [])}
    if not after and current != original:
        raise ValueError('Disk layout changed after planning; start again')
    for number, p in old.items():
        if now.get(number) != p:
            raise ValueError('Existing partition metadata changed: ' + str(number))
    if after:
        if set(now) != set(old) | {p['number'] for p in plan['new']}:
            raise ValueError('Unexpected partitions after installation')
        for p in plan['new']:
            entry = now[p['number']]
            if (entry['start'] * current['sectorsize'], entry['size'] * current['sectorsize'],
                    entry['type'].upper()) != (p['offset'], p['size'], p['type']):
                raise ValueError('New partition geometry or type differs from the plan')


def installer_state():
    class UnixConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect('/run/subiquity/socket')
    connection = UnixConnection('localhost')
    try:
        connection.request('GET', '/meta/status')
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Cannot establish installer state')
        return json.loads(response.read())['state']
    finally:
        connection.close()


def live_environment():
    if os.geteuid() != 0:
        raise ValueError('Run with sudo from the Ubuntu Server installer shell')
    if not Path('/sys/firmware/efi').is_dir() or not Path('/cdrom/casper/install-sources.yaml').is_file():
        raise ValueError('A UEFI-booted Ubuntu Server live installation medium is required')
    import yaml
    release = Path('/etc/os-release').read_text()
    if 'ID=ubuntu\n' not in release or 'VERSION_ID="24.04"' not in release:
        raise ValueError('Only Ubuntu 24.04 Server installation media are supported')
    snap = Path('/snap/subiquity/current').resolve()
    metadata = yaml.safe_load((snap / 'meta/snap.yaml').read_text())
    if str(metadata['version']) != SUPPORTED:
        raise ValueError(f'Validated installer version required: {SUPPORTED}; found {metadata["version"]}')
    for executable in ('sfdisk', 'lsblk', 'openssl', 'systemctl', 'systemd-run', 'cryptsetup'):
        if not shutil.which(executable):
            raise ValueError('Missing live installer tool: ' + executable)
    state = installer_state()
    if state not in ('WAITING', 'NEEDS_CONFIRMATION'):
        raise ValueError('Installer is not idle before installation: ' + str(state))
    return snap


def tty_input(prompt):
    with open('/dev/tty', 'w') as tty:
        tty.write(prompt)
        tty.flush()
    with open('/dev/tty', 'r') as tty:
        return tty.readline().strip()


def credentials(path):
    if path:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
                raise ValueError('Credentials file must be a root-owned regular file with mode 600')
            data = json.load(file)
    else:
        data = dict(hostname=tty_input('Hostname [koolaid]: ') or 'koolaid',
                    username=tty_input('Username [andy]: ') or 'andy')
        for field, prompt in (('login_password', 'Account password'), ('luks_passphrase', 'Encryption passphrase')):
            data[field] = getpass.getpass(prompt + ': ')
            if getpass.getpass('Repeat ' + prompt.lower() + ': ') != data[field]:
                raise ValueError('Passwords did not match')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', data.get('username', '')) or data['username'] == 'root':
        raise ValueError('Invalid username')
    if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', data.get('hostname', '')):
        raise ValueError('Invalid hostname')
    for field in ('login_password', 'luks_passphrase'):
        if not isinstance(data.get(field), str) or len(data[field]) < 8 or any(c in data[field] for c in '\n\r\x00'):
            raise ValueError('Passwords must have at least eight characters and no newlines/NUL')
    return data


def private_write(path, value, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'w') as file:
        file.write(value)


def progress(stage, message):
    """A small non-secret status record survives the calling terminal."""
    value = dict(stage=stage, message=message, updated=time.time())
    temporary = WORK / f'status.{os.getpid()}.tmp'
    temporary.write_text(json.dumps(value) + '\n')
    temporary.chmod(0o600)
    temporary.replace(WORK / 'status.json')
    print(f'ubuntu-mini: {stage}: {message}', flush=True)


def status_record():
    try:
        return json.loads((WORK / 'status.json').read_text())
    except (OSError, ValueError):
        return dict(stage='not-started', message='No ubuntu-mini installation status is available.')


def service_properties():
    result = run('systemctl', 'show', UNIT, '--no-pager',
                 '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState',
                 '-p', 'Result', '-p', 'ExecMainStatus', check=False)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def show_status():
    record = status_record()
    print(f'ubuntu-mini: {record["stage"]}: {record["message"]}', flush=True)
    for key, value in service_properties().items():
        print(f'{key}={value}', flush=True)
    state = Path('/run/subiquity/server-state')
    if state.exists():
        print('Installer state: ' + state.read_text().strip(), flush=True)
    print('Details: /var/log/installer/curtin-install.log\n'
          f'Service log: sudo journalctl -b -u {UNIT} --no-pager -n 30', flush=True)


def follow_progress():
    print('ubuntu-mini installation progress\n'
          'Ctrl+C leaves this viewer; installation continues.\n'
          'From another console: sudo sh ./install.sh --status or --follow\n'
          'Keep the USB inserted until the automatic reboot.\n', flush=True)
    started = last_output = time.monotonic()
    previous = None
    offset = None
    log = Path('/var/log/installer/curtin-install.log')
    try:
        while True:
            record = status_record()
            current = (record['stage'], record['message'])
            if current != previous:
                print(f'[{int(time.monotonic()-started)}s] {current[0]}: {current[1]}', flush=True)
                previous = current
                last_output = time.monotonic()
            if log.exists():
                with log.open(errors='replace') as stream:
                    size = log.stat().st_size
                    if offset is None or size < offset:
                        stream.seek(max(0, size - 4096))
                        lines = stream.read().splitlines()[-8:]
                    else:
                        stream.seek(offset)
                        lines = stream.read().splitlines()
                    offset = stream.tell()
                if lines:
                    for line in lines[-20:]:
                        print(line, flush=True)
                    last_output = time.monotonic()
            if record['stage'] in ('failed', 'complete'):
                show_status()
                return 1 if record['stage'] == 'failed' else 0
            properties = service_properties()
            if properties.get('ActiveState') in ('failed', 'inactive') and (
                    record['stage'] not in ('prepared', 'not-started') or time.monotonic()-started > 30):
                print('Installation service is not running. Inspect the service log shown below.', flush=True)
                show_status()
                return 1
            if time.monotonic() - last_output >= 15:
                print(f'[{int(time.monotonic()-started)}s] Still watching: {record["stage"]}; '
                      f'service {properties.get("ActiveState", "unknown")}. '
                      'No new installer log lines in the last 15 seconds.', flush=True)
                last_output = time.monotonic()
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nViewer closed. Installation continues; use --follow to reconnect.', flush=True)
        return 0


def launch_worker():
    """The service owns the handoff, outside the original installer's cgroup."""
    child = None
    try:
        plan = json.loads((WORK / 'plan.json').read_text())
        snap = live_environment()
        current = inventory(plan['disk'], plan['allocation'])
        if current['identity'] != plan['identity']:
            raise ValueError('Disk identity changed before installer handoff')
        verify_original(plan)
        console = plan.get('progress_console')
        if console:
            run('chvt', str(console))
        progress('handoff', 'Stopping the original installer from an independent service.')
        run('systemctl', 'stop', 'snap.subiquity.subiquity-service.service',
            'snap.subiquity.subiquity-server.service')
        state_dir = Path('/run/subiquity')
        if state_dir.exists():
            state_dir.rename(WORK / 'previous-session')
        progress('starting', 'Launching the official Ubuntu installer. Waiting for its state file.')
        child = subprocess.Popen(['/bin/sh', str(WORK / 'launch.sh')])
        previous = None
        started = time.monotonic()
        heartbeat = time.monotonic()
        while child.poll() is None:
            state = Path('/run/subiquity/server-state')
            value = state.read_text().strip() if state.exists() else 'STARTING'
            if value == 'STARTING' and time.monotonic() - started > 180:
                raise ValueError('Installer produced no state file within three minutes; inspect the service log')
            if value != previous:
                previous = value
                if value == 'DONE' and (WORK / 'verification.json').exists():
                    progress('complete', 'Installation verified. Automatic reboot is next; remove the USB at reboot.')
                else:
                    description = {
                        'STARTING': 'Starting the official installer.',
                        'RUNNING': 'Installing Ubuntu: preparing storage, copying the system and configuring packages.',
                        'UU_RUNNING': 'Installing security updates.',
                        'LATE_COMMANDS_RUNNING': 'Verifying encrypted boot and preservation of existing partitions.',
                    }.get(value, 'Ubuntu installer state: ' + value)
                    progress('installing', description)
            if value == 'ERROR':
                raise ValueError('Ubuntu installer reported ERROR; inspect /var/log/installer/ and the service log')
            if time.monotonic() - heartbeat >= 15:
                print('ubuntu-mini: installer process is running; state: ' + value, flush=True)
                heartbeat = time.monotonic()
            time.sleep(1)
        if child.returncode or not (WORK / 'verification.json').exists():
            raise ValueError(f'Installer exited with status {child.returncode} without a verified completion')
        progress('complete', 'Installation verified. Automatic reboot is next; remove the USB at reboot.')
    except Exception as error:
        progress('failed', str(error))
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr[-4000:], file=sys.stderr, flush=True)
        (WORK / 'luks.key').unlink(missing_ok=True)
        if child is not None and child.poll() is None:
            child.terminate()
        raise


def progress_console(no_follow):
    if no_follow:
        return None
    terminal = os.environ.get('SUDO_TTY', '').removeprefix('/dev/')
    if re.fullmatch(r'tty[1-9][0-9]*', terminal):
        return 4 if terminal == 'tty3' else 3
    # sudo can nest pseudo-terminals; walk back to the live console's login
    # process. SSH sessions have no local VT and keep their current viewer.
    pid = os.getpid()
    for _ in range(32):
        row = run('ps', '-o', 'ppid=,tty=,comm=', '-p', str(pid), check=False).stdout.split(maxsplit=2)
        if len(row) != 3:
            break
        parent, terminal, name = row
        if name.startswith('sshd'):
            break
        if re.fullmatch(r'tty[1-9][0-9]*', terminal):
            return 4 if terminal == 'tty3' else 3
        pid = int(parent)
        if pid <= 1:
            break
    return None


def post_install(plan):
    verify_original(plan, after=True)
    mounts = json.loads(run('findmnt', '--json', '--output', 'TARGET,SOURCE').stdout)['filesystems']
    mounted = {n['target']: n['source'] for root in mounts for n in descendants(root)}
    # findmnt uses 'children', as does lsblk.
    for suffix in ('', '/boot', '/boot/efi'):
        if '/target' + suffix not in mounted:
            raise ValueError('Installed mount missing: /target' + suffix)
    root_number = plan['new'][2]['number']
    root_path = next(p['node'] for p in table_for(plan['disk'])['partitions']
                     if partition_number(p['node']) == root_number)
    luks_uuid = run('cryptsetup', 'luksUUID', root_path).stdout.strip()
    table = table_for(plan['disk'])
    nodes = {partition_number(p['node']): p['node'] for p in table['partitions']}
    expected_mounts = {'/target': '/dev/mapper/cryptroot',
                      '/target/boot': nodes[plan['new'][1]['number']],
                      '/target/boot/efi': nodes[plan['new'][0]['number']]}
    for target, expected in expected_mounts.items():
        if os.path.realpath(mounted[target]) != os.path.realpath(expected):
            raise ValueError('Installed mount uses an unexpected device: ' + target)
    crypttab = Path('/target/etc/crypttab').read_text()
    if not re.search(r'^cryptroot\s+UUID=' + re.escape(luks_uuid) + r'\s+none\s+', crypttab, re.M):
        raise ValueError('Encrypted root is not configured for a passphrase at boot')
    if not Path('/target/boot/efi/EFI/ubuntu/shimx64.efi').is_file():
        raise ValueError('Signed Ubuntu EFI loader is missing')
    run('curtin', 'in-target', '--target=/target', '--', 'update-initramfs', '-u', '-k', 'all')
    run('curtin', 'in-target', '--target=/target', '--', 'update-grub')
    efi = run('curtin', 'in-target', '--target=/target', '--', 'efibootmgr', '-v').stdout
    esp_part = next(p for p in table['partitions'] if partition_number(p['node']) == plan['new'][0]['number'])
    expected_path = f'HD({plan["new"][0]["number"]},GPT,{esp_part["uuid"]},'.lower()
    entries = [re.match(r'^Boot([0-9A-Fa-f]{4})\*?\s+', line).group(1)
               for line in efi.splitlines()
               if re.match(r'^Boot[0-9A-Fa-f]{4}\*?\s+', line)
               and expected_path in line.lower() and '\\efi\\ubuntu\\shimx64.efi' in line.lower()]
    order = re.search(r'^BootOrder:\s*([0-9A-Fa-f,]+)', efi, re.M)
    if not entries or not order:
        raise ValueError('Firmware has no Ubuntu entry pointing to the new ESP')
    ordered = order.group(1).split(',')
    if ordered[0].upper() != entries[0].upper():
        ordered = [entries[0]] + [entry for entry in ordered if entry.upper() != entries[0].upper()]
        run('curtin', 'in-target', '--target=/target', '--', 'efibootmgr', '-o', ','.join(ordered))
        efi = run('curtin', 'in-target', '--target=/target', '--', 'efibootmgr', '-v').stdout
    verification = json.dumps(dict(
        passed=True, existing_partition_metadata_preserved=True, luks_uuid=luks_uuid,
        mounts=mounted, efi_entries=efi), indent=2) + '\n'
    (WORK / 'verification.json').write_text(verification)
    logs = Path('/target/var/log/installer')
    logs.mkdir(parents=True, exist_ok=True)
    private_write(logs / 'ubuntu-mini-verification.json', verification)
    private_write(logs / 'ubuntu-mini-storage-plan.json', json.dumps(plan, indent=2) + '\n')
    # No passphrase/keyfile is copied into the target. The YAML carries only
    # the path to this temporary file, never its contents.
    (WORK / 'luks.key').unlink(missing_ok=True)
    progress('verified', 'Encrypted root, signed boot loader and preserved partition metadata verified.')
    print('Installation verified. Reboot, remove the USB, then run setup.sh.', flush=True)


def start_install(args, plan, snap, data):
    import yaml
    if WORK.exists() or Path('/run/mini-os-install').exists() or Path('/autoinstall.yaml').exists():
        raise ValueError('An installation configuration already exists; boot a fresh live session')
    password_hash = run('openssl', 'passwd', '-6', '-stdin', input=data['login_password']).stdout.strip()
    plan['installer_version'] = SUPPORTED
    plan['helper_sha256'] = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
    WORK.mkdir(mode=0o700)
    private_write(WORK / 'plan.json', json.dumps(plan, indent=2) + '\n')
    private_write(WORK / 'luks.key', data['luks_passphrase'])
    private_write(WORK / 'install.sh', Path(sys.argv[1]).read_text(), 0o700)
    helper = str(WORK / 'install.sh')
    config = dict(version=1)
    config.update({
        'refresh-installer': {'update': False},
        'source': {'id': 'ubuntu-server', 'search_drivers': False},
        'locale': 'en_US.UTF-8', 'keyboard': {'layout': 'us'},
        'identity': dict(hostname=data['hostname'], username=data['username'], password=password_hash),
        'storage': dict(config=storage_actions(plan, str(WORK / 'luks.key')),
                        swap={'size': 0}, grub={'reorder_uefi': False, 'remove_duplicate_entries': False}),
        'packages': ['cryptsetup-initramfs', 'efibootmgr', 'mokutil'],
        'early-commands': [['sh', helper, '--verify-plan', str(WORK / 'plan.json')]],
        'late-commands': [['sh', helper, '--finish-plan', str(WORK / 'plan.json')]],
        'error-commands': [['sh', '-c', 'rm -f /run/ubuntu-mini-install/luks.key']],
        'shutdown': 'reboot',
    })
    config['ssh'] = {'install-server': True, 'authorized-keys': data.get('ssh_authorized_keys', []),
                     'allow-pw': not bool(data.get('ssh_authorized_keys'))}
    if args.mirror:
        from urllib.parse import urlsplit
        for url in (args.mirror, args.security_mirror or args.mirror):
            parsed = urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError('Mirror must be an HTTP(S) URL without credentials')
        config['apt'] = {'geoip': False, 'mirror-selection': {'primary': [{'uri': args.mirror}]},
                         'fallback': 'abort', 'security': [{'arches': ['amd64'], 'uri': args.security_mirror or args.mirror}]}
    private_write(Path('/autoinstall.yaml'), yaml.safe_dump({'autoinstall': config}, sort_keys=False))
    # Validate against the bundled schema before stopping the interactive UI.
    python = str(snap / 'usr/bin/python3.10')
    env = dict(os.environ, SNAP=str(snap), SUBIQUITY_ROOT=str(snap),
               PYTHONPATH=str(snap / 'lib/python3.10/site-packages'), PYTHON=python,
               PY3OR2_PYTHON=python, PATH=f'{snap}/bin:{snap}/usr/bin:' + os.environ['PATH'])
    schema_check = '''import asyncio,jsonschema,yaml
from subiquity.cmd.schema import make_app,make_schema
async def check():
    jsonschema.validate(yaml.safe_load(open('/autoinstall.yaml'))['autoinstall'],make_schema(make_app()))
asyncio.run(check())
'''
    run(python, '-c', schema_check, env=env, cwd=WORK)
    verify_original(plan)
    if installer_state() not in ('WAITING', 'NEEDS_CONFIRMATION'):
        raise ValueError('Installer state changed; refusing to launch')
    cmdline = Path('/proc/cmdline').read_text().strip() + ' autoinstall subiquity-storage-version=2'
    command = [python, '-m', 'subiquity.cmd.server', '--storage-version', '2',
               '--autoinstall', '/autoinstall.yaml', '--kernel-cmdline', cmdline]
    launch = '#!/bin/sh\nset -eu\n'
    for key in ('SNAP', 'SUBIQUITY_ROOT', 'PYTHONPATH', 'PYTHON', 'PY3OR2_PYTHON', 'PATH'):
        launch += 'export ' + key + '=' + shlex.quote(env[key]) + '\n'
    launch += 'exec ' + shlex.join(command) + '\n'
    private_write(WORK / 'launch.sh', launch, 0o700)
    # Everything needed by the worker is staged before it can stop the
    # original installer. Its service is independent of our shell/cgroup.
    console = progress_console(args.no_follow)
    plan['progress_console'] = console
    (WORK / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    progress('prepared', 'Configuration validated. Preparing the independent installer service.')
    if console:
        run('systemctl', 'stop', f'getty@tty{console}.service')
        run('systemd-run', '--unit=' + UNIT + '-console', '--property=Type=exec',
            '--property=StandardInput=tty', '--property=StandardOutput=tty',
            '--property=StandardError=tty', f'--property=TTYPath=/dev/tty{console}',
            '--property=TTYReset=yes', '/bin/sh', helper, '--follow')
        print(f'Progress will appear on Ctrl+Alt+F{console}.', flush=True)
    run('systemd-run', '--unit=' + UNIT, '--property=Type=exec',
        '--property=StandardOutput=journal', '--property=StandardError=journal',
        '/bin/sh', helper, '--launch')
    print('Ubuntu installer launched in an independent service.\n'
          'Progress: sudo sh ./install.sh --follow\n'
          'Status: sudo sh ./install.sh --status\n'
          f'Service log: sudo journalctl -fu {UNIT}\n'
          'The installer will reboot when finished.', flush=True)


def main():
    parser = argparse.ArgumentParser(prog='install.sh', description='ubuntu-mini: install encrypted Ubuntu Server into unallocated GPT space.')
    parser.add_argument('--disk', help='Target disk; required if automatic selection is ambiguous')
    parser.add_argument('--size', type=size_bytes, help='Total allocation: 250G is GiB, 250GB is decimal; default largest free region')
    parser.add_argument('--check', action='store_true', help='Print a read-only storage plan; do not launch installation')
    parser.add_argument('--status', action='store_true', help='Show the current installation stage and service status; do not install')
    parser.add_argument('--follow', action='store_true', help='Reconnect to live progress; Ctrl+C leaves installation running')
    parser.add_argument('--no-follow', action='store_true', help='Launch in the background without a progress console (automation)')
    parser.add_argument('--credentials-file', help='Root-owned mode-600 local JSON; otherwise prompt on the terminal')
    parser.add_argument('--yes', action='store_true', help='Accept the printed installation plan without prompting')
    parser.add_argument('--mirror', help='Optional Ubuntu package mirror URL')
    parser.add_argument('--security-mirror', help='Optional security mirror URL (defaults to --mirror)')
    parser.add_argument('--verify-plan', help=argparse.SUPPRESS)
    parser.add_argument('--finish-plan', help=argparse.SUPPRESS)
    parser.add_argument('--launch', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[2:])
    if args.security_mirror and not args.mirror:
        raise ValueError('--security-mirror requires --mirror')
    if sum((args.check, args.status, args.follow, args.launch)) > 1:
        raise ValueError('Use only one of --check, --status or --follow')
    if os.geteuid() != 0:
        raise ValueError('Run with sudo to inspect installation or disk status')
    if args.status:
        show_status()
        return
    if args.follow:
        sys.exit(follow_progress())
    if args.launch:
        launch_worker()
        return
    if args.verify_plan or args.finish_plan:
        if os.geteuid() != 0:
            raise ValueError('Installer hooks require root')
        plan = json.loads(Path(args.verify_plan or args.finish_plan).read_text())
        if args.finish_plan:
            post_install(plan)
        else:
            current = inventory(plan['disk'], plan['allocation'])
            if current['identity'] != plan['identity']:
                raise ValueError('Disk identity changed')
            verify_original(plan)
        return
    if not args.check and (WORK.exists() or Path('/run/mini-os-install').exists()
                           or Path('/autoinstall.yaml').exists()):
        raise ValueError('A previous installation configuration exists. Boot a fresh live USB session; '
                         'then use --check to inspect available space before retrying.')
    if not args.check:
        print('ubuntu-mini: checking the live environment and installer state...', flush=True)
    snap = None if args.check else live_environment()
    print('ubuntu-mini: inspecting the disk and planning free-space allocation...', flush=True)
    plan = inventory(args.disk, args.size)
    print(json.dumps(plan, indent=2), flush=True)
    if args.check:
        return
    data = credentials(args.credentials_file)
    if not args.yes:
        answer = tty_input(f'Create {plan["allocation"]/GIB:.2f} GiB of encrypted Ubuntu on {plan["disk"]}? Type INSTALL: ')
        if answer != 'INSTALL':
            raise ValueError('Installation cancelled; no disk changes made')
    if WORK.exists() or Path('/run/mini-os-install').exists() or Path('/autoinstall.yaml').exists():
        raise ValueError('An installation configuration already exists; boot a fresh live session')
    try:
        print('ubuntu-mini: validating configuration before starting installation...', flush=True)
        start_install(args, plan, snap, data)
    except Exception:
        # Leave the non-secret plan/logs available for diagnosis.
        (WORK / 'luks.key').unlink(missing_ok=True)
        Path('/autoinstall.yaml').unlink(missing_ok=True)
        if WORK.exists():
            progress('failed', 'Configuration or service launch failed; inspect the error above.')
        raise
    if not args.no_follow:
        sys.exit(follow_progress())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Never echo command stdin, credentials, or the full generated config.
        print('Installation refused/failed: ' + str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr[-4000:], file=sys.stderr)
        sys.exit(1)
MINI_OS_INSTALL_PYTHON
