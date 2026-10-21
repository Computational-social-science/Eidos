"""Tests for framework.gates — every gate must be able to FAIL.

A gate that cannot fail is not a gate. Each test asserts both directions:
the passing case passes and the failing case fails for the stated reason.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.gates import GateRegistry, run_quantitative_gates, run_semantic_gates


def test_acceptance_gate_direction_matters():
    """A lower-is-better metric must be able to fail; this was a real defect."""
    criteria = {"acc": 0.90, "silent": {"threshold": 0.05, "direction": "<="}}

    ok = GateRegistry.run_gate(
        "acceptance-gate", {}, {"results": {"acc": 0.91, "silent": 0.02}, "criteria": criteria}
    )
    assert ok.passed is True
    assert ok.score == 1.0

    bad = GateRegistry.run_gate(
        "acceptance-gate", {}, {"results": {"acc": 0.91, "silent": 0.12}, "criteria": criteria}
    )
    assert bad.passed is False
    assert bad.details["silent"]["met"] is False


def test_acceptance_gate_missing_metric_fails():
    r = GateRegistry.run_gate(
        "acceptance-gate", {}, {"results": {"acc": 0.95}, "criteria": {"acc": 0.90, "kspc": 1.2}}
    )
    assert r.passed is False
    assert r.details["kspc"]["status"] == "MISSING"


def test_acceptance_gate_rejects_unknown_direction():
    r = GateRegistry.run_gate(
        "acceptance-gate",
        {},
        {"results": {"x": 1.0}, "criteria": {"x": {"threshold": 1.0, "direction": "~"}}},
    )
    assert r.passed is False
    assert "BAD_DIRECTION" in r.details["x"]["status"]


def test_planted_truth_requires_all_controls():
    all_ok = GateRegistry.run_gate(
        "planted-truth", {},
        {"planted_controls": [{"expected": "A", "actual": "A"}]},
    )
    assert all_ok.passed is True

    one_bad = GateRegistry.run_gate(
        "planted-truth", {},
        {"planted_controls": [{"expected": "A", "actual": "A"}, {"expected": "B", "actual": "C"}]},
    )
    assert one_bad.passed is False
    assert one_bad.score == 0.5


def test_planted_truth_without_controls_fails():
    r = GateRegistry.run_gate("planted-truth", {}, {})
    assert r.passed is False


def test_independence_bookkeeping_flags_leakage():
    good = GateRegistry.run_gate("independence-bookkeeping", {}, {
        "train_test_split": True, "no_data_leakage": True,
        "proper_cross_validation": True, "independent_seeds": True,
    })
    assert good.passed is True

    leaky = GateRegistry.run_gate("independence-bookkeeping", {}, {
        "train_test_split": True, "no_data_leakage": False,
        "proper_cross_validation": True, "independent_seeds": True,
    })
    assert leaky.passed is False


def test_timing_discipline_flags_budget_overrun():
    within = GateRegistry.run_gate("timing-discipline", {}, {
        "compute_budget": {"gpu_hours": 10}, "actual_compute": {"gpu_hours": 8},
    })
    assert within.passed is True

    over = GateRegistry.run_gate("timing-discipline", {}, {
        "compute_budget": {"gpu_hours": 10}, "actual_compute": {"gpu_hours": 12},
    })
    assert over.passed is False


def test_tool_stewardship_requires_version_and_provenance():
    good = GateRegistry.run_gate("tool-stewardship", {}, {
        "tool_log": [{"version": "1.0", "provenance": "git:abc"}],
    })
    assert good.passed is True

    bad = GateRegistry.run_gate("tool-stewardship", {}, {
        "tool_log": [{"version": None, "provenance": "git:abc"}],
    })
    assert bad.passed is False


def test_unknown_gate_raises():
    try:
        GateRegistry.get_gate("does-not-exist", {})
    except ValueError as exc:
        assert "Unknown gate" in str(exc)
    else:
        raise AssertionError("unknown gate must raise")


def test_suite_runner_reports_each_gate():
    results = run_quantitative_gates({}, {
        "results": {"acc": 0.99},
        "criteria": {"acc": 0.90},
        "planted_controls": [{"expected": 1, "actual": 1}],
        "train_test_split": True, "no_data_leakage": True,
        "proper_cross_validation": True, "independent_seeds": True,
        "compute_budget": {}, "actual_compute": {},
        "tool_log": [{"version": "1", "provenance": "x"}],
    })
    assert len(results) >= 5
    assert all(hasattr(r, "gate_name") for r in results)


def test_bootloops_root_honours_env_override(monkeypatch, tmp_path):
    from framework.gates import resolve_bootloops_root

    monkeypatch.setenv("BOOTLOOPS_ROOT", str(tmp_path))
    assert resolve_bootloops_root() == tmp_path


def test_bootloops_root_ignores_a_bogus_config_path():
    """A nonexistent configured root must not be returned as if valid."""
    import pytest

    from framework.gates import resolve_bootloops_root

    try:
        resolved = resolve_bootloops_root(
            {"quality_gates": {"quantitative": {"root": "Z:/definitely-not-here"}}}
        )
    except FileNotFoundError:
        pytest.skip("no BootLoops installation on this machine")
    assert resolved.is_dir()
    assert str(resolved).replace("\\", "/") != "Z:/definitely-not-here"
