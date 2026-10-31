"""Monitor ownership follows an OS lock, not an arbitrary/reused PID in JSON."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from tools import monitor_supervisor


@pytest.fixture
def lock(tmp_path, monkeypatch):
    path = tmp_path / "monitor.lock"
    monkeypatch.setattr(monitor_supervisor, "LOCK", path)
    yield path
    monitor_supervisor.release()


def test_unrelated_live_pid_does_not_block_ownership(lock):
    lock.write_text(json.dumps({"pid": os.getpid(), "since": 1}), encoding="utf-8")
    assert monitor_supervisor.acquire()


def test_unreadable_old_metadata_does_not_block_ownership(lock):
    lock.write_bytes(b"\xff\xfeobsolete")
    assert monitor_supervisor.acquire()


def test_release_without_ownership_preserves_metadata(lock):
    lock.write_text("another supervisor owns this", encoding="utf-8")
    monitor_supervisor.release()
    assert lock.read_text(encoding="utf-8") == "another supervisor owns this"


def test_process_exit_releases_exclusive_ownership(lock):
    script = (
        "from pathlib import Path; from tools import monitor_supervisor as m; "
        "import sys,os; m.LOCK=Path(sys.argv[1]); "
        "print(('ACQUIRED '+str(os.getpid())) if m.acquire() else 'BUSY', flush=True); sys.stdin.readline()"
    )
    child = subprocess.Popen([sys.executable, "-c", script, str(lock)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             cwd=Path(__file__).resolve().parents[1])
    owner=None
    try:
        acquired=child.stdout.readline().strip().split()
        assert acquired[0] == "ACQUIRED"
        owner=int(acquired[1])
        assert not monitor_supervisor.acquire()
        # Windows venv python.exe can be a launcher; the reported leaf owns the
        # lock. Killing only that launcher leaves its interpreter holding it.
        os.kill(owner,signal.SIGTERM)
        child.wait(timeout=10)
        assert monitor_supervisor.acquire()
    finally:
        if child.poll() is None:
            if owner is not None:
                try:
                    os.kill(owner,signal.SIGTERM)
                except ProcessLookupError:
                    pass
            child.kill()
        child.communicate(timeout=10)
