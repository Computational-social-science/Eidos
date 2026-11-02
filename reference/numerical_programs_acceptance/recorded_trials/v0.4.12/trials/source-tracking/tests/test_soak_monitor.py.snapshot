"""Bounded observation uses a fake clock, never a live monitor or real waiting."""

import json

import pytest

from tools import soak_monitor


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def healthy(seq=1, **changes):
    return {"seq": seq, "sample_age_s": 0.1, "stale": False, "overall": "OK",
            "derived": {"overall": "OK", "faults": []}, **changes}


def observe(tmp_path, fetch, clock=None, **kwargs):
    clock = clock or Clock()
    return soak_monitor.observe(
        url="http://127.0.0.1:8765/api/status", duration=kwargs.pop("duration", 3),
        interval=kwargs.pop("interval", 1), max_age=kwargs.pop("max_age", 2),
        out=tmp_path / "soak.json", fetch=fetch, monotonic=clock.monotonic,
        sleep=kwargs.pop("sleep_override", clock.sleep), **kwargs)


def test_full_duration_is_required_and_progress_never_claims_pass(tmp_path):
    clock = Clock()
    progress = []
    def fetch(_):
        progress.append(json.loads((tmp_path / "soak.json").read_text()))
        return healthy(int(clock.now) + 1)
    result = observe(tmp_path, fetch, clock)
    assert result["status"] == "PASS"
    assert result["elapsed_s"] >= result["requested_duration_s"] == 3
    assert result["observations"] == 4
    assert all(row["status"] == "RUNNING" for row in progress)
    assert json.loads((tmp_path / "soak.json").read_text())["status"] == "PASS"


@pytest.mark.parametrize("payload", [
    healthy(sample_age_s=3), healthy(stale=True), healthy(overall="ALARM"),
    healthy(derived={"overall": "OK", "faults": ["service down"]}),
    healthy(derived={"overall": "STALE", "faults": []}),
    healthy(sample_age_s=float("nan")), healthy(sample_age_s=-1),
    healthy(seq=True), healthy(seq=None), {}, [],
])
def test_invalid_or_unhealthy_status_fails_even_if_later_recovered(tmp_path, payload):
    responses = iter([payload, healthy(2), healthy(3), healthy(4)])
    result = observe(tmp_path, lambda _: next(responses))
    assert result["status"] == "FAIL"
    assert result["failure_count"] == 1


def test_unreachable_is_recorded_and_later_success_cannot_erase_it(tmp_path):
    clock = Clock()
    def fetch(_):
        if clock.now == 0:
            raise OSError("connection refused")
        return healthy(int(clock.now))
    result = observe(tmp_path, fetch, clock)
    assert result["status"] == "FAIL"
    assert result["failure_count"] == 1
    assert "connection refused" in result["recent_samples"][0]["failures"][0]


