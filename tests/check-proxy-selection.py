#!/usr/bin/env python3
"""Check offline server listing and persistent selection; optionally use real Mihomo."""
import argparse
import base64
import contextlib
import http.client
import http.server
import importlib.util
import io
import json
from pathlib import Path
import socket
import socketserver
import select
import ssl
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import urllib.parse
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('proxy', PROJECT / 'setup/proxy/manage.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)
NAMES = ['Alpha (1).+', '日本 🇯🇵', 'Tick```[x]', 'Control\x1b[31m']


def subscription(names):
    # Unreachable loopback endpoints: these fixtures never need a provider account.
    return '\n'.join('vless://11111111-1111-1111-1111-111111111111@127.0.0.1:9'
                     '?security=none&type=tcp#' + urllib.parse.quote(name) for name in names).encode()


def check_https(binary, state):
    """Check real TLS through a working CONNECT proxy, a stalled one and a dead one."""
    certificate, key = state / 'certificate.pem', state / 'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
                    '-keyout', str(key), '-out', str(certificate)],
                   check=True, capture_output=True, timeout=30)
    key.chmod(0o600)

    class HTTPS(http.server.BaseHTTPRequestHandler):
        def do_HEAD(self):
            time.sleep(0.02)  # Keep the measured delay above the API's 0ms failure threshold.
            self.send_response(204 if self.path == '/ok' else 503)
            self.end_headers()
        def log_message(self, *args): pass

    stopping = threading.Event()

    class Connect(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(3)
            try:
                line = self.rfile.readline(8192)
                assert line.startswith(b'CONNECT ')
                while self.rfile.readline(8192).strip():
                    pass
                if self.server.stall:
                    stopping.wait(3)
                    return
                with socket.create_connection(('127.0.0.1', https.server_port), timeout=3) as upstream:
                    self.wfile.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
                    self.wfile.flush()
                    while not stopping.is_set():
                        ready, _, _ = select.select([self.connection, upstream], [], [], 0.2)
                        for source in ready:
                            data = source.recv(65536)
                            if not data:
                                return
                            (upstream if source is self.connection else self.connection).sendall(data)
            except (OSError, AssertionError):
                pass

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True

    https = http.server.ThreadingHTTPServer(('127.0.0.1', 0), HTTPS)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(certificate, key)
    https.socket = tls.wrap_socket(https.socket, server_side=True)
    working, stalled = Server(('127.0.0.1', 0), Connect), Server(('127.0.0.1', 0), Connect)
    working.stall, stalled.stall = False, True
    dead = socket.socket()
    dead.bind(('127.0.0.1', 0))  # Reserved port with no listener: reliably refuses TCP.
    for server in (https, working, stalled):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        names = ['Working 🇯🇵 / (HTTPS)', 'Stalled', 'Unreachable']
        proxies = [{'name': name, 'type': 'http', 'server': '127.0.0.1', 'port': port}
                   for name, port in zip(names, (working.server_address[1], stalled.server_address[1], dead.getsockname()[1]))]
        proxy.write_private(state / 'providers/subscription.txt', json.dumps({'proxies': proxies}, ensure_ascii=False).encode())
        url = f'https://127.0.0.1:{https.server_port}/ok'
        # Trust the ephemeral test CA in this fixture's private config only.
        installed = proxy.load_config()
        installed['tls'] = {'custom-certifactes': [certificate.read_text()]}
        proxy.write_private(state / 'config.json', json.dumps(installed, ensure_ascii=False).encode())
        with proxy.cached_engine(check=True) as (actual, control):
            assert actual == names
            assert proxy.check_server(control, names[0], 2, url).startswith('OK ')
            assert proxy.check_server(control, names[1], 1, url) == 'TIMEOUT'
            assert proxy.check_server(control, names[2], 1, url) in ('FAILED', 'TIMEOUT')
            assert proxy.check_server(control, names[0], 2, url.replace('/ok', '/bad')) == 'FAILED'
        before = (state / 'config.json').read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            proxy.list_servers(timeout=1, url=url)
        assert '[OK ' in output.getvalue() and '[TIMEOUT]' in output.getvalue()
        assert before == (state / 'config.json').read_bytes()
        assert not list(state.glob('.list-*'))
        # A reachable proxy with an untrusted destination certificate must fail.
        installed['tls'] = {}
        proxy.write_private(state / 'config.json', json.dumps(installed).encode())
        with proxy.cached_engine(check=True) as (_, control):
            assert proxy.check_server(control, names[0], 2, url) == 'FAILED'
    finally:
        stopping.set()
        dead.close()
        for server in (working, stalled, https):
            server.shutdown()
            server.server_close()


@contextlib.contextmanager
def engine(binary, directory, config):
    """Load a file provider and expose only a private test Unix socket."""
    config = json.loads(json.dumps(config))
    config['external-controller-unix'] = 'check.sock'
    proxy.write_private(directory / 'probe.json', json.dumps(config, ensure_ascii=False).encode())
    process = subprocess.Popen([str(binary), '-d', str(directory), '-f', str(directory / 'probe.json')],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def query(path):
        connection = http.client.HTTPConnection('localhost', timeout=1)
        try:
            connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.sock.settimeout(1)
            connection.sock.connect(str(directory / 'check.sock'))
            connection.request('GET', path)
            response = connection.getresponse()
            assert response.status == 200
            return json.loads(response.read())
        finally:
            connection.close()
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                # API listener can start before providers/groups are installed,
                # especially under amd64 emulation. Wait for the actual data.
                assert query('/providers/proxies/subscription')['proxies']
                query('/proxies/PROXY')
                break
            except (OSError, AssertionError, http.client.HTTPException):
                assert process.poll() is None and time.monotonic() < deadline, 'Test engine failed to start'
                time.sleep(0.1)
        yield query
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mihomo', type=Path, help='Optional native binary for real cached-provider and filter checks')
    args = parser.parse_args()
    # Keep Unix socket paths short, including on macOS.
    with tempfile.TemporaryDirectory(prefix='mn-', dir='/tmp') as temporary:
        state = Path(temporary)
        original = proxy.configuration('https://provider.invalid/private-token', 'tun', 'fixture')
        original['proxy-groups'].append({'name': 'Personal', 'type': 'select', 'proxies': ['DIRECT']})
        def reset():
            proxy.write_private(state / 'config.json', json.dumps(original).encode())
        with patch.object(proxy, 'STATE', state), patch.object(proxy, 'cached_servers', return_value=NAMES), \
             patch.object(proxy, 'validate') as validate, \
             patch.object(proxy.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as service, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            reset()
            proxy.select_server('2')
            service.assert_called_once_with(['systemctl', 'restart', proxy.UNIT], capture_output=True, timeout=60)
            selected = proxy.load_config()
            group = proxy.proxy_group(selected)
            assert group['filter'] == proxy.server_pattern(NAMES[1]) and group['empty-fallback'] == 'REJECT'
            assert group['type'] == 'select'
            assert {k: v for k, v in selected.items() if k != 'proxy-groups'} == {
                k: v for k, v in original.items() if k != 'proxy-groups'}
            assert selected['proxy-groups'][1] == original['proxy-groups'][1]
            assert (state / 'config.json').stat().st_mode & 0o777 == 0o600
            for name in NAMES:
                proxy.select_server(name)
                proxy.show_servers(proxy.load_config(), NAMES)
            assert '\x1b' not in output.getvalue() and 'private-token' not in output.getvalue()
            assert '[selected]' in output.getvalue()
            proxy.select_server('ALPHA (1)')
            assert proxy.proxy_group(proxy.load_config())['filter'] == proxy.server_pattern(NAMES[0])
            calls = service.call_count
            proxy.select_server('日本', restart=False)
            assert service.call_count == calls
            before = (state / 'config.json').read_bytes()
            for invalid in ('0', '9999', 'does not exist', ''):
                try:
                    proxy.select_server(invalid)
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Invalid selection accepted')
                assert (state / 'config.json').read_bytes() == before
                assert service.call_count == calls
            with patch.object(proxy, 'cached_servers', return_value=['EU 1', 'EU 2', 'EU']):
                proxy.select_server('EU', restart=False)  # Exact match wins over substrings.
                before = (state / 'config.json').read_bytes()
                try:
                    proxy.select_server('eu')
                except proxy.ProxyError as error:
                    assert 'multiple servers' in str(error) and 'EU 1' in str(error)
                else:
                    raise AssertionError('Ambiguous substring accepted')
                assert (state / 'config.json').read_bytes() == before and service.call_count == calls
            validate.side_effect = proxy.ProxyError('Invalid fixture configuration')
            try:
                proxy.select_server('1')
            except proxy.ProxyError:
                pass
            else:
                raise AssertionError('Invalid configuration accepted')
            assert (state / 'config.json').read_bytes() == before
            validate.side_effect = None
            service.return_value = SimpleNamespace(returncode=1)
            try:
                proxy.select_server('1')
            except proxy.ProxyError as error:
                assert 'Selection saved' in str(error) and 'restart failed' in str(error)
            else:
                raise AssertionError('Restart failure reported as success')
            assert proxy.proxy_group(proxy.load_config())['filter'] == proxy.server_pattern(NAMES[0])
            service.return_value = SimpleNamespace(returncode=0)
            with patch('builtins.input', return_value='3'):
                proxy.select_server()
            assert proxy.proxy_group(proxy.load_config())['filter'] == proxy.server_pattern(NAMES[2])
            with patch.object(proxy, 'cached_servers', side_effect=AssertionError('Auto must work without cache')):
                proxy.select_server(automatic=True)
            assert proxy.load_config() == original
            # Exercise argument parsing and return codes without root or host services.
            with patch.object(proxy.os, 'geteuid', return_value=0), patch('sys.argv', ['manage.py', 'list', '--no-check']):
                assert proxy.main() == 0
            with patch.object(proxy.os, 'geteuid', return_value=0), patch('sys.argv', ['manage.py', 'list', '--all']):
                assert proxy.main() == 0
            with patch.object(proxy.os, 'geteuid', return_value=0), patch('sys.argv', ['manage.py', 'select', '1']):
                assert proxy.main() == 0
            calls = service.call_count
            with patch.object(proxy.os, 'geteuid', return_value=0), patch('sys.argv', ['manage.py', 'select', '日本', '--no-restart']):
                assert proxy.main() == 0 and service.call_count == calls
        control = state / 'mock.sock'
        url = proxy.CHECK_URL
        with patch.object(proxy, 'controller_request', side_effect=[
            (200, {'delay': 42}), (200, {'extra': {url: {'alive': True}}})]) as request:
            assert proxy.check_server(control, '日本 / name?', 5, url) == 'OK 42 ms'
            assert '%2F' in request.call_args_list[0].args[1] and 'expected=200-399' in request.call_args_list[0].args[1]
        for response, expected in (((504, {}), 'TIMEOUT'), ((503, {}), 'FAILED')):
            with patch.object(proxy, 'controller_request', return_value=response):
                assert proxy.check_server(control, 'name', 5, url) == expected
        with patch.object(proxy, 'controller_request', side_effect=TimeoutError):
            assert proxy.check_server(control, 'name', 5, url) == 'TIMEOUT'
        with patch.object(proxy, 'controller_request', side_effect=[
            (200, {'delay': 42}), (200, {'extra': {url: {'alive': False}}})]):
            assert proxy.check_server(control, 'name', 5, url) == 'FAILED'
        @contextlib.contextmanager
        def fake_engine(check=False):
            assert check
            yield NAMES, control
        with patch.object(proxy, 'STATE', state), patch.object(proxy, 'cached_engine', fake_engine), \
             patch.object(proxy, 'check_server', side_effect=lambda sock, name, timeout, url: 'OK 42 ms' if name == NAMES[0] else 'TIMEOUT'), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            before = (state / 'config.json').read_bytes()
            proxy.list_servers()
            assert '[OK 42 ms]' in output.getvalue() and '[TIMEOUT]' in output.getvalue()
            assert (state / 'config.json').read_bytes() == before
        with contextlib.redirect_stdout(io.StringIO()) as output:
            proxy.show_servers(original, NAMES, dict(zip(NAMES, ['TIMEOUT', 'OK 100 ms', 'FAILED', 'OK 10 ms'])))
        rows = [line for line in output.getvalue().splitlines() if line.lstrip()[:1].isdigit()]
        assert [int(line.split('.')[0]) for line in rows] == [4, 2, 1, 3], rows
        routes = [{'dev': 'minion-proxy'}, {'dev': 'eth0', 'metric': 200}, {'dev': 'wlp1s0', 'metric': 100}]
        with patch.object(proxy.Path, 'is_dir', return_value=True), \
             patch.object(proxy.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(routes))):
            assert proxy.check_interface({}) == 'wlp1s0'
            assert proxy.check_interface({'interface-name': 'eth0'}) == 'eth0'
        with patch.object(proxy.Path, 'is_dir', return_value=True), \
             patch.object(proxy.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='[]')):
            try:
                proxy.check_interface({})
            except proxy.ProxyError:
                pass
            else:
                raise AssertionError('Checks allowed active TUN without a physical route')
        print('Passed: number/name/substring/prompt selection, ambiguity refusal, default restart/save-only, failure retention and checker status handling.')

        if args.mihomo:
            binary = args.mihomo.resolve()
            with patch.object(proxy, 'STATE', state), patch.object(proxy, 'BINARY', binary):
                # Mixed formats are parsed by Mihomo, including embedded VMess names.
                vmess = base64.b64encode(json.dumps({'v': '2', 'ps': 'VMess display name', 'add': '127.0.0.1',
                    'port': '9', 'id': '11111111-1111-1111-1111-111111111111', 'aid': '0',
                    'scy': 'auto', 'net': 'tcp', 'type': 'none', 'tls': ''}).encode())
                payload = subscription(NAMES) + b'\nvmess://' + vmess
                names = NAMES + ['VMess display name']
                for cached in (payload, base64.b64encode(payload), base64.b64encode(payload).rstrip(b'=')):
                    proxy.write_private(state / 'providers/subscription.txt', cached)
                    assert proxy.cached_servers() == names
                    assert not list(state.glob('.list-*')), 'Temporary core state leaked'
                reset()
                with contextlib.redirect_stdout(io.StringIO()):
                    for name in names:
                        proxy.select_server(name, restart=False)
                        probe = proxy.load_config()
                        # No tunnel/listeners/HTTP provider in the real engine probe.
                        probe['tun']['enable'] = False
                        probe['dns']['enable'] = False
                        probe['mixed-port'] = 0
                        probe['proxy-providers']['subscription'] = {'type': 'file', 'path': './providers/subscription.txt'}
                        with engine(binary, state, probe) as query:
                            group = query('/proxies/PROXY')
                            assert group['all'] == [name] and group['now'] == name, group
                    # A provider refresh removing the pinned name must reject traffic.
                    proxy.write_private(state / 'providers/subscription.txt', subscription(['Different server']))
                    with engine(binary, state, probe) as query:
                        group = query('/proxies/PROXY')
                        assert group['all'] == ['REJECT'] and group['now'] == 'REJECT', group
                    proxy.select_server(automatic=True, restart=False)
                assert proxy.load_config() == original
                check_https(binary, state)
                before = (state / 'config.json').read_bytes()
                proxy.write_private(state / 'providers/subscription.txt', b'invalid subscription')
                try:
                    proxy.cached_servers()
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Invalid cached subscription accepted')
                assert before == (state / 'config.json').read_bytes()
                assert not list(state.glob('.list-*'))
            print('Passed with real Mihomo: URI/base64/VMess listing, Unicode selection, HTTPS success/stall/refusal/bad-status checks and cleanup.')


if __name__ == '__main__':
    main()
