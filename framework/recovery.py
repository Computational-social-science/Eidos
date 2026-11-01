"""Recovery actions, planned from a diagnosis — the second half of the loop.

Detection is not recovery. The watcher measures, `framework.diagnosis` names the failure,
and this module decides whether that failure has a **known, safe action** and runs it. The
three are kept in that order on purpose:

    measure -> diagnose -> plan -> execute -> measure again

A recovery is only offered when the diagnosis maps to an action here. Anything else stays
a human decision: an unknown failure with an automatic "restart everything" is worse than
no automation, because it hides the cause behind a green light.

    python -m framework.recovery            # list what can be recovered
"""

from __future__ import annotations

import datetime
from contextlib import contextmanager
from contextvars import ContextVar
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Where the repaired service must answer before the repair counts as done.
def _msys(path: Path) -> str:
    """Give bash a path it understands: E:/x becomes /e/x.

    MSYS does not translate arguments for native programs here, and bash strips the colon
    and separators from a Windows path, which is how a launcher path became a single token
    that bash could not find. The launcher then "succeeded" without starting anything.
    """
    text = path.as_posix()
    m = re.match(r"^([A-Za-z]):/(.*)$", text)
    return "/" + m.group(1).lower() + "/" + m.group(2) if m else text


STATE = ROOT / "docs" / "status" / "recovery_state.json"
LOG = ROOT / "docs" / "status" / "recoveries.jsonl"
COOLDOWN_S = 600          # between attempts, per service
STARTUP_WINDOW_S = 240    # a launcher needs time to load a 4B model before it is "failing"
MAX_COOLDOWN_S = 3600
_ACTIVE_STATE = ContextVar("recovery_state", default=None)


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate recovery field: " + key)
        result[key] = value
    return result


def _validate_state(state: dict) -> None:
    json.dumps(state, allow_nan=False)
    if not isinstance(state, dict) or any(not isinstance(row, dict) for row in state.values()):
        raise ValueError("recovery state must map services to state rows")
    for row in state.values():
        for key in ("attempts", "failures", "streak"):
            if key in row and (type(row[key]) is not int or row[key] < 0):
                raise ValueError("invalid recovery counter: " + key)
        for key in ("last_attempt", "verified_at"):
            if key in row and (type(row[key]) not in (int, float) or row[key] < 0 or not math.isfinite(row[key])):
                raise ValueError("invalid recovery timestamp: " + key)
        for key in ("in_flight", "pending", "ok"):
            if key in row and type(row[key]) is not bool:
                raise ValueError("invalid recovery flag: " + key)
        if "attempt_id" in row and (not isinstance(row["attempt_id"], str) or not row["attempt_id"]):
            raise ValueError("invalid recovery attempt identity")


def _read_state(path: Path | None = None) -> dict:
    path = Path(path if path is not None else STATE).resolve()
    active = _ACTIVE_STATE.get()
    if active is not None and active[0] == path:
        return active[1]
    try:
        state = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
    except FileNotFoundError:
        return {}
    _validate_state(state)
    return state


def _write_state(state: dict, path: Path | None = None) -> None:
    from .artifacts import atomic_output
    path = Path(path if path is not None else STATE)
    _validate_state(state)
    text = json.dumps(state, indent=2, sort_keys=True, allow_nan=False)
    with atomic_output(path) as temporary:
        temporary.write_text(text + "\n", encoding="utf-8")


@contextmanager
def state_transaction(path: Path | None = None):
    """One state owner for automatic/manual recovery; nested notes share its rows.

    Existing invalid state is preserved and reported, never reset into a new restart
    budget. This protocol coordinates updated callers, not legacy loaded processes.
    """
    from .artifacts import output_lock
    path = Path(path if path is not None else STATE).resolve()
    active = _ACTIVE_STATE.get()
    if active is not None and active[0] == path:
        yield active[1]
        return
    with output_lock(path.parent / ("recovery-state-" + path.name), timeout=10):
        state = _read_state(path)
        token = _ACTIVE_STATE.set((path, state))
        try:
            yield state
            _write_state(state, path)
        finally:
            _ACTIVE_STATE.reset(token)


def _checkpoint_state() -> None:
    """Publish launch intent under ownership before an irreversible process start."""
    active = _ACTIVE_STATE.get()
    if active is None:
        raise RuntimeError("a recovery checkpoint requires state ownership")
    _write_state(active[1], active[0])


