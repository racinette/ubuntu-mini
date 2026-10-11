#!/usr/bin/env python3
"""Check offline server listing and persistent selection; optionally use real Mihomo."""
import argparse
import base64
import contextlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
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
             patch.object(proxy, 'validate') as validate, contextlib.redirect_stdout(io.StringIO()) as output:
            reset()
            proxy.select_server('2')
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
            before = (state / 'config.json').read_bytes()
            for invalid in ('0', '9999', 'does not exist', ''):
                try:
                    proxy.select_server(invalid)
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Invalid selection accepted')
                assert (state / 'config.json').read_bytes() == before
            validate.side_effect = proxy.ProxyError('Invalid fixture configuration')
            try:
                proxy.select_server('1')
            except proxy.ProxyError:
                pass
            else:
                raise AssertionError('Invalid configuration accepted')
            assert (state / 'config.json').read_bytes() == before
            validate.side_effect = None
            with patch('builtins.input', return_value='3'):
                proxy.select_server()
            assert proxy.proxy_group(proxy.load_config())['filter'] == proxy.server_pattern(NAMES[2])
            with patch.object(proxy, 'cached_servers', side_effect=AssertionError('Auto must work without cache')):
                proxy.select_server(automatic=True)
            assert proxy.load_config() == original
            # Exercise argument parsing and return codes without root or host services.
            with patch.object(proxy.os, 'geteuid', return_value=0), patch('sys.argv', ['manage.py', 'list']):
                assert proxy.main() == 0
            with patch.object(proxy.os, 'geteuid', return_value=0), patch('sys.argv', ['manage.py', 'select', '1']):
                assert proxy.main() == 0
        print('Passed: selection by number/name/prompt, auto, output escaping, validation failure retention and private config.')

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
                        proxy.select_server(name)
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
                    proxy.select_server(automatic=True)
                assert proxy.load_config() == original
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
            print('Passed with real Mihomo: URI/base64/VMess listing, exact Unicode/regex/backtick selection, missing-node rejection and cleanup.')


if __name__ == '__main__':
    main()
