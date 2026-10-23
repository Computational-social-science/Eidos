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
import sys
import time
import urllib.request
from pathlib import Path

import chain_states

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
STATUS = ROOT / "docs" / "status"
CURRENT = STATUS / "current.json"
HISTORY = STATUS / "history.jsonl"
ALARMS = STATUS / "alarms.json"
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

    code, body = http_json("http://127.0.0.1:8090/health")
    signals["decision_service"] = {
        "value": 1 if code == 200 and body.get("status") == "ok" else 0,
        "reference": 1, "direction": "min", "unit": "up",
        "source": "127.0.0.1:8090/health", "note": body.get("model") or body.get("error")}

    code, _ = http_json("http://127.0.0.1:18434/v1/models")
    signals["runtime_18434"] = {"value": 1 if code == 200 else 0, "reference": 1,
                                "direction": "min", "unit": "up",
                                "source": "127.0.0.1:18434/v1/models", "note": ""}

    traces = read_json(ROOT / "docs" / "traces" / "latest.json", {}) or {}
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
    for name, state in chain_state.items():
        before = previous_chains.get(name, "IDLE")
        if before != state:
            alarms.append({"ts": now_iso(), "signal": "chain:" + name, "from": before,
                           "to": state, "value": None, "source": "docs/traces/latest.json"})
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

    payload = {"ts": now_iso(), "overall": worst, "signals": states,
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
