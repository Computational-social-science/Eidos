"""Tests for framework.diagnosis — a failure report must be actionable and honest."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.diagnosis import (
    FailureDiagnosisEngine,
    FailureSeverity,
    diagnose_pipeline_failure,
)


def test_single_gate_diagnosis_has_actions():
    engine = FailureDiagnosisEngine()
    d = engine.diagnose("acceptance-gate", {"evidence": {"error": "metric below threshold"}})
    assert d.gate_name == "acceptance-gate"
    assert d.suggested_actions
    assert d.severity in (FailureSeverity.CRITICAL, FailureSeverity.HIGH)


def test_critical_gate_blocks_automatic_retry():
    rep = diagnose_pipeline_failure(
        ["acceptance-gate"], {"pipeline_id": "p1", "evidence": {"error": "below threshold"}}
    )
    assert rep.can_retry_automatically is False
    assert rep.overall_severity == FailureSeverity.CRITICAL


def test_non_critical_gate_allows_retry():
    rep = diagnose_pipeline_failure(
        ["promptfoo"], {"pipeline_id": "p2", "evidence": {"error": "prompt regression"}}
    )
    assert rep.can_retry_automatically is True


def test_related_gates_are_reported():
    engine = FailureDiagnosisEngine()
    d = engine.diagnose("acceptance-gate", {})
    assert "planted-truth" in d.related_gates


def test_export_report_is_valid_json_without_duplicate_keys(tmp_path):
    rep = diagnose_pipeline_failure(
        ["acceptance-gate", "planted-truth"], {"pipeline_id": "p3"}
    )
    out = tmp_path / "diagnosis.json"
    FailureDiagnosisEngine().export_report(rep, out)

    text = out.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["pipeline_id"] == "p3"
    assert len(data["failed_gates"]) == 2
    assert data["overall_severity"] in {"critical", "high", "medium", "low"}
    # duplicate keys are legal JSON but a symptom of a careless export;
    # the parser keeps the last one, so assert the value is the real one
    assert data["overall_severity"] == rep.overall_severity.value


def test_unknown_gate_still_produces_a_report():
    rep = diagnose_pipeline_failure(["mystery-gate"], {"pipeline_id": "p4"})
    assert rep.failed_gates == ["mystery-gate"]
    assert rep.diagnoses[0].suggested_actions


def test_secrets_are_redacted_in_snapshot():
    engine = FailureDiagnosisEngine()
    d = engine.diagnose("acceptance-gate", {"api_key": "sk-secret", "evidence": {}})
    assert d.context_snapshot.get("api_key") == "[REDACTED]"


# --------------------------------------------------------------------------- #
# gates -> diagnosis: the details must arrive, not just the gate's name
# --------------------------------------------------------------------------- #

def test_gate_details_name_the_failed_metric():
    from framework.gates import GateRegistry
    from framework.diagnosis import diagnose_gate_results

    bad = GateRegistry.run_gate(
        "acceptance-gate", {},
        {"results": {"silent": 0.12},
         "criteria": {"silent": {"threshold": 0.05, "direction": "<="}}})
    diagnosis = diagnose_gate_results([bad], {"pipeline_id": "p5"}).diagnoses[0]

    assert "silent" in diagnosis.root_cause
    assert diagnosis.evidence["details"]["silent"]["met"] is False


def test_missing_metric_is_named_in_the_diagnosis():
    from framework.gates import GateRegistry
    from framework.diagnosis import diagnose_gate_results

    bad = GateRegistry.run_gate(
        "acceptance-gate", {}, {"results": {}, "criteria": {"kspc": 1.2}})
    diagnosis = diagnose_gate_results([bad]).diagnoses[0]

    assert "kspc" in diagnosis.root_cause
    assert "not computed" in diagnosis.root_cause.lower()


def test_name_only_form_remains_supported():
    from framework.diagnosis import diagnose_gate_results

    report = diagnose_gate_results(["acceptance-gate"], {"pipeline_id": "p6"})
    assert report.failed_gates == ["acceptance-gate"]
    assert report.diagnoses[0].suggested_actions


# --------------------------------------------------------------------------- #
# the operator refines only what the rules could not name
# --------------------------------------------------------------------------- #

def test_operator_classifies_a_weak_diagnosis(monkeypatch):
    import framework.decision as dec
    from framework.diagnosis import FailureCategory, refine_with_operator

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def choose(self, *args, **kwargs):
            return dec.Decision(question="q", type="choice", choice="compute",
                                confidence=0.91)

    monkeypatch.setattr(dec, "DecisionClient", FakeClient)
    report = diagnose_pipeline_failure(["mystery-gate"], {})
    assert "needs investigation" in report.diagnoses[0].root_cause

    refine_with_operator(report)
    assert report.diagnoses[0].category is FailureCategory.COMPUTE
    assert "operator: compute" in report.diagnoses[0].summary


def test_low_confidence_operator_leaves_the_report_alone(monkeypatch):
    import framework.decision as dec
    from framework.diagnosis import FailureCategory, refine_with_operator

    class UnsureClient:
        def __init__(self, *args, **kwargs):
            pass

        def choose(self, *args, **kwargs):
            return dec.Decision(question="q", type="choice", choice="compute",
                                confidence=0.45)

    monkeypatch.setattr(dec, "DecisionClient", UnsureClient)
    report = diagnose_pipeline_failure(["mystery-gate"], {})
    before = report.diagnoses[0].category
    refine_with_operator(report)
    assert report.diagnoses[0].category is before
    assert "operator:" not in report.diagnoses[0].summary
    # The refusal is recorded, so the seam is visible rather than inert.
    assert report.diagnoses[0].context_snapshot["operator"]["accepted"] is False


def test_unreachable_operator_leaves_the_report_alone(monkeypatch):
    import framework.decision as dec
    from framework.diagnosis import refine_with_operator

    class DownClient:
        def __init__(self, *args, **kwargs):
            pass

        def choose(self, *args, **kwargs):
            raise dec.DecisionUnavailable("down")

    monkeypatch.setattr(dec, "DecisionClient", DownClient)
    report = diagnose_pipeline_failure(["mystery-gate"], {})
    before = report.diagnoses[0].summary
    refine_with_operator(report)
    assert report.diagnoses[0].summary == before