def guard(service: str) -> tuple[bool, str]:
    """May this service be started now, or would that be a restart loop?

    Starting a 4B model takes tens of seconds. A watcher that samples every 15 s would
    otherwise relaunch it before the first launch has finished loading — the diagnosis would
    look busy while making the fault worse. One start in flight, then an exponential cooldown.
    """
    row = _read_state().get(service) or {}
    since = time.time() - float(row.get("last_attempt") or 0)
    if row.get("in_flight") and since < max(STARTUP_WINDOW_S, verification_timeout(service)):
        return False, f"a start is in flight ({since:.0f}s ago); waiting it out"
    if row.get("failures") and since < min(COOLDOWN_S * 2 ** min(row["failures"], 3), MAX_COOLDOWN_S):
        wait = min(COOLDOWN_S * 2 ** min(row["failures"], 3), MAX_COOLDOWN_S) - since
        return False, f"cooldown after {row['failures']} failed attempt(s): {wait:.0f}s left"
    return True, ""


def _log(service: str, action: str, phase: str, ok: bool, **fields) -> dict:
    """One line per decision, in the schema watch_pipeline already writes.

    Same file, same keys (`phase`, `ok`, `error`), so an automatic repair and a manual one are
    read by the same script instead of two dialects living side by side.
    """
    # One schema, checked at the point of writing. A reader can then trust that an attempt row
    # says whether a process started and a terminal row says whether the repair held.
    if phase == "attempt" and "pid" not in fields:
        raise ValueError("an attempt row must record the pid it started")
    if phase in ("verified", "failed", "gave_up") and "outcome" not in fields:
        raise ValueError(f"a {phase} row must record its outcome")
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "service": service, "phase": phase, "action": action, "ok": bool(ok), "error": None}
    row.update({k: v for k, v in fields.items() if v is not None})
    if row.get("attempt_id") and phase in {"attempt", "verified", "failed", "gave_up"}:
        row["event_id"] = service + ":" + row["attempt_id"] + (":attempt" if phase == "attempt" else ":terminal")
    from .artifacts import atomic_output, output_lock
    path = Path(LOG).resolve()
    with output_lock(path.parent / ("recovery-log-" + path.name), timeout=10):
        try:
            previous = path.read_bytes()
        except FileNotFoundError:
            previous = b""
        if previous and not previous.endswith(b"\n"):
            raise ValueError("incomplete recovery journal; preserved")
        for line in previous.splitlines():
            event = json.loads(line, object_pairs_hook=_unique_fields)
            json.dumps(event, allow_nan=False)
            if not isinstance(event, dict):
                raise ValueError("invalid recovery journal row; preserved")
            if row.get("event_id") and event.get("event_id") == row["event_id"]:
                return event  # first observed terminal survives a failed state commit
        encoded = (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        with atomic_output(path) as temporary:
            temporary.write_bytes(previous + encoded)
    return row


def log_terminal(service: str, outcome: str, ok: bool | None = None) -> None:
    """Close an incident. `outcome` is the verdict; `ok` is derived so every row has one."""
    _log(service, "verify", "verified", (outcome == "recovered") if ok is None else ok,
         outcome=outcome)


def finish_attempt(service: str, attempt_id: str | None, healthy: bool,
                   *, path: Path | None = None, **fields) -> bool:
    """Settle the same launch once, even when manual and automatic observers overlap."""
    with state_transaction(path) as state:
        row = state.setdefault(service, {})
        if row.get("attempt_id") != attempt_id:
            return False  # a newer launch owns the service now
        if attempt_id is not None and not row.get("pending"):
            return False  # the other observer already settled this launch
        event = _log(service, "verify", "verified" if healthy else "failed", healthy,
                     outcome="recovered" if healthy else "no effect", attempt_id=attempt_id, **fields)
        healthy = event["ok"]  # replay a prior durable event if its state commit failed
        row.update(in_flight=False, pending=False, ok=healthy)
        if healthy:
            row.update(attempts=0, streak=0, failures=0, verified_at=time.time())
        else:
            row["failures"] = int(row.get("failures", 0)) + 1
        return True


def _note(service: str, **fields) -> None:
    with state_transaction() as state:
        row = state.setdefault(service, {})
        row.update(fields)


PORTS = {
    "decision_service": (8090, 8081),
    "runtime_18434": (18434,),
}

#: Substrings that identify a process as belonging to a service, so a port owner can be
#: attributed instead of merely observed.
OWNER_HINTS = {
    "decision_service": ("startlux", "decision", "uvicorn", "llama-server"),
    "runtime_18434": ("llama-server", "llamacpp"),
}


def _listener_table() -> dict[int, int] | None:
    """Read a completed Windows TCP table; missing data is not an empty table."""
    try:
        from framework.subprocesses import quiet_flags
        run = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=10, creationflags=quiet_flags(),
                             encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if run.returncode != 0:
        return None
    listeners = {}
    observed = False
    for line in (run.stdout or "").splitlines():
        parts = line.split()
        if not parts or parts[0] != "TCP":
            continue
        try:
            if len(parts) != 5:
                return None
            port = int(parts[1].rsplit(":", 1)[1])
            pid = int(parts[4])
            if not 0 <= port <= 65535 or pid < 0:
                return None
            if parts[3] not in {"LISTENING", "LISTEN", "CLOSE_WAIT", "CLOSED", "ESTABLISHED",
                                "FIN_WAIT_1", "FIN_WAIT_2", "LAST_ACK", "SYN_RECEIVED", "SYN_SENT",
                                "SYN_SEND", "TIME_WAIT", "TIMED_WAIT", "CLOSING", "DELETE_TCB", "BOUND"}:
                return None
            observed = True
            if parts[3] in {"LISTENING", "LISTEN"}:
                listeners[port] = pid
        except (ValueError, IndexError):
            return None
    return listeners if observed else None


def port_owner(port: int) -> int | None:
    """Which PID holds this listening port, if attribution is observable."""
    table = _listener_table()
    return (table.get(port) or None) if table is not None else None


def command_line(pid: int) -> str:
    """The full command line, which is what distinguishes our python from someone else's."""
    try:
        from framework.subprocesses import quiet_flags
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"],
            capture_output=True, timeout=15, encoding="utf-8", errors="replace", creationflags=quiet_flags()).stdout or ""
        return out.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def process_name(pid: int) -> str:
    try:
        from framework.subprocesses import quiet_flags
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                             capture_output=True, timeout=10, creationflags=quiet_flags(),
                             encoding="utf-8", errors="replace").stdout or ""
        first = out.strip().splitlines()[0] if out.strip() else ""
        return first.split(",")[0].strip('"') if first else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


