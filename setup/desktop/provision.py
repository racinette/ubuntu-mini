#!/usr/bin/env python3
"""Install common desktop configuration. Run as root in the target Ubuntu system."""
import os
import argparse
import configparser
from pathlib import Path
import pwd
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--user', help='Existing desktop account; defaults to the account invoking sudo')
parser.add_argument('--defer-activation', action='store_true',
                    help='Prepare networking and login for reboot; keep the current session running')
args = parser.parse_args()

def write(path, text, mode=0o644):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.minion.tmp')
    temporary.write_text(text)
    temporary.chmod(mode)
    temporary.replace(target)

def run(*args):
    subprocess.run(args, check=True)

if os.geteuid() != 0:
    raise SystemExit('Run this script as root in the installed target')
if 'ID=ubuntu' not in Path('/etc/os-release').read_text():
    raise SystemExit('This provisioning targets Ubuntu')
username = args.user or os.environ.get('SUDO_USER')
if not username or username == 'root':
    raise SystemExit('Use sudo from your desktop account, or pass --user USERNAME')
user = pwd.getpwnam(username)
if user.pw_uid < 1000:
    raise SystemExit('Select an existing regular desktop account')
os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
os.environ['LC_ALL'] = 'C'
# Prevent the newly installed greeter from taking over the setup console.
mask = Path('/run/systemd/system/greetd.service')
created_mask = args.defer_activation and not (mask.exists() or mask.is_symlink())
if created_mask:
    run('systemctl', 'mask', '--runtime', 'greetd.service')
try:
    run('apt-get', 'install', '-y', '--no-install-recommends', *HERE.joinpath('packages.txt').read_text().split())
finally:
    if created_mask:
        run('systemctl', 'unmask', '--runtime', 'greetd.service')
# Ubuntu splits these rules out of brightnessctl as a recommended package.
# Our no-recommends install includes them explicitly; they grant video-group
# writes to screen backlights. New group membership takes effect next login.
run('usermod', '-a', '-G', 'video', user.pw_name)
for name in ('minion-session', 'minion-session-ready', 'minion-lock', 'minion-idle', 'minion-idle-controls', 'minion-rear-buttons', 'minion-status', 'minion-gamepad', 'minion-window-picker'):
    write('/usr/local/bin/' + name, HERE.joinpath(name).read_text(), 0o755)
write('/etc/minion/sway.conf', HERE.joinpath('sway.conf').read_text())
write('/etc/minion/gamepad.json', HERE.joinpath('gamepad.json').read_text())
write('/etc/systemd/logind.conf.d/60-minion-power.conf', '''[Login]
# Lid close suspends on every power source, including when docked.
HandleLidSwitch=suspend
HandleLidSwitchExternalPower=suspend
HandleLidSwitchDocked=suspend
IdleAction=ignore
''')
# logind grants uinput access to the active local user, as used by common mappers.
# Do not grant access to all keyboards or add the user to the input group.
write('/etc/udev/rules.d/60-minion-gamepad-uinput.rules',
      'SUBSYSTEM=="misc", KERNEL=="uinput", OPTIONS+="static_node=uinput", TAG+="uaccess"\n')
write('/etc/udev/rules.d/60-minion-rear-buttons.rules',
      'SUBSYSTEM=="input", KERNEL=="event*", ATTRS{idVendor}=="2f24", ATTRS{idProduct}=="0135", ENV{ID_INPUT_KEYBOARD}=="1", TAG+="uaccess"\n')
write('/etc/modules-load.d/minion-gamepad.conf', 'uinput\n')
run('modprobe', 'uinput')
run('udevadm', 'control', '--reload-rules')
run('udevadm', 'trigger', '--action=add', '--subsystem-match=backlight')
run('udevadm', 'trigger', '--action=add', '--subsystem-match=misc', '--sysname-match=uinput')
run('udevadm', 'trigger', '--action=change', '--subsystem-match=input')
run('udevadm', 'settle')
for name in ('minion-gamepad', 'minion-screen-lock', 'minion-display-wake', 'minion-rear-buttons'):
    write('/etc/systemd/user/' + name + '.service', HERE.joinpath(name + '.service').read_text())
