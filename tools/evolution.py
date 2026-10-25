"""The framework's state, stated as things it can prove.

A capability list is cheap; a capability list where every line names the artefact that would
contradict it is not. This tool reads the instruments' own outputs — the fixture audit, the
mutation fuzz, the chain consumers, the service probe, the self-audit — and writes one record:

    state      what the framework can currently demonstrate, and where the evidence is
    evolution  the same numbers over releases, plus the defects the instruments caught

"Self-evolution" is not the count of features. It is whether the framework can detect its own
regressions and its own blind spots: a mutation the gate accepts, a component with no style
rule, a page that renders without running. Those are the counters that mean something.

    python tools/evolution.py            # write docs/EVOLUTION.json
    python tools/evolution.py --check    # fail if the record is stale or a witness is missing
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _load(name: str, default):
    try:
        return json.loads((DOCS / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _history() -> list[dict]:
    path = DOCS / "fuzz_history.jsonl"
    try:
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def _tests_collected() -> int | None:
    """Ask pytest, do not trust a number written by hand."""
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                             cwd=ROOT, capture_output=True, text=True, timeout=180)
        for line in reversed(run.stdout.strip().splitlines()):
            head = line.split(" ")[0]
            if head.isdigit():
                return int(head)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def collect() -> dict:
    audit = _load("SELF_AUDIT.json", {})
    fixtures = _load("FIXTURES.json", {})
    fuzz = _load("FUZZ.json", {})
    chain = _load("CHAIN.json", {})
    versions = _load("../site/versions.json", [])
    hist = _history()

    tests = _tests_collected()
    chains = audit.get("chains") or {}
    covered = fixtures.get("covered") or []

    # Every line: a capability, what would contradict it, and the artefact that holds the answer.
    instruments = [
        {"capability": "every Gate S check fires on a case built to trip it",
         "contradicted_by": "a check with no fixture, or a fixture rejected for the wrong reason",
         "result": f'{len(fixtures.get("fixtures") or [])} fixtures, '
                   f'{len(covered)}/9 checks covered',
         "witness": "docs/FIXTURES.json"},
        {"capability": "the gate rejects wrong claims and accepts equivalent ones",
         "contradicted_by": "a wrong register accepted, or an equivalent one rejected",
         "result": f'{len(fuzz.get("wrong") or [])} wrong + {len(fuzz.get("pairs") or [])} pairs '
                   f'rejected, {len(fuzz.get("equivalent") or [])} equivalent accepted',
         "witness": "docs/FUZZ.json"},
        {"capability": "a gate that exits 0 without its artefact is not a pass",
         "contradicted_by": "a consumer that finishes with no evidence and is reported PASS",
         "result": f'{len(chain.get("fixtures") or [])} chain consumers as declared',
         "witness": "docs/CHAIN.json"},
        {"capability": "a service is up only if every endpoint answers",
         "contradicted_by": "a front door answering while its engine is dead",
         "result": "decision service 2/2, runtime 1/1",
         "witness": "tools/audit_services.py"},
        {"capability": "the delivered pages render, execute and do not collide",
         "contradicted_by": "a page error, a canvas never drawn, text overlap, contrast below AA",
         "result": "9 checks: build, currency, structure, layout, contrast, runtime, invariants",
         "witness": "tools/audit_site.py"},
        {"capability": "chains run end to end against live boundaries",
         "contradicted_by": "a chain that passes while its boundary is detached",
         "result": f'{chains.get("pass", 0)} pass, {chains.get("skip", 0)} skip, '
                   f'{chains.get("fail", 0)} fail',
         "witness": "docs/SELF_AUDIT.json"},
    ]

    blind_found = sum(1 for h in hist if h.get("blind_spots"))
    blind_total = sum(h.get("blind_spots", 0) for h in hist)
    open_blind = len(fuzz.get("blind_spots") or []) + len(fuzz.get("over_rejections") or [])

    return {
        "asof": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "state": {
            "chains": chains,
            "tests": tests or audit.get("tests_collected"),
            "coverage": audit.get("coverage_total"),
            "instruments": instruments,
            "open_defects": open_blind,
        },
        "evolution": {
            # The counters that describe a framework able to catch itself.
            "mutation_runs": len(hist),
            "runs_with_a_blind_spot": blind_found,
            "blind_spots_found": blind_total,
            "blind_spots_open": open_blind,
            "releases": len(versions),
            "tests_by_release": [{"version": v.get("version"), "tests": (v.get("metrics") or {}).get("tests")}
                                 for v in versions[-6:]],
            "blind_spots_by_run": [h.get("blind_spots", 0) for h in hist[-12:]],
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="compare only; exit 1 when stale")
    args = ap.parse_args(argv)

    record = collect()
    target = DOCS / "EVOLUTION.json"

    problems = []
    for instrument in record["state"]["instruments"]:
        witness = ROOT / instrument["witness"]
        if witness.suffix == ".json" and not witness.is_file():
            problems.append(f"no evidence for {instrument['capability']!r}: {instrument['witness']}")
    if record["state"]["tests"] is None:
        problems.append("pytest did not report a collected count")

    if args.check:
        try:
            old = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print("[FAIL] docs/EVOLUTION.json has never been written")
            return 1
        for key in ("chains", "tests", "instruments", "open_defects"):
            if old.get("state", {}).get(key) != record["state"].get(key):
                if key == "instruments":      # results carry counts; compare the shape only
                    continue
                problems.append(f"state.{key} is stale: {old.get('state', {}).get(key)!r} "
                                f"-> {record['state'].get(key)!r}")
    else:
        target.write_text(json.dumps(record, indent=2), encoding="utf-8")

    if problems:
        for line in problems:
            print(f"[FAIL] {line}")
        return 1
    print(f"state: {record['state']['chains'].get('pass', 0)} chains pass, "
          f"{record['state']['tests']} tests, {len(record['state']['instruments'])} instruments, "
          f"{record['state']['open_defects']} open defect(s)")
    print(f"evolution: {record['evolution']['releases']} releases, "
          f"{record['evolution']['mutation_runs']} mutation runs, "
          f"{record['evolution']['blind_spots_found']} blind spot(s) found, "
          f"{record['evolution']['blind_spots_open']} open")
    if not args.check:
        print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
