#!/usr/bin/env python3
"""Run commands with the live graphical user's systemd activation environment."""
import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess

spec = importlib.util.spec_from_file_location('experiment', Path(__file__).with_name('vm.py'))
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)

def ssh(directory, command, input=None):
    state = json.loads((directory / 'state.json').read_text())
    result = subprocess.run(['ssh', '-i', str(directory / 'ssh-key'), '-p', str(state['ssh_port']),
        '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'), 'vmuser@127.0.0.1', command],
        input=input, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'Guest command exited {result.returncode}')
    return result.stdout

def graphical(directory, command, input=None):
    return ssh(directory, 'systemd-run --user --quiet --collect --pipe --wait /bin/sh -c ' + shlex.quote(command), input)


def setup_sources(include_gitignore=False):
    """Select only the root entry point and its setup component sources."""
    sources = [experiment.PROJECT / 'setup.sh']
    if include_gitignore:
        sources.append(experiment.PROJECT / '.gitignore')
    sources.extend(p for p in sorted((experiment.PROJECT / 'setup').rglob('*'))
                   if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return sources


def stage_setup(directory, target, include_gitignore=False):
    """Copy source files into the disposable guest without building an archive."""
    destination = Path(target)
    if (not destination.is_absolute() or '..' in destination.parts
            or destination.parent != Path('/home/vmuser')):
        raise ValueError('Stage setup in a direct child of the fixture user home')
    sources = setup_sources(include_gitignore)
    folders = sorted({str(destination / p.relative_to(experiment.PROJECT).parent) for p in sources})
    ssh(directory, 'mkdir -p ' + ' '.join(shlex.quote(p) for p in folders))
    state = json.loads((directory / 'state.json').read_text())
    for source in sources:
        relative = source.relative_to(experiment.PROJECT)
        subprocess.run(['scp', '-p', '-i', str(directory / 'ssh-key'), '-P', str(state['ssh_port']),
                        '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                        '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'), str(source),
                        'vmuser@127.0.0.1:' + str(destination / relative)], check=True, capture_output=True)
    return sources

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory')
    p.add_argument('command')
    args = p.parse_args()
    print(graphical(experiment.select_directory(args.directory), args.command), end='')
