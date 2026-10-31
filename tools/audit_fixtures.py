"""Does every gate check actually fire, for the reason it claims?

A checklist that has never rejected anything is a claim about the checklist, not evidence of it.
Each fixture under reference/fixtures is a finished project that is wrong in exactly one way.
The audit requires two things of every rejection: the gate must FAIL, and the *check that fires*
must be the one the fixture was built to trip. A fixture that fails for an unrelated reason is a
broken fixture, not a passing control.

    python tools/audit_fixtures.py

Exit 0 means: S1-S12 each have a fixture that trips them, the clean fixture passes, and no
fixture fails for a reason other than the one it was built for.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.validity import ScientificValidityGate, CHECK_IDS  # noqa: E402

FIXTURES = ROOT / "reference" / "fixtures"

#: fixture -> (expected verdict, the check that must fire). `None` means no finding at all.
EXPECTED = {
    "clean": ("PASS", None),
    "s1_no_claims": ("FAIL", "S1"),
    "s2_span_gone": ("FAIL", "S2"),
    "s3_pointer_broken": ("FAIL", "S3"),
    "s4_unearned": ("FAIL", "S4"),
    "s5_scope_hole": ("FAIL", "S5"),
    "s6_no_power": ("FAIL", "S6"),
    "s7_no_referee": ("FAIL", "S7"),
    "s8_formal_lie": ("FAIL", "S8"),
    "s9_prose_number": ("FAIL", "S9"),
    "s10_statistics_rejected": ("FAIL", "S10"),
    "s11_wrong_verdict": ("FAIL", "S11"),
    "s12_mismatch": ("FAIL", "S12"),
}


def run_one(name: str) -> tuple[str, set[str], list[str]]:
    root = FIXTURES / name
    gate = ScientificValidityGate(root, register=root / "analysis" / "CLAIMS.yaml",
                                  document=root / "docs" / "REPORT.md")
    result = gate.run()
    verdict = "PASS" if result.passed else "FAIL"
    details = getattr(result, "details", {}) or {}
    findings = details.get("findings") or []
    checks = {f"S{n}" for f in findings for n in re.findall(r"\[S(\d+)\]", str(f))}
    return verdict, checks, [str(f) for f in findings]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="verify every gate check has a fixture")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    problems: list[str] = []
    covered: set[str] = set()
    record: list[dict] = []
    print(f"{'fixture':<18} {'expect':<7} {'actual':<7} {'fired':<10} verdict")
    print("-" * 58)
    for name, (want_verdict, want_check) in EXPECTED.items():
        if not (FIXTURES / name).is_dir():
            problems.append(f"{name}: fixture directory is missing")
            print(f"{name:<18} {want_verdict:<7} {'—':<7} {'—':<10} MISSING")
            continue
        verdict, checks, findings = run_one(name)
        good = verdict == want_verdict and checks == ({want_check} if want_check else set())
        covered |= checks
        record.append({"fixture": name, "expected": want_verdict, "actual": verdict,
                       "checks": sorted(checks), "ok": good})
        print(f"{name:<18} {want_verdict:<7} {verdict:<7} "
              f"{','.join(sorted(checks)) or '—':<10} {'ok' if good else 'WRONG'}")
        if not good:
            problems.append(f"{name}: expected {want_verdict} on {want_check or 'no check'}, "
                            f"got {verdict} on {sorted(checks) or 'nothing'}")
            if args.verbose:
                for finding in findings[:4]:
                    print(f"    {finding}")

    missing = set(CHECK_IDS) - covered
    if missing:
        problems.append(f"no fixture trips {', '.join(sorted(missing))}")

    # A machine record: the page renders this table, so the showcase and the test are one
    # artefact rather than two that can drift.
    (ROOT / "docs" / "FIXTURES.json").write_text(
        json.dumps({"fixtures": record, "covered": sorted(covered), "required_checks": list(CHECK_IDS), "ok": not problems},
                   indent=2), encoding="utf-8")

    print()
    if problems:
        for line in problems:
            print(f"[FAIL] {line}")
        return 1
    print(f"[OK] {len(EXPECTED)} fixtures: S1-S12 each trip once, the clean control passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
