#!/usr/bin/python3
"""Check battery policy and warnings without changing host power or battery state."""
import argparse
import configparser
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import time
from unittest.mock import Mock, patch

DESKTOP = Path(__file__).resolve().parents[1] / 'setup/desktop'


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def unit_checks():
    policy = load('battery_policy', DESKTOP / 'battery.py')
    warnings = load('battery_warnings', DESKTOP / 'minion-battery-warnings')
    notify, close = Mock(return_value=42), Mock()
    tracker = warnings.Warnings(notify, close)
    device = dict(Type=2, IsPresent=True, Percentage=20.0, WarningLevel=3)
    tracker.update(False, device)
    tracker.update(True, dict(device, Percentage=80.0, WarningLevel=1))
    notify.assert_not_called()
    tracker.update(True, device)
    assert notify.call_args.args[0] == 0 and notify.call_args.args[-2:] == (1, 15000)
    for reading in (device, dict(device, Percentage=19), dict(device, WarningLevel=1), device):
        tracker.update(True, reading)
    assert notify.call_count == 1  # No spam, including threshold oscillation.
    tracker.update(True, dict(device, Percentage=10, WarningLevel=4))
    assert notify.call_args.args[0] == 42 and notify.call_args.args[-2:] == (2, 0)
    tracker.update(True, dict(device, Percentage=5, WarningLevel=5))
    assert notify.call_count == 3 and 'shutdown pending' in notify.call_args.args[1]
    tracker.update(False, device)
    close.assert_called_once_with(42)
    assert tracker.announced == 0 and tracker.notification_id == 0
    tracker.update(True, dict(device, Percentage=8, WarningLevel=4))
    assert notify.call_count == 4 and notify.call_args.args[0] == 0  # Low-charge startup/unplug.
    tracker.update(False, device)
    for invalid in (dict(device, Percentage=float('nan')), dict(device, Percentage=-1),
                    dict(device, Percentage=101), dict(device, IsPresent=False),
                    dict(device, Type=5), dict(device, WarningLevel=6)):
        tracker.update(True, invalid)
    assert notify.call_count == 4
    notify.side_effect = RuntimeError('notification server unavailable')
    try:
        tracker.update(True, device)
    except RuntimeError:
        pass
    assert tracker.announced == 0
    notify.side_effect = None
    tracker.update(True, device)
    assert tracker.announced == 3

    with tempfile.TemporaryDirectory(prefix='minion-battery-policy-') as temporary:
        path = Path(temporary) / 'UPower.conf'
        with patch.object(policy.os, 'chown'):
            assert policy.install(path)
            first = path.read_bytes()
            assert not policy.install(path) and path.read_bytes() == first
            assert path.stat().st_mode & 0o777 == 0o644
            for original in ('# keep comment\n[UPower]\nIgnoreLid=true\nPercentageAction=2\n'
                             'NoPollBatteries=true\n[Other]\ncustom=value\n',
                             '[Other]\ncustom=value\n',
                             '[UPower]\nPercentageLow=15\nPercentageLow=18\n'):
                path.write_text(original)
                assert policy.install(path)
                config = configparser.ConfigParser(strict=False)
                config.optionxform = str
                config.read(path)
                assert {key: config['UPower'][key] for key in policy.POLICY} == policy.POLICY
                if 'IgnoreLid' in original:
                    assert config['UPower']['IgnoreLid'] == 'true'
                    assert config['UPower']['NoPollBatteries'] == 'true'
                    assert path.read_text().startswith('# keep comment\n')
                if '[Other]' in original:
                    assert config['Other']['custom'] == 'value'
                assert not policy.install(path)
            path.write_text('not a config')
            try:
                policy.install(path)
            except configparser.Error:
                pass
            else:
                raise AssertionError('Malformed UPower config overwritten')
            assert path.read_text() == 'not a config'
            link = Path(temporary) / 'link'
            link.symlink_to(path)
            try:
                policy.install(link)
            except ValueError:
                pass
            else:
                raise AssertionError('UPower symlink accepted')


