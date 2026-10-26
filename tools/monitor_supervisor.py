"""Single supervisor for the monitor: one loop, one lock, restart on exit.

Windows gives no free supervisor, and a batch file that loops cannot tell whether another copy of
itself is already looping — three `cmd` windows each restarting a server that cannot bind is what
that looks like. This process is the supervisor: it holds `docs/status/monitor.lock` with its own
PID, refuses to start if the PID inside is alive, and restarts `tools/serve_site.py` when it exits.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "docs" / "status" / "monitor.lock"
LOG = ROOT / "docs" / "status" / "serve.log"
RESTART_DELAY = 5


def _alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                         capture_output=True, text=True)
    return str(pid) in (out.stdout or "")


def acquire() -> bool:
    """Take the lock, or report that a live supervisor already holds it."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.is_file():
        try:
            holder = json.loads(LOCK.read_text(encoding="utf-8")).get("pid")
        except (OSError, json.JSONDecodeError):
            holder = None
        if holder and _alive(int(holder)):
            print(f"monitor supervisor already running (pid {holder})")
            return False
    LOCK.write_text(json.dumps({"pid": os.getpid(), "since": time.time()}), encoding="utf-8")
    return True


def release() -> None:
    try:
        LOCK.unlink()
    except OSError:
        pass


def main() -> int:
    if not acquire():
        return 0
    python = os.environ.get("PYTHON") or sys.executable
    print(f"supervisor {os.getpid()} using {python}", flush=True)
    try:
        while True:
            log = LOG.open("a", encoding="utf-8")
            started = time.time()
            code = subprocess.call([python, "tools/serve_site.py", "--port", "8765"],
                                   cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} serve_site exited {code} "
                      f"after {time.time() - started:.0f}s; restarting in {RESTART_DELAY}s\n")
            log.close()
            time.sleep(RESTART_DELAY)
    finally:
        release()


if __name__ == "__main__":
    raise SystemExit(main())
