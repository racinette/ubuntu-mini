#!/usr/bin/env python3
"""Check regional rule precedence, retained settings and real direct/proxy routing."""
import argparse
from contextlib import contextmanager, redirect_stdout
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('proxy_bypass', ROOT / 'setup/proxy/manage.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mihomo', type=Path)
    args = parser.parse_args()
    original = proxy.configuration('https://provider.invalid/private', 'tun', 'fixture')
    assert original['rules'][-3:] == proxy.BY_RULES + ['MATCH,PROXY']
    assert 'бел'.encode('idna').decode() == 'xn--90ais'
    original['rules'].insert(0, 'DOMAIN,personal.invalid,REJECT')
    original['rule-providers'] = {'personal': {'type': 'inline', 'behavior': 'domain', 'payload': ['personal.invalid']}}
    enabled = proxy.regional_bypass_config(original, True)
    assert enabled['rules'][-3:] == proxy.RU_RULES + ['MATCH,PROXY']
    assert enabled['rules'][:-3] == original['rules'][:-1]
    assert enabled['tun'] == original['tun'] and enabled['dns'] == original['dns']
    assert enabled['proxy-providers'] == original['proxy-providers']
    assert proxy.regional_bypass_config(enabled, True) == enabled
    assert proxy.regional_bypass_config(enabled, False) == original
    assert enabled['rule-providers']['personal'] == original['rule-providers']['personal']
    belarus = proxy.regional_bypass_config(enabled, True, 'by')
    assert belarus['rules'][-2:] == proxy.BY_IP_RULES + ['MATCH,PROXY']
    assert proxy.regional_bypass_config(belarus, True, 'by') == belarus
    assert proxy.regional_bypass_config(belarus, False, 'by') == enabled
    assert belarus['rule-providers']['minion-ru-ips'] == enabled['rule-providers']['minion-ru-ips']
    conflict_by = json.loads(json.dumps(enabled))
    conflict_by['rule-providers']['minion-by-ips'] = {'type': 'file', 'path': './personal'}
    try:
        proxy.regional_bypass_config(conflict_by, True, 'by')
    except proxy.ProxyError:
        pass
    else:
        raise AssertionError('Overwrote a personal Belarus provider')
    conflict = json.loads(json.dumps(original))
    conflict['rule-providers']['minion-ru-domains'] = {'type': 'file', 'path': './personal'}
    try:
        proxy.regional_bypass_config(conflict, True)
    except proxy.ProxyError:
        pass
    else:
        raise AssertionError('Overwrote a personal provider')
    with tempfile.TemporaryDirectory(prefix='mn-ru-bypass-', dir='/tmp') as temporary:
        state = Path(temporary)
        with patch.object(proxy, 'STATE', state):
            proxy.write_private(state / 'config.json', json.dumps(original).encode())
            before = (state / 'config.json').read_bytes()
            with patch.object(proxy, 'cache_bypass_rules', side_effect=proxy.ProxyError('Failed download')):
                try:
                    proxy.set_bypass(True)
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Accepted a failed download')
            assert (state / 'config.json').read_bytes() == before
            with patch.object(proxy, 'cache_bypass_rules'), patch.object(proxy, 'validate'), redirect_stdout(io.StringIO()):
                proxy.set_bypass(True)
                assert proxy.load_config() == enabled
                proxy.set_bypass(False)
                assert proxy.load_config() == original
            before = (state / 'config.json').read_bytes()
            with patch.object(proxy, 'cache_bypass_rules', side_effect=proxy.ProxyError('Failed download')):
                try:
                    proxy.set_bypass(True, 'by')
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Accepted a failed Belarus download')
            assert (state / 'config.json').read_bytes() == before
            with patch.object(proxy, 'cache_bypass_rules'), patch.object(proxy, 'validate'), redirect_stdout(io.StringIO()):
                proxy.set_bypass(True, 'by')
                assert proxy.load_config() == proxy.regional_bypass_config(original, True, 'by')
                proxy.set_bypass(False, 'by')
                assert proxy.load_config() == original
        if args.mihomo:
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200); self.end_headers(); self.wfile.write(b'direct fixture')
                def log_message(self, *args): pass
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            listener = socket.socket(); listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]; listener.close()
            config = {'mode': 'rule', 'mixed-port': port, 'bind-address': '127.0.0.1',
                      'external-controller-unix': str(state / 'api.sock'),
                      'hosts': {'direct.test.invalid': '127.0.0.1', 'proxy.test.invalid': '127.0.0.1'},
                      'proxy-groups': [{'name': 'PROXY', 'type': 'select', 'proxies': ['REJECT']}],
                      'rule-providers': {}, 'rules': ['DOMAIN,blocked.by,REJECT'] + proxy.BY_RULES + proxy.RU_RULES + proxy.BY_IP_RULES + ['MATCH,PROXY']}
            belarus_domains = ['hoster.by', 'api.hoster.by', 'пример.бел'.encode('idna').decode()]
            for host in belarus_domains + ['hoster.by.example.invalid', 'blocked.by']:
                config['hosts'][host] = '127.0.0.1'
            for name, definition in (proxy.RU_PROVIDERS | proxy.BY_PROVIDERS).items():
                config['rule-providers'][name] = {'type': 'file', 'behavior': definition['behavior'],
                                                 'format': 'text', 'path': definition['path']}
            (state / 'rules').mkdir()
            (state / 'rules/ru-domains.list').write_text('+.test.invalid\n')
            # An unrelated IP range makes the domain test depend on domain routing.
            (state / 'rules/ru-ips.list').write_text('192.0.2.0/24\n')
            (state / 'rules/by-ips.list').write_text('198.51.100.0/24\n')
            path = state / 'fixture.json'; path.write_text(json.dumps(config))
            def request(host):
                client = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                try:
                    client.request('GET', f'http://{host}:{server.server_port}/')
                    response = client.getresponse()
                    return response.status, response.read()
                except (OSError, http.client.HTTPException):
                    return None, b''
                finally:
                    client.close()
            @contextmanager
            def run_checks():
                with (state / 'core.log').open('w') as log:
                    child = subprocess.Popen([str(args.mihomo.resolve()), '-d', str(state), '-f', str(path)], stdout=log, stderr=log)
                    try:
                        for _ in range(100):
                            if (state / 'api.sock').exists(): break
                            if child.poll() is not None: raise AssertionError((state / 'core.log').read_text())
                            time.sleep(.05)
                        yield child
                    finally:
                        child.terminate(); child.wait(timeout=5)
            try:
                with run_checks():
                    assert request('direct.test.invalid') == (200, b'direct fixture'), 'Domain bypass failed'
                    for host in belarus_domains:
                        assert request(host) == (200, b'direct fixture'), 'Belarus suffix bypass failed: ' + host
                    assert request('hoster.by.example.invalid')[0] != 200, 'Suffix lookalike bypassed PROXY'
                    assert request('blocked.by')[0] != 200, 'Bypass overrode an earlier personal rule'
                    assert request('127.0.0.1')[0] != 200, 'Unmatched destination bypassed PROXY'
                (state / 'api.sock').unlink(missing_ok=True)
                (state / 'rules/ru-ips.list').write_text('127.0.0.1/32\n')
                with run_checks():
                    assert request('127.0.0.1') == (200, b'direct fixture'), 'IP bypass failed'
                (state / 'api.sock').unlink(missing_ok=True)
                (state / 'rules/ru-ips.list').write_text('192.0.2.0/24\n')
                (state / 'rules/by-ips.list').write_text('127.0.0.1/32\n')
                with run_checks():
                    assert request('127.0.0.1') == (200, b'direct fixture'), 'Belarus IP bypass failed'
                    status, connections = proxy.controller_request(state / 'api.sock', '/rules')
                    assert status == 200 and any(r.get('payload') == 'minion-by-ips' for r in connections['rules'])
            finally:
                server.shutdown(); server.server_close(); worker.join(timeout=5)
            print('Passed: Russian domain/IP and Belarus suffix/IP direct routing, IDNA/subdomains, earlier exceptions and unmatched traffic through PROXY.')
    print('Passed: bypass precedence, idempotence, personal settings, disabling and failed-download preservation.')


if __name__ == '__main__':
    main()
