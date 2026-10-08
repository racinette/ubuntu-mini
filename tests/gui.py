#!/usr/bin/env python3
"""Send real virtual keyboard events and capture the VM framebuffer through QMP."""
import argparse
import importlib.util
import json
from pathlib import Path
import time

from PIL import Image
from qmp import Monitor

spec = importlib.util.spec_from_file_location('experiment', Path(__file__).with_name('vm.py'))
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)

def key(monitor, keys):
    monitor.execute('send-key', {'keys': [{'type': 'qcode', 'data': k} for k in keys], 'hold-time': 40})
    time.sleep(0.08)

def type_text(monitor, text):
    punctuation = {' ': ('spc', False), '\n': ('ret', False), '-': ('minus', False), '_': ('minus', True),
                   '=': ('equal', False), '+': ('equal', True), '.': ('dot', False), ',': ('comma', False),
                   '/': ('slash', False), ':': ('semicolon', True), ';': ('semicolon', False),
                   "'": ('apostrophe', False), '"': ('apostrophe', True), '\\': ('backslash', False),
                   '|': ('backslash', True), '[': ('bracket_left', False), ']': ('bracket_right', False),
                   '(': ('9', True), ')': ('0', True), '$': ('4', True), '>': ('dot', True), '<': ('comma', True),
                   '%': ('5', True), '?': ('slash', True), '!': ('1', True), '@': ('2', True),
                   '#': ('3', True), '^': ('6', True), '&': ('7', True), '*': ('8', True),
                   '`': ('grave_accent', False), '~': ('grave_accent', True),
                   '{': ('bracket_left', True), '}': ('bracket_right', True), '\t': ('tab', False)}
    if any(not (c.isascii() and c.isalnum() or c in punctuation) for c in text):
        raise ValueError('Only ASCII keyboard fixture text is supported')
    for char in text:
        if char.isascii() and char.isalnum():
            code, shift = char.lower(), char.isupper()
        else:
            code, shift = punctuation[char]
        key(monitor, (['shift'] if shift else []) + [code])

def capture(monitor, directory, name):
    if Path(name).name != name:
        raise ValueError('Use a plain screenshot name')
    ppm = directory / (name + '.ppm')
    monitor.execute('screendump', {'filename': str(ppm)})
    target = directory / (name + '.png')
    Image.open(ppm).save(target)
    ppm.unlink()
    print(target)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory')
    p.add_argument('action', choices=['key', 'type', 'password', 'capture'])
    p.add_argument('value', nargs='?', default='')
    args = p.parse_args()
    directory = experiment.select_directory(args.directory)
    monitor = Monitor(directory / 'qmp.sock')
    try:
        if args.action == 'key': key(monitor, args.value.split('+'))
        elif args.action == 'type': type_text(monitor, args.value)
        elif args.action == 'password':
            creds = json.loads(directory.joinpath('credentials.json').read_text())
            type_text(monitor, creds['login_password'] + '\n')
        else: capture(monitor, directory, args.value)
    finally:
        monitor.close()

if __name__ == '__main__': main()