def integration():
    """Run the real watcher against isolated UPower and notification D-Bus fixtures."""
    from gi.repository import Gio, GLib
    fixture = load('battery_fixture', DESKTOP / 'minion-battery-warnings')
    daemon = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                              stdout=subprocess.PIPE, text=True)
    watcher = None
    try:
        address = daemon.stdout.readline().strip()
        bus = Gio.DBusConnection.new_for_address_sync(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)

        def name(method, value):
            return bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', method,
                GLib.Variant('(su)', (value, 0)) if method == 'RequestName' else GLib.Variant('(s)', (value,)),
                None, Gio.DBusCallFlags.NONE, 2000, None)

        name('RequestName', fixture.UPOWER)
        name('RequestName', fixture.NOTIFICATIONS)
        state = dict(OnBattery=False, Type=2, IsPresent=True, Percentage=100.0, WarningLevel=1)
        calls, closed, reads = [], [], []
        xml = '''<node><interface name="org.freedesktop.DBus.Properties">
          <method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
          <signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>
        </interface><interface name="org.freedesktop.Notifications">
          <method name="Notify"><arg type="s" direction="in"/><arg type="u" direction="in"/>
          <arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/>
          <arg type="as" direction="in"/><arg type="a{sv}" direction="in"/><arg type="i" direction="in"/>
          <arg type="u" direction="out"/></method>
          <method name="CloseNotification"><arg type="u" direction="in"/></method>
        </interface></node>'''
        interfaces = Gio.DBusNodeInfo.new_for_xml(xml).interfaces

        def properties(connection, sender, path, interface, method, parameters, invocation):
            reads.append(path)
            keys = ['OnBattery'] if path == fixture.ROOT else ['Type', 'IsPresent', 'Percentage', 'WarningLevel']
            kinds = dict(OnBattery='b', Type='u', IsPresent='b', Percentage='d', WarningLevel='u')
            invocation.return_value(GLib.Variant('(a{sv})',
                ({key: GLib.Variant(kinds[key], state[key]) for key in keys},)))

        def notifications(connection, sender, path, interface, method, parameters, invocation):
            if method == 'Notify':
                calls.append(parameters.unpack())
                invocation.return_value(GLib.Variant('(u)', (42,)))
            else:
                closed.append(parameters.unpack()[0])
                invocation.return_value(GLib.Variant('()', ()))

        for path in (fixture.ROOT, fixture.DISPLAY):
            bus.register_object(path, interfaces[0], properties, None, None)
        bus.register_object('/org/freedesktop/Notifications', interfaces[1], notifications, None, None)
        watcher = subprocess.Popen(['/usr/bin/python3', str(DESKTOP / 'minion-battery-warnings')],
            env={**os.environ, 'DBUS_SYSTEM_BUS_ADDRESS': address, 'DBUS_SESSION_BUS_ADDRESS': address},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        context = GLib.MainContext.default()

        def wait(predicate, seconds=3):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                while context.pending():
                    context.iteration(False)
                assert watcher.poll() is None, 'Battery watcher stopped unexpectedly'
                if predicate():
                    return
                time.sleep(.01)
            raise AssertionError('Battery D-Bus transition timed out')

        def emit(path=fixture.DISPLAY):
            bus.emit_signal(None, path, fixture.PROPERTIES, 'PropertiesChanged',
                GLib.Variant('(sa{sv}as)', (fixture.UPOWER + '.Device', {}, [])))
            bus.flush_sync(None)

        wait(lambda: len(reads) >= 2)
        assert not calls  # Quiet while charged.
        for percentage, level, count in ((20., 3, 1), (10., 4, 2), (5., 5, 3)):
            state.update(OnBattery=True, Percentage=percentage, WarningLevel=level)
            emit()
            wait(lambda: len(calls) == count)
            assert calls[-1][1] == (0 if count == 1 else 42)
            assert calls[-1][6]['urgency'] == (1 if level == 3 else 2)
            assert calls[-1][7] == (15000 if level == 3 else 0)
        baseline = len(reads)
        emit()
        wait(lambda: len(reads) >= baseline + 2)
        assert len(calls) == 3
        # A peripheral event must not be observed.
        baseline = len(reads)
        emit(fixture.ROOT + '/devices/headphones')
        end = time.monotonic() + .15
        while time.monotonic() < end:
            while context.pending():
                context.iteration(False)
            time.sleep(.01)
        assert len(reads) == baseline
        state.update(OnBattery=False, WarningLevel=1)
        emit(fixture.ROOT)
        wait(lambda: closed == [42])
        state.update(OnBattery=True, Percentage=8., WarningLevel=4)
        emit()
        wait(lambda: len(calls) == 4)
        assert calls[-1][1] == 0
        # An UPower owner restart triggers a fresh snapshot without alert spam.
        baseline = len(reads)
        name('ReleaseName', fixture.UPOWER)
        name('RequestName', fixture.UPOWER)
        wait(lambda: len(reads) >= baseline + 2)
        assert len(calls) == 4
        bus.close_sync(None)
    finally:
        if watcher:
            watcher.terminate()
            watcher.communicate(timeout=3)
        daemon.terminate()
        daemon.communicate(timeout=3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration', action='store_true', help='Use an isolated real D-Bus')
    args = parser.parse_args()
    unit_checks()
    if args.integration:
        integration()
    print('Passed: UPower policy, warning escalation/deduplication, charger reset and notification retry'
          + ('; isolated real D-Bus watcher' if args.integration else ''))
