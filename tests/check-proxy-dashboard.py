#!/usr/bin/env python3
"""Check dashboard migration, safe assets and native selector persistence without a subscription."""
import argparse
from contextlib import contextmanager, redirect_stdout
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
proxy = load('proxy_dashboard_management', ROOT / 'setup/proxy/manage.py')
dashboard = load('dashboard_assets', ROOT / 'setup/proxy/dashboard.py')


def archive(entries):
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode='w:gz') as output:
        for name, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = '/tmp/escape'
            data = b'<html>fixture</html>'
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            output.addfile(member, io.BytesIO(data) if member.size else None)
    return content.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mihomo', type=Path)
    parser.add_argument('--dashboard-dir', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mn-dashboard-', dir='/tmp') as temporary:
        state = Path(temporary)
        target = state / 'assets'
        target.mkdir()
        dashboard.unpack(archive([('index.html', tarfile.REGTYPE)]), target)
        for name, kind in (('../escape', tarfile.REGTYPE), ('/tmp/escape', tarfile.REGTYPE),
                           ('link', tarfile.SYMTYPE), ('link', tarfile.LNKTYPE)):
            try:
                dashboard.unpack(archive([('index.html', tarfile.REGTYPE), (name, kind)]), target)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe dashboard archive accepted')
        secret = 'fixture-secret-' + 'x' * 32
        proxy.write_private(state / 'dashboard.json', json.dumps({'secret': secret}).encode())
        original = proxy.configuration('https://provider.invalid/private', 'tun', 'fixture')
        original['proxy-groups'].append({'name': 'Personal', 'type': 'select', 'proxies': ['DIRECT']})

        def legacy(name=None):
            config = json.loads(json.dumps(original))
            config['proxy-groups'] = [g for g in config['proxy-groups'] if g['name'] != 'Automatic']
            group = proxy.proxy_group(config)
            group.clear()
            if name is None:
                group.update(name='PROXY', type='url-test', use=['subscription'],
                             url='https://www.gstatic.com/generate_204', interval=300, tolerance=50)
            else:
                import re
                pattern = '^' + re.escape(name).replace('`', r'\x60') + '$'
                group.update(name='PROXY', type='select', use=['subscription'],
                             filter=pattern, **{'empty-fallback': 'REJECT'})
            return config

        with patch.object(proxy, 'STATE', state):
            runtime = proxy.dashboard_runtime(original)
            assert proxy.proxy_group(original)['type'] == 'select'
            assert runtime['tun'] == original['tun'] and runtime['rules'] == original['rules']
            assert runtime['external-controller'] == '127.0.0.1:9090'
            assert runtime['secret'] == secret and runtime['profile']['store-selected']
            assert proxy.proxy_group(runtime)['proxies'] == ['Automatic']
            assert proxy.migrate_dashboard(original) == original
            pending = state / 'dashboard-migration.json'
            with patch.object(proxy, 'validate'), patch.object(proxy, 'controller_request', side_effect=OSError):
                for name in (None, '日本 🇯🇵', r'EU [1].*`test\path'):
                    old = legacy(name)
                    migrated = proxy.migrate_dashboard(old)
                    assert proxy.proxy_group(migrated) == proxy.proxy_group(original)
                    assert migrated['rules'] == old['rules'] and migrated['tun'] == old['tun']
                    assert migrated['proxy-providers'] == old['proxy-providers']
                    assert next(g for g in migrated['proxy-groups'] if g['name'] == 'Personal') == original['proxy-groups'][-1]
                    assert json.loads(pending.read_text())['name'] == (name or 'Automatic')
                    assert pending.stat().st_mode & 0o777 == 0o600
                    assert proxy.migrate_dashboard(migrated) == migrated
            # A newer graphical selection wins over the historical CLI pin.
            with patch.object(proxy, 'validate'), patch.object(proxy, 'controller_request', return_value=(200, {'now':'New', 'all':['Old','New','Automatic']})):
                proxy.migrate_dashboard(legacy('Old'))
                assert json.loads(pending.read_text())['name'] == 'New'
            with patch.object(proxy, 'validate'), patch.object(proxy, 'controller_request', side_effect=[
                    (200, {'now':'Configured selection','all':['Configured selection','Old','New','Automatic']}),
                    (200, {'now':'Old'})]):
                proxy.migrate_dashboard(legacy('Old'))
                assert json.loads(pending.read_text())['name'] == 'Old'
            # Validation failures preserve both the old config and pending choice.
            before = (state / 'config.json').read_bytes(), pending.read_bytes()
            with patch.object(proxy, 'validate', side_effect=proxy.ProxyError('fixture')), patch.object(proxy, 'controller_request', side_effect=OSError):
                try:
                    proxy.migrate_dashboard(legacy('Another'))
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Failed migration validation accepted')
            assert before == ((state / 'config.json').read_bytes(), pending.read_bytes())
            invalid = legacy('Old')
            proxy.proxy_group(invalid)['filter'] = '^EU.*$'
            try:
                proxy.migrate_dashboard(invalid)
            except proxy.ProxyError:
                pass
            else:
                raise AssertionError('Personal regex treated as a literal pin')
            # Only clear a migration after the native API confirms the choice.
            child = type('Child', (), {'poll': lambda self: None})()
            proxy.write_private(pending, b'{"name":"Old"}')
            with patch.object(proxy, 'controller_request', side_effect=[
                    (200, {'all':['Old','New']}), (204,None), (200,{'now':'Old'})]):
                proxy.restore_migrated_selection(child)
            assert not pending.exists()
            with patch.object(proxy, 'controller_request') as request:
                proxy.restore_migrated_selection(child)
                request.assert_not_called()
            proxy.write_private(pending, b'{"name":"Missing"}')
            stopped = type('Child', (), {'poll': lambda self: 1})()
            try:
                proxy.restore_migrated_selection(stopped)
            except proxy.ProxyError:
                assert pending.exists()
            else:
                raise AssertionError('Lost a failed migration')
            pending.unlink()
            if args.mihomo:
                binary = args.mihomo.resolve()
                names = ['Alpha', '日本 🇯🇵']
                payload = '\n'.join('vless://11111111-1111-1111-1111-111111111111@127.0.0.1:9?security=none&type=tcp#'+urllib.parse.quote(name) for name in names)
                proxy.write_private(state / 'providers/subscription.txt', payload.encode())
                config = original
                config['tun']['enable'] = config['dns']['enable'] = False
                config['mixed-port'] = 0
                config['proxy-providers']['subscription'] = {'type': 'file', 'path': './providers/subscription.txt'}
                proxy.write_private(state / 'config.json', json.dumps(config).encode())
                sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
                @contextmanager
                def engine():
                    config = proxy.migrate_dashboard(proxy.load_config())
                    runtime = proxy.dashboard_runtime(config)
                    runtime['external-controller'] = f'127.0.0.1:{port}'
                    if args.dashboard_dir:
                        runtime['external-ui'] = str(args.dashboard_dir.resolve())
                    path = state / 'test-runtime.json'
                    proxy.write_private(path, json.dumps(runtime, ensure_ascii=False).encode())
                    environment = dict(os.environ, SAFE_PATHS=runtime['external-ui'])
                    with (state / 'engine.log').open('a') as log:
                        child = subprocess.Popen([str(binary), '-d', str(state), '-f', str(path)], stdout=log, stderr=subprocess.STDOUT, env=environment)
                        try:
                            deadline = time.monotonic() + 10
                            while True:
                                try:
                                    status, group = proxy.controller_request(state / 'dashboard.sock', '/proxies/PROXY')
                                    if status == 200 and names[0] in group.get('all', []): break
                                except (OSError, ValueError, http.client.HTTPException): pass
                                if child.poll() is not None or time.monotonic() > deadline:
                                    raise AssertionError('Native dashboard core failed to start: ' + (state / 'engine.log').read_text()[-1500:])
                                time.sleep(.05)
                            proxy.restore_migrated_selection(child)
                            yield child, port
                        finally:
                            child.terminate()
                            child.wait(timeout=5)
                def query(path, method='GET', body=None):
                    return proxy.controller_request(state / 'dashboard.sock', path, method=method, body=body)
                with engine():
                    assert query('/proxies/PROXY')[1]['now'] == 'Automatic'
                    client = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                    client.request('GET', '/version')
                    response = client.getresponse(); response.read()
                    assert response.status == 401
                    client.close()
                    if args.dashboard_dir:
                        client = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                        client.request('GET', '/ui/')
                        response = client.getresponse(); content = response.read()
                        assert response.status == 200 and b'MetaCubeXD' in content and secret.encode() not in content
                        client.close()
                    assert query('/proxies/PROXY', 'PUT', {'name': names[1]})[0] == 204
                    assert query('/proxies/PROXY')[1]['now'] == names[1]
                    time.sleep(.3)
                with engine():
                    assert query('/proxies/PROXY')[1]['now'] == names[1], 'Dashboard selection lost on restart'
                proxy.write_private(state / 'providers/subscription.txt', payload.split('\n')[0].encode())
                with engine():
                    assert query('/proxies/PROXY')[1]['now'] == 'Automatic', 'Missing GUI choice did not fall back to the first option'
                proxy.write_private(state / 'providers/subscription.txt', payload.encode())
                # A legacy pin is restored once, then GUI changes stay authoritative.
                for active_gui_choice in (None, names[0]):
                    old = legacy(names[1])
                    old['tun']['enable'] = old['dns']['enable'] = False
                    old['mixed-port'] = 0
                    old['proxy-providers']['subscription'] = {'type': 'file', 'path': './providers/subscription.txt'}
                    proxy.write_private(state / 'config.json', json.dumps(old, ensure_ascii=False).encode())
                    if active_gui_choice is None:
                        read = patch.object(proxy, 'controller_request', side_effect=OSError)
                    else:
                        read = patch.object(proxy, 'controller_request', return_value=(200,{'now':active_gui_choice,'all':['Automatic',*names]}))
                    with patch.object(proxy, 'BINARY', binary), read:
                        proxy.migrate_dashboard(proxy.load_config())
                    with engine():
                        assert query('/proxies/PROXY')[1]['now'] == (active_gui_choice or names[1])
                        assert query('/proxies/PROXY', 'PUT', {'name': names[0]})[0] == 204
                    assert not (state / 'dashboard-migration.json').exists()
                    with engine():
                        assert query('/proxies/PROXY')[1]['now'] == names[0], 'Legacy policy overrode a newer dashboard choice'
                print('Passed: native authenticated API, local panel, Unicode selection persistence, missing-node fallback and one-time migration across restarts.')
        print('Passed: safe dashboard assets, native selector, one-time legacy migration, current GUI choice, preservation/rollback and confirmed migration cleanup.')


if __name__ == '__main__':
    main()