def preflight(service: str) -> dict:
    """What already exists for this service: a live probe, the port owners, and whether the
    owner is *this* service or a stranger occupying the port."""
    hints = OWNER_HINTS.get(service, ())
    report = {"service": service, "healthy": False, "ports": {}, "conflict": False,
              "owned_by_self": False, "owners": []}
    urls = ENDPOINTS.get(service) or ((HEALTH.get(service),) if HEALTH.get(service) else ())
    if urls:
        report["answered"] = {u: _answers(u) for u in urls}
        report["healthy"] = all(report["answered"].values())
    for port in PORTS.get(service, ()):
        pid = port_owner(port)
        name = process_name(pid) if pid else ""
        cmd = command_line(pid) if pid else ""
        haystack = (name + " " + cmd).lower()
        self_owned = bool(pid) and any(h in haystack for h in hints)
        listening = True if pid else port_listening(port)
        report["ports"][port] = {"pid": pid, "name": name, "self": self_owned,
                                 "command_observed": bool(cmd), "listening": listening}
        if pid:
            report["owners"].append(pid)
            report["owned_by_self"] = report["owned_by_self"] or self_owned
            if not self_owned:
                report["conflict"] = True
    return report


def port_listening(port: int) -> bool | None:
    """A listener still exists when PID attribution is unavailable (including POSIX)."""
    if os.name == "nt":
        table = _listener_table()
        if table is not None:
            return port in table
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except ConnectionRefusedError:
        return False
    except OSError:
        return None


def _shell() -> str:
    """The POSIX shell this host actually has, not the one PATH happens to name.

    `bash` on PATH here can be WSL's, whose filesystem is not this one: it answers "no such
    file" for a path the caller can see. SHELL, when set by the harness, is git-bash.
    """
    shell = os.environ.get("SHELL", "")
    if shell and "system32" not in shell.lower() and Path(shell).is_file():
        return shell
    found = shutil.which("bash") or "bash"
    return found


#: Which endpoints must answer is declared once, in framework.services: the monitor and the
#: repair path cannot disagree about "up" if they read the same table.
try:                                    # imported as framework.recovery
    from . import services as _services
except ImportError:                     # imported flat, with framework/ itself on the path
    import services as _services

HEALTH = {name: urls[0] for name, urls in _services.ENDPOINTS.items()}
ENDPOINTS = _services.ENDPOINTS
_answers = _services.answers