write('/etc/greetd/config.toml', '''[terminal]
vt = 1
[default_session]
command = "agreety --cmd /usr/local/bin/minion-session"
user = "_greetd"
''')
write('/etc/systemd/system/greetd.service.d/tty.conf', '''[Unit]
After=getty@tty1.service
Conflicts=getty@tty1.service
''')
# Common Ubuntu PAM includes preserve password policy and logind registration.
# The Server login stack references removed pam_lastlog.so; don't inherit it.
for service in ('greetd', 'greetd-greeter'):
    write('/etc/pam.d/' + service, '''#%PAM-1.0
auth requisite pam_nologin.so
@include common-auth
@include common-account
session required pam_loginuid.so
session optional pam_keyinit.so force revoke
session required pam_limits.so
@include common-session
session required pam_env.so
session required pam_env.so envfile=/etc/default/locale
''')
write('/etc/xdg/xdg-desktop-portal/sway-portals.conf', '''[preferred]
default=gtk
org.freedesktop.impl.portal.ScreenCast=wlr
org.freedesktop.impl.portal.Screenshot=wlr
''')
write('/etc/systemd/user/minion-session.target', '''[Unit]
Description=Minion graphical session services
BindsTo=graphical-session.target
After=graphical-session.target
Wants=mako.service minion-polkit.service minion-idle.service minion-display-wake.service minion-rear-buttons.service minion-network-applet.service minion-bluetooth-applet.service minion-gamepad.service
''')
write('/etc/systemd/user/mako.service.d/session.conf', '''[Unit]
PartOf=minion-session.target
After=graphical-session.target
''')
for portal in ('xdg-desktop-portal', 'xdg-desktop-portal-gtk', 'xdg-desktop-portal-wlr'):
    write('/etc/systemd/user/' + portal + '.service.d/session.conf', '''[Unit]
PartOf=minion-session.target
After=graphical-session.target
''')
services = {
    'polkit': '/usr/libexec/polkit-mate-authentication-agent-1',
    'idle': '/usr/local/bin/minion-idle',
    'network-applet': '/usr/bin/nm-applet',
    'bluetooth-applet': '/usr/bin/blueman-applet',
}
for name, command in services.items():
    write('/etc/systemd/user/minion-' + name + '.service', f'''[Unit]
Description=Minion {name}
PartOf=minion-session.target
After=graphical-session.target
[Service]
ExecStart={command}
Restart=on-failure
RestartSec=3
''')
# Merge the renderer through Netplan; retain existing interface matches/DHCP.
write('/etc/netplan/90-minion-renderer.yaml', 'network:\n  version: 2\n  renderer: NetworkManager\n', 0o600)
run('netplan', 'generate')
# A Server installation leaves networkd enabled. Restarting that unused backend
# during upgrades removed the VM's address while NM still showed 'connected'.
# Retain networkd when any explicitly configured Netplan interface needs it.
if not list(Path('/run/systemd/network').glob('*netplan*')):
    run('systemctl', 'disable', *([] if args.defer_activation else ['--now']), 'systemd-networkd-wait-online.service',
        'systemd-networkd.service', 'systemd-networkd.socket')
run('systemctl', 'daemon-reload')
run('systemctl', 'enable', 'NetworkManager.service', 'bluetooth.service', 'greetd.service')
run('systemctl', 'set-default', 'graphical.target')
if args.defer_activation:
    print('Desktop configured. Reboot to activate networking and password-authenticated login.')
    raise SystemExit(0)
# Start/apply only after package/config writes. Existing SSH remains a fallback.
run('systemctl', 'start', 'NetworkManager.service', 'bluetooth.service')
run('netplan', 'apply')
run('nm-online', '--quiet', '--wait-for-startup', '--timeout=60')
# On a first renderer transition NM can retain an assumed external connection
# with only link-local IPv6. Activate its existing compatible Netplan profile;
# never create a guessed connection or replace a normal active user profile.
profiles = {}
for path in Path('/run/NetworkManager/system-connections').glob('netplan-*.nmconnection'):
    config = configparser.ConfigParser(interpolation=None)
    config.read(path)
    if config.getboolean('connection', 'autoconnect', fallback=True):
        profile_id = config.get('connection', 'id')
        uuid = subprocess.check_output(['nmcli', '-g', 'connection.uuid', 'connection',
                                       'show', 'id', profile_id], text=True).strip()
        profiles[uuid] = config.getint('connection', 'autoconnect-priority', fallback=0)
devices = subprocess.check_output(['nmcli', '-t', '-f', 'DEVICE,STATE', 'device'], text=True)
for line in devices.splitlines():
    device, state = line.split(':', 1)
    if '(externally)' not in state:
        continue
    available = subprocess.check_output(['nmcli', '-g', 'CONNECTIONS.AVAILABLE-CONNECTIONS',
                                       'device', 'show', device], text=True)
    compatible = [line.split(' | ', 1)[0].strip() for line in available.splitlines()]
    candidates = [uuid for uuid in compatible if uuid in profiles]
    if candidates:
        selected = max(candidates, key=lambda uuid: profiles[uuid])
        run('nmcli', '--wait', '60', 'connection', 'up', 'uuid', selected, 'ifname', device)
run('nm-online', '--quiet', '--timeout=60')
print('Desktop configured. Reboot to start the password-authenticated session.')
