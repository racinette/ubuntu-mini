#!/usr/bin/env python3
"""Check Wi-Fi selection without opening a GUI or touching host networking."""
import runpy
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
import sys


class Wifi:
    def __init__(self, aps, active=None):
        self.aps, self.active = aps, active
    def get_path(self): return '/wifi/1'
    def get_access_points(self): return self.aps
    def get_active_access_point(self): return self.active
    def get_state(self): return 100
    def filter_connections(self, connections): return connections


def ap(path, name, strength, flags=1, security=0):
    return SimpleNamespace(get_path=lambda: path, get_ssid=lambda: (
        SimpleNamespace(get_data=lambda: name) if name is not None else None),
        get_strength=lambda: strength, get_flags=lambda: flags,
        get_wpa_flags=lambda: security, get_rsn_flags=lambda: security,
        connection_valid=lambda connection: connection.valid)


nm = SimpleNamespace(DeviceWifi=Wifi, DeviceState=SimpleNamespace(ACTIVATED=100),
                     utils_ssid_to_utf8=lambda value: value.decode('utf-8', errors='replace'))
setattr(nm, '80211ApFlags', SimpleNamespace(PRIVACY=1))
setattr(nm, '80211ApSecurityFlags', SimpleNamespace(KEY_MGMT_802_1X=512))
gi = ModuleType('gi'); gi.require_version = Mock()
repository = ModuleType('gi.repository')
repository.Gio = SimpleNamespace()
repository.GLib = SimpleNamespace(Error=RuntimeError)
repository.Gtk = SimpleNamespace(Application=object)
repository.NM = nm
script = Path(__file__).resolve().parents[1] / 'setup/desktop/minion-network'
with patch.dict(sys.modules, {'gi': gi, 'gi.repository': repository}):
    module = runpy.run_path(str(script))

weak = ap('/ap/weak', b'Cafe', 20)
strong = ap('/ap/strong', b'Cafe', 80)
open_ap = ap('/ap/open', b'Cafe', 60, flags=0)
hidden = ap('/ap/hidden', None, 90)
quoted = ap('/ap/quoted', b'Guest: "network"; $(literal)', 50)
device = Wifi([weak, strong, open_ap, hidden, quoted], weak)
client = Mock()
client.get_devices.return_value = [object(), device]
entries = module['nearby_networks'](client)
assert entries[0][1] is weak and entries[0][3] is True
assert len(entries) == 3  # Duplicate radios merge; different security stays distinct.
assert any(entry[2] == 'Guest: "network"; $(literal)' for entry in entries)
device.active = None
assert module['nearby_networks'](client)[0][1] is strong


def profile(priority, timestamp, valid=True):
    setting = SimpleNamespace(get_autoconnect_priority=lambda: priority,
                              get_timestamp=lambda: timestamp)
    return SimpleNamespace(get_setting_connection=lambda: setting, valid=valid)

old, recent, preferred, wrong = profile(0, 1), profile(0, 2), profile(10, 0), profile(100, 99, False)
client.get_connections.return_value = [old, recent, preferred, wrong]
assert module['saved_connection'](client, device, strong) is preferred
client.get_connections.return_value = [old, recent]
assert module['saved_connection'](client, device, strong) is recent

app = module['Networks'].__new__(module['Networks'])
app.client = client
app.refresh = Mock()
app.edit = Mock()
app.activation_started = Mock()
# Selecting a known AP reuses its saved profile and never duplicates it.
app.connect_network(None, device, strong, 'Cafe')
client.activate_connection_async.assert_called_once_with(recent, device, '/ap/strong', None,
                                                         app.activation_started, False)
client.add_and_activate_connection_async.assert_not_called()
assert app.busy
# Unknown personal networks delegate connection completion and secrets to NM.
client.get_connections.return_value = []
app.connect_network(None, device, quoted, 'Guest: "network"; $(literal)')
client.add_and_activate_connection_async.assert_called_once_with(None, device, '/ap/quoted', None,
                                                                app.activation_started, True)
# Unknown enterprise APs need explicit configuration, never guessed credentials.
client.reset_mock()
client.get_connections.return_value = []
enterprise = ap('/ap/enterprise', b'Office', 70, security=512)
app.connect_network(None, device, enterprise, 'Office')
app.edit.assert_called_once()
client.add_and_activate_connection_async.assert_not_called()
client.activate_connection_async.assert_not_called()
print('Wi-Fi picker passed: AP grouping, literal SSIDs, saved-profile reuse, secret-agent delegation and enterprise guard.')
