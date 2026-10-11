#!/usr/bin/env python3
"""Configure and supervise the optional private Mihomo proxy service."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

STATE = Path('/var/lib/minion/proxy')
BINARY = Path('/usr/local/lib/minion-proxy/mihomo')
UNIT = 'minion-proxy.service'
USER_AGENT = 'minion-proxy/1.0'
MAX_SUBSCRIPTION = 4 * 1024 * 1024
LAN = ['127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
       '169.254.0.0/16', '224.0.0.0/4', '::1/128', 'fc00::/7', 'fe80::/10', 'ff00::/8']


class ProxyError(Exception):
    """A controlled diagnostic that contains no remote data or credentials."""


def device_headers(identity):
    return {'User-Agent': USER_AGENT, 'x-hwid': identity,
            'x-device-os': 'Linux', 'x-ver-os': '24.04', 'x-device-model': 'minion'}


def device_identity():
    path = STATE / 'device-id'
    if not path.exists():
        write_private(path, str(uuid.uuid4()).encode())
    identity = path.read_text().strip()
    if not 10 <= len(identity) <= 64 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=-' for c in identity):
        raise ProxyError('Invalid stored device identity')
    return identity


def configuration(url, mode, identity):
    """Keep machine routing local; import only the provider's server definitions."""
    return {
        'mixed-port': 7890, 'bind-address': '127.0.0.1', 'allow-lan': False,
        'mode': 'rule', 'log-level': 'warning', 'ipv6': True,
        'external-controller': '',
        'proxy-providers': {'subscription': {
            'type': 'http', 'url': url, 'path': './providers/subscription.txt',
            'interval': 3600, 'proxy': 'DIRECT', 'size-limit': MAX_SUBSCRIPTION,
            'header': {key: [value] for key, value in device_headers(identity).items()},
        }},
        'proxy-groups': [{'name': 'PROXY', 'type': 'url-test', 'use': ['subscription'],
                          'url': 'https://www.gstatic.com/generate_204', 'interval': 300,
                          'tolerance': 50}],
        'rules': [f'IP-CIDR{6 if ":" in cidr else ""},{cidr},DIRECT,no-resolve'
                  for cidr in LAN] + ['MATCH,PROXY'],
        'tun': {
            'enable': mode == 'tun', 'device': 'minion-proxy', 'stack': 'gvisor',
            'auto-route': True, 'auto-redirect': False,
            'auto-detect-interface': True, 'strict-route': True,
            'dns-hijack': ['any:53', 'tcp://any:53'],
            'inet6-address': ['fdfe:dcba:9876::1/126'],
            'route-exclude-address': LAN,
        },
        'dns': {
            'enable': True, 'listen': '127.0.0.1:1053', 'ipv6': True,
            'enhanced-mode': 'fake-ip', 'fake-ip-range': '198.18.0.1/16',
            'respect-rules': True,
            'default-nameserver': ['1.1.1.1', '8.8.8.8'],
            'proxy-server-nameserver': ['1.1.1.1', '8.8.8.8'],
            'direct-nameserver': ['1.1.1.1', '8.8.8.8'],
            'nameserver': ['https://1.1.1.1/dns-query', 'https://8.8.8.8/dns-query'],
        },
    }


def validate_url(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.fragment or any(c.isspace() for c in url)):
        raise ProxyError('Supply an HTTPS subscription URL without whitespace or a fragment')
    return url


