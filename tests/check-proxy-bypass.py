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
    original['rules'].insert(0, 'DOMAIN,personal.invalid,REJECT')
    original['rule-providers'] = {'personal': {'type': 'inline', 'behavior': 'domain', 'payload': ['personal.invalid']}}
    enabled = proxy.ru_bypass_config(original, True)
    assert enabled['rules'][-3:] == proxy.RU_RULES + ['MATCH,PROXY']
    assert enabled['rules'][:-3] == original['rules'][:-1]
    assert enabled['tun'] == original['tun'] and enabled['dns'] == original['dns']
    assert enabled['proxy-providers'] == original['proxy-providers']
    assert proxy.ru_bypass_config(enabled, True) == enabled
    assert proxy.ru_bypass_config(enabled, False) == original
    assert enabled['rule-providers']['personal'] == original['rule-providers']['personal']
    conflict = json.loads(json.dumps(original))
    conflict['rule-providers']['minion-ru-domains'] = {'type': 'file', 'path': './personal'}
    try:
        proxy.ru_bypass_config(conflict, True)
    except proxy.ProxyError:
        pass
    else:
        raise AssertionError('Overwrote a personal provider')
    with tempfile.TemporaryDirectory(prefix='mn-ru-bypass-', dir='/tmp') as temporary:
        state = Path(temporary)
        with patch.object(proxy, 'STATE', state):
            proxy.write_private(state / 'config.json', json.dumps(original).encode())
            before = (state / 'config.json').read_bytes()
            with patch.object(proxy, 'cache_ru_rules', side_effect=proxy.ProxyError('Failed download')):
                try:
                    proxy.set_ru_bypass(True)
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Accepted a failed download')
            assert (state / 'config.json').read_bytes() == before
            with patch.object(proxy, 'cache_ru_rules'), patch.object(proxy, 'validate'), redirect_stdout(io.StringIO()):
                proxy.set_ru_bypass(True)
                assert proxy.load_config() == enabled
                proxy.set_ru_bypass(False)
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
                      'rule-providers': {}, 'rules': proxy.RU_RULES + ['MATCH,PROXY']}
            for name, definition in proxy.RU_PROVIDERS.items():
                config['rule-providers'][name] = {'type': 'file', 'behavior': definition['behavior'],
                                                 'format': 'text', 'path': definition['path']}
            (state / 'rules').mkdir()
            (state / 'rules/ru-domains.list').write_text('+.test.invalid\n')
            # An unrelated IP range makes the domain test depend on domain routing.
            (state / 'rules/ru-ips.list').write_text('192.0.2.0/24\n')
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
                    assert request('127.0.0.1')[0] != 200, 'Unmatched destination bypassed PROXY'
                (state / 'api.sock').unlink(missing_ok=True)
                (state / 'rules/ru-ips.list').write_text('127.0.0.1/32\n')
                with run_checks():
                    assert request('127.0.0.1') == (200, b'direct fixture'), 'IP bypass failed'
            finally:
                server.shutdown(); server.server_close(); worker.join(timeout=5)
            print('Passed: real domain and IP direct routing with unmatched traffic sent to PROXY.')
    print('Passed: bypass precedence, idempotence, personal settings, disabling and failed-download preservation.')


if __name__ == '__main__':
    main()