#: Actions are declared by the *service* they repair, not by the symptom. One entry per
#: thing this machine can actually start; everything else is "not restartable" and says so.
ACTIONS = {
    "runtime_18434": {
        "description": "start the managed llama.cpp runtime on 127.0.0.1:18434",
        "script": ("hermes", "scripts", "start_local_runtime.py"),
        "env_root": "LOCALAPPDATA",
        "kind": "python",
    },
    # The typed-decision server is a sibling project, started by its own idempotent script
    # (llama.cpp :8081, then the decision server :8090). Without this entry the monitor could
    # only ever report decision_service = DOWN; detection without a declared action is not a
    # control loop.
    "decision_service": {
        "description": "start llama.cpp :8081 then the typed-decision server :8090",
        "script": ("decision-service", "scripts", "serve.sh"),
        "root": "repo",
        "kind": "bash",
    },
}


@dataclass
class RecoveryPlan:
    service: str
    action: str
    description: str
    available: bool
    reason: str = ""


def plan(service: str) -> RecoveryPlan:
    """Map a failing service to an action, or say precisely why there is none."""
    spec = ACTIONS.get(service)
    if spec is None:
        return RecoveryPlan(service, "none", "", False, "no recovery action is declared")
    if spec.get("root") == "repo":
        root = str(ROOT.parent)          # siblings of the framework live beside it
    else:
        root = os.environ.get(spec["env_root"], "")
        if not root:
            return RecoveryPlan(service, service, spec["description"], False,
                                f"{spec['env_root']} is not set, so the script cannot be located")
    script = Path(root) / Path(*spec["script"])
    if not script.is_file():
        return RecoveryPlan(service, service, spec["description"], False,
                            f"start script not found: {script}")
    return RecoveryPlan(service, service, spec["description"], True)


def execute(plan_: RecoveryPlan) -> dict:
    """Run a plan. Returns what happened, never raises for an expected failure."""
    with state_transaction():
        return _execute(plan_)


def _execute(plan_: RecoveryPlan) -> dict:
    if not plan_.available:
        return {"ok": False, "error": plan_.reason}
    # Ask the machine before asking the launcher: is this already alive, and is the port
    # held by this service or by a stranger? Starting a second copy of a 4B model because a
    # probe timed out is how a diagnosis makes the fault worse.
    look = preflight(plan_.service)
    if look["healthy"]:
        _note(plan_.service, in_flight=False, ok=True, failures=0)
        _log(plan_.service, plan_.action, "skipped", True, reason="already healthy")
        return {"ok": True, "skipped": True, "service": plan_.service,
                "reason": "already healthy; nothing to start", "preflight": look}
    # A port that already has a listener is not a port to start on. Five llama-server processes
    # accumulated on :18434 this way: each attempt answered "ok", each verification timed out while
    # the model loaded, and ten minutes later the next attempt started a sixth.
    held = {p: v.get("pid") or "unattributed listener"
            for p, v in (look.get("ports") or {}).items() if v.get("pid") or v.get("listening")}
    if held and not look["healthy"]:
        _log(plan_.service, plan_.action, "refused", False,
             reason="port already held; refusing to start a second instance", ports=held)
        return {"ok": False, "skipped": True, "service": plan_.service,
                "reason": "port already held by pid " + ", ".join(str(v) for v in held.values())
                          + "; waiting for it to become healthy beats starting a duplicate",
                "preflight": look}
    unknown = [p for p, row in (look.get("ports") or {}).items()
               if row.get("listening") is None and not row.get("pid")]
    if unknown:
        _log(plan_.service, plan_.action, "refused", False,
             reason="listener state unobservable", ports=unknown)
        return {"ok": False, "skipped": True, "service": plan_.service,
                "reason": "listener state unobservable; refusing an unaccounted launch", "preflight": look}
    if look["conflict"]:
        _log(plan_.service, plan_.action, "refused", False, reason="port held by another process",
             ports={p: v["pid"] for p, v in look["ports"].items() if v["pid"]})
        return {"ok": False, "skipped": True, "service": plan_.service,
                "reason": "port held by another process: " + ", ".join(
                    f"{p} pid={v['pid']} {v['name']}" for p, v in look["ports"].items() if v["pid"]),
                "preflight": look}
    if look["owned_by_self"]:
        # Half a pair is not a start in progress. If the front door answers but the engine does
        # not, the launcher must run: it is idempotent and starts only what is missing.
        row = (_read_state().get(plan_.service) or {})
        since = time.time() - float(row.get("last_attempt") or 0)
        if row.get("in_flight") and since < max(STARTUP_WINDOW_S, verification_timeout(plan_.service)):
            _log(plan_.service, plan_.action, "skipped", True,
                 reason=f"a start is in flight ({since:.0f}s ago)")
            return {"ok": True, "skipped": True, "service": plan_.service,
                    "reason": "a start is in flight; waiting it out", "preflight": look}

    allowed, why = guard(plan_.service)
    if not allowed:
        _log(plan_.service, plan_.action, "skipped", False, reason=why)
        return {"ok": False, "skipped": True, "service": plan_.service, "reason": why}
    row = _read_state().get(plan_.service) or {}
    _note(plan_.service, last_attempt=time.time(), in_flight=True, pending=True, streak=0,
          attempts=int(row.get("attempts", 0)) + 1, attempt_id=uuid.uuid4().hex)
    _checkpoint_state()  # if this fails, Popen must not run; later failures retain intent

    spec = ACTIONS[plan_.service]
    base = (ROOT.parent if spec.get("root") == "repo"
            else Path(os.environ[spec["env_root"]]))
    script = base / Path(*spec["script"])
    if spec.get("kind") == "bash":
        # A login shell so PATH matches what an operator gets: a bare `bash` from a service
        # process has a thinner environment and the launcher quietly fails.
        cmd = [_shell(), _msys(script)]
        cwd = script.parent.parent
    else:
        cmd = [sys.executable, str(script)]
        cwd = None
    # Lifetime belongs to the service supervisor. Console/group flags are separate:
    # DETACHED_PROCESS made the venv redirector create a visible console for its child.
    flags = 0
    if os.name == "nt":
        from .subprocesses import quiet_flags
        flags = quiet_flags() | subprocess.CREATE_NEW_PROCESS_GROUP
    log_dir = ROOT / "docs" / "status"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"recovery-{plan_.service}.log"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n=== " + time.strftime("%Y-%m-%d %H:%M:%S") + " " + plan_.description + "\n")
            log.flush()
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, close_fds=True,
                                    creationflags=flags or 0)
    except OSError as exc:
        _note(plan_.service, in_flight=False, pending=False, ok=False,
              failures=int((_read_state().get(plan_.service) or {}).get("failures", 0)) + 1,
              error=str(exc))
        _log(plan_.service, plan_.action, "failed", False, outcome="launch failed", error=str(exc),
             attempt_id=_read_state()[plan_.service]["attempt_id"])
        return {"ok": False, "attempted": True, "error": str(exc)}
    _log(plan_.service, plan_.action, "attempt", True, pid=proc.pid,
         attempt_id=_read_state()[plan_.service]["attempt_id"])
    return {"ok": True, "attempted": True, "pid": proc.pid, "service": plan_.service,
            "action": plan_.action, "description": plan_.description}


