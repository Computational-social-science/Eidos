"""An unfinished or stale training run must never be promoted into evidence."""
import copy
import json
from pathlib import Path
import pytest


def test_empty_training_evidence_is_rejected():
    from reference.softmax_training.validate import validate_report
    assert validate_report({}, {}, check_files=False)


def test_running_training_evidence_is_not_a_completed_result():
    from reference.softmax_training.validate import validate_report
    errors = validate_report({"status": "RUNNING", "runs": []}, {"seeds": [0, 1, 2]}, check_files=False)
    assert any("COMPLETE" in error for error in errors)
    assert any("seeds" in error for error in errors)


def test_empty_backend_case_list_cannot_be_qualified():
    from reference.softmax_training.validate import qualified_backend
    assert not qualified_backend({"verdict": "PASS", "cases": [], "negative_controls": []})
    assert not qualified_backend({"verdict": "PASS", "cases": [{"verdict": "PASS"}] * 12,
                                  "negative_controls": []})


def test_duplicate_backend_cases_cannot_replace_the_declared_inventory():
    from reference.softmax_training.validate import qualified_backend
    assert not qualified_backend({"verdict": "PASS", "cases": [{"verdict": "PASS"}] * 12,
                                  "negative_controls": [{"rejected": True}] * 2})


@pytest.mark.parametrize("mutation", ["protocol", "runtime", "data", "artifacts", "states", "negative_drift", "accuracy"])
def test_training_gate_rejects_corrupted_record(mutation):
    from reference.softmax_training.validate import validate_report
    here = Path(__file__).resolve().parents[1] / "reference/softmax_training"
    report = json.loads((here / "docs/evidence.json").read_text(encoding="utf-8"))
    protocol = json.loads((here / "protocol.json").read_text(encoding="utf-8"))
    report = copy.deepcopy(report)
    if mutation == "protocol": report["protocol"] = {"distillation_steps": 1}
    if mutation == "runtime": report["runtime"]["dtype"] = "float64"
    if mutation == "data":
        for run in report["runs"]: run.pop("data_sha256", None)
    if mutation == "artifacts": report["artifacts"] = {}
    if mutation == "states":
        for run in report["runs"]:
            run.pop("teacher_state_sha256", None)
            for variant in run["variants"].values():
                variant.pop("initial_state_sha256", None); variant.pop("final_state_sha256", None)
    if mutation == "negative_drift": report["runs"][0]["variants"]["standard"]["checkpoints"][-1]["parameter_displacement_l2"] = -1
    if mutation == "accuracy": report["runs"][0]["variants"]["standard"]["checkpoints"][-1]["test_accuracy"] = 1.01
    assert validate_report(report, protocol, check_files=False), mutation


def test_completed_evidence_matches_sources_splits_and_saved_weights():
    from reference.softmax_training.validate import validate_report
    here = Path(__file__).resolve().parents[1] / "reference/softmax_training"
    report = json.loads((here / "docs/evidence.json").read_text(encoding="utf-8"))
    protocol = json.loads((here / "protocol.json").read_text(encoding="utf-8"))
    assert validate_report(report, protocol) == []
    report["runs"][0]["variants"]["standard"]["checkpoints"][-1]["parameter_displacement_l2"] = 0
    assert any("not reproduced from weights" in e for e in validate_report(report, protocol))
