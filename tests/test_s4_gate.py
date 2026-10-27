"""S11: a design verdict is arithmetic, and an asserted verdict must follow from the fields.

The model scored 13/15 on structured design records and missed exactly the two comparisons
(docs/MODEL_VERDICTS.md). So the gate does not ask it: the record carries the fields, the rule decides,
and an asserted verdict that disagrees fails — whoever wrote it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.validity import ScientificValidityGate


@pytest.fixture()
def gate(tmp_path: Path) -> ScientificValidityGate:
    return ScientificValidityGate(tmp_path)


def record(**over) -> dict:
    base = {"power": 0.93, "required": 0.80, "named": 2, "adjusted": 2,
            "prereg": True, "declared": False, "verdict": "PASS"}
    base.update(over)
    return base


def test_a_verdict_consistent_with_the_fields_passes(gate):
    findings, blocked = gate._s4_verdict("C1", record())
    assert findings == [] and blocked == []


def test_a_verdict_that_contradicts_the_arithmetic_fails(gate):
    """The exact miss the model made: three confounders named, one adjusted, asserted PASS."""
    findings, blocked = gate._s4_verdict("C2", record(named=3, adjusted=1))
    assert blocked == []
    assert any("does not follow" in str(f) and "adjusted 1" in str(f) for f in findings)


def test_a_declaration_cannot_rescue_power_below_the_floor(gate):
    findings, _ = gate._s4_verdict("C3", record(power=0.74, declared=True, verdict="WEAK_PASS"))
    assert any("does not follow" in str(f) for f in findings)


def test_an_incomplete_record_blocks_rather_than_guessing(gate):
    findings, blocked = gate._s4_verdict("C4", record(adjusted=None))
    assert findings == []
    assert any("incomplete" in b for b in blocked)


def test_a_record_without_a_verdict_cannot_be_checked(gate):
    findings, blocked = gate._s4_verdict("C5", record(verdict=""))
    assert findings == [] and any("states no verdict" in b for b in blocked)


def test_a_prose_claim_is_not_adjudicated_here():
    """No fields, no verdict: prose extraction is 7/10 on unseen text and cannot gate anything."""
    fields = {"power": None, "required": 0.80, "prereg": None, "named": None,
              "adjusted": None, "declared": None}
    from framework.verifiers import extract_s4
    assert extract_s4.complete(fields) is False
