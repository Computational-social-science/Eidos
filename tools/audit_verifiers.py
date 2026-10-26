"""Run the deterministic verifiers: citations (proofpath) and statistics (the kernel).

    python tools/audit_verifiers.py --stats tests/fixtures/verifiers/stats_good.json
    python tools/audit_verifiers.py --citations refs.txt [--offline]
    python tools/audit_verifiers.py --fixtures        # every fixture must land on its expectation

Exit code 1 means a verifier said no — which is the only useful reason for a gate to exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.verifiers import citations, stats  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "verifiers"


def _run_stats(path: Path) -> int:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    result = stats.check(spec)
    bad = [c for c in result["checks"] if c["status"] != "PASS"]
    print(f"{'PASS' if result['verdict'] == 'PASS' else 'FAIL'}  statistics {Path(path).name}")
    for check in result["checks"]:
        detail = (f"reported {check['reported']} vs recomputed {check['recomputed']:.6g}"
                  if "recomputed" in check else "")
        print(f"  {check['status']:4s} {check['id']:6s} {detail}")
    for check in bad:
        print(f"  reason: {check.get('detail') or check.get('allowed')}")
    print(f"  artefact: {result['artefact']}")
    return 0 if result["verdict"] == "PASS" else 1


def _run_citations(path: Path, offline: bool) -> int:
    refs = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]
    result = citations.check(refs, network=not offline)
    print(f"{'PASS' if result['verdict'] == 'PASS' else 'BLOCKED'}  citations "
          f"({result['verified']}/{result['n']} verified)")
    for record in result["records"]:
        print(f"  {record['status']:18s} {record['reference'][:60]:60s} "
              f"{record.get('reason') or record.get('title') or ''}")
    print(f"  artefact: {result['artefact']}")
    return 0 if result["verdict"] == "PASS" else 1


def _run_fixtures() -> int:
    """Every fixture states its expected verdict; a fixture that disagrees is a broken verifier."""
    expectations = {"stats_good": "PASS", "stats_bad_p": "FAIL", "stats_bad_d": "FAIL"}
    failures = 0
    for name, expected in expectations.items():
        spec = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        result = stats.recompute(spec)
        ok = result["verdict"] == expected
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {result['verdict']} (expected {expected})")
        failures += 0 if ok else 1

    refs = [line.strip() for line in (FIXTURES / "refs.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    result = citations.check(refs, network=False, cache_path=FIXTURES / "cache.json",
                             out=ROOT / "docs" / "status" / "_citation_fixtures.json")
    expected_status = ["VERIFIED", "BLOCKED", "BLOCKED"]
    got = [r["status"] for r in result["records"]]
    ok = got == expected_status and result["verdict"] == "BLOCKED"
    print(f"  {'PASS' if ok else 'FAIL'}  citations fixture: {got} (expected {expected_status})")
    failures += 0 if ok else 1
    return 1 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stats", type=Path, help="spec file to recompute")
    ap.add_argument("--citations", type=Path, help="one reference per line")
    ap.add_argument("--offline", action="store_true", help="use the cache only")
    ap.add_argument("--fixtures", action="store_true", help="run every fixture against its expectation")
    args = ap.parse_args(argv)
    if args.fixtures:
        return _run_fixtures()
    if args.stats:
        return _run_stats(args.stats)
    if args.citations:
        return _run_citations(args.citations, args.offline)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
