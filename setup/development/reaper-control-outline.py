#!/usr/bin/python3
"""Draw a click-through selection border as children of REAPER's X11 window.

The owning ReaScript supplies screen rectangles, refreshed while Mixer is active.
No mouse events, window-manager rules, service or additional Python packages.
"""
import argparse
import ctypes as C
import fcntl
import json
import os
from pathlib import Path
import socket
import struct
import time


def focused_pid():
    """Check compositor focus too: Xwayland can retain stale X input focus."""
    def receive(sock, size):
        data = b''
        while len(data) < size:
            part = sock.recv(size - len(data))
            if not part:
                raise OSError('Closed Sway connection')
            data += part
        return data

    def find(node):
        if node.get('focused'):
            return node.get('pid')
        for child in node.get('nodes', []) + node.get('floating_nodes', []):
            result = find(child)
            if result is not None:
                return result

    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(.15)
        sock.connect(os.environ['SWAYSOCK'])
        sock.sendall(b'i3-ipc' + struct.pack('<II', 0, 4))
        header = receive(sock, 14)
        if header[:6] != b'i3-ipc':
            raise OSError('Invalid Sway response')
        size, _ = struct.unpack('<II', header[6:])
        if size > 16 * 1024 * 1024:
            raise OSError('Unexpected Sway tree size')
        return find(json.loads(receive(sock, size)))


