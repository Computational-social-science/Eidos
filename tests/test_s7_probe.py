"""The S7 probe's shape must stay honest: both directions scored, labels planted by construction.

A probe that only checks "did it object" rewards a model that objects to everything. These tests pin
the eight-defect / four-clean split, the scoring rule, and the fact that a clean case scored as failed
is a miss rather than a near-miss.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import probe_s7  # noqa: E402


def test_twelve_cases_eight_defective_four_clean():
    assert len(probe_s7.CASES) == 12
    defective = [c for c in probe_s7.CASES if c[1]]
    clean = [c for c in probe_s7.CASES if not c[1]]
    assert len(defective) == 8 and len(clean) == 4
    for _, planted, _ in defective:
        assert planted in {"statistics", "support", "identification", "design"}


def test_a_major_objection_counts_and_a_minor_one_does_not():
    hard, cats = probe_s7.judge({"objections": [
        {"severity": "major", "category": "statistics", "evidence_pointer": "/x"}]})
    assert hard is True and cats == "statistics"

    hard, cats = probe_s7.judge({"objections": [
        {"severity": "minor", "category": "statistics", "evidence_pointer": "/x"}]})
    assert hard is False


def test_an_empty_objection_list_is_a_clean_case():
    hard, _ = probe_s7.judge({"verdict": "PASS", "objections": []})
    assert hard is False


def test_the_planted_category_must_match_not_merely_be_present():
    """S7-03 was detected but labelled `design`; under the pointer rule that is a miss."""
    answer = {"verdict": "FAIL", "objections": [
        {"severity": "major", "category": "design", "evidence_pointer": "/x"}]}
    hard, cats = probe_s7.judge(answer)
    assert hard is True and "support" not in cats
