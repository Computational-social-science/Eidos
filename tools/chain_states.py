"""Discrete state machine for the chain nodes, and the timeline that records it.

STATES
    IDLE      no run has been observed yet
    RUNNING   an audit is executing (marker file is fresh)
    PASS      the chain ran and its assertion held
    SKIP      the chain could not be exercised (absent tool or checkout)
    FAIL      the chain ran and its assertion did not hold
    STALE     the last observation is older than its window

TRANSITIONS (enforced, not decorative)
    IDLE -> RUNNING, IDLE -> PASS          first observation, with or without a live run
    RUNNING -> PASS, RUNNING -> SKIP, RUNNING -> FAIL
    PASS|SKIP|FAIL -> RUNNING              a new audit started
    PASS|SKIP|FAIL -> PASS|SKIP|FAIL       re-observation after a new run
    PASS|SKIP|FAIL|IDLE -> STALE           the window elapsed with no new run

    Every other edge is rejected: a chain cannot jump from FAIL to PASS without passing
    through RUNNING, because that would mean it was declared fixed without being executed.

WHY THE TIMELINE IS THE POINT
    A single verdict says where the system is. The timeline says how it got there: which
    node flapped, which one has been RUNNING for too long, which one has not been observed
    at all. That is the difference between a status page and a monitor.
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "status"
TRACE = ROOT / "docs" / "traces" / "latest.json"
TIMELINE = STATUS / "timeline.json"
RUNNING = STATUS / "running.json"
RUNNING_TTL = 900.0          # a marker older than this is a crashed audit, not a run
TIMELINE_CAP = 600

STATES = ("IDLE", "RUNNING", "PASS", "SKIP", "FAIL", "STALE")

TRANSITIONS = {
    "IDLE": {"RUNNING", "PASS", "SKIP", "FAIL", "STALE"},
    "RUNNING": {"PASS", "SKIP", "FAIL"},
    "PASS": {"RUNNING", "PASS", "STALE"},
    "SKIP": {"RUNNING", "SKIP", "STALE"},
    "FAIL": {"RUNNING", "FAIL", "STALE"},
    "STALE": {"RUNNING", "STALE"},
}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def can_transition(before: str, after: str) -> bool:
    if before == after:
        return True
    return after in TRANSITIONS.get(before, set())


def transition(before: str, after: str) -> str:
    if can_transition(before, after):
        return after
    # A rejected edge is not silently smoothed: the machine falls back to STALE, which is
    # the honest statement that the observation is not trustworthy.
    return "STALE"


def mark_running(label: str = "audit_chains") -> None:
    STATUS.mkdir(parents=True, exist_ok=True)
    RUNNING.write_text(json.dumps({"label": label, "started": time.time(),
                                   "started_iso": now_iso()}), encoding="utf-8")


def clear_running() -> None:
    try:
        RUNNING.unlink()
    except FileNotFoundError:
        pass


def running_age() -> float | None:
    try:
        data = json.loads(RUNNING.read_text(encoding="utf-8"))
        return time.time() - float(data.get("started", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def observed() -> dict[str, str]:
    """The state each chain was last seen in, from the newest trace."""
    try:
        doc = json.loads(TRACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    states = {}
    for span in doc.get("spans", []):
        status = span.get("status")
        states[span["name"]] = status if status in ("PASS", "SKIP", "FAIL") else "STALE"
    return states


def advance(previous: dict[str, str], observed_now: dict[str, str],
            live: bool) -> dict[str, str]:
    """One step of the machine for every chain in either snapshot."""
    out: dict[str, str] = {}
    for name in sorted(set(previous) | set(observed_now)):
        before = previous.get(name, "IDLE")
        if live and before != "RUNNING":
            out[name] = transition(before, "RUNNING")
            continue
        after = observed_now.get(name)
        out[name] = transition(before, after) if after else before
    return out


def append(timestamp: str, states: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    try:
        rows = json.loads(TIMELINE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rows = []
    if rows and rows[-1].get("states") == states:
        # Same state, later time: keep the sample but mark it as a repeat so the renderer
        # can draw a continuous block instead of a new cell boundary.
        rows.append({"ts": timestamp, "states": states, "repeat": True})
    else:
        rows.append({"ts": timestamp, "states": states})
    rows = rows[-TIMELINE_CAP:]
    STATUS.mkdir(parents=True, exist_ok=True)
    TIMELINE.write_text(json.dumps(rows, indent=0) + chr(10), encoding="utf-8")
    return rows
