#!/usr/bin/env python3
"""Loopback observer and browser fixture commands for controller mapping tests."""
import http.server
import json
from pathlib import Path

state = {}
command = {'id': 0}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/state':
            body, kind = json.dumps(state).encode(), 'application/json'
        elif self.path == '/command':
            body, kind = json.dumps(command).encode(), 'application/json'
        elif self.path == '/':
            body, kind = Path(__file__).with_name('gamepad-mapping-test.html').read_bytes(), 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global state, command
        value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/state':
            state = value
        elif self.path == '/command':
            command = dict(value, id=command['id'] + 1)
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(command).encode())

    def log_message(self, *args):
        pass


http.server.HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
