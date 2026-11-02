"""Chain-level consumers: what happens outside Gate S.

Gate S judges a register. The chain also has to survive a gate command that fails, a gate that
exits 0 without producing the artefact it promised, and a gate whose binary does not exist.
Each registered project below declares what it expects; this audit runs them and compares.

    python tools/audit_chain_fixtures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.project import load_project, run_command  # noqa: E402

EXPECTED = {
    "chain_ok": "PASS",
    "chain_cmd_fails": "FAIL",
    "chain_no_output": "FAIL",
    "chain_tool_missing": "SKIP",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    rows, problems = [], []
    for name, want in EXPECTED.items():
        spec = load_project(ROOT / "projects" / name / "project.yaml")
        run = run_command(spec, "gate", timeout=120)
        ok = run.status == want
        rows.append({"project": name, "expected": want, "status": run.status, "ok": ok})
        print(f"{name:<22} expect {want:<5} got {run.status:<5} {'ok' if ok else 'WRONG'}")
        if args.verbose or not ok:
            tail = (run.stderr_tail or run.stdout_tail or "").strip().splitlines()[-2:]
            for line in tail:
                print(f"    {line[:110]}")
        if not ok:
            problems.append(f"{name}: expected {want}, got {run.status}")

    (ROOT / "docs" / "CHAIN.json").write_text(
        json.dumps({"fixtures": rows, "ok": not problems}, indent=2), encoding="utf-8")

    print()
    if problems:
        for line in problems:
            print(f"[FAIL] {line}")
        return 1
    print(f"[OK] {len(rows)} chain consumers behave as declared "
          "(a vacuous pass and a missing tool are both refused)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
