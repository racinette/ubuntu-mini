#!/usr/bin/env python3
"""Boot a diskless KVM/UEFI guest, capture evidence, and shut it down."""

import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time


def main():
    project = Path(__file__).resolve().parents[1]
    runs = project / ".local" / "vm"
    runs.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="probe-", dir=runs))
    variables = run / "OVMF_VARS.fd"
    shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", variables)
    monitor = run / "qmp.sock"
    command = [
        "/usr/bin/qemu-system-x86_64",
        "-machine", "q35,accel=kvm", "-cpu", "host",
        "-m", "512", "-smp", "2", "-nodefaults",
        "-device", "VGA", "-display", "none",
        "-monitor", "none", "-serial", "none", "-nic", "none",
        "-drive", "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,unit=1,file={variables}",
        "-qmp", f"unix:{monitor},server=on,wait=off", "-no-reboot",
    ]
    report = {"command": command, "run_directory": str(run)}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10)
    stream = None
    process = None
    with (run / "qemu.log").open("wb") as log:
        try:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"QEMU exited early: {process.returncode}")
                try:
                    sock.connect(str(monitor))
                    break
                except (FileNotFoundError, ConnectionRefusedError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("QMP did not become available")
                    time.sleep(0.1)
            stream = sock.makefile("rwb")
            report["greeting"] = json.loads(stream.readline())

            def execute(name, arguments=None):
                request = {"execute": name, "id": name}
                if arguments is not None:
                    request["arguments"] = arguments
                stream.write(json.dumps(request).encode() + b"\n")
                stream.flush()
                while True:
                    response = json.loads(stream.readline())
                    if response.get("id") == name:
                        if "error" in response:
                            raise RuntimeError(response["error"])
                        return response["return"]

            execute("qmp_capabilities")
            report["kvm"] = execute("query-kvm")
            if not report["kvm"].get("enabled"):
                raise RuntimeError("KVM acceleration is not enabled")
            report["version"] = execute("query-version")
            time.sleep(8)
            report["status"] = execute("query-status")
            if not report["status"].get("running"):
                raise RuntimeError("Guest is not running")
            screenshot = run / "uefi.ppm"
            execute("screendump", {"filename": str(screenshot)})
            if not screenshot.is_file() or screenshot.stat().st_size < 100:
                raise RuntimeError("Framebuffer capture is missing")
            report["screenshot"] = str(screenshot)
            execute("quit")
            process.wait(timeout=10)
            report["exit_code"] = process.returncode
            if process.returncode:
                raise RuntimeError(f"QEMU exited with {process.returncode}")
            report["passed"] = True
        except Exception as error:
            report["passed"] = False
            report["error"] = str(error)
            raise
        finally:
            if stream is not None:
                stream.close()
            sock.close()
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            monitor.unlink(missing_ok=True)
            (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
