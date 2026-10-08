#!/usr/bin/env python3
"""Exercise standalone setup on a generated server-only VM branch."""
import argparse
import hashlib
import json
import shlex
import time

from gui import experiment
from session import ssh, stage_setup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('--rerun', action='store_true', help='Verify the final source revision and retained user settings')
    args = parser.parse_args()
    directory = experiment.select_directory(args.directory)
    baseline = json.loads((directory / 'baseline.json').read_text())
    experiment.select_directory(baseline['directory'])
    state = json.loads((directory / 'state.json').read_text())
    if not any('mount_tag=setup_assets' in arg for arg in state['command']):
        raise ValueError('Launch with --setup-assets to expose only the read-only artifact cache')
    credentials = json.loads((directory / 'credentials.json').read_text())

    def root(command):
        return ssh(directory, 'sudo -k -S -p "" sh -ec ' + shlex.quote(command),
                   credentials['login_password'] + '\n')

    if args.rerun:
        previous = json.loads((directory / 'post-install-setup-report.json').read_text())
        if not previous['passed']:
            raise ValueError('First standalone setup must have passed')
        root('mkdir -p /mnt/mini-os-assets; mountpoint -q /mnt/mini-os-assets || mount -t 9p -o trans=virtio,version=9p2000.L,ro setup_assets /mnt/mini-os-assets')
        stage_setup(directory, '/home/vmuser/mini-os-setup')
        settings = ['.bashrc', '.config/foot/foot.ini', '.config/atuin/config.toml', '.config/sway/mini-os.conf']
        ssh(directory, "mkdir -p ~/.config/sway; printf 'input type:keyboard {\\n    xkb_layout us,ru\\n    xkb_options grp:alt_shift_toggle\\n}\\n' > ~/.config/sway/mini-os.conf")
        for name in settings[:3]:
            ssh(directory, 'printf "\\n# Preserve this personal preference on setup reruns.\\n" >> ' + shlex.quote('/home/vmuser/' + name))
        hashes_before = {name: hashlib.sha256(ssh(directory, 'cat ' + shlex.quote('/home/vmuser/' + name)).encode()).hexdigest() for name in settings}
        # Force the final local-file code path to install a real signed browser.
        # This is the disposable VM, before any browser user data is created.
        root('snap remove --purge firefox')
        output = root('/home/vmuser/mini-os-setup/setup.sh --asset-dir /mnt/mini-os-assets')
        (directory / 'standalone-setup-rerun-console.log').write_text(output)
        hashes_after = {name: hashlib.sha256(ssh(directory, 'cat ' + shlex.quote('/home/vmuser/' + name)).encode()).hexdigest() for name in settings}
        result = json.loads(root("python3 -c " + shlex.quote('''
import json,subprocess,hashlib
from pathlib import Path
run=Path(json.loads(Path('/var/lib/mini-os/setup/last-success.json').read_text())['run'])
data=json.loads((run/'result.json').read_text())
print(json.dumps({'result':data,
 'gpt':json.loads(subprocess.check_output(['sfdisk','--json','/dev/vda'],text=True)),
 'packages':subprocess.check_output(['dpkg-query','-W','-f=${Package} ${db:Status-Status}\\n','alsa-ucm-conf','alsa-utils','mesa-va-drivers'],text=True),
 'snaps':subprocess.check_output(['snap','list'],text=True),
 'bash_include_count':Path('/home/vmuser/.bashrc').read_text().splitlines().count('source /usr/local/share/mini-os/bashrc.bash')}))
''')))
        source_matches = all(experiment.digest(experiment.PROJECT / name) == checksum
                             for name, checksum in result['result']['source_sha256'].items())
        report = {'passed': result['result']['passed'] and hashes_before == hashes_after
                  and result['gpt'] == previous['before']['gpt'] and result['bash_include_count'] == 1
                  and source_matches and all(name + ' installed' in result['packages']
                                              for name in ('alsa-ucm-conf', 'alsa-utils', 'mesa-va-drivers')),
                  'user_setting_hashes_before': hashes_before, 'user_setting_hashes_after': hashes_after,
                  'staged_sources_match_current': source_matches, 'after': result}
        (directory / 'post-install-rerun-report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['passed']:
            raise ValueError('Rerun acceptance assertion failed')
        # Software rendering is a fixture adaptation, never part of device setup.
        root("printf 'export WLR_RENDERER=pixman\\nexport WLR_NO_HARDWARE_CURSORS=1\\n' > /etc/mini-os/vm-environment")
        print('Final setup source passed: local signed browser install, driver prerequisites, user settings and GPT preservation.', flush=True)
        return

    report = {'started_at': time.time(), 'baseline': baseline, 'passed': False}
    try:
        before = json.loads(root("python3 -c " + shlex.quote('''
import json,subprocess
from pathlib import Path
def output(*args):
    return subprocess.check_output(args,text=True).strip()
print(json.dumps({'gpt':json.loads(output('sfdisk','--json','/dev/vda')),
 'kernel':output('uname','-r'),
 'no_setup_state':not Path('/var/lib/mini-os/setup').exists(),
 'no_desktop':subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}','sway'],capture_output=True,text=True).stdout.strip()!='installed',
 'no_firefox':subprocess.run(['snap','list','firefox'],capture_output=True).returncode!=0}))
''')))
        report['before'] = before
        if not all(before[k] for k in ('no_setup_state', 'no_desktop', 'no_firefox')):
            raise ValueError('The fixture must begin as an unconfigured Ubuntu Server installation')
        root('mkdir -p /mnt/mini-os-assets; mount -t 9p -o trans=virtio,version=9p2000.L,ro setup_assets /mnt/mini-os-assets')
        stage_setup(directory, '/home/vmuser/mini-os-setup')
        command = '/home/vmuser/mini-os-setup/setup.sh --asset-dir /mnt/mini-os-assets'
        refusal = root('if ' + command + ' --user root --check >/tmp/mini-os-invalid-user.log 2>&1; then exit 1; fi; cat /tmp/mini-os-invalid-user.log')
        if 'existing regular user' not in refusal and 'normal account' not in refusal:
            raise ValueError('Wrong-account preflight did not refuse for the expected reason')
        refusal = root('if /home/vmuser/mini-os-setup/setup.sh --asset-dir /tmp/mini-os-missing-assets --check >/tmp/mini-os-missing-assets.log 2>&1; then exit 1; fi; cat /tmp/mini-os-missing-assets.log')
        if 'Missing or incorrect artifact' not in refusal:
            raise ValueError('Missing-asset preflight did not refuse for the expected reason')
        report['preflight_refusals'] = {'wrong_account': True, 'missing_assets': True,
                                       'no_setup_state_written': root('test ! -e /var/lib/mini-os/setup; printf OK').strip() == 'OK'}
        report['check_output'] = root(command + ' --check')
        report['check_left_setup_state_absent'] = root('test ! -e /var/lib/mini-os/setup; printf OK').strip() == 'OK'
        print('Preflight refusals and read-only check passed. Applying standalone setup...', flush=True)
        output = root(command)
        (directory / 'standalone-setup-console.log').write_text(output)
        report['after'] = json.loads(root("python3 -c " + shlex.quote('''
import json,subprocess
from pathlib import Path
def output(*args):return subprocess.check_output(args,text=True).strip()
run=Path(json.loads(Path('/var/lib/mini-os/setup/last-success.json').read_text())['run'])
print(json.dumps({'result':json.loads((run/'result.json').read_text()),
 'backup_exists':(run/'configuration-before.tar.gz').is_file(),
 'gpt':json.loads(output('sfdisk','--json','/dev/vda')),
 'networkd_still_active':subprocess.run(['systemctl','is-active','--quiet','systemd-networkd']).returncode==0,
 'greetd_deferred':subprocess.run(['systemctl','is-active','--quiet','greetd']).returncode!=0,
 'no_runtime_mask':not Path('/run/systemd/system/greetd.service').is_symlink(),
 'packages':output('dpkg-query','-W','-f=${Package} ${Version} ${db:Status-Status}\\n','linux-generic-hwe-24.04','linux-firmware','amd64-microcode','libgl1-mesa-dri','libegl-mesa0','mesa-vulkan-drivers','sway','greetd','foot','pipewire','wireplumber'),
 'snaps':output('snap','list'), 'atuin':output('atuin','--version')}))
''')))
        after = report['after']
        report['gpt_unchanged'] = before['gpt'] == after['gpt']
        report['passed'] = all((after['result']['passed'], after['backup_exists'], after['networkd_still_active'],
            after['greetd_deferred'], after['no_runtime_mask'], report['gpt_unchanged'],
            report['check_left_setup_state_absent'], report['preflight_refusals']['no_setup_state_written']))
        if not report['passed']:
            raise ValueError('Standalone setup acceptance assertion failed')
        print('Standalone setup completed; GPT unchanged, current networking/login retained, reboot pending.', flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['finished_at'] = time.time()
        (directory / 'post-install-setup-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
