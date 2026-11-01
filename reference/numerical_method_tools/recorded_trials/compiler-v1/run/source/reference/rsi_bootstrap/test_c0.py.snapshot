"""Single-attempt C0 core controls; transports here are explicit test doubles."""
import json

import pytest

from reference.rsi_bootstrap import c0
from reference.rsi_bootstrap.test_expressions import valid_program


def response(program=None):
    return json.dumps({"program": program or valid_program(), "explanation": "Development fixture."})


def test_one_proposal_actual_execution_and_no_scientific_promotion():
    calls = []

    def provider(prompt):
        calls.append(prompt)
        return response()

    result = c0.run_once(provider)
    assert calls == [c0.PROMPT]
    assert result["status"] == "DEVELOPMENT_CONFORMING"
    assert len(result["points"]) == 23
    assert result["baseline_conforming_points"] == 8
    assert result["candidate_conforming_points"] == 23
    assert result["retained_for_development"] is True
    assert result["scientific_promotion"] is False
    assert result["model_execution_attested"] is False
    assert result["raw_response"] == response()


@pytest.mark.parametrize("payload", ["not JSON", "[]", "{}", "x" * 32769,
    '{"program":{},"program":{},"explanation":"dup"}',
    '{"program":{"loss":{"const":NaN}},"explanation":"bad"}',
    '{"program":{},"explanation":""}'], ids=["text", "array", "empty", "oversize", "duplicate", "nan", "explanation"])
def test_invalid_response_retains_failure_without_retry(payload):
    calls = []
    result = c0.run_once(lambda prompt: calls.append(prompt) or payload)
    assert len(calls) == 1
    assert result["status"] == "INVALID_RESPONSE"
    assert result["retained_for_development"] is False
    assert len(result["raw_response"]) <= 32768


@pytest.mark.parametrize("error,status", [(TimeoutError, "TRANSPORT_TIMEOUT"),
                                           (ConnectionError, "TRANSPORT_ERROR")])
def test_transport_failure_is_not_a_model_accuracy_result(error, status):
    def provider(prompt):
        raise error("potentially sensitive transport details")

    result = c0.run_once(provider)
    assert result["status"] == status
    assert result["points"] == []
    assert "potentially sensitive" not in json.dumps(result)


def test_always_zero_cannot_be_retained():
    program = {"loss": {"const": 0}, "gradient": {"const": 0}}
    result = c0.run_once(lambda _: response(program))
    assert result["status"] == "DEVELOPMENT_NONCONFORMING"
    assert result["candidate_conforming_points"] == 0
    assert result["retained_for_development"] is False


def test_changed_inputs_withdraw_candidate(monkeypatch):
    snapshots = iter([{"source": "before"}, {"source": "after"}])
    monkeypatch.setattr(c0, "source_snapshot", lambda: next(snapshots))
    result = c0.run_once(lambda _: response())
    assert result["status"] == "INPUT_CHANGED"
    assert not result["retained_for_development"]


def test_evaluator_failure_is_recorded_without_retaining_candidate(monkeypatch):
    def broken(*args):
        raise ArithmeticError("oracle failed")

    monkeypatch.setattr(c0.grader, "grade", broken)
    result = c0.run_once(lambda _: response())
    assert result["status"] == "EVALUATOR_ERROR"
    assert not result["retained_for_development"]


def test_unobservable_final_inputs_withdraw_candidate(monkeypatch):
    calls = []

    def snapshot():
        if calls:
            raise OSError("input disappeared")
        calls.append(None)
        return {"source": "initial"}

    monkeypatch.setattr(c0, "source_snapshot", snapshot)
    result = c0.run_once(lambda _: response())
    assert result["status"] == "INPUT_UNOBSERVABLE"
    assert not result["retained_for_development"]


def test_extreme_but_valid_constants_retain_strict_json_failure_record():
    program = {"loss": {"const": 1e300}, "gradient": {"const": 1e300}}
    result = c0.run_once(lambda _: response(program))
    assert result["status"] == "DEVELOPMENT_NONCONFORMING"
    assert not result["retained_for_development"]
    assert any(point.get("diagnostic_range_error") for point in result["points"])
    json.dumps(result, allow_nan=False)
