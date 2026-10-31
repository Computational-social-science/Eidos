"""Record the framework's own audit state as a machine-checkable artefact.

Gate S cannot read prose: it resolves a JSON pointer and compares values. So the
framework's claims about itself need a file that is *produced*, not written by hand --
otherwise the register would be asserting numbers a human typed, which is exactly the
failure mode the gate exists to catch.

This tool runs the chain audit and the test collection, and writes `docs/SELF_AUDIT.json`.
It is intentionally the only writer of that file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "SELF_AUDIT.json"


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def collect() -> dict:
    chains = _run([sys.executable, "tools/audit_chains.py", "--json", "--ci"])
    if chains.returncode not in (0, 1):
        raise SystemExit(f"chain audit failed to run: {chains.stderr[-400:]}")
    rows = json.loads(chains.stdout)
    counts = {"total": len(rows),
              "pass": sum(1 for r in rows if r["status"] == "PASS"),
              "skip": sum(1 for r in rows if r["status"] == "SKIP"),
              "fail": sum(1 for r in rows if r["status"] in ("FAIL", "ERROR"))}

    tests = _run([sys.executable, "-m", "pytest", "--collect-only", "-q"], timeout=300)
    m = re.search(r"(\d+)\s+tests? collected", tests.stdout + tests.stderr)
    collected = int(m.group(1)) if m else None

    # Coverage is measured, not asserted: the number is recorded so a drop becomes a
    # visible drift, and the gate only refuses a drop larger than one point.
    coverage_total = None
    if _run([sys.executable, "-m", "coverage", "--version"], timeout=120).returncode == 0:
        executed = _run([sys.executable, "-m", "coverage", "run", "--source=framework", "-m", "pytest", "-q"], timeout=900)
        report = _run([sys.executable, "-m", "coverage", "report"], timeout=300)
        m2 = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", report.stdout)
        coverage_total = int(m2.group(1)) if m2 else None
    else:
        executed = _run([sys.executable, "-m", "pytest", "-q"], timeout=900)
    test_output = executed.stdout + executed.stderr
    test_counts = {}
    for label in ("passed", "failed", "skipped", "errors"):
        pattern = "errors?" if label == "errors" else label
        count = re.search(rf"(\d+)\s+{pattern}\b", test_output)
        test_counts[label] = int(count.group(1)) if count else 0

    gate = _run([sys.executable, "tools/audit_validity.py",
                 "--project", "tests/fixtures/valid_project", "--json"])
    try:
        gate_status = json.loads(gate.stdout).get("status")
    except json.JSONDecodeError:
        gate_status = "UNREADABLE"

    # The framework's own register: this may be FAIL (open objections are recorded, not
    # hidden). What must not happen is the number creeping up unnoticed, so --check
    # compares this block against the committed record.
    self_run = _run([sys.executable, "tools/audit_validity.py",
                     "--project", ".", "--document", "README.md", "--json"])
    try:
        self_data = json.loads(self_run.stdout)
    except json.JSONDecodeError:
        self_data = {"status": "UNREADABLE", "findings": []}
    self_findings = self_data.get("findings", [])
    # Parse the number the gate reports rather than counting findings: one finding can
    # name five objections.
    open_objections = 0
    for finding in self_findings:
        m2 = re.search(r"(\d+)\s+referee objection", str(finding))
        if m2:
            open_objections = int(m2.group(1))

    diagnostics = {name: (run.stdout + run.stderr)[-12000:] for name, run in
                   (("tests", executed), ("test_collection", tests), ("chains", chains),
                    ("gate_s", gate), ("self_gate_s", self_run)) if run.returncode != 0}
    return {"chains": counts, "tests_collected": collected, "tests": test_counts,
            "diagnostics": diagnostics,
            "coverage_total": coverage_total,
            "coverage_scope": "framework; unexecuted modules included; tests and tools excluded",
            "gate_s": {"fixture_status": gate_status},
            "self_gate_s": {"status": self_data.get("status"), "findings": self_findings,
                            "open_objections": open_objections},
            "exit_codes": {"chains": chains.returncode, "gate_s": gate.returncode,
                           "self_gate_s": self_run.returncode,
                           "test_collection": tests.returncode, "tests": executed.returncode}}


def measurement_failures(record: dict) -> list[str]:
    """A repeated failure is still a failure, even when the baseline contains it."""
    codes = record.get("exit_codes", {})
    failures = [f"{stage} exited {codes.get(stage)!r}"
                for stage in ("chains", "test_collection", "tests", "gate_s", "self_gate_s")
                if codes.get(stage) != 0]
    if record.get("chains", {}).get("fail", 0):
        failures.append("one or more chains failed")
    if record.get("gate_s", {}).get("fixture_status") != "PASS":
        failures.append("fixture Gate S did not pass")
    if record.get("self_gate_s", {}).get("status") != "PASS":
        failures.append("framework Gate S did not pass")
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="compare with the recorded file instead of writing it")
    args = ap.parse_args(argv)

    new = collect()
    failures = measurement_failures(new)
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        for stage, output in new.get("diagnostics", {}).items():
            print(f"--- {stage} diagnostic ---\n{output}")
        return 1
    if args.check:
        if not OUT.is_file():
            print(f"[FAIL] {OUT.name} has never been recorded")
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        # Only machine-independent fields are compared: how many chains PASS depends on
        # whether a service happens to be running, and a CI runner has none. Total, FAIL
        # count, the Gate S verdict and the open-objection count are stable everywhere.
        def pick(d):
            return {"chains.total": d.get("chains", {}).get("total"),
                    "chains.fail": d.get("chains", {}).get("fail"),
                    "gate_s.fixture_status": d.get("gate_s", {}).get("fixture_status"),
                    "self_gate_s.status": d.get("self_gate_s", {}).get("status"),
                    "self_gate_s.open_objections": d.get("self_gate_s", {}).get("open_objections")}
        def coverage(d):
            return {"coverage_total": d.get("coverage_total")}
        before, after = pick(old), pick(new)
        drift = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        old_cov, new_cov = coverage(old)["coverage_total"], coverage(new)["coverage_total"]
        if isinstance(old_cov, int) and isinstance(new_cov, int) and new_cov < old_cov - 1:
            drift["coverage_total"] = (old_cov, new_cov)
        if drift:
            for k, (before, after) in drift.items():
                print(f"DRIFT {k}: {before} -> {after}")
            return 1
        print("no drift in the self-audit record")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {new['chains']} tests={new['tests_collected']} "
          f"gate_s={new['gate_s']['fixture_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