class Outline:
    def __init__(self, pid):
        self.pid, self.parent, self.windows = pid, None, []
        self.x = C.CDLL('libX11.so.6')
        self.shape = C.CDLL('libXext.so.6')
        ptr, xid, integer = C.c_void_p, C.c_ulong, C.c_int
        signatures = {
            'XOpenDisplay': ([C.c_char_p], ptr),
            'XDefaultRootWindow': ([ptr], xid),
            'XInternAtom': ([ptr, C.c_char_p, integer], xid),
            'XQueryTree': ([ptr, xid, C.POINTER(xid), C.POINTER(xid), C.POINTER(C.POINTER(xid)), C.POINTER(C.c_uint)], integer),
            'XGetWindowProperty': ([ptr, xid, xid, C.c_long, C.c_long, integer, xid, C.POINTER(xid), C.POINTER(integer), C.POINTER(xid), C.POINTER(xid), C.POINTER(ptr)], integer),
            'XTranslateCoordinates': ([ptr, xid, xid, integer, integer, C.POINTER(integer), C.POINTER(integer), C.POINTER(xid)], integer),
            'XCreateSimpleWindow': ([ptr, xid, integer, integer, C.c_uint, C.c_uint, C.c_uint, xid, xid], xid),
            'XMoveResizeWindow': ([ptr, xid, integer, integer, C.c_uint, C.c_uint], integer),
            'XMapRaised': ([ptr, xid], integer), 'XUnmapWindow': ([ptr, xid], integer),
            'XStoreName': ([ptr, xid, C.c_char_p], integer),
            'XDestroyWindow': ([ptr, xid], integer), 'XFlush': ([ptr], integer),
            'XSync': ([ptr, integer], integer), 'XFree': ([ptr], integer),
            'XCloseDisplay': ([ptr], integer),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.x, name)
            function.argtypes, function.restype = args, result
        self.error = False
        self.handler = C.CFUNCTYPE(integer, ptr, ptr)(self.on_error)
        self.x.XSetErrorHandler.argtypes = [C.c_void_p]
        self.x.XSetErrorHandler(self.handler)
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise OSError('No Xwayland display')
        self.root = self.x.XDefaultRootWindow(self.display)
        self.atom = self.x.XInternAtom(self.display, b'_NET_WM_PID', False)
        self.shape.XShapeCombineRectangles.argtypes = [ptr, xid, integer, integer, integer, ptr, integer, integer, integer]

    def on_error(self, *_):
        self.error = True
        return 0

    def children(self, window):
        root, parent, children, count = C.c_ulong(), C.c_ulong(), C.POINTER(C.c_ulong)(), C.c_uint()
        if not self.x.XQueryTree(self.display, window, C.byref(root), C.byref(parent), C.byref(children), C.byref(count)):
            return []
        result = list(children[:count.value])
        if children:
            self.x.XFree(children)
        return result

    def owner(self, window):
        actual, bits, count, remaining, data = C.c_ulong(), C.c_int(), C.c_ulong(), C.c_ulong(), C.c_void_p()
        self.x.XGetWindowProperty(self.display, window, self.atom, 0, 1, False, 6,
                                 C.byref(actual), C.byref(bits), C.byref(count), C.byref(remaining), C.byref(data))
        result = C.cast(data, C.POINTER(C.c_ulong))[0] if data and count.value and bits.value == 32 else None
        if data:
            self.x.XFree(data)
        return result

    def origin(self, window):
        x, y, child = C.c_int(), C.c_int(), C.c_ulong()
        if not self.x.XTranslateCoordinates(self.display, window, self.root, 0, 0, C.byref(x), C.byref(y), C.byref(child)):
            raise OSError('REAPER window disappeared')
        return x.value, y.value

    def locate(self, rect):
        # TCP rectangles belong to the main project window. Pick the owning
        # top-level whose client rectangle contains the control, not an FX dialog.
        for window in self.children(self.root):
            if self.owner(window) != self.pid:
                continue
            x, y = self.origin(window)
            # Query geometry without relying on theme titles or translated names.
            root, gx, gy, width, height, border, depth = C.c_ulong(), C.c_int(), C.c_int(), C.c_uint(), C.c_uint(), C.c_uint(), C.c_uint()
            self.x.XGetGeometry.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int), C.POINTER(C.c_int), *([C.POINTER(C.c_uint)] * 4)]
            if self.x.XGetGeometry(self.display, window, C.byref(root), C.byref(gx), C.byref(gy), C.byref(width), C.byref(height), C.byref(border), C.byref(depth)):
                if x <= rect[0] and y <= rect[1] and rect[0] + rect[2] <= x + width.value and rect[1] + rect[3] <= y + height.value:
                    return window

    def hide(self):
        for window in self.windows:
            self.x.XUnmapWindow(self.display, window)
        self.x.XFlush(self.display)

    def show(self, rect):
        if self.parent is None:
            self.parent = self.locate(rect)
            if self.parent is None:
                return False
            for _ in range(4):
                window = self.x.XCreateSimpleWindow(self.display, self.parent, 0, 0, 1, 1, 0, 0, 0x55DDFF)
                # ShapeInput=2, ShapeSet=0; an empty input region passes every
                # pointer event through to the native control underneath.
                self.shape.XShapeCombineRectangles(self.display, window, 2, 0, 0, None, 0, 0, 0)
                self.x.XStoreName(self.display, window, b'REAPER gamepad selection')
                self.windows.append(window)
        origin = self.origin(self.parent)
        x, y, w, h = rect
        x, y, w, h = x - origin[0] - 2, y - origin[1] - 2, w + 4, h + 4
        for window, box in zip(self.windows, ((x, y, w, 2), (x, y + h - 2, w, 2), (x, y, 2, h), (x + w - 2, y, 2, h))):
            self.x.XMoveResizeWindow(self.display, window, *box)
            self.x.XMapRaised(self.display, window)
        self.x.XSync(self.display, False)
        return not self.error

    def close(self):
        for window in self.windows:
            self.x.XDestroyWindow(self.display, window)
        self.x.XCloseDisplay(self.display)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    with args.state.with_suffix('.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        outline = Outline(args.pid)
        previous = None
        try:
            while Path(f'/proc/{args.pid}').exists():
                try:
                    if time.time() - args.state.stat().st_mtime > 2:
                        break
                    values = args.state.read_text().split()
                    rect = tuple(map(int, values)) if len(values) == 4 else None
                    if rect and (min(rect[2:]) <= 0 or max(rect[2:]) > 32768):
                        rect = None
                    if rect and focused_pid() != args.pid:
                        rect = None
                    if rect:
                        # Even unchanged screen coordinates need translating
                        # again when the parent window moves.
                        if not outline.show(rect):
                            break
                    elif previous:
                        outline.hide()
                    previous = rect
                except FileNotFoundError:
                    break
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    outline.hide()
                time.sleep(.1)
        finally:
            outline.close()


if __name__ == '__main__':
    main()
