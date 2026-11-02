"""End-to-end render check. Skipped where Quarto is absent (the CI runner has no
TinyTeX, and a skipped chain must never look like a passing one)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(not os.environ.get("QUARTO_BIN"),
                                reason="QUARTO_BIN not set: render chain not reachable")


def test_render_produces_three_formats(tmp_path):
    out = tmp_path / "render.json"
    run = subprocess.run([sys.executable, "tools/check_render.py", "--out", str(out)],
                         cwd=ROOT, capture_output=True, text=True, timeout=900)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert run.returncode == 0, run.stdout + run.stderr
    assert payload["ok"] is True
    assert set(payload["formats"]) == {"html", "pdf", "docx"}
    for row in payload["formats"].values():
        assert row["bytes"] > 1024
