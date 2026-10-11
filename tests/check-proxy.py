#!/usr/bin/env python3
"""Check provider refusals, failed-update preservation and service log redaction."""
import base64
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('proxy', str(PROJECT / 'setup/proxy/manage.py'))
spec = importlib.util.spec_from_loader(loader.name, loader)
proxy = importlib.util.module_from_spec(spec)
loader.exec_module(proxy)
URL = 'https://provider.invalid/private-subscription-token'
LINK = b'vless://11111111-1111-1111-1111-111111111111@server.invalid:443?security=tls&type=tcp#test'


class Response:
    def __init__(self, payload, headers):
        self.payload, self.headers = payload, headers
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.payload[:size]


def fetch(payload, headers=None):
    response = Response(payload, headers or {})
    with patch.object(proxy.urllib.request, 'build_opener') as factory:
        factory.return_value.open.return_value = response
        result = proxy.fetch_subscription(URL, 'fixture-device-0001')
        request = factory.return_value.open.call_args.args[0]
        sent = {key.lower(): value for key, value in request.header_items()}
        assert sent['x-hwid'] == 'fixture-device-0001'
        return result


def main():
    for url in ('http://provider.invalid/key', 'happ://crypto/key',
                'https://user:password@provider.invalid/key', URL + '\n', URL + '#fragment'):
        try:
            proxy.validate_url(url)
        except proxy.ProxyError:
            pass
        else:
            raise AssertionError('Unsafe subscription URL accepted')
    assert fetch(LINK) == LINK
    assert fetch(base64.b64encode(LINK)) == base64.b64encode(LINK)
    assert fetch(base64.b64encode(LINK).rstrip(b'=')) == base64.b64encode(LINK).rstrip(b'=')
    for payload, headers in (
        (LINK, {'x-hwid-not-supported': 'true'}),
        (LINK, {'x-hwid-max-devices-reached': 'true'}),
        (LINK, {'x-hwid-limit': 'true'}),
        (b'<html>Sign in</html>', {}),
        (base64.b64encode(b'vless://id@0.0.0.0:1#App%20not%20supported'), {}),
    ):
        try:
            fetch(payload, headers)
        except proxy.ProxyError as error:
            assert URL not in str(error)
        else:
            raise AssertionError('Provider refusal/placeholder accepted')

    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary)
        with patch.object(proxy, 'STATE', state):
            first = proxy.device_identity()
            assert first == proxy.device_identity()
            assert (state / 'device-id').stat().st_mode & 0o777 == 0o600
            proxy.write_private(state / 'config.json', b'previous config')
            proxy.write_private(state / 'providers/subscription.txt', b'previous servers')
            before = [(state / name).read_bytes() for name in ('config.json', 'providers/subscription.txt')]
            with patch.object(proxy, 'fetch_subscription', return_value=LINK), \
                 patch.object(proxy, 'validate', side_effect=proxy.ProxyError('Invalid configuration')):
                try:
                    proxy.configure(URL, 'tun')
                except proxy.ProxyError:
                    pass
                else:
                    raise AssertionError('Invalid update accepted')
            assert before == [(state / name).read_bytes() for name in ('config.json', 'providers/subscription.txt')]
            assert proxy.device_identity() == first

            # Exercise the real child-process output path, not just a string helper.
            binary = state / 'fixture-core'
            binary.write_text('#!/usr/bin/env python3\nimport json,sys,urllib.parse\n'
                              'url=json.load(open(sys.argv[-1]))["proxy-providers"]["subscription"]["url"]\n'
                              'print(url); print(urllib.parse.quote(url,safe="")); print(urllib.parse.urlsplit(url).path)\n')
            binary.chmod(0o755)
            proxy.write_private(state / 'config.json', json.dumps(proxy.configuration(URL, 'proxy', first)).encode())
            output = io.StringIO()
            original = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
            try:
                with patch.object(proxy, 'BINARY', binary), contextlib.redirect_stdout(output):
                    assert proxy.supervise() == 0
            finally:
                for signum, handler in original.items():
                    signal.signal(signum, handler)
            assert 'private-subscription-token' not in output.getvalue()
            assert '[subscription redacted]' in output.getvalue()
            # Mihomo may keep its HTTP listener alive after TUN startup fails.
            # The service must fail and stop that child instead of reporting a
            # working system-wide proxy.
            binary.write_text('#!/usr/bin/env python3\nimport time\n'
                              'print("Start TUN listening error: fixture failure", flush=True)\n'
                              'time.sleep(60)\n')
            proxy.write_private(state / 'config.json', json.dumps(proxy.configuration(URL, 'tun', first)).encode())
            try:
                with patch.object(proxy, 'BINARY', binary), contextlib.redirect_stdout(io.StringIO()):
                    assert proxy.supervise() == 1
            finally:
                for signum, handler in original.items():
                    signal.signal(signum, handler)
    print('Passed: subscription formats, device refusals, placeholder rejection, stable identity, failed-update preservation, subprocess log redaction and TUN failure supervision.')


if __name__ == '__main__':
    main()
