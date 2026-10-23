"""Regenerate docs/evidence.json for the surrogate reference study.

The numbers are produced, never typed: the grader runs the same audit the framework
ships (`tools/audit_surrogate.py`), keeps both arms, and stores the whole grid so a
reader can recompute any row.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "docs" / "evidence.json"


def main() -> int:
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "audit_surrogate.py"),
                          "--json", "--negative-test"],
                         cwd=ROOT, capture_output=True, text=True, timeout=1800)
    if run.returncode != 0:
        print(run.stdout[-800:], run.stderr[-800:], sep="\n")
        return run.returncode
    payload = json.loads(run.stdout)
    payload["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    f, c = payload["forward"], payload["control"]
    print(f"forward {f['within_5pct']}/{f['points']} within 5%, "
          f"control {c['within_5pct']}/{c['points']}, caught={payload['caught']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
