#!/usr/bin/env python3
"""Configure and supervise the optional private Mihomo proxy service."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import getpass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
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
CHECK_URL = 'https://www.gstatic.com/generate_204'
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


def validate(config, directory=None):
    directory = STATE if directory is None else directory
    result = subprocess.run([str(BINARY), '-t', '-d', str(directory), '-f', str(config)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
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
    (STATE / 'dashboard-selection-source.json').unlink(missing_ok=True)
    print('Subscription cached and configuration validated. Mode: ' + mode)
    print('Start or restart with: sudo systemctl restart ' + UNIT)
    print('Enable at boot with: sudo systemctl enable ' + UNIT)


def load_config():
    try:
        return json.loads((STATE / 'config.json').read_text())
    except (OSError, ValueError):
        raise ProxyError('From the repository, run sudo python3 setup/proxy/manage.py configure first') from None


def server_pattern(name):
    # Escape backtick filter separators too, producing one literal match.
    return '^' + re.escape(name).replace('`', r'\x60') + '$'


def controller_request(path, request_path, timeout=1, method='GET', body=None):
    connection = http.client.HTTPConnection('localhost', timeout=timeout)
    try:
        connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.sock.settimeout(timeout)
        connection.sock.connect(str(path))
        connection.request(method, request_path, body=None if body is None else json.dumps(body),
                           headers={} if body is None else {'Content-Type': 'application/json'})
        response = connection.getresponse()
        data = response.read(2 * MAX_SUBSCRIPTION + 1)
        if len(data) > 2 * MAX_SUBSCRIPTION:
            raise ProxyError('Mihomo control response exceeded the size limit')
        return response.status, json.loads(data) if data else None
    finally:
        connection.close()


def check_interface(config):
    if config.get('interface-name'):
        return config['interface-name']
    if not Path('/sys/class/net/minion-proxy').is_dir():
        return None
    # Bind checks to the real uplink rather than checking every candidate
    # through the currently selected TUN proxy. Its routes use a policy table;
    # Ubuntu's physical default route remains in the main table.
    result = subprocess.run(['ip', '-j', 'route', 'show', 'table', 'main', 'default'],
                            capture_output=True, text=True, timeout=5)
    routes = json.loads(result.stdout) if result.returncode == 0 else []
    routes = [route for route in routes if route.get('dev') not in (None, 'minion-proxy', 'lo')]
    if not routes:
        raise ProxyError('Could not find the uplink for checks; use list --no-check or stop the proxy first')
    return min(routes, key=lambda route: route.get('metric', 0))['dev']


@contextmanager
def cached_engine(check=False):
    """Parse/check the cached provider in an isolated Mihomo instance.

    Only a Unix control socket in a private directory opens. No proxy/DNS
    listeners, TUN routes or HTTP subscription refreshes are created.
    """
    try:
        with (STATE / 'providers/subscription.txt').open('rb') as source:
            payload = source.read(MAX_SUBSCRIPTION + 1)
    except OSError:
        raise ProxyError('No cached subscription; run configure first') from None
    if len(payload) > MAX_SUBSCRIPTION:
        raise ProxyError('Cached subscription exceeds the 4 MiB limit')
    with tempfile.TemporaryDirectory(prefix='.list-', dir=STATE) as temporary:
        scratch = Path(temporary)
        write_private(scratch / 'subscription.txt', payload)
        config = {
            'external-controller': '', 'external-controller-unix': 'control.sock',
            'log-level': 'silent', 'mode': 'rule',
            'dns': {'enable': False}, 'tun': {'enable': False},
            'proxy-providers': {'subscription': {'type': 'file', 'path': './subscription.txt'}},
            'rules': ['MATCH,DIRECT'],
        }
        if check:
            installed = load_config()
            interface = check_interface(installed)
            if interface:
                config['interface-name'] = interface
            # Resolve server hostnames directly using the installed resolver
            # settings, independently of system DNS routed into an active TUN.
            config['dns'] = dict(installed['dns'], enable=True, listen='',
                                 **{'respect-rules': False, 'enhanced-mode': 'redir-host'})
            config['tls'] = {'custom-certifactes': installed.get('tls', {}).get('custom-certifactes', [])}
        write_private(scratch / 'config.json', json.dumps(config, ensure_ascii=False).encode())
        env = {key: value for key, value in os.environ.items() if not key.startswith('CLASH_')}
        child = subprocess.Popen([str(BINARY), '-d', str(scratch), '-f', str(scratch / 'config.json')],
                                 env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 15
            while child.poll() is None:
                try:
                    status, data = controller_request(scratch / 'control.sock', '/providers/proxies/subscription')
                    if status == 200:
                        names = [item['name'] for item in data['proxies']]
                        if names and all(isinstance(name, str) and name for name in names):
                            if len(names) != len(set(names)):
                                raise ProxyError('Subscription contains duplicate server names')
                            break
                except (OSError, ValueError, KeyError, http.client.HTTPException):
                    pass
                if time.monotonic() >= deadline:
                    raise ProxyError('Timed out reading servers from the cached subscription')
                time.sleep(0.1)
            else:
                raise ProxyError('Could not read servers from the cached subscription with Mihomo')
            yield names, scratch / 'control.sock'
        finally:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def cached_servers():
    with cached_engine() as (names, _):
        return names


def check_server(control, name, timeout, url):
    path = '/providers/proxies/subscription/' + urllib.parse.quote(name, safe='')
    query = urllib.parse.urlencode({'url': url, 'timeout': timeout * 1000, 'expected': '200-399'})
    try:
        status, data = controller_request(control, path + '/healthcheck?' + query, timeout + 2)
        if status == 504:
            return 'TIMEOUT'
        if status == 200 and isinstance(data.get('delay'), int) and data['delay'] > 0:
            # URLTest can return a delay even for an unexpected HTTP status.
            # Its per-URL alive state records whether the status was acceptable.
            status, node = controller_request(control, path)
            if status == 200 and node.get('extra', {}).get(url, {}).get('alive') is True:
                return f"OK {data['delay']} ms"
        return 'FAILED'
    except (TimeoutError, socket.timeout):
        return 'TIMEOUT'
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        return 'FAILED'


def list_servers(check=True, timeout=5, url=CHECK_URL):
    config = load_config()
    if not check:
        show_servers(config, cached_servers())
        return
    with cached_engine(check=True) as (names, control):
        print(f'Checking {len(names)} servers through HTTPS: {url} ({timeout}s timeout, up to 8 at once)', flush=True)
        results = {}
        pool = ThreadPoolExecutor(max_workers=8)
        try:
            pending = {pool.submit(check_server, control, name, timeout, url): name for name in names}
            for count, future in enumerate(as_completed(pending), 1):
                results[pending[future]] = future.result()
                if count % 8 == 0 and count < len(names):
                    print(f'Checked {count}/{len(names)}...', flush=True)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        show_servers(config, names, results)
        passed = sum(result.startswith('OK ') for result in results.values())
        print(f'{passed}/{len(names)} servers passed the HTTPS check.')
        print('Results apply to this HTTPS destination now; they do not test TUN capture or every website.')


def proxy_group(config):
    groups = [group for group in config['proxy-groups'] if group['name'] == 'PROXY']
    if len(groups) != 1:
        raise ProxyError('Expected one managed PROXY group in the configuration')
    return groups[0]


def show_servers(config, names, results=None):
    group = proxy_group(config)
    automatic = group['type'] == 'url-test' and not group.get('filter')
    print('Saved selection: automatic (latency)' if automatic else 'Saved selection: pinned/filter active')
    rows = list(enumerate(names, 1))
    if results is not None:
        # Retain the cached-list numbers so sorting never changes select NUMBER.
        rows.sort(key=lambda row: int(results[row[1]].split()[1])
                  if results[row[1]].startswith('OK ') else float('inf'))
        print('Ordered by HTTPS response latency (lowest first); failed checks follow.')
    for number, name in rows:
        selected = group.get('filter') == server_pattern(name)
        # Quote display names to prevent embedded terminal controls from running.
        status = f' [{results[name]}]' if results is not None else ''
        print(f'{number:3}. {json.dumps(name, ensure_ascii=False)}' + status + (' [selected]' if selected else ''))
    print('Numbers refer to this cached list and can change after subscription refresh.')


def save_config(config):
    with tempfile.TemporaryDirectory(prefix='.update-', dir=STATE) as temporary:
        path = Path(temporary) / 'config.json'
        # Mihomo reads JSON through its YAML parser, which rejects JSON's
        # surrogate-pair escapes for emoji. Write actual UTF-8 names instead.
        content = (json.dumps(config, indent=2, ensure_ascii=False) + '\n').encode()
        write_private(path, content)
        validate(path)
        write_private(STATE / 'config.json', content)


def match_server(server, names):
    if server.isascii() and server.isdecimal():
        number = int(server)
        if not 1 <= number <= len(names):
            raise ProxyError('Server number out of range; run list to see available servers')
        return names[number - 1]
    if server in names:
        return server
    matches = [(number, name) for number, name in enumerate(names, 1)
               if server and server.casefold() in name.casefold()]
    if not matches:
        raise ProxyError('Server not found; run list to see available servers')
    if len(matches) > 1:
        choices = '\n'.join(f'{number:3}. {json.dumps(name, ensure_ascii=False)}' for number, name in matches)
        raise ProxyError('Substring matches multiple servers; choose a number or a more specific substring:\n' + choices)
    return matches[0][1]


def select_server(server=None, automatic=False, restart=True):
    config = load_config()
    group = proxy_group(config)
    if automatic:
        replacement = configuration('', 'proxy', '')['proxy-groups'][0]
    else:
        names = cached_servers()
        if server is None:
            show_servers(config, names)
            server = input('Server number, exact name or unique substring: ').strip()
        name = match_server(server, names)
        replacement = {'name': 'PROXY', 'type': 'select', 'use': ['subscription'],
                       'filter': server_pattern(name), 'empty-fallback': 'REJECT'}
    group.clear()
    group.update(replacement)
    save_config(config)
    (STATE / 'dashboard-selection-source.json').unlink(missing_ok=True)
    print('Saved selection: ' + ('automatic (latency)' if automatic else json.dumps(name, ensure_ascii=False)))
    if restart:
        try:
            result = subprocess.run(['systemctl', 'restart', UNIT], capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            raise ProxyError('Selection saved, but service restart could not complete; check sudo journalctl -u ' + UNIT) from None
        if result.returncode:
            raise ProxyError('Selection saved, but service restart failed; check sudo journalctl -u ' + UNIT)
        print('Proxy service restarted. Run sudo python3 setup/proxy/manage.py test to check connectivity.')
    else:
        print('Saved only. Activate with: sudo systemctl restart ' + UNIT)


def dashboard_runtime(config):
    """Keep the saved CLI policy intact and expose a native, persistent selector."""
    settings = STATE / 'dashboard.json'
    if not settings.exists():
        return config, None
    access = json.loads(settings.read_text())
    if not isinstance(access.get('secret'), str) or len(access['secret']) < 32:
        raise ProxyError('Invalid dashboard identity; rerun proxy provisioning')
    runtime = json.loads(json.dumps(config))
    saved = proxy_group(runtime)
    fingerprint = hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest()
    automatic = configuration('', 'proxy', '')['proxy-groups'][0]
    automatic['name'] = 'Automatic'
    groups = runtime['proxy-groups']
    if any(group['name'] in ('Automatic', 'Configured selection') for group in groups):
        raise ProxyError('Dashboard group names conflict with personal proxy groups')
    if saved['type'] == 'url-test' and not saved.get('filter'):
        groups.remove(saved)
        default = 'Automatic'
    else:
        saved['name'] = 'Configured selection'
        default = 'Configured selection'
    groups.insert(0, {'name': 'PROXY', 'type': 'select',
                      'proxies': [default] + ([] if default == 'Automatic' else ['Automatic']),
                      'use': ['subscription']})
    groups.append(automatic)
    runtime.update({'external-controller': '127.0.0.1:9090',
                    'external-controller-unix': 'dashboard.sock',
                    'external-ui': str(STATE / 'ui'), 'secret': access['secret'],
                    'external-controller-cors': {'allow-origins': ['http://127.0.0.1:9090']}})
    runtime.setdefault('profile', {})['store-selected'] = True
    return runtime, {'fingerprint': fingerprint, 'default': default}


def reconcile_dashboard(child, selection):
    """A deliberate CLI policy change supersedes the last dashboard selection once."""
    marker = STATE / 'dashboard-selection-source.json'
    if marker.exists() and json.loads(marker.read_text()).get('fingerprint') == selection['fingerprint']:
        return
    deadline = time.monotonic() + 15
    while child.poll() is None:
        try:
            status, group = controller_request(STATE / 'dashboard.sock', '/proxies/PROXY')
            if status == 200 and selection['default'] in group.get('all', []):
                status, _ = controller_request(STATE / 'dashboard.sock', '/proxies/PROXY',
                                               method='PUT', body={'name': selection['default']})
                if status != 204:
                    raise ProxyError('Could not restore configured proxy selection')
                write_private(marker, json.dumps(selection).encode())
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        if time.monotonic() >= deadline:
            raise ProxyError('Dashboard control did not initialize')
        time.sleep(.1)
    raise ProxyError('Proxy stopped before dashboard selection initialized')


def supervise():
    config = load_config()
    runtime, selection = dashboard_runtime(config)
    configuration_path = STATE / 'config.json'
    if selection:
        configuration_path = STATE / 'dashboard-runtime.json'
        write_private(configuration_path, (json.dumps(runtime, ensure_ascii=False) + '\n').encode())
        validate(configuration_path)
    url = config['proxy-providers']['subscription']['url']
    parsed = urllib.parse.urlsplit(url)
    secrets = [url, urllib.parse.quote(url, safe='')]
    if len(parsed.path) > 1:
        secrets.append(parsed.path)
    if parsed.query:
        secrets.append(parsed.query)
    if selection:
        secrets.append(runtime['secret'])
    child = subprocess.Popen([str(BINARY), '-d', str(STATE), '-f', str(configuration_path)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    def forward(signum, frame):
        if child.poll() is None:
            child.send_signal(signum)
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, forward)
    failures = []
    def reconcile():
        try:
            reconcile_dashboard(child, selection)
        except Exception:
            failures.append('Dashboard selection could not initialize')
            child.terminate()
    reconciliation = threading.Thread(target=reconcile) if selection else None
    if reconciliation:
        reconciliation.start()
    failed = False
    for line in child.stdout:
        if config['tun']['enable'] and 'Start TUN listening error:' in line:
            failed = True
            child.terminate()
        for secret in secrets:
            line = line.replace(secret, '[subscription redacted]')
        print(line, end='', flush=True)
    code = child.wait()
    if reconciliation:
        reconciliation.join(timeout=3)
    return 1 if failed or failures else code


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


def check_timeout(value):
    try:
        seconds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('Timeout must be a whole number of seconds from 1 to 30') from None
    if not 1 <= seconds <= 30:
        raise argparse.ArgumentTypeError('Timeout must be from 1 to 30 seconds')
    return seconds


def check_url(value):
    try:
        return validate_url(value)
    except ProxyError:
        raise argparse.ArgumentTypeError('Check URL must use HTTPS without credentials, whitespace or a fragment') from None


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    setup = sub.add_parser('configure', help='Privately enter and validate an HTTPS subscription')
    setup.add_argument('--subscription-file', type=Path, help='Root-owned mode-600 file containing only the URL')
    setup.add_argument('--mode', choices=('proxy', 'tun'), default='tun')
    listing = sub.add_parser('list', help='List cached servers with HTTPS connectivity checks')
    listing.add_argument('--all', '--no-check', dest='no_check', action='store_true',
                         help='Original unchecked list of all cached names/numbers; works offline')
    listing.add_argument('--timeout', type=check_timeout, default=5, help='Per-server timeout in seconds (1–30; default: 5)')
    listing.add_argument('--url', type=check_url, default=CHECK_URL, help='HTTPS destination to check through each server')
    selection = sub.add_parser('select', help='Save a server choice and restart the proxy service')
    selection.add_argument('server', nargs='?', help='Number, exact name or unique case-insensitive substring; omit to choose interactively')
    selection.add_argument('--auto', action='store_true', help='Restore automatic latency-based selection')
    selection.add_argument('--no-restart', action='store_true', help='Only save the selection; keep the service as it is')
    mode = sub.add_parser('mode', help='Change mode; restart the service separately to activate')
    mode.add_argument('mode', choices=('proxy', 'tun'))
    sub.add_parser('validate', help='Validate the existing private configuration')
    sub.add_parser('ready', help='Wait for configured listeners/interface to initialize')
    sub.add_parser('activate-dns', help='Service entry point for temporary tunnel DNS')
    sub.add_parser('run', help='Service entry point with subscription URL redaction')
    sub.add_parser('test', help='Test HTTPS using the localhost proxy listener')
    args = parser.parse_args()
    if args.command == 'select' and args.auto and args.server is not None:
        parser.error('Use select SERVER or select --auto, not both')
    if os.geteuid() != 0:
        parser.error('Run with sudo')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    try:
        if args.command == 'configure':
            url = private_file(args.subscription_file) if args.subscription_file else getpass.getpass('Subscription URL (hidden): ').strip()
            configure(url, args.mode)
        elif args.command == 'list':
            list_servers(not args.no_check, args.timeout, args.url)
        elif args.command == 'select':
            select_server(args.server, args.auto, not args.no_restart)
        elif args.command == 'mode':
            config = load_config()
            config['tun']['enable'] = args.mode == 'tun'
            save_config(config)
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
