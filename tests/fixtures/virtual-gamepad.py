#!/usr/bin/env python3
"""Disposable guest-only uinput controller/mouse fixture, controlled over a private socket."""
import fcntl
import json
import os
from pathlib import Path
import socket
import struct
import sys

BUTTONS = [304, 305, 307, 308, 310, 311, 314, 315, 316, 317, 318]
AXES = {0: (-32768, 32767), 1: (-32768, 32767), 2: (0, 255),
        3: (-32768, 32767), 4: (-32768, 32767), 5: (0, 255),
        16: (-1, 1), 17: (-1, 1)}


class Device:
    def __init__(self, kind):
        self.fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, 0x40045564, 1)  # UI_SET_EVBIT EV_KEY
            buttons = BUTTONS if kind == 'gamepad' else [272, 273]
            for code in buttons:
                fcntl.ioctl(self.fd, 0x40045565, code)
            if kind == 'gamepad':
                fcntl.ioctl(self.fd, 0x40045564, 3)  # EV_ABS
                for code, (minimum, maximum) in AXES.items():
                    fcntl.ioctl(self.fd, 0x401c5504,
                                struct.pack('@H2xiiiiii', code, 0, minimum, maximum, 0, 0, 0))
            else:
                fcntl.ioctl(self.fd, 0x40045564, 2)  # EV_REL
                for code in (0, 1, 8):
                    fcntl.ioctl(self.fd, 0x40045566, code)
            name = ('ubuntu-mini virtual ' + kind + ' fixture').encode()
            # BUS_VIRTUAL, synthetic VID/PID; this does not emulate a USB controller protocol.
            fcntl.ioctl(self.fd, 0x405c5503, struct.pack('@HHHH80sI', 6, 0x1209, 1, 1, name, 0))
            fcntl.ioctl(self.fd, 0x5501)  # UI_DEV_CREATE
            buf = bytearray(128)
            fcntl.ioctl(self.fd, 0x8080552c, buf, True)  # UI_GET_SYSNAME
            self.sysname = buf.split(b'\0')[0].decode()
        except Exception:
            os.close(self.fd)
            raise

    def emit(self, events):
        for event_type, code, value in events:
            os.write(self.fd, struct.pack('@llHHi', 0, 0, event_type, code, value))
        os.write(self.fd, struct.pack('@llHHi', 0, 0, 0, 0, 0))

    def close(self):
        fcntl.ioctl(self.fd, 0x5502)  # UI_DEV_DESTROY
        os.close(self.fd)

    def probe(self, events):
        node = next((Path('/sys/class/input') / self.sysname).glob('event*')).name
        fd = os.open('/dev/input/' + node, os.O_RDONLY | os.O_NONBLOCK)
        try:
            self.emit(events)
            import select
            if not select.select([fd], [], [], 2)[0]:
                raise ValueError('Kernel event observer received no events')
            data = os.read(fd, 65536)
            size = struct.calcsize('@llHHi')
            return [list(struct.unpack('@llHHi', data[i:i + size])[2:])
                    for i in range(0, len(data), size)]
        finally:
            os.close(fd)


def main():
    if os.geteuid() != 0 or Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != 'QEMU':
        raise SystemExit('This fixture runs as root only inside the generated QEMU guest')
    directory = Path(sys.argv[1])
    directory.mkdir(mode=0o700)
    devices = {}
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(directory / 'control.sock'))
    server.listen(1)
    try:
        running = True
        while running:
            connection, _ = server.accept()
            with connection, connection.makefile('rwb') as stream:
                try:
                    request = json.loads(stream.readline())
                    operation = request['operation']
                    kind = request.get('kind', 'gamepad')
                    if kind not in ('gamepad', 'mouse'):
                        raise ValueError('Unknown fixture device')
                    if operation == 'create':
                        if kind in devices:
                            raise ValueError('Device already exists')
                        devices[kind] = Device(kind)
                        reply = {'sysname': devices[kind].sysname}
                    elif operation == 'emit':
                        devices[kind].emit(request['events'])
                        reply = {'sent': len(request['events'])}
                    elif operation == 'probe':
                        reply = {'events': devices[kind].probe(request['events'])}
                    elif operation == 'pulse':
                        import time
                        delay = float(request.get('delay', .12))
                        if not .02 <= delay <= 2:
                            raise ValueError('Invalid fixture pulse duration')
                        devices[kind].emit(request['events'])
                        time.sleep(delay)
                        devices[kind].emit(request['release'])
                        reply = {'pulsed': len(request['events'])}
                    elif operation == 'destroy':
                        devices.pop(kind).close()
                        reply = {'destroyed': kind}
                    elif operation == 'stop':
                        running = False
                        reply = {'stopped': True}
                    else:
                        raise ValueError('Unknown operation')
                except Exception as error:
                    reply = {'error': str(error)}
                stream.write((json.dumps(reply) + '\n').encode())
                stream.flush()
    finally:
        for device in devices.values():
            device.close()
        server.close()
        (directory / 'control.sock').unlink(missing_ok=True)
        directory.rmdir()


if __name__ == '__main__':
    main()
