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
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "docs" / "status" / "monitor.lock"
LOG = ROOT / "docs" / "status" / "serve.log"
RESTART_DELAY = 5
_LOCK_HANDLE: BinaryIO | None = None


def _lock(handle: BinaryIO, acquire: bool) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB if acquire else fcntl.LOCK_UN)


def acquire() -> bool:
    """Hold an OS lock for the process lifetime; metadata is not proof of ownership."""
    global _LOCK_HANDLE
    if _LOCK_HANDLE is not None:
        return False
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK.open("a+b")
    try:
        _lock(handle, True)
    except OSError:
        handle.close()
        print("monitor supervisor lock is held by another process")
        return False
    try:
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "since": time.time()}).encode("utf-8"))
        handle.flush()
    except BaseException:
        handle.close()
        raise
    _LOCK_HANDLE = handle
    return True


def release() -> None:
    global _LOCK_HANDLE
    handle, _LOCK_HANDLE = _LOCK_HANDLE, None
    if handle is not None:
        try:
            _lock(handle, False)
        finally:
            handle.close()
    # Keep the inode/path: unlinking lets a racing process lock a different file.


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
