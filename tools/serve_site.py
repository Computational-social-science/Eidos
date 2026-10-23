"""Serve the delivery page with a live status endpoint.

A file:// page cannot poll; that is a browser rule, not a design choice. This server adds
the one thing the snapshot page lacks — a near-real-time feed — without changing the page:

    http://127.0.0.1:8765/            the same site/index.html
    http://127.0.0.1:8765/api/status  the control loop sample, refreshed every 5 s
    http://127.0.0.1:8765/api/pipeline the composed pipeline document

The sampler runs in a background thread and never blocks a request. If the watcher fails,
the endpoint returns the last good sample with `stale: true` rather than pretending.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import watch_pipeline  # noqa: E402

STATE: dict = {"payload": None, "sampled": 0.0, "error": None}


def sampler(interval: float) -> None:
    while True:
        try:
            STATE["payload"] = watch_pipeline.sample(append=True)
            STATE["sampled"] = time.time()
            STATE["error"] = None
        except Exception as exc:  # noqa: BLE001 - keep serving, report the failure
            STATE["error"] = f"{type(exc).__name__}: {exc}"
        time.sleep(interval)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "site"), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib name
        pass

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        if self.path in ("/", "/index.html"):
            blob = (ROOT / "site" / "dashboard.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(blob)
            return
        if self.path.startswith("/api/status"):
            payload = STATE["payload"] or {}
            body = dict(payload)
            body["stale"] = (time.time() - STATE["sampled"]) > 30
            body["server_error"] = STATE["error"]
            self._send(body)
            return
        if self.path.startswith("/api/pipeline"):
            path = ROOT / "docs" / "pipeline.json"
            try:
                self._send(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                self._send({"error": str(exc)}, status=503)
            return
        super().do_GET()

    def _send(self, payload: dict, status: int = 200) -> None:
        blob = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(blob)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args(argv)

    threading.Thread(target=sampler, args=(args.interval,), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"serving http://127.0.0.1:{args.port}/  (status every {args.interval:.0f}s)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
