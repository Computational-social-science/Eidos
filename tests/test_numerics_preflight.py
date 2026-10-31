"""A numerical capability must reject the known bad kernels, not just name the paper."""

import numpy as np

from framework.verifiers import numerics


def test_preflight_rejects_a_collapsed_target_despite_small_absolute_residual():
    def broken(z, target):
        return 0.0, np.array([0.0, np.exp(-40.0), np.exp(-40.0)])
    result = numerics.probe_hard_cross_entropy(broken, np.array([40.0, 0.0, 0.0]), 0)
    assert result["verdict"] == "FAIL"


def test_preflight_rejects_stationary_teacher_noise():
    def broken(student, teacher):
        return 0.0, np.array([1e-12, -1e-12, 0.0])
    values = np.array([2.0, 1.0, 0.0])
    result = numerics.probe_logit_distillation(broken, values, values)
    assert result["verdict"] == "FAIL"


def test_builtin_preflight_earns_pass_and_both_negative_controls_fire():
    report = numerics.kernel_regression_report()
    assert report["verdict"] == "PASS"
    assert len(report["cases"]) >= 8
    assert all(case["verdict"] == "PASS" for case in report["cases"])
    assert all(control["rejected"] for control in report["negative_controls"])
    assert report["paper"] == "arxiv:2610.31642v3"


def test_candidate_cannot_relax_tolerance_by_silently_downcasting():
    def downgraded(z, target):
        return np.float32(np.log(3)), np.array([-2 / 3, 1 / 3, 1 / 3], dtype=np.float32)
    result = numerics.probe_hard_cross_entropy(downgraded, np.zeros(3, dtype=np.float64), 0)
    assert result["verdict"] == "ERROR"
    assert "dtype" in result["error"]
