"""Public development-oracle controls; not model or sealed-task evaluation."""

from decimal import Decimal, localcontext
import hashlib
import os
from pathlib import Path

import numpy as np
import pytest

from reference.rsi_bootstrap import grader


def test_protocol_domain_and_precision_convergence():
    cases = grader.development_cases()
    assert len(cases) == 23
    assert len({case.name for case in cases}) == len(cases)
    for case in cases:
        low = grader.reference(case, precision=420)
        high = grader.reference(case, precision=520)
        for name in ("loss", "gradient"):
            a = np.asarray(float(low[name]), dtype=case.value.dtype)
            b = np.asarray(float(high[name]), dtype=case.value.dtype)
            assert a.tobytes() == b.tobytes(), (case.name, name)
            assert np.isfinite(a) and abs(a) >= np.finfo(a.dtype).tiny


def test_reference_at_independent_ordinary_point():
    case = grader.Case("ordinary", np.asarray(1.0, dtype=np.float64))
    ref = grader.reference(case)
    assert abs(ref["loss"] - Decimal("-0.45867514538708189102164364506732970187697790669219")) < Decimal("1e-48")
    assert abs(ref["gradient"] - Decimal("0.58197670686932642438500200510901155854686930107540")) < Decimal("1e-48")


def test_oracle_tail_requires_sufficient_precision():
    case = grader.Case("large", np.asarray(600.0, dtype=np.float64))
    with pytest.raises(ArithmeticError):
        grader.reference(case, precision=100)
    ref = grader.reference(case)
    assert ref["loss"] < 0 and ref["gradient"] > 0


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_correct_ordinary_formula_can_pass(dtype):
    case = grader.Case("ordinary", np.asarray(1.0, dtype=dtype))
    assert grader.grade(case, *grader.textbook(case.value))["passed"] is True


@pytest.mark.parametrize("fault", ["nonfinite", "shape", "dtype"])
def test_result_contract_refuses_faults(fault):
    case = grader.Case("contract", np.asarray(1.0, dtype=np.float64))
    loss, gradient = grader.repair(case.value)
    if fault == "nonfinite":
        gradient = np.asarray(np.nan, dtype=np.float64)
    elif fault == "shape":
        gradient = gradient.reshape(1)
    else:
        gradient = gradient.astype(np.float32)
    assert grader.grade(case, loss, gradient)["passed"] is False


def test_small_results_cannot_hide_in_absolute_tolerance():
    case = grader.Case("tail", np.asarray(50.0, dtype=np.float64))
    loss, gradient = grader.repair(case.value)
    zeros = np.zeros_like(case.value)
    assert np.isclose(zeros, loss, atol=1e-8)
    assert np.isclose(zeros, gradient, atol=1e-8)
    assert grader.grade(case, zeros, zeros)["passed"] is False


def test_partial_repair_does_not_certify_derivative():
    case = grader.Case("small", np.asarray(1e-5, dtype=np.float32))
    loss, _ = grader.repair(case.value)
    _, bad_gradient = grader.textbook(case.value)
    outcome = grader.grade(case, loss, bad_gradient)
    assert outcome["loss_relative_error"] < grader.TOLERANCES["float32"]
    assert outcome["passed"] is False


def test_complete_calibration_has_all_controls_and_no_model_claim():
    report = grader.calibrate()
    assert report["status"] == "PASS"
    assert report["case_count"] == 23
    assert set(report["controls"]) == {
        "repair", "textbook", "loss_only", "gradient_floor", "log1p_only",
        "expm1_only", "sign_flip", "always_zero", "wrong_dtype",
    }
    for name, row in report["controls"].items():
        assert row["observed"] == row["expected"], name
        assert len(row["points"]) == 23
    assert report["model_evaluation"] == "NOT_RUN"
    assert report["sealed_evaluation"] == "NOT_RUN"
    assert report["scientific_rsi"] == "NOT_DEMONSTRATED"


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_reference_input_never_produces_a_pass(value):
    with pytest.raises(ValueError):
        grader.reference(grader.Case("invalid", np.asarray(value)))


def test_changed_protocol_during_execution_cannot_publish_pass(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.md"
    protocol.write_text("frozen")
    monkeypatch.setattr(grader, "_input_paths", lambda: [protocol])
    original = grader.repair

    def changed(value):
        protocol.write_text("changed during evaluation")
        return original(value)

    monkeypatch.setattr(grader, "repair", changed)
    with pytest.raises(RuntimeError, match="inputs changed"):
        grader.calibrate()


def test_runtime_identity_drift_cannot_publish_pass(monkeypatch):
    calls = []

    def identity():
        calls.append(None)
        return {"version": str(len(calls))}

    monkeypatch.setattr(grader, "_runtime_identity", identity)
    with pytest.raises(RuntimeError, match="runtime identity changed"):
        grader.calibrate()


@pytest.mark.parametrize("name", ["grader.py", "test_grader.py", "protocol"])
def test_output_cannot_overwrite_bound_inputs(name, monkeypatch):
    path = grader.PROTOCOL if name == "protocol" else Path(grader.__file__).with_name(name)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    def unexpected_calibration():
        pytest.fail("destination must be refused before measurement")

    monkeypatch.setattr(grader, "calibrate", unexpected_calibration)
    with pytest.raises(SystemExit) as error:
        grader.main(["--output", str(path)])
    assert error.value.code == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_output_hardlink_alias_cannot_overwrite_input(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text("frozen")
    alias = tmp_path / "alias.json"
    try:
        os.link(source, alias)
    except OSError:
        pytest.skip("test volume does not support hard links")
    monkeypatch.setattr(grader, "_input_paths", lambda: [source])
    with pytest.raises(SystemExit) as error:
        grader.main(["--output", str(alias)])
    assert error.value.code == 2
    assert source.read_text() == "frozen"


def test_error_rounding_cannot_admit_value_above_tolerance(monkeypatch):
    case = grader.Case("boundary", np.asarray(1.0, dtype=np.float64))
    with localcontext() as context:
        context.prec = 120
        error = Decimal("2e-12") + Decimal("1e-40")
        target = Decimal(1) / (1 + error)
    monkeypatch.setattr(grader, "reference", lambda _: {"loss": -target, "gradient": target})
    outcome = grader.grade(case, np.asarray(-1.0), np.asarray(1.0))
    assert outcome["gradient_relative_error"] == grader.TOLERANCES["float64"]
    assert outcome["passed"] is False
