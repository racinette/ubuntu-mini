#!/usr/bin/env python3
"""Verify source-only Git clone setup on a disposable, previously tested VM branch."""
import argparse
import json
import shlex
import time

from gui import experiment
from session import ssh, stage_setup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    args = parser.parse_args()
    directory = experiment.select_directory(args.directory)
    baseline = json.loads((directory / 'baseline.json').read_text())
    parent = experiment.select_directory(baseline['directory'])
    if not json.loads((parent / 'post-install-setup-report.json').read_text())['passed']:
        raise ValueError('Use a new disposable branch of a passed standalone setup fixture')
    credentials = json.loads((directory / 'credentials.json').read_text())

    def root(command):
        return ssh(directory, 'sudo -k -S -p "" sh -ec ' + shlex.quote(command),
                   credentials['login_password'] + '\n')

    def snapshot():
        return json.loads(root('python3 -c ' + shlex.quote('''
import hashlib,json,subprocess
from pathlib import Path
files=['.bashrc','.config/foot/foot.ini','.config/atuin/config.toml']
print(json.dumps({'gpt':json.loads(subprocess.check_output(['sfdisk','--json','/dev/vda'],text=True)),
 'snaps':subprocess.check_output(['snap','list'],text=True),
 'settings':{n:hashlib.sha256((Path('/home/vmuser')/n).read_bytes()).hexdigest() for n in files}}))
''')))

    report = {'passed': False, 'started_at': time.time(), 'baseline': baseline,
              'scope': 'Default online setup from a source-only local Git clone on an existing desktop; fresh Snap Store install tested separately with command isolation'}
    try:
        deadline = time.monotonic() + 180
        while True:
            try:
                ssh(directory, 'true')
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)
        root('apt-get update >/tmp/mini-os-git-apt.log; DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git >>/tmp/mini-os-git-apt.log')
        origin = '/home/vmuser/mini-os-source-origin'
        clone = '/home/vmuser/mini-os-source-clone'
        ssh(directory, f'test ! -e {origin}; test ! -e {clone}')
        sources = stage_setup(directory, origin, include_gitignore=True)
        output = ssh(directory, f'cd {origin}; git init -q; git add .; git -c user.name="VM fixture" -c user.email="fixture@example.invalid" commit -qm "Source setup fixture"; git clone -q {origin} {clone}; cd {clone}; git ls-files')
        report['clone_files'] = output.splitlines()
        expected = sorted(str(p.relative_to(experiment.PROJECT)) for p in sources)
        if sorted(report['clone_files']) != expected:
            raise ValueError('Source-only clone does not match staged sources')
        before = snapshot()
        report['check_output'] = root(clone + '/setup.sh --check')
        if 'Online setup:' not in report['check_output']:
            raise ValueError('No-argument preflight must choose online setup')
        report['check_left_settings_and_partitions_unchanged'] = snapshot() == before
        output = root(clone + '/setup.sh')
        (directory / 'source-setup-console.log').write_text(output)
        after = snapshot()
        result = json.loads(root('python3 -c ' + shlex.quote('''
import json
from pathlib import Path
run=Path(json.loads(Path('/var/lib/mini-os/setup/last-success.json').read_text())['run'])
print((run/'result.json').read_text())
''')))
        report['setup_result'] = result
        report['settings_and_partitions_and_snaps_preserved'] = before == after
        report['upstream_shell_downloads'] = all('from ' + item['url'] in output for item in
                                               json.loads((experiment.PROJECT / 'setup/shell/artifacts.json').read_text()).values())
        report['no_cache_arguments'] = all('--asset-url' not in s['command'] for s in result['steps'])
        report['source_hashes_match'] = all(experiment.digest(experiment.PROJECT / name) == checksum
                                          for name, checksum in result['source_sha256'].items())
        report['passed'] = all((result['passed'], report['check_left_settings_and_partitions_unchanged'],
                               report['settings_and_partitions_and_snaps_preserved'],
                               report['upstream_shell_downloads'], report['no_cache_arguments'],
                               report['source_hashes_match']))
        if not report['passed']:
            raise ValueError('Source clone setup acceptance failed')
        print('Source-only Git clone setup passed: real upstream shell downloads, preserved settings, Snaps and GPT.', flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['finished_at'] = time.time()
        (directory / 'source-setup-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
