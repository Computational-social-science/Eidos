"""Adversarial controls for the closed numerical candidate language."""

import json

import numpy as np
import pytest

from reference.rsi_bootstrap import expressions, grader


def op(name, *args):
    return {"op": name, "args": list(args)}


def valid_program():
    x = {"input": "x"}
    negative = op("neg", x)
    small = op("log", op("neg", op("expm1", negative)))
    large = op("log1p", op("neg", op("exp", negative)))
    return {"loss": op("where", op("le", x, {"const": 0.6931471805599453}), small, large),
            "gradient": op("div", op("exp", negative), op("neg", op("expm1", negative)))}


def test_actual_interpreted_repair_matches_independent_reference():
    program = expressions.parse_program(json.dumps(valid_program()))
    for case in grader.development_cases():
        before = case.value.tobytes()
        loss, gradient = expressions.execute(program, case.value)
        assert grader.grade(case, loss, gradient)["passed"], case.name
        assert case.value.tobytes() == before


@pytest.mark.parametrize("node", [
    {"const": True}, {"const": "__import__('os')"}, {"input": "secret"},
    {"op": "open", "args": [{"const": 1}]},
    {"op": "exp", "args": []},
    {"input": "x", "file": "answers.json"},
    {"op": "log", "args": [{"input": "x"}], "code": "print(1)"},
    {"op": "where", "args": [{"const": 1}, {"const": 0}, {"const": 1}]},
    {"op": "le", "args": [{"const": 1}, {"const": 2}]},
])
def test_unsafe_or_wrongly_typed_programs_are_refused(node):
    payload = {"loss": node, "gradient": {"const": 1}}
    with pytest.raises(ValueError):
        expressions.parse_program(json.dumps(payload))


@pytest.mark.parametrize("payload", [
    '{"loss":{"const":1},"loss":{"const":2},"gradient":{"const":1}}',
    '{"loss":{"const":NaN},"gradient":{"const":1}}',
    '{"loss":{"const":Infinity},"gradient":{"const":1}}',
    '{"loss":{"const":1e999},"gradient":{"const":1}}',
    '{"loss":', '[]',
])
def test_malformed_duplicate_and_nonfinite_json_are_refused(payload):
    with pytest.raises(ValueError):
        expressions.parse_program(payload)


def test_size_depth_and_node_budgets_are_enforced():
    with pytest.raises(ValueError, match="size"):
        expressions.parse_program(" " * 32769)
    deep = {"input": "x"}
    for _ in range(20):
        deep = op("neg", deep)
    with pytest.raises(ValueError, match="depth"):
        expressions.parse_program(json.dumps({"loss": deep, "gradient": {"const": 1}}))
    wide = {"const": 1}
    for _ in range(8):
        wide = op("add", wide, wide)
    with pytest.raises(ValueError, match="node"):
        expressions.parse_program(json.dumps({"loss": wide, "gradient": {"const": 1}}))


def test_invalid_unselected_branch_is_still_validated():
    node = op("where", op("le", {"const": 0}, {"const": 1}),
              {"const": 1}, {"op": "__import__", "args": []})
    with pytest.raises(ValueError):
        expressions.parse_program(json.dumps({"loss": node, "gradient": {"const": 1}}))


def test_nonfinite_numeric_results_are_rejected_by_grader():
    payload = {"loss": op("log", {"const": -1}), "gradient": {"const": 1}}
    program = expressions.parse_program(json.dumps(payload))
    case = grader.Case("bad", np.asarray(1, dtype=np.float32))
    assert not grader.grade(case, *expressions.execute(program, case.value))["passed"]


@pytest.mark.parametrize("value", [np.asarray([1.0]), np.asarray(1, dtype=np.float16),
                                    np.asarray(0.0), np.asarray(np.inf)])
def test_inputs_cannot_expand_the_execution_contract(value):
    program = expressions.parse_program(json.dumps(valid_program()))
    with pytest.raises(ValueError):
        expressions.execute(program, value)