def test_short_interval_repeated_sequence_is_allowed_within_window(tmp_path):
    clock = Clock()
    result = observe(tmp_path, lambda _: healthy(1 + int(clock.now // 2)), clock,
                     duration=5, interval=0.5, max_age=2)
    assert result["status"] == "PASS"
    assert result["sequence_advances"] == 2


def test_frozen_sequence_fails_despite_rewritten_fresh_age(tmp_path):
    result = observe(tmp_path, lambda _: healthy(7), duration=4)
    assert result["status"] == "FAIL"
    assert any("stagnant" in error for row in result["recent_samples"]
               for error in row["failures"])


def test_regressed_sequence_is_a_recorded_restart_and_strict_failure(tmp_path):
    responses = iter([healthy(50), healthy(1), healthy(2), healthy(3)])
    result = observe(tmp_path, lambda _: next(responses))
    assert result["status"] == "FAIL"
    assert result["restart_events"] == 1


def test_interrupt_preserves_partial_evidence_as_incomplete(tmp_path):
    clock = Clock()
    def interrupted_sleep(_):
        clock.now += 0.5
        raise KeyboardInterrupt
    result = observe(tmp_path, lambda _: healthy(), clock, sleep_override=interrupted_sleep)
    assert result["status"] == "INCOMPLETE"
    assert result["elapsed_s"] < result["requested_duration_s"]
    assert json.loads((tmp_path / "soak.json").read_text())["status"] == "INCOMPLETE"


def test_long_observation_keeps_only_bounded_recent_samples(tmp_path):
    clock = Clock()
    result = observe(tmp_path, lambda _: healthy(int(clock.now)), clock, duration=150)
    assert result["status"] == "PASS"
    assert result["observations"] == 151
    assert len(result["recent_samples"]) == soak_monitor.RECENT_LIMIT


def test_oversleep_does_not_turn_an_unobserved_day_into_pass(tmp_path):
    clock = Clock()
    def suspended(_):
        clock.now += 1000
    result = observe(tmp_path, lambda _: healthy(int(clock.now)), clock,
                     sleep_override=suspended)
    assert result["status"] == "FAIL"
    assert any("observation gap" in error for row in result["recent_samples"]
               for error in row["failures"])


@pytest.mark.parametrize("field", ["duration", "interval", "max_age"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_invalid_configuration_fails_before_fetch_or_report(tmp_path, field, value):
    def must_not_fetch(_):
        pytest.fail("invalid settings must not make HTTP calls")
    with pytest.raises(ValueError):
        observe(tmp_path, must_not_fetch, **{field: value})
    assert not (tmp_path / "soak.json").exists()


def test_atomic_report_keeps_prior_file_when_replace_fails(tmp_path, monkeypatch):
    out = tmp_path / "soak.json"
    out.write_text('{"status":"RUNNING"}')
    def fail_replace(*_):
        raise OSError("disk unavailable")
    monkeypatch.setattr(soak_monitor.os, "replace", fail_replace)
    with pytest.raises(OSError):
        soak_monitor.write_report(out, {"status": "PASS"})
    assert json.loads(out.read_text())["status"] == "RUNNING"
    assert list(tmp_path.iterdir()) == [out]


@pytest.mark.parametrize("status, expected", [("PASS", 0), ("FAIL", 1), ("INCOMPLETE", 2)])
def test_cli_exit_code_reflects_final_status(tmp_path, monkeypatch, status, expected):
    monkeypatch.setattr(soak_monitor, "observe", lambda **_: {"status": status})
    assert soak_monitor.main(["--duration", "1", "--out", str(tmp_path / "out.json")]) == expected


@pytest.mark.parametrize("url", ["file:///private", "http://user:secret@localhost/status", "http:///status"])
def test_non_http_or_credential_urls_are_rejected_without_request(tmp_path, url):
    with pytest.raises(ValueError):
        soak_monitor.observe(url=url, duration=1, interval=1, max_age=1,
                             out=tmp_path / "out.json", fetch=lambda _: pytest.fail("no request"))


def test_request_latency_counts_against_freshness(tmp_path):
    clock = Clock()
    def slow_fetch(_):
        clock.now += 3
        return healthy(int(clock.now))
    result = observe(tmp_path, slow_fetch, clock)
    assert result["status"] == "FAIL"
    assert "request time" in result["recent_samples"][0]["failures"][0]


def test_server_error_is_not_healthy_even_when_overall_is_ok(tmp_path):
    result = observe(tmp_path, lambda _: healthy(server_error="sampler failed"))
    assert result["status"] == "FAIL"


def test_failure_totals_survive_recent_history_eviction(tmp_path):
    clock = Clock()
    result = observe(tmp_path, lambda _: healthy(int(clock.now), stale=clock.now == 0),
                     clock, duration=150)
    assert result["status"] == "FAIL"
    assert result["failure_count"] == 1
    assert all(not row["failures"] for row in result["recent_samples"])


def test_fetch_uses_only_get_with_timeout_and_bounded_body(monkeypatch):
    observed = {}
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, limit):
            observed["limit"] = limit
            return json.dumps(healthy()).encode()
    class Opener:
        def open(self, request, timeout):
            observed["method"] = request.get_method()
            observed["timeout"] = timeout
            return Response()
    monkeypatch.setattr(soak_monitor.urllib.request, "build_opener", lambda *_: Opener())
    assert soak_monitor.fetch_status(soak_monitor.DEFAULT_URL)["seq"] == 1
    assert observed == {"method": "GET", "timeout": 8,
                        "limit": soak_monitor.MAX_RESPONSE_BYTES + 1}


def test_fetch_rejects_oversized_responses(monkeypatch):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, limit):
            return b"x" * limit
    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()
    monkeypatch.setattr(soak_monitor.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(ValueError, match="size limit"):
        soak_monitor.fetch_status(soak_monitor.DEFAULT_URL)


def test_cli_invalid_settings_return_nonzero_without_observation(tmp_path):
    assert soak_monitor.main(["--duration", "nan", "--out", str(tmp_path / "out.json")]) == 1
    assert not (tmp_path / "out.json").exists()
