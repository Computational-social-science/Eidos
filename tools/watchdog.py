"""Watch the watcher: the monitor is only as honest as its own freshness.

`watch_pipeline` writes `docs/status/current.json` every few seconds. If it dies, the page
keeps serving the last sample and its "live" badge only flips to "stale" in the browser
that is open — nobody is told. This tool is the outside check:

    python tools/watchdog.py                 # exit 1 when the sample is older than 120 s
    python tools/watchdog.py --max-age 300

Schedule it (Windows):

    schtasks /create /tn "eidos-watchdog" /tr "python E:\\...\\tools\\watchdog.py" ^
             /sc minute /mo 5

It appends to `docs/status/watchdog.log` only on failure, so the file stays a record of
outages rather than a heartbeat.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs" / "status" / "current.json"
#: What the last run saw. The sequence comparison below is the only way to tell a live sampler from
#: one that keeps rewriting the same sample.
STATE = ROOT / "docs" / "status" / "watchdog_state.json"
LOG = ROOT / "docs" / "status" / "watchdog.log"


def age_seconds(ts: str) -> float | None:
    try:
        stamp = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return (datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-age", type=float, default=120.0)
    ap.add_argument("--quiet", action="store_true", help="print nothing either way")
    ap.add_argument("--verbose", action="store_true", help="print the OK line as well")
    args = ap.parse_args(argv)

    if not CURRENT.exists():
        problem = "current.json does not exist: the watcher has never run"
        age = None
    else:
        try:
            payload = json.loads(CURRENT.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problem = f"current.json is not readable: {exc}"
            age = None
        else:
            age = age_seconds(payload.get("ts", ""))
            problem = (f"the watcher has not sampled for {age:.0f}s "
                       f"(limit {args.max_age:.0f}s)") if age is not None and age > args.max_age else ""

            seq = payload.get("seq")
            if not problem and seq is not None:
                try:
                    record = json.loads(STATE.read_text(encoding="utf-8"))
                except Exception:            # noqa: BLE001 - first run, or an unreadable record
                    record = {}
                seen = int(record.get("seq") or 0)
                since = age_seconds(record.get("checked", "")) or 0.0
                if int(seq) > seen or int(seq) < seen:
                    # Advanced, or the sampler restarted and its counter began again: both are fine.
                    STATE.parent.mkdir(parents=True, exist_ok=True)
                    STATE.write_text(json.dumps({"seq": int(seq), "checked": datetime.datetime.now(
                        datetime.timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
                elif since > args.max_age:
                    problem = (f"sample seq is still {seq} after {since:.0f}s: the file is fresh but "
                               f"the content is not advancing")

    if problem:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": datetime.datetime.now(datetime.timezone.utc)
                                     .isoformat(timespec="seconds"),
                                     "problem": problem}) + "\n")
        if not args.quiet:
            print(f"FAIL  {problem}")
        return 1

    # Silent on success by design: a scheduled job that speaks every five minutes is
    # noise, and the log already records only failures.
    if args.verbose and not args.quiet:
        print(f"OK    last sample {age:.0f}s ago" if age is not None else "OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
