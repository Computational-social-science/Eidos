"""Regenerate the calibration evidence for the operator consumer.

The measurement is the one the framework already ships (`tools/decision_probe.py`); this
script only runs it, keeps the full per-item record, and adds a timestamp. Nothing is
typed by hand, so the register cannot drift from the artefact.

    python build_evidence.py        # 100 items, ~25 s against the local service
Exit codes: 0 = measured, 3 = operator unavailable (the registry maps it to SKIP).
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
PROBE = ROOT / "tools" / "decision_probe.py"


def main() -> int:
    run = subprocess.run([sys.executable, str(PROBE), "--n", "100", "--json", str(OUT)],
                         cwd=ROOT, capture_output=True, text=True, timeout=3600)
    if run.returncode != 0:
        print(run.stdout[-1500:], run.stderr[-1500:], sep="\n")
        return run.returncode
    data = json.loads(OUT.read_text(encoding="utf-8"))
    data["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    answered = [r for r in data["items"] if r["class"] == "answerable"]
    unknown = [r for r in data["items"] if r["class"] == "unanswerable"]
    print(f"answerable {len(answered)}, unanswerable {len(unknown)}, "
          f"accuracy {data['accuracy']:.3f}, abstain(unknown) {data['abstain_unanswerable']:.2f}, "
          f"abstain(answerable) {data['abstain_answerable']:.2f}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
