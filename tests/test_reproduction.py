"""A converted paper is a tool; a run number is evidence.

Paper2Agent's own claim is that it produces *reliable* MCP servers. Reliable is exactly the word a
framework should refuse to take on trust: this module requires the server to print a number, compares
it with the paper's number, and blocks a claim that cites the method without one. These tests cover
both refusals — an incomplete delivery, and a run that does not match.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "reference" / "reproduction"

import sys
sys.path.insert(0, str(ROOT))

from framework import reproduction  # noqa: E402
from framework.validity import ScientificValidityGate  # noqa: E402


def test_a_complete_delivery_is_registrable():
    report = reproduction.check_delivery(FIXTURES / "valid_delivery")
    assert report["ok"] is True
    assert report["skill"].endswith("SKILL.md") and report["usage"].endswith("USAGE.md")


def test_a_delivery_without_the_mcp_component_is_refused():
    """Paper2Agent's own contract calls this a partial run; a partial run cannot be registered."""
    report = reproduction.check_delivery(FIXTURES / "incomplete_delivery")
    assert report["ok"] is False
    assert any("USAGE.md" in problem for problem in report["problems"])


def test_the_missing_directory_case_is_refused_not_raised(tmp_path):
    report = reproduction.check_delivery(tmp_path / "does-not-exist")
    assert report["ok"] is False and report["problems"]


def test_matching_and_mismatching_are_decided_by_the_tolerance():
    assert reproduction.compare(0.927, 0.9274, 1e-3)[0] == reproduction.MATCH
    assert reproduction.compare(0.927, 0.95, 1e-3)[0] == reproduction.MISMATCH
    # Relative tolerance is opt-in. A 0.008 error fails an absolute 0.005 but passes 2% relative.
    assert reproduction.compare(0.927, 0.935, 0.005)[0] == reproduction.MISMATCH
    assert reproduction.compare(0.927, 0.935, 0.02, relative=True)[0] == reproduction.MATCH


def test_running_the_spec_records_a_match(tmp_path):
    spec = json.loads((FIXTURES / "match.json").read_text(encoding="utf-8"))
    record = reproduction.run_spec(spec, cwd=ROOT)
    assert record["verdict"] == reproduction.MATCH
    path = reproduction.write(record, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["observed"] == 0.927


def test_running_the_spec_records_a_mismatch(tmp_path):
    spec = json.loads((FIXTURES / "broken.json").read_text(encoding="utf-8"))
    record = reproduction.run_spec(spec, cwd=ROOT)
    assert record["verdict"] == reproduction.MISMATCH
    assert record["delta"] > 0.5


def test_a_spec_without_a_command_is_a_programming_error():
    try:
        reproduction.run_spec({"paper": "x", "expected": 1})
    except ValueError as exc:
        assert "command" in str(exc)
    else:
        raise AssertionError("a spec with no command must not silently pass")


def test_a_failing_command_is_unrun_not_mismatch():
    record = reproduction.run_spec({"paper": "x", "command": [sys.executable, "-c", "raise SystemExit(3)"],
                                    "expected": 1})
    assert record["verdict"] == reproduction.UNRUN and "exited 3" in record["reason"]


def test_output_that_is_not_json_is_unrun():
    record = reproduction.run_spec({"paper": "x", "command": [sys.executable, "-c", "print('hello')"],
                                    "expected": 1})
    assert record["verdict"] == reproduction.UNRUN


def test_gate_s_blocks_a_claim_without_a_reproduction_record(tmp_path):
    gate = ScientificValidityGate(tmp_path)
    findings, blocked = gate._reproduction_verdict("C1", "some-paper")
    assert findings == [] and any("does not exist" in b for b in blocked)


def test_gate_s_fails_a_claim_whose_reproduction_mismatched(tmp_path):
    reproduction.write({"paper": "p", "verdict": reproduction.MISMATCH, "expected": 0.927,
                        "observed": 0.4, "delta": 0.527}, tmp_path / "artifacts" / "reproduction")
    findings, blocked = ScientificValidityGate(tmp_path)._reproduction_verdict("C2", "p")
    assert blocked == []
    assert any("S12" in str(f) and "MISMATCH" in str(f) for f in findings)


def test_gate_s_passes_a_claim_whose_reproduction_matched(tmp_path):
    reproduction.write({"paper": "p", "verdict": reproduction.MATCH, "expected": 0.927,
                        "observed": 0.927, "delta": 0.0}, tmp_path / "artifacts" / "reproduction")
    findings, blocked = ScientificValidityGate(tmp_path)._reproduction_verdict("C3", "p")
    assert findings == [] and blocked == []
