#!/usr/bin/env python3
"""Prove a cold boot requires LUKS unlock and a separate console login."""

import json
import argparse
from pathlib import Path
import socket
import sys
import time

from qmp import Monitor
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location("experiment", Path(__file__).with_name("vm.py"))
experiment = module_from_spec(spec)
spec.loader.exec_module(experiment)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory')
args = p.parse_args()
directory = experiment.select_directory(args.directory)
credentials = json.loads((directory / "credentials.json").read_text())
log = directory / "boot-serial.log"
report = {}
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect(str(directory / "serial.sock"))
sock.setblocking(False)


def wait_for(markers, start=0, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            while sock.recv(65536):
                pass
        except BlockingIOError:
            pass
        text = log.read_text(errors="replace")[start:]
        for marker in markers:
            if marker in text:
                return len(log.read_text(errors="replace"))
        time.sleep(0.5)
    raise TimeoutError(f"Console did not show any expected marker: {markers}")


def capture(name):
    monitor = Monitor(directory / "qmp.sock")
    try:
        monitor.execute("screendump", {"filename": str(directory / (name + ".ppm"))})
    finally:
        monitor.close()


try:
    position = wait_for(["Please unlock disk cryptroot", "Enter passphrase for", "Please unlock disk"])
    report["luks_prompt_observed"] = True
    capture("luks-prompt")
    print("Cold boot reached the LUKS passphrase prompt", flush=True)
    sock.sendall(b"intentionally-wrong-vm-passphrase\n")
    position = wait_for(["bad password", "No key available", "cryptsetup failed"], position)
    report["wrong_luks_passphrase_refused"] = True
    print("Wrong LUKS passphrase was refused", flush=True)
    time.sleep(1)
    sock.sendall(credentials["luks_passphrase"].encode() + b"\n")
    position = wait_for(['mini-os-vm login:'], position)
    report['correct_luks_passphrase_booted'] = True
    capture('user-login-prompt')
    print('Correct passphrase booted Ubuntu to a separate login prompt', flush=True)
    sock.sendall(b'vmuser\n')
    position = wait_for(['Password:'], position)
    report['separate_user_password_prompt_observed'] = True
    sock.sendall(credentials['login_password'].encode() + b'\n')
    wait_for(['vmuser@mini-os-vm:'], position)
    sock.sendall(b"printf 'MINI_OS_CONSOLE_LOGIN_OK\\n'\n")
    wait_for(['MINI_OS_CONSOLE_LOGIN_OK'], position)
    report['password_login_succeeded'] = True
    capture('console-login')
    sock.sendall(b'exit\n')
    print('User password authentication succeeded', flush=True)
    report["passed"] = True
except Exception as error:
    report.update(passed=False, error=str(error))
    raise
finally:
    sock.close()
    filename = 'boot-authentication-report.json'
    (directory / filename).write_text(json.dumps(report, indent=2) + "\n")
