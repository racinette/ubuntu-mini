#!/usr/bin/env python3
"""Collect service/package evidence; this does not substitute for GUI checks."""
import argparse
import json

from gui import experiment
from session import ssh, graphical

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
units = 'mini-os-session.target mako mini-os-polkit mini-os-idle mini-os-network-applet mini-os-bluetooth-applet pipewire pipewire-pulse wireplumber'
states = graphical(directory, 'systemctl --user is-active ' + units)
failed = ssh(directory, 'systemctl --user --failed --no-legend')
report = {
    'units': units.split(), 'active_states': states.splitlines(),
    'failed_user_units': failed,
    'network': ssh(directory, 'nmcli device status; ip -4 address; ip route'),
    'kernel': ssh(directory, 'uname -r').strip(),
    'packages': ssh(directory, "dpkg-query -W -f='${Package} ${Version}\\n' sway greetd foot mate-polkit pipewire wireplumber network-manager"),
    'snaps': ssh(directory, 'snap list'),
    'atuin': ssh(directory, 'atuin --version').strip(),
    'system_failed_units': ssh(directory, 'systemctl --failed --no-legend'),
}
report['passed'] = (len(report['active_states']) == len(report['units'])
                    and all(state == 'active' for state in report['active_states'])
                    and not failed.strip() and not report['system_failed_units'].strip())
directory.joinpath('desktop-state-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if not report['passed']:
    raise SystemExit('Desktop service state check failed')
