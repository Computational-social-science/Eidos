"""Sample the pipeline as a control loop, not a pass/fail report.

CYBERNETICS, CONCRETELY
    Each signal has a **reference** (setpoint), a **measurement**, and an **error**
    (reference - measurement). A signal is in ALARM when the error is on the wrong side,
    UNOBSERVABLE when nothing can be measured, and STALE when the artefact behind it has
    not been refreshed inside its window. The overall state is the worst signal, so a
    single dead service cannot be averaged away.

    Alarms are **edge-triggered**: a transition is recorded once, when the state changes,
    not once per sample. That is what makes the alarm log readable and what stops a
    flapping signal from filling it.

WHY A WATCHER AND NOT A REPORT
    A report answers "did it work when someone looked". A watcher answers "is it working
    now, and when did it stop". The second question is the one that catches a service that
    died quietly between two green runs.

    python tools/watch_pipeline.py            # one sample, appended to history
    python tools/watch_pipeline.py --loop 30  # sample every 30 s until interrupted
    python tools/watch_pipeline.py --status   # current state as JSON, no append
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import chain_states
import status_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
STATUS = ROOT / "docs" / "status"
CURRENT = STATUS / "current.json"
RECOVERY_STATE = STATUS / "recovery_state.json"
RECOVERIES = STATUS / "recoveries.jsonl"
STREAK_NEEDED = 3          # consecutive samples in ALARM before acting (~12 s at 4 s)
COOLDOWN_S = 600           # never retry the same service sooner than this
MAX_ATTEMPTS = 3           # then stop and leave it to a human
HISTORY = STATUS / "history.jsonl"
ALARMS = STATUS / "alarms.json"
FAULTS = STATUS / "faults.jsonl"
DURATIONS = STATUS / "durations.jsonl"
HISTORY_CAP = 2000
ALARM_CAP = 200


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default=None):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(type(default), type) else value
    except (OSError, json.JSONDecodeError):
        return default


def http_json(url: str, timeout: float = 2.0) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - absence is the measurement
        return 0, {"error": type(exc).__name__}


def http_status(url: str, headers: dict | None = None, timeout: float = 2.0) -> int:
    """Return the HTTP status, or 0 when nothing answers.

    401 is not absence: it proves the server is alive and enforcing auth. Treating it as
    "down" made an authenticated runtime look dead on the dashboard.
    """
    import urllib.error
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:  # noqa: BLE001 - absence is the measurement
        return 0


def age_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        stamp = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = datetime.datetime.now(datetime.timezone.utc) - stamp
    return round(delta.total_seconds() / 3600.0, 2)


def measure() -> dict:
    """One sample. Each entry: value, reference, direction, and where it came from."""
    signals: dict[str, dict] = {}

    # The decision service is a pair: the HTTP layer on 8090 and the engine it calls on 8081.
    # /health on 8090 answers even when the engine is gone, so a probe that stops there reports
    # "up" for a service whose every request returns 502 — the monitor would contradict the
    # chain audit. Both must answer.
    code, body = http_json("http://127.0.0.1:8090/health")
    engine = http_status("http://127.0.0.1:8081/health")
    up = code == 200 and body.get("status") == "ok" and engine in (200, 401)
    note = body.get("model") or body.get("error")
    if not up and code == 200 and engine not in (200, 401):
        note = "engine :8081 down"
    signals["decision_service"] = {
        "value": 1 if up else 0,
        "reference": 1, "direction": "min", "unit": "up",
        "source": "127.0.0.1:8090/health + :8081/health", "note": note}

    key = os.environ.get("HERMES_LOCAL_LLAMACPP_KEY", "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    code = http_status("http://127.0.0.1:18434/v1/models", headers)
    signals["runtime_18434"] = {
        "value": 1 if code in (200, 401) else 0, "reference": 1,
        "direction": "min", "unit": "up", "source": "127.0.0.1:18434/v1/models",
        "note": "auth required" if code == 401 else ("key unset" if code == 200 and not key else "")}

    # Services the chains call out to. Existence is enough for a binary or an installed
    # package; a wrong answer here would show green for something that cannot run.
    import importlib.util
    import shutil

    env_quarto = os.environ.get("QUARTO_BIN", "")
    # Reuse the bridge's own locator: it knows the local install even when PATH does not.
    try:
        from framework.quarto_bridge import QuartoBridge
        has_quarto = QuartoBridge({}).quarto_available
        quarto_where = "framework.quarto_bridge"
    except Exception:  # noqa: BLE001 - absence is the datum
        has_quarto = (bool(env_quarto) and Path(env_quarto).is_file()) or bool(shutil.which("quarto"))
        quarto_where = env_quarto or "PATH"
    signals["quarto"] = {"value": 1 if has_quarto else 0, "reference": 1,
                         "direction": "min", "unit": "up", "source": quarto_where,
                         "note": env_quarto or "on PATH"}
    for package in ("dvc", "mlflow"):
        signals[package] = {"value": 1 if importlib.util.find_spec(package) else 0,
                            "reference": 1, "direction": "min", "unit": "up",
                            "source": f"python -m {package}", "note": ""}

    traces = read_json(ROOT / "docs" / "traces" / "latest.json", {}) or {}
    trace_meta = traces.get("trace") or {}
    trace_id = trace_meta.get("id")
    if trace_id:
        last_id = None
        try:
            lines = DURATIONS.read_text(encoding="utf-8").splitlines()
            if lines:
                last_id = json.loads(lines[-1]).get("trace")
        except (OSError, json.JSONDecodeError):
            last_id = None
        if trace_id != last_id:
            # One row per audit, not per sample: the series is of runs, not of polls.
            STATUS.mkdir(parents=True, exist_ok=True)
            with DURATIONS.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "ts": now_iso(), "trace": trace_id,
                    "durations": {s["name"]: s.get("duration_ms")
                                  for s in traces.get("spans", [])}}) + chr(10))
    spans = traces.get("spans", []) if isinstance(traces, dict) else []
    if spans:
        failed = sum(1 for s in spans if s.get("status") in ("FAIL", "ERROR"))
        skipped = sum(1 for s in spans if s.get("status") == "SKIP")
        # The reference is zero failures, not "all passed": a SKIP is an unexercised
        # boundary, and counting it as a fault would keep the loop red for a design choice.
        signals["chains_failed"] = {"value": failed, "reference": 0,
                                    "direction": "max", "unit": "chains",
                                    "source": "docs/traces/latest.json",
                                    "note": f"{failed} failed, {skipped} skipped"}
        duration = float((traces.get("trace") or {}).get("duration_ms", 0)) / 1000.0
        signals["chains_duration"] = {"value": round(duration, 1), "reference": 180.0,
                                      "direction": "max", "unit": "s",
                                      "source": "docs/traces/latest.json", "note": ""}
        started = (traces.get("trace") or {}).get("start_ts")
        if started:
            signals["chains_age"] = {
                "value": round((time.time() - float(started)) / 3600.0, 2),
                "reference": 24.0, "direction": "max", "unit": "h",
                "source": "docs/traces/latest.json", "note": "last audit"}
    else:
        signals["chains_failed"] = {"value": None, "reference": 0, "direction": "max",
                                    "unit": "chains", "source": "docs/traces/latest.json",
                                    "note": "no trace recorded"}

    audit = read_json(ROOT / "docs" / "SELF_AUDIT.json", {}) or {}
    self_gate = ((audit.get("self_gate_s") or {}).get("status")
                 if isinstance(audit, dict) else None) or "UNKNOWN"
    signals["self_audit"] = {"value": 1 if self_gate == "PASS" else 0, "reference": 1,
                             "direction": "min", "unit": "gate S",
                             "source": "docs/SELF_AUDIT.json", "note": self_gate}

    render = read_json(ROOT / "docs" / "RENDER_CHECK.json", {}) or {}
    render_ok = bool(render.get("ok")) if isinstance(render, dict) else False
    signals["render_chain"] = {"value": 1 if render_ok else 0, "reference": 1,
                               "direction": "min", "unit": "up",
                               "source": "docs/RENDER_CHECK.json",
                               "note": (render.get("generated") or "")[:16]}
    render_age = age_hours((render.get("generated") or "")[:19] + "+00:00"
                           if render.get("generated") else None)
    if render_age is not None:
        signals["render_age"] = {"value": render_age, "reference": 24 * 7,
                                 "direction": "max", "unit": "h",
                                 "source": "docs/RENDER_CHECK.json", "note": "one host"}

    evidence = read_json(ROOT / "reference" / "operator_calibration" / "docs"
                         / "evidence.json", {}) or {}
    ev_age = age_hours(evidence.get("generated") if isinstance(evidence, dict) else None)
    if ev_age is not None:
        signals["consumer_evidence_age"] = {
            "value": ev_age, "reference": 24 * 7, "direction": "max", "unit": "h",
            "source": "reference/operator_calibration/docs/evidence.json",
            "note": "calibration measurement"}

    return signals


def classify(signal: dict) -> tuple[str, float | None]:
    value, reference = signal.get("value"), signal.get("reference")
    if value is None:
        return "UNOBSERVABLE", None
    error = float(reference) - float(value) if signal.get("direction") == "min" \
        else float(value) - float(reference)
    ok = error <= 0
    return ("OK" if ok else "ALARM"), round(error, 2)


def maybe_auto_recover(states: dict) -> dict:
    """Closed loop: sustain a fault long enough, then act once and verify the effect.

    The guard rails are the point. A single bad sample is noise; a service that stays down
    for three samples gets one attempt, no more than once per ten minutes and three times
    in total. Every attempt and its verification is appended to recoveries.jsonl, so the
    automatic action is as auditable as a manual one.
    """
    if os.environ.get("EIDOS_AUTO_RECOVER", "1") == "0":
        return states
    state = read_json(RECOVERY_STATE, {}) or {}
    now = time.time()
    changed = False
    for name, row in states.items():
        entry = state.setdefault(name, {"streak": 0, "last_attempt": 0.0,
                                        "attempts": 0, "pending": False})
        ok = row.get("state") == "OK"
        if entry.get("pending"):
            if ok:
                _append_recovery({"ts": now_iso(), "service": name, "phase": "verified",
                                  "outcome": "recovered"})
                entry.update(pending=False, attempts=0, streak=0)
                changed = True
            elif now - entry.get("last_attempt", 0) > 60:
                _append_recovery({"ts": now_iso(), "service": name, "phase": "verified",
                                  "outcome": "no effect"})
                entry.update(pending=False)
                changed = True
            continue
        if ok:
            if entry.get("streak"):
                entry["streak"] = 0
                changed = True
            continue
        entry["streak"] = int(entry.get("streak", 0)) + 1
        changed = True
        plan_row = row.get("recovery") or {}
        if (entry["streak"] >= STREAK_NEEDED and plan_row.get("available")
                and now - entry.get("last_attempt", 0) > COOLDOWN_S
                and entry.get("attempts", 0) < MAX_ATTEMPTS):
            from framework import recovery as recovery_mod
            plan = recovery_mod.plan(name)
            result = recovery_mod.execute(plan)
            entry.update(last_attempt=now, pending=True, streak=0,
                         attempts=int(entry.get("attempts", 0)) + 1)
            _append_recovery({"ts": now_iso(), "service": name, "phase": "attempt",
                              "action": plan.description, "ok": result.get("ok"),
                              "pid": result.get("pid"), "error": result.get("error")})
            row["recovery_auto"] = {"attempted": True, "result": result}
    if changed:
        STATUS.mkdir(parents=True, exist_ok=True)
        RECOVERY_STATE.write_text(json.dumps(state, indent=1) + chr(10), encoding="utf-8")
    return states


def _append_recovery(row: dict) -> None:
    STATUS.mkdir(parents=True, exist_ok=True)
    with RECOVERIES.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + chr(10))


def sample(append: bool = True) -> dict:
    signals = measure()
    states = {}
    worst = "OK"
    for name, signal in signals.items():
        state, error = classify(signal)
        states[name] = {**signal, "state": state, "error": error}
        if state == "ALARM":
            worst = "ALARM"
        elif state == "UNOBSERVABLE" and worst == "OK":
            worst = "UNOBSERVABLE"

    live = chain_states.running_age() is not None         and chain_states.running_age() < chain_states.RUNNING_TTL
    previous_chains = {}
    try:
        previous_rows = json.loads(chain_states.TIMELINE.read_text(encoding="utf-8"))
        if previous_rows:
            previous_chains = previous_rows[-1].get("states", {}) or {}
    except (OSError, json.JSONDecodeError):
        previous_chains = {}
    chain_state = chain_states.advance(previous_chains, chain_states.observed(), live)
    # A green node that has not been exercised for a day is not green: it is unobserved.
    age_h = (signals.get("chains_age") or {}).get("value")
    if age_h is not None and float(age_h) > 24.0:
        chain_state = {name: "STALE" for name in chain_state}
    previous = read_json(CURRENT, {}) or {}
    previous_states = (previous.get("signals") or {}) if isinstance(previous, dict) else {}
    alarms = read_json(ALARMS, []) or []
    if not isinstance(alarms, list):
        alarms = []
    for name, row in states.items():
        before = (previous_states.get(name) or {}).get("state")
        if before and before != row["state"]:
            alarms.append({"ts": now_iso(), "signal": name, "from": before,
                           "to": row["state"], "value": row["value"],
                           "source": row["source"]})
    new_faults = []
    for name, state in chain_state.items():
        before = previous_chains.get(name, "IDLE")
        if before != state:
            row = {"ts": now_iso(), "signal": "chain:" + name, "from": before,
                   "to": state, "value": None, "source": "docs/traces/latest.json"}
            alarms.append(row)
            if state in ("FAIL", "STALE"):
                new_faults.append(row)
    for name, row in states.items():
        if row["state"] == "ALARM":
            delta = (previous_states.get(name) or {}).get("state")
            if delta != "ALARM":
                new_faults.append({"ts": now_iso(), "signal": name, "from": delta or "UNKNOWN",
                                   "to": "ALARM", "value": row["value"],
                                   "source": row["source"]})
    if new_faults:
        STATUS.mkdir(parents=True, exist_ok=True)
        with FAULTS.open("a", encoding="utf-8") as handle:
            for row in new_faults:
                handle.write(json.dumps(row) + chr(10))
    alarms = alarms[-ALARM_CAP:]

    history = []
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding="utf-8").splitlines()[-HISTORY_CAP:]:
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if append:
        history.append({"ts": now_iso(),
                        "values": {k: v["value"] for k, v in states.items()}})
        history = history[-HISTORY_CAP:]
        STATUS.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text("".join(json.dumps(row) + chr(10) for row in history),
                           encoding="utf-8")

    timeline = chain_states.append(now_iso(), chain_state)

    # Diagnosis and recovery are the framework's own modules: the watcher measures, the
    # engine names the failure, the recovery module says whether an action exists.
    try:
        from framework.diagnosis import FailureDiagnosisEngine
        from framework import recovery as recovery_mod
        engine = FailureDiagnosisEngine()
        for name, row in states.items():
            if row["state"] == "OK":
                continue
            evidence = {"error": str(row.get("note") or "").lower() or "no answer"}
            diag = engine.diagnose("service:" + name, {"evidence": evidence})
            row["diagnosis"] = {"severity": diag.severity.value,
                                "category": diag.category.value,
                                "root_cause": diag.root_cause,
                                "actions": diag.suggested_actions}
            plan_row = recovery_mod.plan(name)
            row["recovery"] = {"available": plan_row.available,
                               "description": plan_row.description,
                               "reason": plan_row.reason}
    except Exception as exc:  # noqa: BLE001 - a broken diagnosis must not blind the monitor
        for row in states.values():
            row.setdefault("diagnosis", {"error": f"{type(exc).__name__}: {exc}"})

    states = maybe_auto_recover(states)

    derived = status_view.derive(states, chain_state)
    payload = {"ts": now_iso(), "overall": derived["overall"], "derived": derived,
               "signals": states,
               "chains": chain_state, "timeline": timeline[-60:], "live_run": live,
               "alarms": alarms[-20:], "samples": len(history),
               "history": [{k: row.get(k) for k in ("ts", "values")} for row in history[-40:]]}
    CURRENT.parent.mkdir(parents=True, exist_ok=True)
    CURRENT.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    ALARMS.write_text(json.dumps(alarms, indent=2) + chr(10), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--loop", type=float, default=0, help="seconds between samples")
    ap.add_argument("--status", action="store_true", help="print JSON, do not append history")
    args = ap.parse_args(argv)

    if args.status:
        print(json.dumps(sample(append=False), indent=2))
        return 0

    if args.loop <= 0:
        payload = sample()
        print(f"{payload['overall']:<12} " + "  ".join(
            f"{name}={'OK' if row['state'] == 'OK' else row['state']}"
            for name, row in payload["signals"].items()))
        return 0

    try:
        while True:
            payload = sample()
            stamp = payload["ts"][11:19]
            print(f"{stamp} {payload['overall']:<12} "
                  + " ".join(f"{n}:{r['state'][:4]}" for n, r in payload["signals"].items()),
                  flush=True)
            time.sleep(args.loop)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
