#!/usr/bin/env python3
"""Test real Ubuntu installation/systemd/TUN in an isolated disposable Podman container.

The subscription and optional reusable device ID are private input files, never
arguments containing secrets. Only the container's network namespace is changed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

PROJECT = Path(__file__).resolve().parents[1]
CONTAINERFILE = '''FROM docker.io/library/ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends systemd systemd-sysv systemd-resolved dbus python3 curl ca-certificates iproute2 && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /etc/systemd/resolved.conf.d && printf '[Resolve]\\nDNS=1.1.1.1\\n' > /etc/systemd/resolved.conf.d/qa.conf
ENV container=podman
CMD ["/sbin/init"]
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subscription-file', type=Path, required=True)
    parser.add_argument('--device-id-file', type=Path, help='Reuse one test registration across repeated runs')
    parser.add_argument('--platform', default='linux/amd64', choices=('linux/amd64', 'linux/arm64'))
    parser.add_argument('--skip-tun', action='store_true', help='Skip TUN checks on hosts with incomplete syscall emulation')
    args = parser.parse_args()
    for path in (args.subscription_file, args.device_id_file):
        if path and (not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077):
            parser.error('Private inputs must be regular files with no group/other permissions')
    root = PROJECT / '.local/proxy-qa'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix='container-', dir=root))
    directory.chmod(0o700)
    name = 'minion-proxy-' + directory.name
    report = {'passed': False, 'platform': args.platform, 'tun_tested': not args.skip_tun, 'checks': []}
    image = 'localhost/minion-proxy-qa-resolved:24.04-' + args.platform.split('/')[1]
    log = (directory / 'test.log').open('wb')
    os.chmod(directory / 'test.log', 0o600)

    def run(*command, check=True, timeout=180):
        result = subprocess.run([str(v) for v in command], capture_output=True, timeout=timeout)
        log.write(result.stdout + result.stderr + b'\n')
        log.flush()
        if check and result.returncode:
            raise RuntimeError('Command failed: ' + str(command[0]) + ' (details in private test.log)')
        return result

    def guest(*command, **kwargs):
        return run('podman', 'exec', name, *command, **kwargs)

    def check(label, condition=True):
        if not condition:
            raise RuntimeError(label + ' failed')
        report['checks'].append(label)
        print(label + ': passed', flush=True)

    def wait_active():
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if guest('systemctl', 'is-active', '--quiet', 'minion-proxy', check=False).returncode == 0:
                return
            time.sleep(0.5)
        raise RuntimeError('Proxy service failed to activate')

    def digest(path):
        return guest('sha256sum', path).stdout.split()[0]

    def install(check_only=False):
        # Exercise the actual component without installing a whole desktop.
        # The host layout check verifies that ordinary setup invokes it.
        command = ['python3', '/opt/project/setup/proxy/provision.py']
        return guest(*command, *(['--check'] if check_only else []))

    def manage(*args, **kwargs):
        return guest('python3', '/opt/project/setup/proxy/manage.py', *args, **kwargs)

    def egress(proxy=False):
        options = ['--proxy', 'http://127.0.0.1:7890'] if proxy else ['--noproxy', '*']
        return guest('curl', '-fsS', '--max-time', '45', *options, 'https://api.ipify.org').stdout.strip()

    def public_route():
        route = json.loads(guest('ip', '-j', 'route', 'get', '1.1.1.1').stdout)[0]
        # Podman can assign a new source IP across container reboot. Compare
        # forwarding behavior, rather than that unrelated DHCP address.
        return {key: route.get(key) for key in ('dev', 'gateway', 'table', 'type')}

    try:
        if run('podman', 'image', 'exists', image, check=False).returncode:
            (directory / 'Containerfile').write_text(CONTAINERFILE)
            run('podman', 'build', '--platform', args.platform, '-t', image,
                '-f', directory / 'Containerfile', directory, timeout=600)
        run('podman', 'run', '-d', '--name', name, '--platform', args.platform,
            '--privileged', '--systemd=always', '--dns', '127.0.0.53', '--tmpfs', '/run', '--tmpfs', '/tmp', image)
        guest('useradd', '-m', '-s', '/bin/bash', 'vmuser')
        guest('mkdir', '-p', '/opt/project')
        run('podman', 'cp', PROJECT / 'setup', name + ':/opt/project/setup')
        run('podman', 'cp', PROJECT / 'setup.sh', name + ':/opt/project/setup.sh')
        if args.skip_tun:
            # glibc can use direct DNS for the explicit-proxy test even when
            # systemd-resolved's credential syscalls cannot be emulated.
            guest('python3', '-c', "open('/etc/resolv.conf','w').write('nameserver 1.1.1.1\\n')")
        else:
            guest('systemctl', 'start', 'systemd-resolved')
        install(check_only=True)
        check('read-only preflight', guest('test', '!', '-e', '/var/lib/minion/setup', check=False).returncode == 0)
        install()
        check('no globally installed management command', guest('test', '!', '-e', '/usr/local/bin/minion-proxy', check=False).returncode == 0)
        check('runtime script is root-owned', guest('stat', '-c', '%a %u', '/usr/local/lib/minion-proxy/manage.py').stdout.strip() == b'644 0')
        check('installer leaves service disabled', guest('systemctl', 'is-enabled', '--quiet', 'minion-proxy', check=False).returncode != 0)
        check('installer leaves service stopped', guest('systemctl', 'is-active', '--quiet', 'minion-proxy', check=False).returncode != 0)
        guest('systemd-analyze', 'verify', '/etc/systemd/system/minion-proxy.service')
        direct = egress()
        before_route = public_route()
        run('podman', 'cp', args.subscription_file.resolve(), name + ':/root/subscription-url')
        guest('chmod', '600', '/root/subscription-url')
        if args.device_id_file:
            run('podman', 'cp', args.device_id_file.resolve(), name + ':/var/lib/minion/proxy/device-id')
            guest('chmod', '600', '/var/lib/minion/proxy/device-id')
        manage('configure', '--subscription-file', '/root/subscription-url', '--mode', 'proxy')
        run('podman', 'cp', name + ':/var/lib/minion/proxy/device-id', directory / 'device-id')
        os.chmod(directory / 'device-id', 0o600)
        check('private configuration permissions', guest('stat', '-c', '%a %u', '/var/lib/minion/proxy/config.json').stdout.strip() == b'600 0')
        saved_config = digest('/var/lib/minion/proxy/config.json')
        saved_identity = digest('/var/lib/minion/proxy/device-id')
        guest('chmod', '644', '/root/subscription-url')
        rejection = manage('configure', '--subscription-file', '/root/subscription-url', check=False)
        check('insecure input refused without replacing configuration', rejection.returncode != 0 and saved_config == digest('/var/lib/minion/proxy/config.json'))
        guest('chmod', '600', '/root/subscription-url')
        guest('systemctl', 'start', 'minion-proxy')
        wait_active()
        manage('test')
        check('HTTPS through explicit HTTP proxy')
        check('proxy public egress differs', egress(proxy=True) != direct)
        pid = guest('systemctl', 'show', '-p', 'MainPID', '--value', 'minion-proxy').stdout
        install()
        check('rerun preserves configuration and registration', saved_config == digest('/var/lib/minion/proxy/config.json') and saved_identity == digest('/var/lib/minion/proxy/device-id'))
        check('rerun does not restart running service', pid == guest('systemctl', 'show', '-p', 'MainPID', '--value', 'minion-proxy').stdout)
        if not args.skip_tun:
            manage('mode', 'tun')
            guest('systemctl', 'restart', 'minion-proxy')
            wait_active()
            manage('test')
            guest('ip', 'link', 'show', 'minion-proxy')
            check('TUN captures ordinary HTTPS traffic', egress() != direct)
            dns = guest('getent', 'ahostsv4', 'github.com').stdout
            check('DNS captured by Mihomo resolver', b'198.18.' in dns or b'198.19.' in dns)
            lan_route = guest('ip', 'route', 'get', '192.168.250.1').stdout
            check('private-network route bypasses TUN', b'minion-proxy' not in lan_route)
            ipv6_route = guest('ip', '-6', 'route', 'get', '2606:4700:4700::1111', check=False)
            # No uplink IPv6 means no IPv6 connectivity to capture; assert no
            # direct IPv6 default instead of claiming dual-stack validation.
            if ipv6_route.returncode == 0:
                check('public IPv6 route captured', b'minion-proxy' in ipv6_route.stdout)
            else:
                report['ipv6'] = 'No IPv6 uplink; public IPv6 is unreachable'
        guest('systemctl', 'enable', 'minion-proxy')
        guest('mv', '/opt/project', '/opt/project-hidden')
        run('podman', 'restart', name)
        if args.skip_tun:
            guest('python3', '-c', "open('/etc/resolv.conf','w').write('nameserver 1.1.1.1\\n')")
        wait_active()
        guest('python3', '/usr/local/lib/minion-proxy/manage.py', 'test')
        check('enabled service survives container reboot')
        check('boot service works without source checkout')
        guest('mv', '/opt/project-hidden', '/opt/project')
        guest('systemctl', 'disable', '--now', 'minion-proxy')
        check('stop removes TUN', guest('ip', 'link', 'show', 'minion-proxy', check=False).returncode != 0)
        check('stop restores original public route', before_route == public_route())
        check('stop restores direct egress', egress() == direct)
        if not args.skip_tun:
            dns = guest('getent', 'ahostsv4', 'github.com').stdout
            check('stop restores ordinary DNS', b'198.18.' not in dns and b'198.19.' not in dns)
        journal = guest('journalctl', '-u', 'minion-proxy', '--no-pager', '-o', 'cat').stdout
        secret = args.subscription_file.read_bytes().strip()
        check('subscription URL absent from service journal', secret not in journal)
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        diagnostics = guest('journalctl', '-u', 'minion-proxy', '--no-pager', '-o', 'cat', check=False)
        (directory / 'service-journal.log').write_bytes(diagnostics.stdout)
        os.chmod(directory / 'service-journal.log', 0o600)
        print('Container test failed; see private report and log in ' + str(directory), flush=True)
    finally:
        run('podman', 'rm', '-f', name, check=False)
        log.close()
        (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        os.chmod(directory / 'report.json', 0o600)
        print('Report: ' + str(directory / 'report.json'), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
