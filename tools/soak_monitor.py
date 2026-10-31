"""Observe monitor health for a bounded period without taking recovery actions.

PASS means all periodic observations passed for the requested duration, not continuous
availability between polls or a reboot test. A sequence regression is recorded as a
restart event and fails this strict soak even if subsequent observations recover.
Repeated sequences are allowed for max_age seconds. Interrupted runs are INCOMPLETE.
Reports keep totals and the latest 120 observations; failures remain in the totals.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RECENT_LIMIT = 120
DEFAULT_URL = "http://127.0.0.1:8765/api/status"
MAX_RESPONSE_BYTES = 2_000_000


def write_report(out: Path, report: dict) -> None:
    """Publish a complete JSON file using a closed temporary file on the same volume."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=out.parent,
                                         prefix=out.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, out)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch_status(url: str) -> object:
    """Issue only GET, without environment proxies; cap response size and request time."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, method="GET"), timeout=8) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("status response exceeds size limit")
    return json.loads(raw)


def _positive(value: float) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def _payload_errors(payload: object, max_age: float, request_seconds: float) -> list[str]:
    if not isinstance(payload, dict):
        return ["status payload is not an object"]
    errors = []
    age = payload.get("sample_age_s")
    if (isinstance(age, bool) or not isinstance(age, (int, float))
            or not math.isfinite(age) or age < 0):
        errors.append("sample age is missing or invalid")
    elif age + request_seconds > max_age:
        errors.append(f"sample age plus request time exceeds {max_age:g}s")
    if payload.get("stale") is not False:
        errors.append("sample is stale or freshness flag is missing")
    if payload.get("overall") != "OK":
        errors.append("overall is not OK")
    derived = payload.get("derived")
    if not isinstance(derived, dict):
        errors.append("derived health is missing or invalid")
    else:
        if derived.get("overall") != "OK":
            errors.append("derived overall is not OK")
        if derived.get("faults") != []:
            errors.append("derived faults are present or invalid")
    if payload.get("faults"):
        errors.append("top-level faults are present")
    if payload.get("server_error"):
        errors.append("server reports an error")
    seq = payload.get("seq")
    if type(seq) is not int or seq < 0:
        errors.append("sequence is missing or invalid")
    return errors


def observe(*, url: str, duration: float, interval: float, max_age: float, out: Path,
            fetch: Callable[[str], object] = fetch_status,
            monotonic: Callable[[], float] = time.monotonic,
            sleep: Callable[[float], None] = time.sleep) -> dict:
    """Observe immediately and at intervals, including a final sample at the deadline.

    Inject fetch/clock/sleep to test failures without touching the live monitor. Request
    time contributes to sample age. A poll gap beyond interval + max_age fails the
    observation, so suspension cannot silently count as an observed workday.
    """
    if not all(_positive(v) for v in (duration, interval, max_age)):
        raise ValueError("duration, interval and max-age must be finite and positive")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("url must be an HTTP(S) status endpoint without credentials")
    started = monotonic()
    report = {"status": "RUNNING", "url": url,
              "started_at": datetime.now(timezone.utc).isoformat(),
              "requested_duration_s": duration, "interval_s": interval, "max_age_s": max_age,
              "restart_policy": "sequence regression fails the strict soak",
              "scope": "periodic HTTP observations; no reboot or continuous-availability proof",
              "elapsed_s": 0.0, "observations": 0, "failure_count": 0,
              "sequence_advances": 0, "restart_events": 0, "recent_samples": []}
    last_seq = None
    last_advance = started
    last_observation = None
    print(f"RUNNING monitor observation for {duration:g}s; report {out}", flush=True)
    try:
        write_report(out, report)
        while True:
            request_start = monotonic()
            payload = None
            try:
                payload = fetch(url)
                now = monotonic()
                errors = _payload_errors(payload, max_age, now - request_start)
            except Exception as exc:  # a failed GET is evidence, not a reason to stop observing
                now = monotonic()
                errors = [f"request failed: {type(exc).__name__}: {str(exc)[:300]}"]
            if last_observation is not None and now - last_observation > interval + max_age:
                errors.append("observation gap exceeds interval plus max-age")
            seq = payload.get("seq") if isinstance(payload, dict) else None
            if type(seq) is int and seq >= 0:
                if last_seq is None:
                    last_advance = now
                elif seq < last_seq:
                    report["restart_events"] += 1
                    errors.append(f"sequence regressed from {last_seq} to {seq}; restart event")
                    last_advance = now
                elif seq > last_seq:
                    report["sequence_advances"] += 1
                    last_advance = now
                elif now - last_advance > max_age:
                    errors.append(f"sequence stagnant for more than {max_age:g}s")
                last_seq = seq
            else:
                seq = None
            report["observations"] += 1
            if errors:
                report["failure_count"] += 1
                print(f"FAIL observation {report['observations']}: {'; '.join(errors)}", flush=True)
            report["elapsed_s"] = max(0.0, now - started)
            report["recent_samples"].append({"elapsed_s": report["elapsed_s"],
                                               "seq": seq, "failures": errors})
            del report["recent_samples"][:-RECENT_LIMIT]
            last_observation = now
            if report["elapsed_s"] >= duration:
                report["status"] = "FAIL" if report["failure_count"] else "PASS"
                break
            write_report(out, report)
            sleep(min(interval, duration - report["elapsed_s"]))
    except KeyboardInterrupt:
        report["status"] = "INCOMPLETE"
        report["elapsed_s"] = max(0.0, monotonic() - started)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_report(out, report)
    print(f"{report['status']} monitor observation: {report['elapsed_s']:.1f}s, "
          f"{report['observations']} samples, {report['failure_count']} failed", flush=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--duration", type=float, default=86400)
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--max-age", type=float, default=45)
    parser.add_argument("--out", type=Path, default=ROOT / ".scratch/quality/soak.json")
    args = parser.parse_args(argv)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        report = observe(url=args.url, duration=args.duration, interval=args.interval,
                         max_age=args.max_age, out=args.out)
    except (OSError, ValueError) as exc:
        print(f"FAIL monitor observation: {exc}", flush=True)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}.get(report["status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
