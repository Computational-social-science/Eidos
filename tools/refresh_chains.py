"""Run the chains that are due, and say so.

The monitor can only show what something has recently measured. Until this exists, "chain state"
means "the last time a human ran the audit", which is not monitoring.

Every call:

1. reads docs/status/chains.json — each chain's own last run
2. runs the chains whose age exceeds their tier (light: 10 min, heavy: 2 h)
3. writes docs/status/scheduler.json — a heartbeat with what it ran and what failed

The heartbeat is the part that matters: if this stops being called, the sampler sees the
heartbeat go stale and raises a fault. A scheduler nobody watches is a single point of silent
failure.

    python tools/refresh_chains.py            # run what is due
    python tools/refresh_chains.py --force    # run everything now
    python tools/refresh_chains.py --dry-run  # print the plan
    python tools/refresh_chains.py --report   # heartbeat and due-ness, run nothing
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
STATUS = ROOT / "docs" / "status"
CHAINS = STATUS / "chains.json"
HEARTBEAT = STATUS / "scheduler.json"

#: Minutes between runs, per chain. Anything not listed is light.
TIERS = {"tracking": 120, "quarto": 120, "decision": 120}
LIGHT_MIN = 10


def now() -> float:
    return time.time()


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def due(report: dict, interval_min: int) -> tuple[list[str], dict[str, float]]:
    """Which chains are older than their tier, and how old each one is."""
    chains = report.get("chains") or {}
    ages = {}
    for name, row in chains.items():
        ran = float(row.get("ts") or 0)
        ages[name] = max(0.0, (now() - ran) / 60.0) if ran else float("inf")
    stale = sorted(name for name, age in ages.items()
                   if age >= TIERS.get(name, interval_min))
    return stale, ages


def run_chain(name: str) -> dict:
    started = now()
    from tools.bounded_process import run_tree
    try:
        proc = run_tree([sys.executable, "tools/audit_chains.py", "--only", name, '--json'],
                        cwd=ROOT, timeout=900)
    except subprocess.TimeoutExpired:
        return {'chain':name,'exit':124,'status':'ERROR','ms':round((now()-started)*1000,1),
                'tail':['chain timed out after 900s; owned process tree terminated']}
    try:
        rows=json.loads(proc.stdout)
        if (not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict)
                or rows[0].get('chain')!=name or rows[0].get('status') not in {'PASS','SKIP','FAIL','ERROR'}):
            raise ValueError('expected exactly one named chain verdict')
        status=rows[0]['status']
        if (proc.returncode==0)!=(status in {'PASS','SKIP'}):
            raise ValueError('chain exit and structured verdict disagree')
        tail=[str(rows[0].get('detail',''))[-1000:]]
        code=proc.returncode
    except (ValueError,TypeError):
        status='ERROR';code=proc.returncode or 2
        tail=['invalid or contradictory structured chain result',
              (proc.stderr or proc.stdout or '')[-1000:]]
    return {'chain':name,'exit':code,'status':status,'ms':round((now()-started)*1000,1),'tail':tail}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="run every registered chain")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true", help="print state, run nothing")
    ap.add_argument("--interval", type=int, default=LIGHT_MIN)
    ap.add_argument("--loop", action="store_true",
                    help="keep ticking every --interval minutes (the scheduler itself)")
    args = ap.parse_args(argv)
    if args.interval<1:
        ap.error('--interval must be positive')
    if args.loop and (args.report or args.dry_run):
        ap.error('--loop cannot be combined with --report or --dry-run')

    from framework.artifacts import output_lock
    with ExitStack() as ownership:
        if not (args.report or args.dry_run):
            kind='scheduler-loop' if args.loop else 'scheduler-tick'
            try:
                ownership.enter_context(output_lock(STATUS/kind,timeout=0))
            except TimeoutError:
                print(f'{kind} is already owned; no duplicate work started')
                return 0 if args.loop else 75
        return _dispatch(args)


def _dispatch(args) -> int:

    if args.loop:
        # No elevation is available on this host for a scheduled task, and an agent-based cron
        # would spend tokens on a heartbeat. A supervised loop is the honest substitute: it
        # writes the same heartbeat, and the sampler raises a fault when the loop stops.
        while True:
            try:
                main(["--interval", str(args.interval)] + (["--force"] if args.force else []))
            except Exception as exc:  # noqa: BLE001 - the loop must survive one bad tick
                print(f"tick failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(max(60, args.interval * 60))

    report = load(CHAINS, {})
    if not report.get("chains"):
        print("[FAIL] docs/status/chains.json is empty; run tools/audit_chains.py once")
        return 1

    stale, ages = due(report, args.interval)
    if args.force:
        stale = sorted(report["chains"])

    if args.report or args.dry_run:
        for name in sorted(report["chains"]):
            tier = TIERS.get(name, args.interval)
            print(f"{name:<28} {ages[name]:>7.1f} min  interval {tier:>3} min  "
                  f"{'DUE' if name in stale else 'fresh'}")
        print(f"\n{len(stale)} due of {len(report['chains'])}")
        return 0

    ran, failed = [], []
    for name in stale:
        result = run_chain(name)
        ran.append(result)
        if result["exit"] != 0:
            failed.append(name)
        print(f"{result['status']}  {name:<28} "
              f"{result['ms']:>8.0f} ms")

    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    beat = load(HEARTBEAT, {})
    beat = {
        "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "epoch": now(),
        "interval_min": args.interval,
        "due": stale,
        "ran": ran,
        "failed": failed,
        "ticks": int(beat.get("ticks") or 0) + 1,
        "failures_total": int(beat.get("failures_total") or 0) + len(failed),
        "pid": os.getpid(), "python": sys.executable,
        "python_version": sys.version.split()[0],
    }
    from framework.artifacts import atomic_output
    with atomic_output(HEARTBEAT) as temporary:
        temporary.write_text(json.dumps(beat, indent=2), encoding="utf-8")

    if not stale:
        print("nothing due; heartbeat refreshed")
    print(f"heartbeat: {beat['ts']} · tick {beat['ticks']} · {len(failed)} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
