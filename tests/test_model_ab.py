"""The A/B rule: agreement and drift, with a control that proves the harness can say PASS."""

import pytest

import framework.model_ab as ab


def _rows(choices, probs=None):
    probs = probs or [0.8] * len(choices)
    return [{"question": f"q{i}", "choice": c, "probability": p}
            for i, (c, p) in enumerate(zip(choices, probs))]


def test_identical_endpoints_pass():
    base = _rows(["a"] * 12)
    result = ab.compare(base, base)
    assert ab.decide(result)["ok"] is True
    assert result["agreement"] == 1.0 and result["mean_abs_delta"] == 0.0


def test_one_flip_in_twelve_is_inside_the_declared_tolerance():
    # 11/12 = 0.917 >= 0.90. The rule is pre-registered with that tolerance, so a single flip
    # passes; pretending otherwise would be moving the threshold to fit the result.
    base = _rows(["a"] * 12)
    candidate = _rows(["a"] * 11 + ["b"])
    result = ab.compare(base, candidate)
    assert result["agreement"] == pytest.approx(11 / 12)
    assert ab.decide(result)["ok"] is True


def test_two_flips_in_twelve_fail():
    base = _rows(["a"] * 12)
    candidate = _rows(["a"] * 10 + ["b", "b"])
    verdict = ab.decide(ab.compare(base, candidate))
    assert verdict["ok"] is False
    assert any("agreement" in reason for reason in verdict["reasons"])


def test_a_score_shift_beyond_the_band_fails_even_when_choices_match():
    base = _rows(["a"] * 12, [0.9] * 12)
    candidate = _rows(["a"] * 12, [0.6] * 12)
    verdict = ab.decide(ab.compare(base, candidate))
    assert verdict["ok"] is False
    assert any("Δp" in reason for reason in verdict["reasons"])


def test_a_short_run_is_not_a_pass():
    base = _rows(["a"] * 4)
    verdict = ab.decide(ab.compare(base, base))
    assert verdict["ok"] is False
    assert any("only 4" in reason for reason in verdict["reasons"])


def test_unanswered_questions_are_excluded_not_counted_as_agreement():
    base = _rows(["a"] * 12)
    candidate = _rows(["a"] * 12)
    for row in candidate[:6]:
        row["choice"] = None
    result = ab.compare(base, candidate)
    assert result["n"] == 6
    assert ab.decide(result)["ok"] is False
