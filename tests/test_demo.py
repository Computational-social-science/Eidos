"""The demo's numbers are measured against a closed form, not asserted.

The page renders these values directly, so a regression in the operator or in the demo
data must fail here rather than ship a nicer-looking wrong curve.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.surrogate.demo import CHECK, GRID, build_demo  # noqa: E402


def test_grid_tracks_the_analytic_fixed_point():
    data = build_demo()
    assert len(data["rows"]) == GRID == 91
    assert data["max_rel_error"] < 0.05
    assert data["median_rel_error"] < 0.01


def test_every_recovered_fixed_point_is_attracting():
    data = build_demo()
    assert all(r["rho"] is not None and r["rho"] < 1.0 for r in data["rows"])


def test_checkpoints_and_traces_are_present_for_the_page():
    data = build_demo()
    assert len(data["checkpoints"]) == len(CHECK)
    assert set(data["traces"]) == {"0.20", "0.50", "0.90"}
    for trace in data["traces"].values():
        assert len(trace) >= 2
        # a Newton trace must end closer to its fixed point than it started
        assert abs(trace[-1] - trace[-2]) < 1e-3
