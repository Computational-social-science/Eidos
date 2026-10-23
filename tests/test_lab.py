"""The interactive lab must be backed by numbers that meet the audit's tolerance."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_lab():
    spec = importlib.util.spec_from_file_location("surrogate_lab",
                                                  ROOT / "tools" / "surrogate_lab.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lab_grid_tracks_the_analytic_fixed_point():
    data = load_lab().build()
    assert len(data["rows"]) == 91
    assert data["max_rel_error"] < 0.05
    assert data["median_rel_error"] < 0.01
    # every learned fixed point must be attracting
    assert all(r["rho"] is None or r["rho"] < 1.0 for r in data["rows"])


def test_lab_page_is_self_contained():
    lab = load_lab()
    page = lab.render(lab.build())
    assert "<canvas id=\"plot\"" in page
    assert "const DATA = {" in page
    assert "fetch(" not in page          # file:// forbids it
    assert "http://" not in page and "https://" not in page


def test_lab_page_carries_the_apparatus_and_mathml():
    """A demo is a deliverable: it must state its question, its method and its limits, and
    it must typeset its formulas rather than spell them out in ASCII."""
    lab = load_lab()
    page = lab.render(lab.build())
    for section in ("Abstract", "Method", "What this does and does not show", "Table 1"):
        assert section in page
    assert page.count("<math") >= 10
    assert "__" not in page               # every token was substituted
    assert "doi:10.1038/s42256-026-01265-1" in page
