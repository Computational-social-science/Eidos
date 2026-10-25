"""Third act: a gate that exits 0 and produces nothing must not count as a pass.

The registry declares `expects: [docs/evidence.json, docs/results.html]`. This script builds a
copy of the project whose gate command does nothing, registers it, runs it, and expects FAIL.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in (HERE, *HERE.parents) if (p / "framework" / "project.py").is_file())


def main() -> int:
    tmp = ROOT / "docs" / "status" / "_vacuous_demo"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    (tmp / "project.yaml").write_text(
        "name: vacuous_demo\nroot: .\n"
        'gate_command: ["python", "-c", "pass"]\n'
        "expects:\n  - docs/evidence.json\n", encoding="utf-8")
    registry = ROOT / "projects" / "vacuous_demo"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "project.yaml").write_text(
        (tmp / "project.yaml").read_text(encoding="utf-8").replace("root: .", f"root: {tmp.as_posix()}"),
        encoding="utf-8")
    try:
        run = subprocess.run([sys.executable, "-m", "framework.project", "check", "vacuous_demo"],
                             cwd=ROOT, capture_output=True, text=True)
        print(run.stdout.strip()[:400])
        rejected = "FAIL" in run.stdout and "declared output missing" in run.stdout
        print(f"\n{'[OK]' if rejected else '[FAIL]'} the vacuous pass was "
              f"{'refused' if rejected else 'accepted — that is a defect'}")
        return 0 if rejected else 1
    finally:
        shutil.rmtree(registry, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