def private_file(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ProxyError('The subscription file must be a root-owned regular file with mode 600')
    return path.read_text().strip()


def fetch_subscription(url, identity):
    request = urllib.request.Request(url, headers=device_headers(identity))
    try:
        # Fetch directly, independently of shell proxy environment variables.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=30) as response:
            if response.headers.get('x-hwid-not-supported', '').lower() == 'true':
                raise ProxyError('The provider refused the device identity; check provider support')
            if any(response.headers.get(key, '').lower() == 'true'
                   for key in ('x-hwid-limit', 'x-hwid-max-devices-reached')):
                raise ProxyError('The provider device limit is reached; free a device slot and retry')
            payload = response.read(MAX_SUBSCRIPTION + 1)
    except (OSError, urllib.error.URLError):
        raise ProxyError('Could not download the subscription; URL and response withheld') from None
    if len(payload) > MAX_SUBSCRIPTION:
        raise ProxyError('Subscription exceeds the 4 MiB limit')
    try:
        text = payload.decode('utf-8').strip()
        if '://' not in text:
            encoded = ''.join(text.split())
            text = base64.b64decode(encoded + '=' * (-len(encoded) % 4), validate=True).decode('utf-8').strip()
        schemes = ('vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://', 'hysteria2://', 'hy2://', 'tuic://')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines or not all(line.startswith(schemes) for line in lines):
            raise ValueError
        if all(urllib.parse.urlsplit(line).hostname in ('0.0.0.0', '::') for line in lines):
            raise ProxyError('The provider returned only placeholder servers; existing configuration retained')
    except (ValueError, UnicodeError):
        raise ProxyError('Expected a URI/base64 server subscription for the minion-proxy user agent') from None
    return payload


def write_private(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate(config, directory=STATE):
    result = subprocess.run([str(BINARY), '-t', '-d', str(directory), '-f', str(config)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ProxyError('Mihomo rejected the configuration; diagnostic output withheld to protect credentials')


def configure(url, mode):
    identity = device_identity()
    payload = fetch_subscription(validate_url(url), identity)
    # Validate before replacing either of the installed configuration/cache files.
    with tempfile.TemporaryDirectory(prefix='.configure-', dir=STATE) as temporary:
        scratch = Path(temporary)
        write_private(scratch / 'providers/subscription.txt', payload)
        content = (json.dumps(configuration(url, mode, identity), indent=2) + '\n').encode()
        write_private(scratch / 'config.json', content)
        validate(scratch / 'config.json', scratch)
        write_private(STATE / 'providers/subscription.txt', payload)
        write_private(STATE / 'config.json', content)
    print('Subscription cached and configuration validated. Mode: ' + mode)
    print('Start or restart with: sudo systemctl restart ' + UNIT)
    print('Enable at boot with: sudo systemctl enable ' + UNIT)


def load_config():
    try:
        return json.loads((STATE / 'config.json').read_text())
    except (OSError, ValueError):
        raise ProxyError('From the repository, run sudo python3 setup/proxy/manage.py configure first') from None


def supervise():
    config = load_config()
    url = config['proxy-providers']['subscription']['url']
    parsed = urllib.parse.urlsplit(url)
    secrets = [url, urllib.parse.quote(url, safe='')]
    if len(parsed.path) > 1:
        secrets.append(parsed.path)
    if parsed.query:
        secrets.append(parsed.query)
    child = subprocess.Popen([str(BINARY), '-d', str(STATE), '-f', str(STATE / 'config.json')],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    def forward(signum, frame):
        if child.poll() is None:
            child.send_signal(signum)
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, forward)
    failed = False
    for line in child.stdout:
        if config['tun']['enable'] and 'Start TUN listening error:' in line:
            failed = True
            child.terminate()
        for secret in secrets:
            line = line.replace(secret, '[subscription redacted]')
        print(line, end='', flush=True)
    code = child.wait()
    return 1 if failed else code


def wait_ready():
    config = load_config()
    deadline = time.monotonic() + 15
    stable_since = None
    while True:
        ready = False
        try:
            with socket.create_connection(('127.0.0.1', 7890), timeout=0.3):
                ready = not config['tun']['enable'] or Path('/sys/class/net/minion-proxy').is_dir()
        except OSError:
            pass
        if ready:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 1:
                return
        else:
            stable_since = None
        if time.monotonic() >= deadline:
            raise ProxyError('Proxy listener or TUN interface did not initialize; check the service journal')
        time.sleep(0.2)


def activate_dns():
    wait_ready()
    if not load_config()['tun']['enable']:
        return
    if not any(line.split()[:2] in (['nameserver', '127.0.0.53'], ['nameserver', '127.0.0.54'])
               for line in Path('/etc/resolv.conf').read_text().splitlines()):
        raise ProxyError('TUN mode requires the Ubuntu systemd-resolved stub in /etc/resolv.conf')
    # Per-link settings disappear with the TUN interface. Do not rewrite Wi-Fi
    # DNS or resolv.conf; use the tunnel's DNS hijack endpoint through resolved.
    for args in (('dns', 'minion-proxy', '198.18.0.2'),
                 ('domain', 'minion-proxy', '~.'),
                 ('default-route', 'minion-proxy', 'yes')):
        result = subprocess.run(['resolvectl', *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        if result.returncode:
            raise ProxyError('Could not configure tunnel DNS with systemd-resolved; service startup aborted')


def test_connection():
    wait_ready()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({
        'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}))
    # Clear no_proxy so the connectivity check cannot silently bypass the listener.
    previous = {key: os.environ.pop(key) for key in ('no_proxy', 'NO_PROXY') if key in os.environ}
    try:
        for url in ('https://www.gstatic.com/generate_204', 'https://github.com'):
            try:
                with opener.open(url, timeout=30) as response:
                    status = response.status
                if not 200 <= status < 400:
                    raise ValueError
            except (OSError, ValueError, urllib.error.URLError):
                raise ProxyError('Proxy HTTPS connectivity failed; check sudo journalctl -u ' + UNIT) from None
            print(urllib.parse.urlsplit(url).hostname + ': HTTPS through localhost proxy succeeded')
    finally:
        os.environ.update(previous)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    setup = sub.add_parser('configure', help='Privately enter and validate an HTTPS subscription')
    setup.add_argument('--subscription-file', type=Path, help='Root-owned mode-600 file containing only the URL')
    setup.add_argument('--mode', choices=('proxy', 'tun'), default='tun')
    mode = sub.add_parser('mode', help='Change mode; restart the service separately to activate')
    mode.add_argument('mode', choices=('proxy', 'tun'))
    sub.add_parser('validate', help='Validate the existing private configuration')
    sub.add_parser('ready', help='Wait for configured listeners/interface to initialize')
    sub.add_parser('activate-dns', help='Service entry point for temporary tunnel DNS')
    sub.add_parser('run', help='Service entry point with subscription URL redaction')
    sub.add_parser('test', help='Test HTTPS using the localhost proxy listener')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    try:
        if args.command == 'configure':
            url = private_file(args.subscription_file) if args.subscription_file else getpass.getpass('Subscription URL (hidden): ').strip()
            configure(url, args.mode)
        elif args.command == 'mode':
            config = load_config()
            config['tun']['enable'] = args.mode == 'tun'
            with tempfile.TemporaryDirectory(prefix='.mode-', dir=STATE) as temporary:
                path = Path(temporary) / 'config.json'
                content = (json.dumps(config, indent=2) + '\n').encode()
                write_private(path, content)
                validate(path)
                write_private(STATE / 'config.json', content)
            print('Mode: ' + args.mode + '. Activate with: sudo systemctl restart ' + UNIT)
        elif args.command == 'validate':
            load_config()
            validate(STATE / 'config.json')
            print('Proxy configuration is valid')
        elif args.command == 'ready':
            wait_ready()
        elif args.command == 'activate-dns':
            activate_dns()
        elif args.command == 'run':
            return supervise()
        elif args.command == 'test':
            test_connection()
    except ProxyError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, EOFError, subprocess.TimeoutExpired):
        # Errors can embed URL credentials or remote content: never print raw exceptions.
        print('Proxy operation failed. Verify configuration, connectivity and private file permissions.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
