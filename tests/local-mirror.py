#!/usr/bin/env python3
"""Serve a project-local read-through Ubuntu mirror for repeat VM installs.

Upstream packages/indices keep their signed Ubuntu metadata. This server does
not generate, alter or sign repository content. Only two fixed upstreams exist.
"""

import argparse
from collections import defaultdict
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / ".local" / "mirror"
UPSTREAMS = {"ubuntu": "https://archive.ubuntu.com/ubuntu/",
             "ubuntu-security": "https://security.ubuntu.com/ubuntu/"}
LOCKS = defaultdict(threading.Lock)
EVENT_LOCK = threading.Lock()


def event(**fields):
    fields["timestamp"] = time.time()
    with EVENT_LOCK:
        with (ROOT / "events.jsonl").open("a") as file:
            file.write(json.dumps(fields) + "\n")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        self.respond(head=True)

    def do_GET(self):
        self.respond(head=False)

    def respond(self, head):
        path = unquote(urlsplit(self.path).path)
        if path == "/health":
            data = b"mini-os local mirror ready\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not head:
                self.wfile.write(data)
            return
        pieces = path.lstrip("/").split("/")
        if len(pieces) == 2 and pieces[0] == "assets" and pieces[1] not in ("", ".", "..") and "\\" not in pieces[1]:
            target = ROOT / "assets" / pieces[1]
            if not target.is_file() or target.is_symlink():
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(target.stat().st_size))
            self.send_header("X-Mini-OS-Cache", "HIT")
            self.end_headers()
            if not head:
                with target.open("rb") as file:
                    shutil.copyfileobj(file, self.wfile, length=1024**2)
            event(kind="asset_served", path=path, bytes=0 if head else target.stat().st_size)
            return
        if len(pieces) < 3 or pieces[0] not in UPSTREAMS or pieces[1] not in ("dists", "pool"):
            self.send_error(404)
            return
        if any(piece in ("", ".", "..") or "\\" in piece for piece in pieces):
            self.send_error(400)
            return
        target = ROOT / "cache" / Path(*pieces)
        url = UPSTREAMS[pieces[0]] + "/".join(pieces[1:])
        cache_hit = False
        headers_sent = False
        try:
            with LOCKS[str(target)]:
                # Immutable pool/by-hash objects stay cached. Refresh mutable
                # indices after one hour; apt still validates signatures/hashes.
                immutable = pieces[1] == "pool" or "by-hash" in pieces
                cache_hit = target.is_file() and (immutable or time.time() - target.stat().st_mtime < 3600)
                if not cache_hit:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = None
                    try:
                        with urlopen(url, timeout=120) as response:
                            self.send_response(200)
                            self.send_header("Content-Type", "application/octet-stream")
                            if response.headers.get("Content-Length"):
                                self.send_header("Content-Length", response.headers["Content-Length"])
                            self.send_header("X-Mini-OS-Cache", "MISS")
                            self.end_headers()
                            headers_sent = True
                            connected = True
                            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as file:
                                temporary = Path(file.name)
                                while chunk := response.read(65536):
                                    file.write(chunk)
                                    if not head and connected:
                                        try:
                                            self.wfile.write(chunk)
                                        except (BrokenPipeError, ConnectionResetError):
                                            connected = False
                        expected_size = response.headers.get("Content-Length")
                        if expected_size is not None and temporary.stat().st_size != int(expected_size):
                            raise ValueError("Upstream response ended before its declared length")
                        os.replace(temporary, target)
                        event(kind="upstream_download", path=path, bytes=target.stat().st_size)
                        event(kind="served" if connected else "client_disconnected", path=path,
                              bytes=0 if head else target.stat().st_size, cache_hit=False)
                        return
                    finally:
                        if temporary is not None:
                            temporary.unlink(missing_ok=True)
            size = target.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("X-Mini-OS-Cache", "HIT" if cache_hit else "MISS")
            self.end_headers()
            if not head:
                with target.open("rb") as file:
                    shutil.copyfileobj(file, self.wfile, length=1024**2)
            event(kind="served", path=path, bytes=0 if head else size, cache_hit=cache_hit)
        except HTTPError as error:
            self.send_error(error.code)
            event(kind="upstream_error", path=path, status=error.code)
        except (BrokenPipeError, ConnectionResetError):
            event(kind="client_disconnected", path=path)
        except Exception as error:
            if not headers_sent:
                self.send_error(502)
            self.close_connection = True
            event(kind="error", path=path, error=str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--daemon", action="store_true", help="Run a persistent project-local server")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    if args.daemon:
        import subprocess
        import sys
        with (ROOT / 'server.log').open('ab') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--port', str(args.port)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        import time
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError('Mirror failed to start; inspect .local/mirror/server.log')
            if (ROOT / 'server.json').exists():
                state = json.loads((ROOT / 'server.json').read_text())
                if state.get('pid') == process.pid:
                    print(json.dumps(state, indent=2))
                    return
            time.sleep(0.1)
        raise TimeoutError('Mirror state file was not written')
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    port = server.server_port
    state = {"pid": os.getpid(), "port": port, "host_url": f"http://127.0.0.1:{port}",
             "guest_url": f"http://10.0.2.2:{port}", "upstreams": UPSTREAMS}
    (ROOT / "server.json").write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state, indent=2), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