def verification_timeout(service: str) -> float:
    """The automatic observer and explicit verification use the same startup window."""
    return 300.0 if service == "runtime_18434" else 90.0


def verify(service: str, timeout: float | None = None, interval: float = 3.0) -> dict:
    """Wait for the boundary to answer. A restart is only a repair if the probe agrees."""
    # Loading a 4B GGUF on a busy GPU can take minutes; 90 s was short enough that a healthy start
    # was recorded as "no effect" and retried, which is how duplicates were born.
    timeout = float(timeout if timeout is not None else verification_timeout(service))
    attempt_id = (_read_state().get(service) or {}).get("attempt_id")
    urls = ENDPOINTS.get(service) or ((HEALTH.get(service),) if HEALTH.get(service) else ())
    if not urls:
        return {"verified": False, "error": f"no health endpoint declared for {service}"}
    url = urls[0]
    deadline = time.time() + timeout
    last = "no attempt"
    while time.time() < deadline:
        try:
            missing = [u for u in urls if not _answers(u)]
            if missing:
                last = "silent: " + ", ".join(missing)
            else:                                   # every endpoint, not just the front door
                    recorded = finish_attempt(service, attempt_id, True,
                        seconds=round(timeout - (deadline - time.time()), 1), url=url)
                    return {"verified": True, "url": url,
                            "recorded": recorded,
                            "seconds": round(timeout - (deadline - time.time()), 1)}
        except (urllib.error.URLError, OSError) as exc:
            last = str(exc)
        time.sleep(interval)
    recorded = finish_attempt(service, attempt_id, False, error=last[:200], waited=timeout, url=url)
    return {"verified": False, "url": url, "error": last, "waited": timeout, "recorded": recorded}


if __name__ == "__main__":
    for name in ACTIONS:
        plan_ = plan(name)
        print(f"{name:16s} {'available' if plan_.available else 'unavailable':12s} "
              f"{plan_.description}{'' if plan_.available else ' — ' + plan_.reason}")
