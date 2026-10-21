"""Tool-missing behaviour: a SKIP is neither a pass nor a failure.

Before this, `ref-check` and `vale` raised FileNotFoundError out of the gate and
aborted the whole suite with a traceback — verified on this host. The project's own
contract says a missing engine is a skip, because failing it trains a reader to
ignore the gate. These tests pin both sides: missing → SKIP, present-and-failing →
FAIL, present-and-passing → PASS.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.gates import GateRegistry, GateResult

MISSING = ["definitely-not-installed-tool-xyz"]


def test_missing_tool_is_skip_not_crash():
    r = GateRegistry.run_gate(
        "ref-check", {"command": MISSING}, {"bibliography_path": "refs.bib"}
    )
    assert r.status == "SKIP"
    assert r.passed is False
    assert r.details["missing_tool"] == MISSING[0]
    assert r.details["install"]


def test_failing_tool_is_fail_not_skip():
    cmd = [sys.executable, "-c", "raise SystemExit(1)"]
    r = GateRegistry.run_gate(
        "ref-check", {"command": cmd}, {"bibliography_path": "refs.bib"}
    )
    assert r.status == "FAIL"
    assert r.passed is False


def test_passing_tool_is_pass():
    cmd = [sys.executable, "-c", "pass"]
    r = GateRegistry.run_gate(
        "ref-check", {"command": cmd}, {"bibliography_path": "refs.bib"}
    )
    assert r.status == "PASS"
    assert r.passed is True


def test_prose_lint_missing_tool_is_skip():
    r = GateRegistry.run_gate(
        "prose-lint", {"command": MISSING}, {"manuscript_path": "m.html"}
    )
    assert r.status == "SKIP"


def test_ragas_absent_library_is_skip_not_fail():
    if importlib.util.find_spec("ragas") is not None:
        pytest.skip("ragas is installed here; the missing-library path cannot be exercised")
    r = GateRegistry.run_gate("ragas", {}, {"ragas_dataset": "some/dataset"})
    assert r.status == "SKIP"
    assert r.details["missing_tool"] == "ragas"


def test_suite_survives_a_crashing_gate(monkeypatch):
    """One crashing gate must not prevent the others from reporting."""

    class Boom:
        def __init__(self, config):
            self.config = config

        def run(self, context):
            raise RuntimeError("boom")

    monkeypatch.setitem(GateRegistry.GATES, "boom", Boom)

    results = GateRegistry.run_suite(
        ["boom", "acceptance-gate"],
        {},
        {"results": {"a": 1.0}, "criteria": {"a": 1.0}},
    )

    assert results[0].status == "ERROR"
    assert "boom" in results[0].details["error"]
    assert results[1].status == "PASS"


def test_status_defaults_to_fail_when_not_passed():
    """A gate that says passed=False but forgets a status is a FAIL, never green."""
    r = GateResult(gate_name="x", passed=False)
    assert r.status == "FAIL"
