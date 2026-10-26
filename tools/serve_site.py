"""Serve the monitor at / and the document at /index.html, with one live status feed.

A file:// page cannot poll; that is a browser rule, not a design choice. This server adds the
one thing the static pages lack — a near-real-time feed — without changing the pages:

    http://127.0.0.1:8765/            site/dashboard.html   (the assembly monitor)
    http://127.0.0.1:8765/index.html  site/index.html       (the document)
    http://127.0.0.1:8765/api/status  one sample, refreshed on an interval
    http://127.0.0.1:8765/api/pipeline the composed pipeline document

Two rules learned the hard way:

  * one instance only — Windows will happily let two processes bind the same port, and then
    whichever answers first wins, with two samplers writing the same files;
  * sample on an interval, redraw on a longer one — a full SVG rebuild every few seconds is
    pure heat for a page nobody watches that closely.

The sampler runs in a background thread and never blocks a request. If it fails, the endpoint
returns the last good sample with `stale: true` rather than pretending.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import watch_pipeline  # noqa: E402

STATE: dict = {"payload": None, "sampled": 0.0, "error": None, "strip": "", "strip_sig": None,
               "written": 0.0, "page_sig": None, "interval": 15.0}
PAGES = {"/": "dashboard.html", "/dashboard.html": "dashboard.html", "/index.html": "index.html"}



def ensure_scheduler(interval_min: int = 10) -> str:
    """Keep the chain scheduler alive from the process that is always running.

    A heartbeat catches a dead scheduler after the fact; something has to restart it. The server
    is the only long-lived process on this host, so it supervises: if the heartbeat is older than
    two intervals, spawn the loop detached. A live loop keeps the heartbeat fresh, so this
    cannot start a second one.
    """
    beat_path = ROOT / "docs" / "status" / "scheduler.json"
    stale_after = interval_min * 60 * 2
    try:
        beat = json.loads(beat_path.read_text(encoding="utf-8"))
        age = time.time() - float(beat.get("epoch") or 0)
    except (OSError, json.JSONDecodeError, ValueError):
        age = float("inf")
    if age < stale_after:
        return f"scheduler alive ({age / 60:.0f} min since last tick)"

    log = (ROOT / "docs" / "status" / "scheduler.log").open("a", encoding="utf-8")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen([sys.executable, "tools/refresh_chains.py", "--loop",
                      "--interval", str(interval_min)],
                     cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                     creationflags=flags, start_new_session=(os.name != "nt"))
    return f"scheduler was stale ({age / 60:.0f} min); started it"


STALL_LIMIT = 180.0   # a sample that takes longer than this is a hang, not a slow probe


def stall_watchdog(limit: float = STALL_LIMIT, check_every: float = 20.0) -> None:
    """Exit the process when sampling stops, so the supervisor can start a clean one.

    The sampler caught exceptions but a blocked probe does not raise — the thread simply stops
    producing samples while the server keeps answering, which is how the monitor served a page
    seven minutes old with no error to show for it.
    """
    while True:
        time.sleep(check_every)
        last = STATE.get("sampled") or 0.0
        age = time.time() - last
        if age > limit:
            stamp = datetime.datetime.now().isoformat(timespec="seconds")
            line = f"{stamp} sampler stalled for {age:.0f} s; exiting so the supervisor restarts it"
            print(line, flush=True)
            try:
                (ROOT / "docs" / "status" / "serve.log").open("a", encoding="utf-8").write(
                    line + chr(10))
            except OSError:
                pass
            os._exit(3)


def sampler(interval: float, page_interval: float) -> None:
    import dashboard

    while True:
        started = time.time()
        try:
            note = ensure_scheduler()
            if "started" in note:
                print(note, flush=True)
            payload = watch_pipeline.sample(append=True)
            STATE["payload"] = payload
            STATE["sampled"] = time.time()
            STATE["error"] = None

            timeline = payload.get("timeline") or []
            sig = (len(timeline), timeline[-1].get("ts") if timeline else None)
            if sig != STATE["strip_sig"]:
                STATE["strip"] = dashboard.strip(timeline)
                STATE["strip_sig"] = sig

            page_sig = json.dumps(payload.get("chains") or {}, sort_keys=True)
            if page_sig != STATE["page_sig"] or time.time() - STATE["written"] > page_interval:
                # Render into memory. Writing the file here made a tracked build artefact
                # change every minute, so git status was never clean, and an edit to the
                # builder was silently overwritten by the module this process imported.
                # Reload the builder before rendering: this process imported it at start, so
                # without the reload an edit to dashboard.py is invisible until a restart and
                # the monitor keeps serving the old page.
                globals()["dashboard"] = importlib.reload(dashboard)
                STATE["page"] = dashboard.build()
                STATE["written"] = time.time()
                STATE["page_sig"] = page_sig
        except Exception as exc:  # noqa: BLE001 - keep serving, report the failure
            STATE["error"] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        time.sleep(max(interval - (time.time() - started), 1.0))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "site"), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib name
        pass

    def _html(self, name: str) -> None:
        if name == "dashboard.html" and STATE.get("page"):
            blob = STATE["page"].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(blob)
            return
        path = ROOT / "site" / name
        if not path.is_file():
            self.send_error(404, f"{name} has not been built")
            return
        blob = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        clean = self.path.split("?")[0]
        if clean in PAGES:
            self._html(PAGES[clean])
            return
        if clean == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if clean.startswith("/api/status"):
            body = dict(STATE["payload"] or {})
            body["stale"] = (time.time() - STATE["sampled"]) > 3 * STATE["interval"]
            body["server_error"] = STATE["error"]
            body["strip_html"] = STATE["strip"]        # rendered once per sample, not per request
            self._send(body)
            return
        if clean.startswith("/api/pipeline"):
            path = ROOT / "docs" / "pipeline.json"
            try:
                self._send(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                self._send({"error": str(exc)}, status=503)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        if not self.path.startswith("/api/restart/"):
            self._send({"error": "unknown endpoint"}, status=404)
            return
        name = self.path.rsplit("/", 1)[-1]
        sys.path.insert(0, str(ROOT))
        from framework import recovery
        plan_ = recovery.plan(name)
        if not plan_.available:
            self._send({"ok": False, "error": plan_.reason or "no recovery action"}, status=400)
            return
        result = recovery.execute(plan_)
        if result.get("ok") and not result.get("skipped"):
            result["verify"] = recovery.verify(name, timeout=120)
        self._send(result, status=202)

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
    ap.add_argument("--interval", type=float, default=15.0,
                    help="seconds between samples (each costs ~200 ms)")
    ap.add_argument("--page-interval", type=float, default=60.0,
                    help="maximum seconds between full HTML redraws")
    args = ap.parse_args(argv)

    # One instance only: two binds of the same port is how "the site is down" happens while a
    # process is sitting right there.
    try:
        with socket.create_connection(("127.0.0.1", args.port), timeout=0.6):
            print(f"[FAIL] something is already serving on 127.0.0.1:{args.port}")
            return 2
    except OSError:
        pass

    STATE["interval"] = args.interval
    threading.Thread(target=sampler, args=(args.interval, args.page_interval),
                     daemon=True).start()
    threading.Thread(target=stall_watchdog, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"serving http://127.0.0.1:{args.port}/  "
          f"(sample every {args.interval:.0f}s, redraw every {args.page_interval:.0f}s)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
