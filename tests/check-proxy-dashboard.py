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
        with patch.object(proxy, 'STATE', state):
            runtime, selection = proxy.dashboard_runtime(original)
            assert proxy.proxy_group(original)['type'] == 'url-test'
            assert runtime['tun'] == original['tun'] and runtime['rules'] == original['rules']
            assert runtime['external-controller'] == '127.0.0.1:9090'
            assert runtime['secret'] == secret and runtime['profile']['store-selected']
            assert proxy.proxy_group(runtime)['proxies'] == ['Automatic']
            pinned = json.loads(json.dumps(original))
            proxy.proxy_group(pinned).update(type='select', filter=proxy.server_pattern('日本 🇯🇵'), **{'empty-fallback': 'REJECT'})
            result, choice = proxy.dashboard_runtime(pinned)
            assert choice['default'] == 'Configured selection'
            legacy = next(group for group in result['proxy-groups'] if group['name'] == 'Configured selection')
            assert legacy['filter'] == proxy.server_pattern('日本 🇯🇵') and legacy['empty-fallback'] == 'REJECT'
            assert result['proxy-groups'][2] == original['proxy-groups'][1]
            assert choice['fingerprint'] != selection['fingerprint']
            assert proxy.dashboard_runtime(original)[1] == selection
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
                    runtime, selected = proxy.dashboard_runtime(proxy.load_config())
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
                            proxy.reconcile_dashboard(child, selected)
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
                with patch.object(proxy, 'BINARY', binary), redirect_stdout(io.StringIO()):
                    proxy.select_server(automatic=True, restart=False)
                with engine():
                    assert query('/proxies/PROXY')[1]['now'] == 'Automatic', 'Explicit auto did not supersede GUI selection'
                    assert query('/proxies/PROXY', 'PUT', {'name': names[1]})[0] == 204
                with patch.object(proxy, 'BINARY', binary), patch.object(proxy, 'cached_servers', return_value=names), redirect_stdout(io.StringIO()):
                    proxy.select_server('Alpha', restart=False)
                with engine():
                    assert query('/proxies/PROXY')[1]['now'] == 'Configured selection'
                    assert query('/proxies/Configured%20selection')[1]['now'] == 'Alpha'
                with engine():
                    assert query('/proxies/PROXY')[1]['now'] == 'Configured selection'
                print('Passed: native authenticated API, local static panel, Unicode selection persistence and deliberate CLI override across restarts.')
        print('Passed: safe dashboard extraction, automatic/pinned migration, preserved routing/credentials/personal groups and stable selection source.')


if __name__ == '__main__':
    main()
