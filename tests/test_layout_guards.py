"""The layout audit must catch what a bounding-box intersection cannot.

Two failures shipped to the browser and were found by looking: a header band painted over the
column labels, and a footer that ran past its band. Both are now machine-checkable, and these
tests prove the checks fire by building a page that contains each defect.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "dashboard.html"


def _run_defective(tmp_path: Path, injected: str) -> subprocess.CompletedProcess:
    source = PAGE.read_text(encoding="utf-8")
    target = tmp_path / "defective.html"
    target.write_text(source.replace("</svg>", injected + "</svg>", 1), encoding="utf-8")
    return subprocess.run([sys.executable, "tools/audit_layout.py", "--widths", "1280",
                           "--page", str(target)], cwd=ROOT, capture_output=True, text=True,
                          timeout=300)


def test_an_opaque_rect_over_a_label_is_reported(tmp_path):
    run = _run_defective(tmp_path, "<rect x='300' y='22' width='420' height='16' fill='#12151a'/>")
    assert run.returncode == 1, run.stdout + run.stderr
    assert "painted over by a rect" in run.stdout


def test_an_html_overlay_is_reported(tmp_path):
    overlay = ("<div style='position:absolute;top:60px;left:20px;width:900px;height:40px;"
               "background:#12151a;z-index:99'></div>")
    source = PAGE.read_text(encoding="utf-8")
    target = tmp_path / "overlay.html"
    target.write_text(source.replace("</body>", overlay + "</body>"), encoding="utf-8")
    run = subprocess.run([sys.executable, "tools/audit_layout.py", "--widths", "1280",
                          "--page", str(target)], cwd=ROOT, capture_output=True, text=True,
                         timeout=300)
    assert run.returncode == 1, run.stdout + run.stderr
    assert "is covered by" in run.stdout


def test_text_outside_the_viewbox_is_reported(tmp_path):
    run = _run_defective(tmp_path, "<text x='5000' y='20' font-size='10' fill='#fff'>far out</text>")
    assert run.returncode == 1, run.stdout + run.stderr
    assert "falls outside its viewBox" in run.stdout
