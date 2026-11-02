"""Pointers decide admissibility. A model answer that cites nothing checkable is not a verdict.

`tests/fixtures/s4_real_answer.json` is the verbatim reply the deployed ScienceRSI-8b produced on
this host (CPU, 4.4 s, 35 tokens) for a design whose achieved power was 0.41 against a required
0.80. It is used here so the schema is tested against a real model output, not a hand-written ideal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.verifiers import pointers

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def root(tmp_path):
    (tmp_path / "artifacts" / "evaluation").mkdir(parents=True)
    (tmp_path / "artifacts" / "literature" / "support").mkdir(parents=True)
    (tmp_path / "artifacts" / "evaluation" / "stat_recompute.json").write_text(json.dumps(
        {"verdict": "FAIL", "power": {"achieved": 0.41, "required": 0.80},
         "checks": [{"id": "power", "status": "FAIL"}]}), encoding="utf-8")
    (tmp_path / "artifacts" / "literature" / "proofpath.json").write_text(json.dumps(
        {"records": [{"reference": "10.1/x", "status": "VERIFIED"}]}), encoding="utf-8")
    (tmp_path / "artifacts" / "literature" / "support" / "C1.json").write_text(json.dumps(
        {"claim": "C1", "verdict": "SUPPORTED", "passage": {"source": "10.1/x", "start": 0, "end": 8}}),
        encoding="utf-8")
    return tmp_path


def test_rfc6901_resolution():
    doc = {"a": {"b": [10, {"c": 3}]}, "x/y": 1, "m~n": 2}
    assert pointers.resolve(doc, "/a/b/1/c") == 3
    assert pointers.resolve(doc, "/x~1y") == 1
    assert pointers.resolve(doc, "/m~0n") == 2
    with pytest.raises(pointers.PointerError):
        pointers.resolve(doc, "/a/b/9")


def test_the_real_model_answer_is_admissible(root):
    answer = json.loads((FIXTURES / "s4_real_answer.json").read_text(encoding="utf-8"))
    assert pointers.check_s4(root, answer) == []


def test_a_dangling_fragment_is_a_problem(root):
    answer = {"verdict": "FAIL", "checks": [{"id": "power", "status": "FAIL",
              "evidence_pointer": "/artifacts/evaluation/stat_recompute.json#/power/nope"}],
              "blocking": ["power"]}
    problems = pointers.check_s4(root, answer)
    assert any("nope" in p for p in problems)


def test_pass_cannot_carry_a_failed_check(root):
    answer = {"verdict": "PASS", "checks": [{"id": "power", "status": "FAIL",
              "evidence_pointer": "/artifacts/evaluation/stat_recompute.json#/power"}]}
    assert any("PASS with failed checks" in p for p in pointers.check_s4(root, answer))


def test_blocking_must_name_a_failed_check(root):
    answer = {"verdict": "FAIL", "checks": [{"id": "power", "status": "PASS",
              "evidence_pointer": "/artifacts/evaluation/stat_recompute.json#/power"}],
              "blocking": ["power"]}
    assert any("did not fail" in p for p in pointers.check_s4(root, answer))


def test_a_pointer_cannot_escape_the_project(root):
    answer = {"verdict": "FAIL", "checks": [{"id": "power", "status": "FAIL",
              "evidence_pointer": "/../../etc/passwd"}]}
    assert any("escapes" in p or "does not exist" in p for p in pointers.check_s4(root, answer))


def test_s7_category_must_point_at_its_own_artefact(root):
    wrong = {"verdict": "FAIL", "objections": [
        {"severity": "major", "category": "statistics", "resolvable": False,
         "evidence_pointer": "/artifacts/literature/proofpath.json#/records/0"}]}
    assert any("must point into stat_recompute.json" in p for p in pointers.check_s7(root, wrong))

    right = {"verdict": "FAIL", "objections": [
        {"severity": "major", "category": "statistics", "resolvable": False,
         "evidence_pointer": "/artifacts/evaluation/stat_recompute.json#/checks/0"}]}
    assert pointers.check_s7(root, right) == []


def test_s7_pass_with_an_unresolved_major_objection_is_illegal(root):
    answer = {"verdict": "PASS", "objections": [
        {"severity": "major", "category": "support", "resolvable": False,
         "evidence_pointer": "/artifacts/literature/support/C1.json#/verdict"}]}
    assert any("unresolved" in p for p in pointers.check_s7(root, answer))

    answer["objections"][0]["resolvable"] = True
    assert pointers.check_s7(root, answer) == []
