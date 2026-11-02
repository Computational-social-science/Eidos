"""Disposable loopback service; only its private owner can request a crash/stop."""

import ctypes
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
import threading

BASE = Path(__file__).resolve().parent
config = json.loads((BASE / "config.json").read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, code, body=b"{}", **headers):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_GET(self):
        current = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
        if self.path == "/health":
            self.respond(200)
        elif self.path == "/engine":
            self.respond(current.get("engine_status", 200))
        elif self.path.startswith("/status/"):
            self.respond(int(self.path.rsplit("/", 1)[1]))
        elif self.path == "/redirect":
            self.respond(307, b"", Location="/health")
        else:
            self.respond(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length)) if 0 < length < 512 else {}
        if body.get("owner") != config["owner"]:
            self.respond(403)
            return
        self.respond(202)
        if self.path == "/crash":
            os._exit(17)
        elif self.path == "/stop":
            threading.Thread(target=self.server.shutdown, daemon=True).start()


class Server(HTTPServer):
    allow_reuse_address = True


with Server(("127.0.0.1", config["port"]), Handler) as server:
    console = None
    visible = None
    if os.name == "nt":
        get_console = ctypes.windll.kernel32.GetConsoleWindow
        get_console.restype = ctypes.c_void_p
        console = int(get_console() or 0)
        is_visible = ctypes.windll.user32.IsWindowVisible
        is_visible.argtypes = [ctypes.c_void_p]
        visible = bool(is_visible(console)) if console else False
    record = {
        "pid": os.getpid(),
        "port": server.server_port,
        "python": sys.executable,
        "console_window": console,
        "console_visible": visible,
    }
    with (BASE / "boots.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps(record) + "\n")
    server.serve_forever(poll_interval=0.05)
