"""Small synchronous QMP client for the local experimental VM."""

import json
import socket


class Monitor:
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(15)
        self.socket.connect(str(path))
        self.stream = self.socket.makefile("rwb")
        self.greeting = json.loads(self.stream.readline())
        self.execute("qmp_capabilities")

    def execute(self, name, arguments=None):
        request = {"execute": name, "id": name}
        if arguments is not None:
            request["arguments"] = arguments
        self.stream.write(json.dumps(request).encode() + b"\n")
        self.stream.flush()
        while True:
            line = self.stream.readline()
            if not line:
                raise EOFError("QMP disconnected")
            response = json.loads(line)
            if response.get("id") == name:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response["return"]

    def close(self):
        self.stream.close()
        self.socket.close()
