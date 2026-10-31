"""The MCP package for Barron (2026): the tool inventory, the arithmetic, and the verifier's report.

The tools live in a fastmcp server, so the arithmetic tests skip when fastmcp is absent (the CI
interpreter does not carry it). The report test reads what Paper2Agent's verifier wrote and checks that
it still describes this package — a stale report cannot pass silently.
"""

import json
from pathlib import Path

import pytest

MCP = Path(__file__).resolve().parents[1] / "reference" / "reproduction" / "barron2026" / "mcp"


def test_the_verifier_report_records_a_passing_run():
    report = json.loads((MCP / "verify.json").read_text(encoding="utf-8"))
    assert report["success"] is True
    assert report["mode"] == "calls"
    cases = json.loads((MCP / "cases.json").read_text(encoding="utf-8"))
    assert len(report["cases"]) == len(cases) == 7
    assert all(case["success"] for case in report["cases"])
    assert report["missing"] == [] and report["unexpected"] == []
    assert report["require_all_tools"] is True


def test_the_expected_inventory_names_four_tools():
    expected = json.loads((MCP / "expected.json").read_text(encoding="utf-8"))
    assert expected == ["log_softmax", "softmax", "hard_cross_entropy", "soft_target_cross_entropy"]


def test_every_expected_tool_has_a_case():
    expected = json.loads((MCP / "expected.json").read_text(encoding="utf-8"))
    cases = json.loads((MCP / "cases.json").read_text(encoding="utf-8"))
    assert sorted({case["tool"] for case in cases}) == sorted(expected)


def test_the_paper_arithmetic_holds():
    pytest.importorskip("fastmcp", reason="fastmcp is only installed in the reproduction venv")
    import importlib.util

    spec = importlib.util.spec_from_file_location("barron_mcp", MCP / "server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)

    stable = server.log_softmax([9, -9, -9])
    from framework.verifiers.numerics import reference_log_softmax
    import math
    expected = float(reference_log_softmax([9, -9, -9])[0])
    assert math.isclose(stable["first"], expected, rel_tol=1e-14, abs_tol=0)
    assert server.softmax([9, -9, -9])["is_normalised"] is True

    hard = server.hard_cross_entropy([9, -9, -9], 0)
    assert hard["grad_sum_is_zero"] is True
    assert abs(hard["loss"] - (-stable["first"])) < 1e-18

    soft = server.soft_target_cross_entropy([1, 0], [0.5, 0.5])
    assert soft["grad"] == [0.2310585786300049, -0.2310585786300049]
    assert soft["grad_sum_is_zero"] is True


def test_declared_mcp_cases_match_the_current_tools_exactly():
    pytest.importorskip("fastmcp")
    import importlib.util

    spec = importlib.util.spec_from_file_location("barron_cases_test", MCP / "server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    cases = json.loads((MCP / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        observed = getattr(server, case["tool"])(**case["arguments"])
        for field, expected in case["expected_subset"].items():
            assert observed[field] == expected, (case["name"], field, observed[field], expected)


def test_logit_soft_target_cases_match_independent_decimal_oracle():
    pytest.importorskip("fastmcp")
    import importlib.util
    import numpy as np
    from framework.verifiers.numerics import probe_logit_distillation

    spec = importlib.util.spec_from_file_location("barron_oracle_test", MCP / "server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    teacher = np.array([2, 1, 0], dtype=np.float32)
    near = teacher + np.array([-1e-7, 1e-7, 0], dtype=np.float32)
    def candidate(student, teacher):
        result = server.soft_target_cross_entropy(student.tolist(), teacher.tolist(),
                                                  teacher_kind="logits", dtype="float32")
        return result["loss"], np.asarray(result["grad"], dtype=np.float32)
    for student in (teacher, near):
        assert probe_logit_distillation(candidate, student, teacher)["verdict"] == "PASS"
