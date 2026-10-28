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
    assert len(report["cases"]) == 4
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
    assert abs(stable["first"] + 3.0459958e-08) < 1e-15
    assert server.softmax([9, -9, -9])["is_normalised"] is True

    hard = server.hard_cross_entropy([9, -9, -9], 0)
    assert hard["grad_sum_is_zero"] is True
    assert abs(hard["loss"] - (-stable["first"])) < 1e-18

    soft = server.soft_target_cross_entropy([1, 0], [0.5, 0.5])
    assert soft["grad"] == [0.2310585786300049, -0.2310585786300049]
    assert soft["grad_sum_is_zero"] is True
