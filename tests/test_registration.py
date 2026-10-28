"""S4b: 'preregistered' is a date, not an adjective.

A register that says `design: preregistered` while carrying no registration date has asserted the one
thing that cannot be checked. These four cases pin the helper, because the full gate has many other
reasons to fail and a passing run would not isolate this one.
"""

import json
from pathlib import Path

import pytest

from framework.validity import ScientificValidityGate


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "analysis").mkdir()
    (tmp_path / "docs" / "evidence.json").write_text(
        json.dumps({"recorded_at": "2026-10-20T10:00:00+00:00", "value": 1.0}), encoding="utf-8")
    return tmp_path


def _claim() -> dict:
    return {"id": "C1", "evidence": {"file": "docs/evidence.json", "pointer": "/value", "value": 1.0}}


def _gate(project: Path) -> ScientificValidityGate:
    return ScientificValidityGate(project)


def test_a_missing_registration_date_is_a_finding(project):
    findings = _gate(project)._registration(_claim(), "C1", {"claims": [_claim()]})
    assert findings and "asserted, not evidenced" in str(findings[0])


def test_a_registration_after_the_evidence_is_a_finding(project):
    register = {"registered_at": "2026-10-21T00:00:00+00:00"}
    findings = _gate(project)._registration(_claim(), "C1", register)
    assert findings and "chosen after the result" in str(findings[0])


def test_a_registration_before_the_evidence_is_clean(project):
    register = {"registered_at": "2026-10-19T00:00:00+00:00"}
    assert _gate(project)._registration(_claim(), "C1", register) == []


def test_an_unreadable_date_is_treated_as_missing(project):
    findings = _gate(project)._registration(_claim(), "C1", {"registered_at": "last Tuesday"})
    assert findings and "asserted, not evidenced" in str(findings[0])
