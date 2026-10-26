"""Step 3 is a contract, not a tool: a SUPPORTED claim must show its passage.

No support-checking service could be verified as accessible, so the framework defines the contract
a backend must satisfy. These tests pin it, and pin the gate behaviour when nothing has run —
BLOCKED, not PASS and not FAIL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.validity import ScientificValidityGate
from framework.verifiers import support

SOURCE = ("We report a two-sample t test. The treated group (n=30) had mean 1.2 (SD 0.4), the "
          "control group (n=30) mean 1.0 (SD 0.5); t(58) = 1.71, p = 0.09.")


def test_a_supported_verdict_needs_offsets_and_a_source():
    with pytest.raises(ValueError, match="passage"):
        support.record("C1", support.SUPPORTED, "does the source report p = 0.09?")
    with pytest.raises(ValueError, match="offsets"):
        support.record("C1", support.SUPPORTED, "q", passage={"source": "10.1/x"})


def test_a_quoted_passage_must_match_the_source_at_those_offsets(tmp_path):
    start = SOURCE.index("p = 0.09")
    with pytest.raises(ValueError, match="does not match"):
        support.record("C1", support.SUPPORTED, "q",
                       passage={"source": "10.1/x", "start": start, "end": start + 8,
                                "text": "p = 0.42"},
                       source_text=SOURCE, store=tmp_path)
    row = support.record("C1", support.SUPPORTED, "q",
                         passage={"source": "10.1/x", "start": start, "end": start + 8,
                                  "text": SOURCE[start:start + 8]},
                         source_text=SOURCE, store=tmp_path)
    assert row["verdict"] == support.SUPPORTED


def test_an_unchecked_claim_is_not_passable(tmp_path):
    allowed, reason = support.passable("C-never-checked", store=tmp_path)
    assert allowed is False and "unchecked" in reason
    assert support.load("C-never-checked", store=tmp_path)["verdict"] == support.UNCHECKED


def test_not_supported_and_unclear_are_both_refusals(tmp_path):
    for verdict in (support.NOT_SUPPORTED, support.UNCLEAR):
        support.record("C2", verdict, "q", store=tmp_path)
        allowed, reason = support.passable("C2", store=tmp_path)
        assert allowed is False and verdict in reason


def _gate(tmp_path: Path) -> ScientificValidityGate:
    return ScientificValidityGate(tmp_path)


def _artefacts(root: Path, citations=None, stats=None) -> None:
    if citations is not None:
        path = root / "artifacts" / "literature" / "proofpath.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(citations), encoding="utf-8")
    if stats is not None:
        path = root / "artifacts" / "evaluation" / "stat_recompute.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats), encoding="utf-8")


def test_missing_verifier_artefacts_block_rather_than_fail(tmp_path):
    findings, blocked = _gate(tmp_path)._verifier_findings(
        [{"id": "C1", "citations": ["10.1/x"]},
         {"id": "C2", "statistics": {"test": "t"}}])
    assert findings == []
    assert any("proofpath.json does not exist" in b for b in blocked)
    assert any("stat_recompute.json does not exist" in b for b in blocked)


def test_a_retracted_citation_is_a_failure_not_a_block(tmp_path):
    _artefacts(tmp_path, citations={"records": [
        {"reference": "10.1/x", "status": "BLOCKED", "reason": "retracted"}]})
    findings, blocked = _gate(tmp_path)._verifier_findings([{"id": "C1", "citations": ["10.1/x"]}])
    assert any("retracted" in str(f) for f in findings)
    assert blocked == []


def test_a_statistic_that_does_not_recompute_fails(tmp_path):
    _artefacts(tmp_path, stats={"verdict": "FAIL",
                                "checks": [{"id": "p", "status": "FAIL"}]})
    findings, _ = _gate(tmp_path)._verifier_findings(
        [{"id": "C2", "statistics": {"test": "t"}}])
    assert any("statistics do not recompute" in str(f) for f in findings)


def test_support_required_without_a_record_blocks_and_with_one_passes(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr(support, "STORE", root / "artifacts" / "literature" / "support")
    findings, blocked = _gate(root)._verifier_findings([{"id": "C3", "support": "required"}])
    assert findings == [] and any("support unchecked" in b for b in blocked)

    start = SOURCE.index("p = 0.09")
    support.record("C3", support.SUPPORTED, "q",
                   passage={"source": "10.1/x", "start": start, "end": start + 8,
                            "text": SOURCE[start:start + 8]}, source_text=SOURCE)
    findings, blocked = _gate(root)._verifier_findings([{"id": "C3", "support": "required"}])
    assert findings == [] and blocked == []
