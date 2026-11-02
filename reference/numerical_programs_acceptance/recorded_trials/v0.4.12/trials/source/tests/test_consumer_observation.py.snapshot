"""Reverification does not rewrite the experiment clock or erase real failures."""

from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

NOW = datetime(2026, 11, 1, 9, 40, tzinfo=timezone.utc)


@pytest.mark.parametrize("expected", ["PASS", "FAIL"])
def test_recent_verification_of_old_evidence_preserves_experiment_bytes(
    tmp_path, expected
):
    from tools.consumer_observation import verification_freshness

    path = tmp_path / "docs/evidence.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"generated": (NOW - timedelta(hours=40)).isoformat()}),
        encoding="utf-8",
    )
    before = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
    result = verification_freshness(tmp_path, expected, NOW.isoformat(), now=NOW)
    assert result["stale"] is False and result["age_h"] == 0
    assert result["source"] == "verification" and result["artifact_age_h"] > 24
    assert before == (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_mtime_ns,
    )


@pytest.mark.parametrize(
    "checked",
    [None, "", "invalid", True, 1, "2026-11-01T09:40:00", "2026-11-02T09:40:00+00:00"],
)
def test_fresh_artifact_does_not_substitute_missing_or_invalid_verification(
    tmp_path, checked
):
    from tools.consumer_observation import verification_freshness

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/evidence.json").write_text(
        json.dumps({"generated": NOW.isoformat()}), encoding="utf-8"
    )
    result = verification_freshness(tmp_path, "PASS", checked, now=NOW)
    assert result["stale"] is True and result["age_h"] is None


def test_expired_verification_is_stale_even_with_fresh_evidence(tmp_path):
    from tools.consumer_observation import verification_freshness

    result = verification_freshness(
        tmp_path, "PASS", (NOW - timedelta(hours=25)).isoformat(), now=NOW
    )
    assert result["stale"] is True and result["age_h"] == 25


def test_recent_check_cannot_hide_an_unexpected_verdict(tmp_path):
    from tools.dashboard import consumer_strip

    markup = consumer_strip(
        {
            "consumers": [
                {
                    "name": "positive",
                    "root": str(tmp_path),
                    "expected": "PASS",
                    "gate_s": "FAIL",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }
    )
    assert 'data-state="FAIL"' in markup and "Unexpected verdict" in markup


def test_changed_input_withdraws_even_recent_success(tmp_path):
    from tools.dashboard import consumer_strip

    markup = consumer_strip(
        {
            "stale_consumers": ["positive"],
            "consumers": [
                {
                    "name": "positive",
                    "root": str(tmp_path),
                    "expected": "PASS",
                    "gate_s": "PASS",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
    )
    assert 'data-stale="1"' in markup and "Declared inputs changed" in markup


def test_positive_card_uses_check_clock_and_still_displays_evidence_age(tmp_path):
    from tools.dashboard import consumer_strip

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/evidence.json").write_text(
        json.dumps(
            {
                "generated": (
                    datetime.now(timezone.utc) - timedelta(hours=40)
                ).isoformat()
            }
        ),
        encoding="utf-8",
    )
    markup = consumer_strip(
        {
            "consumers": [
                {
                    "name": "positive",
                    "root": str(tmp_path),
                    "expected": "PASS",
                    "gate_s": "PASS",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }
    )
    assert 'data-state="PASS"' in markup and "Checked" in markup
    assert "evidence 40.0 h old" in markup


@pytest.mark.parametrize("expected", ["PASS", "FAIL"])
def test_homepage_uses_the_same_verification_clock(tmp_path, expected):
    from tools.build_site import adopt_rows

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/evidence.json").write_text(
        json.dumps(
            {
                "generated": (
                    datetime.now(timezone.utc) - timedelta(hours=40)
                ).isoformat()
            }
        ),
        encoding="utf-8",
    )
    row = {
        "name": "recorded-project",
        "root": str(tmp_path),
        "gate": "gate",
        "available": True,
        "expected": expected,
        "gate_s": expected,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    markup = adopt_rows([row])
    assert "STALE" not in markup and "original measurement time retained" in markup


def test_documented_clock_skew_tolerance_is_bounded(tmp_path):
    from tools.consumer_observation import verification_freshness

    within = verification_freshness(
        tmp_path, "PASS", (NOW + timedelta(seconds=30)).isoformat(), now=NOW
    )
    beyond = verification_freshness(
        tmp_path, "PASS", (NOW + timedelta(seconds=61)).isoformat(), now=NOW
    )
    assert within["age_h"] == 0 and within["stale"] is False
    assert beyond["age_h"] is None and beyond["stale"] is True


@pytest.mark.parametrize("limit", [True, 0, -1, float("nan"), float("inf"), "24"])
def test_invalid_verification_limits_are_refused(tmp_path, limit):
    from tools.consumer_observation import verification_freshness

    with pytest.raises(ValueError, match="age limit"):
        verification_freshness(
            tmp_path, "PASS", NOW.isoformat(), max_age_h=limit, now=NOW
        )
