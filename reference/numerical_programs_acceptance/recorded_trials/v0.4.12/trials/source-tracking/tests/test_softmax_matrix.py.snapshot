"""The matrix is accepted by complete paired evidence, never by favorable accuracy."""
import copy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "reference/softmax_matrix"


def test_matrix_has_exact_supported_precision_epsilon_seed_inventory():
    from reference.softmax_matrix.verify import expected_cells
    p = json.loads((BASE / "protocol.json").read_text())
    cells = expected_cells(p)
    assert len(cells) == len(set(cells)) == 36
    assert {c[1] for c in cells} == {"float32", "float64"}
    assert set(p["unqualified_loss_dtypes"]) == {"bfloat16"}
    assert p["model_dtype"] == "float32"


def test_completion_cannot_omit_a_cell_or_backend_evidence():
    from reference.softmax_matrix.verify import validate_structure
    p = json.loads((BASE / "protocol.json").read_text())
    assert validate_structure({"status": "COMPLETE", "protocol": p, "runs": []}, p)


def test_gradient_counts_and_time_points_are_not_just_decorative():
    from reference.softmax_matrix.verify import validate_point
    point = {"step": 200, "train_accuracy": 1., "test_accuracy": 0., "mean_margin": 20.,
             "cross_entropy_float64": 1e-8, "training_loss": 1e-8, "sample_count": 480,
             "zero_target_loss": 480, "zero_target_model": 480}
    assert not validate_point(point, 480)
    for key, bad in (("zero_target_loss", 481), ("zero_target_model", True), ("zero_target_model", 0),
                     ("training_loss", float("nan")), ("test_accuracy", 1.1)):
        broken = copy.deepcopy(point); broken[key] = bad
        assert validate_point(broken, 480)


def test_saved_matrix_accepts_only_complete_bound_evidence():
    from reference.softmax_matrix.verify import validate, validate_final_check
    p = json.loads((BASE / "protocol.json").read_text())
    r = json.loads((BASE / "docs/evidence.json").read_text())
    assert not validate(r, p)
    assert not validate_final_check(r)
    for change in ("missing_cell", "missing_artifacts", "wrong_parent", "erased_ce"):
        broken = copy.deepcopy(r)
        if change == "missing_cell": broken["runs"].pop()
        elif change == "missing_artifacts": broken["artifacts"] = {}
        elif change == "wrong_parent": broken["parent_evidence_sha256"] = "0" * 64
        else: broken["runs"][0]["checkpoints"][-1]["cross_entropy_float64"] = 0
        assert validate(broken, p), change
    broken = copy.deepcopy(r)
    broken["runs"][0]["checkpoints"][-1]["training_loss"] = 0
    assert validate_final_check(broken), "finite but false zero loss cannot pass the final audit"
