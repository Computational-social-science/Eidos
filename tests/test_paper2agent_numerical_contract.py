"""The existing converted agent must satisfy the v3 gradient contract."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastmcp")
SERVER = Path(__file__).resolve().parents[1] / "reference/reproduction/barron2026/mcp/server.py"
spec = importlib.util.spec_from_file_location("paper_contract_server", SERVER)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_converted_hard_loss_preserves_target_gradient_past_float64_cliff():
    result = server.hard_cross_entropy([40.0, 0.0, 0.0], 0)
    assert result["loss"] > 0
    assert result["grad"][0] < 0
    assert result["grad_sum_is_zero"]


def test_the_gradient_check_has_no_absolute_floor():
    assert not server._sum_is_zero(np.array([0.0, 4.248354e-18, 4.248354e-18]))


def test_converted_distillation_accepts_explicit_teacher_logits():
    result = server.soft_target_cross_entropy([2.0, 1.0, 0.0], [2.0, 1.0, 0.0],
                                               teacher_kind="logits")
    assert result["teacher_kind"] == "logits"
    assert result["grad"] == [0.0, 0.0, 0.0]


def test_probability_targets_remain_an_explicit_legacy_contract():
    result = server.soft_target_cross_entropy([1.0, 0.0], [0.5, 0.5],
                                               teacher_kind="probabilities")
    assert result["teacher_kind"] == "probabilities"
    np.testing.assert_allclose(result["grad"], [0.2310585786300049, -0.2310585786300049],
                               rtol=1e-14, atol=0)
