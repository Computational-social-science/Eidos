"""The probe must contain cases a power-only reader would get wrong, or it proves nothing.

A fixture set where every label follows from the headline number measures whether the model can read
a number. These tests assert that four cases are decided by a qualification instead — absent
pre-registration, an unadjusted confounder, an undeclared shortfall, a power below the 0.75 floor —
so a model that tracks only power scores 11/15 by construction and 0.90 is a real bar.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import probe_s4  # noqa: E402


def power_only_label(case: dict) -> str:
    if case["power"] is None or case["power"] < 0.75:
        return "FAIL"
    return "PASS" if case["power"] >= 0.80 else "WEAK_PASS"


def test_fifteen_labelled_cases():
    assert len(probe_s4.CASES) >= 15
    assert len({c["id"] for c in probe_s4.CASES}) == len(probe_s4.CASES)


def test_the_labels_follow_the_documented_rule():
    assert probe_s4.label(dict(power=None, prereg=True, named=0, adjusted=0, declared=False)) == "FAIL"
    assert probe_s4.label(dict(power=0.86, prereg=True, named=3, adjusted=1, declared=False)) == "FAIL"
    assert probe_s4.label(dict(power=0.78, prereg=True, named=1, adjusted=1, declared=True)) == "WEAK_PASS"
    assert probe_s4.label(dict(power=0.78, prereg=True, named=1, adjusted=1, declared=False)) == "FAIL"
    assert probe_s4.label(dict(power=0.74, prereg=True, named=1, adjusted=1, declared=True)) == "FAIL"
    assert probe_s4.label(dict(power=0.86, prereg=False, named=1, adjusted=1, declared=False)) == "WEAK_PASS"
    assert probe_s4.label(dict(power=0.93, prereg=True, named=2, adjusted=2, declared=False)) == "PASS"


def test_three_cases_are_decided_by_a_qualification_not_by_power():
    discriminating = [c["id"] for c in probe_s4.CASES
                      if probe_s4.label(c) != power_only_label(c)]
    assert discriminating == ["s4-04", "s4-06", "s4-07"]


def test_a_declaration_cannot_rescue_power_below_the_floor():
    """s4-08 is the boundary: 0.74 with a declaration is still FAIL, not WEAK_PASS."""
    case = dict(power=0.74, prereg=True, named=1, adjusted=1, declared=True)
    assert probe_s4.label(case) == "FAIL"
    assert power_only_label(case) == "FAIL"      # the floor is a power rule too
    assert probe_s4.label(dict(case, power=0.75)) == "WEAK_PASS"
