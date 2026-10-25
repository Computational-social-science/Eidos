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
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
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


def _read_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def guard(service: str) -> tuple[bool, str]:
    """May this service be started now, or would that be a restart loop?

    Starting a 4B model takes tens of seconds. A watcher that samples every 15 s would
    otherwise relaunch it before the first launch has finished loading — the diagnosis would
    look busy while making the fault worse. One start in flight, then an exponential cooldown.
    """
    row = _read_state().get(service) or {}
    since = time.time() - float(row.get("last_attempt") or 0)
    if row.get("in_flight") and since < STARTUP_WINDOW_S:
        return False, f"a start is in flight ({since:.0f}s ago); waiting it out"
    if row.get("failures") and since < min(COOLDOWN_S * 2 ** min(row["failures"], 3), MAX_COOLDOWN_S):
        wait = min(COOLDOWN_S * 2 ** min(row["failures"], 3), MAX_COOLDOWN_S) - since
        return False, f"cooldown after {row['failures']} failed attempt(s): {wait:.0f}s left"
    return True, ""


def _log(service: str, action: str, phase: str, ok: bool, **fields) -> None:
    """One line per decision, in the schema watch_pipeline already writes.

    Same file, same keys (`phase`, `ok`, `error`), so an automatic repair and a manual one are
    read by the same script instead of two dialects living side by side.
    """
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "service": service, "phase": phase, "action": action, "ok": bool(ok), "error": None}
    row.update({k: v for k, v in fields.items() if v is not None})
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _note(service: str, **fields) -> None:
    state = _read_state()
    row = state.get(service) or {}
    row.update(fields)
    state[service] = row
    _write_state(state)


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


def port_owner(port: int) -> int | None:
    """Which PID holds this listening port, if any."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=10,
                             encoding="utf-8", errors="replace").stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
            try:
                return int(parts[4])
            except ValueError:
                continue
    return None


def command_line(pid: int) -> str:
    """The full command line, which is what distinguishes our python from someone else's."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"],
            capture_output=True, timeout=15, encoding="utf-8", errors="replace").stdout or ""
        return out.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def process_name(pid: int) -> str:
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                             capture_output=True, timeout=10,
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
        report["healthy"] = all(_answers(u) for u in urls)
        report["answered"] = {u: _answers(u) for u in urls}
    for port in PORTS.get(service, ()):
        pid = port_owner(port)
        name = process_name(pid) if pid else ""
        cmd = command_line(pid) if pid else ""
        haystack = (name + " " + cmd).lower()
        self_owned = bool(pid) and any(h in haystack for h in hints)
        report["ports"][port] = {"pid": pid, "name": name, "self": self_owned,
                                 "cmd": cmd[:120]}
        if pid:
            report["owners"].append(pid)
            report["owned_by_self"] = report["owned_by_self"] or self_owned
            if not self_owned:
                report["conflict"] = True
    return report


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
        if row.get("in_flight") and since < STARTUP_WINDOW_S:
            _log(plan_.service, plan_.action, "skipped", True,
                 reason=f"a start is in flight ({since:.0f}s ago)")
            return {"ok": True, "skipped": True, "service": plan_.service,
                    "reason": "a start is in flight; waiting it out", "preflight": look}

    allowed, why = guard(plan_.service)
    if not allowed:
        _log(plan_.service, plan_.action, "skipped", False, reason=why)
        return {"ok": False, "skipped": True, "service": plan_.service, "reason": why}
    _note(plan_.service, last_attempt=time.time(), in_flight=True)

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
    # A spawned child that dies with its parent is not a recovery. On Windows the launcher is
    # detached into its own process group so the service outlives this call.
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    log_dir = ROOT / "docs" / "status"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"recovery-{plan_.service}.log"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n=== " + time.strftime("%Y-%m-%d %H:%M:%S") + " " + plan_.description + "\n")
            log.flush()
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=log, close_fds=True,
                                    creationflags=flags or 0)
    except OSError as exc:
        _note(plan_.service, in_flight=False, ok=False,
              failures=int((_read_state().get(plan_.service) or {}).get("failures", 0)) + 1,
              error=str(exc))
        return {"ok": False, "error": str(exc)}
    _log(plan_.service, plan_.action, "attempt", True, pid=proc.pid)
    return {"ok": True, "pid": proc.pid, "service": plan_.service,
            "action": plan_.action, "description": plan_.description}


def verify(service: str, timeout: float = 90.0, interval: float = 3.0) -> dict:
    """Wait for the boundary to answer. A restart is only a repair if the probe agrees."""
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
                    _note(service, in_flight=False, ok=True, failures=0, verified_at=time.time())
                    _log(service, "verify", "verified", True,
                         seconds=round(timeout - (deadline - time.time()), 1), url=url)
                    return {"verified": True, "url": url,
                            "seconds": round(timeout - (deadline - time.time()), 1)}
        except (urllib.error.URLError, OSError) as exc:
            last = str(exc)
        time.sleep(interval)
    row = (_read_state().get(service) or {})
    _note(service, in_flight=False, ok=False,
          failures=int(row.get("failures", 0)) + 1, last_error=last)
    _log(service, "verify", "failed", False, error=last[:200], waited=timeout, url=url)
    return {"verified": False, "url": url, "error": last, "waited": timeout}


if __name__ == "__main__":
    for name in ACTIONS:
        plan_ = plan(name)
        print(f"{name:16s} {'available' if plan_.available else 'unavailable':12s} "
              f"{plan_.description}{'' if plan_.available else ' — ' + plan_.reason}")
