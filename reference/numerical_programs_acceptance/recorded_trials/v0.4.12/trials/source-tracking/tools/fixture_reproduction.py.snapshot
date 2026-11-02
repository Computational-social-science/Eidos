"""Execute the controlled S12 stub in a disposable gate-fixture copy.

This is test-fixture preparation, never migration of a research receipt. The
historical fixture JSON supplies the stub value; it does not supply a verdict.
The original reference tree is preserved. Each copy gets its own executed,
source-bound receipt so paths, interpreter and implementation are current.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from framework import reproduction


def prepare(root: Path) -> None:
    old = reproduction.load("fixture-reproducible", root / "artifacts/reproduction")
    if old is None:
        return  # Other S1-S11 fixtures need no reproduction control.
    value = old["observed"]
    reproduction.compare(0.927, value, 1e-3)
    folder = root / ".fixture-reproduction"
    folder.mkdir()
    worker = folder / "worker.py"
    worker.write_text(
        "print(" + repr(json.dumps({"value": value})) + ")\n", encoding="utf-8"
    )
    spec = {
        "paper": "fixture-reproducible",
        "tool": "controlled scalar stub",
        "command": [sys.executable, str(worker)],
        "expected": 0.927,
        "registered_at": "2026-10-26T00:00:00+00:00",
        "seed": None,
        "seed_reason": "deterministic gate-fixture stub",
        "data_version": "controlled-fixture-v2",
        "config_version": "S12-v2",
    }
    source = folder / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    record = reproduction.run_spec(spec, cwd=root, source_file=source)
    if record["verdict"] == reproduction.UNRUN:
        raise RuntimeError("controlled reproduction fixture did not execute")
    reproduction.write(record, root / "artifacts/reproduction")
