"""Exercise recovery outcomes and incident ownership without touching live services."""

import json
from types import SimpleNamespace

import pytest

from framework import recovery
from tools import watch_pipeline as watcher


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    state = tmp_path / "recovery_state.json"
    log = tmp_path / "recoveries.jsonl"
    monkeypatch.setattr(recovery, "STATE", state)
    monkeypatch.setattr(recovery, "LOG", log)
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    monkeypatch.setattr(watcher, "STATUS", tmp_path)
    monkeypatch.setattr(watcher, "RECOVERY_STATE", state)
    monkeypatch.setattr(watcher, "RECOVERIES", log)
    monkeypatch.setenv("EIDOS_AUTO_RECOVER", "1")
    clock = [10000.0]
    monkeypatch.setattr(recovery.time, "time", lambda: clock[0])
    monkeypatch.setattr(
        recovery.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay)
    )
    return SimpleNamespace(state=state, log=log, clock=clock)


@pytest.mark.parametrize("healthy", [True, False])
def test_verification_always_records_a_terminal_outcome(isolated, monkeypatch, healthy):
    monkeypatch.setattr(recovery, "ENDPOINTS", {"svc": ("test:a", "test:b")})
    monkeypatch.setattr(recovery, "_answers", lambda url: healthy or url == "test:a")
    result = recovery.verify("svc", timeout=2, interval=1)
    assert result["verified"] is healthy
    row = json.loads(isolated.log.read_text(encoding="utf-8").splitlines()[-1])
    assert row["ok"] is healthy and row["outcome"] == (
        "recovered" if healthy else "no effect"
    )
    assert row["phase"] == ("verified" if healthy else "failed")
    stored = json.loads(isolated.state.read_text(encoding="utf-8"))["svc"]
    assert stored["in_flight"] is False and stored["ok"] is healthy


def fault():
    return {"svc": {"state": "ALARM", "recovery": {"available": True}}}


def test_automatic_attempt_preserves_launcher_fields_and_has_one_attempt_row(
    isolated, monkeypatch
):
    plan = recovery.RecoveryPlan("svc", "start", "controlled start", True)
    monkeypatch.setattr(recovery, "plan", lambda name: plan)

    def execute(plan):
        recovery._note("svc", in_flight=True, failures=2, launcher_token="retained")
        recovery._log("svc", "start", "attempt", True, pid=123)
        return {"ok": True, "pid": 123}

    monkeypatch.setattr(recovery, "execute", execute)
    for _ in range(3):
        watcher.maybe_auto_recover(fault())
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["svc"]
    assert (
        row["in_flight"] is True
        and row["failures"] == 2
        and row["launcher_token"] == "retained"
    )
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(event["phase"] == "attempt" for event in events) == 1


def test_new_measured_healthy_incident_can_recover_after_budget_exhaustion(
    isolated, monkeypatch
):
    isolated.state.write_text(
        json.dumps(
            {
                "svc": {
                    "attempts": 3,
                    "pending": False,
                    "streak": 12,
                    "last_attempt": 1.0,
                }
            }
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        recovery,
        "plan",
        lambda name: recovery.RecoveryPlan(name, "start", "test", True),
    )

    def execute(plan):
        calls.append(plan.service)
        recovery._note("svc", attempts=1, last_attempt=isolated.clock[0], pending=True)
        return {"ok": True, "pid": 123}

    monkeypatch.setattr(recovery, "execute", execute)
    watcher.maybe_auto_recover(fault())
    assert calls == []
    watcher.maybe_auto_recover({"svc": {"state": "OK"}})
    for _ in range(3):
        watcher.maybe_auto_recover(fault())
    assert calls == ["svc"]


def test_long_model_start_is_not_failed_after_only_sixty_seconds(isolated):
    isolated.state.write_text(
        json.dumps(
            {
                "runtime_18434": {
                    "attempts": 1,
                    "pending": True,
                    "streak": 0,
                    "last_attempt": isolated.clock[0] - 61,
                }
            }
        ),
        encoding="utf-8",
    )
    watcher.maybe_auto_recover({"runtime_18434": {"state": "ALARM"}})
    assert (
        json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"][
            "pending"
        ]
        is True
    )
    assert not isolated.log.exists()


def test_corrupt_recovery_state_is_preserved_and_cannot_restart(isolated, monkeypatch):
    isolated.state.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(
        recovery, "execute", lambda plan: pytest.fail("unsafe recovery")
    )
    with pytest.raises(ValueError):
        watcher.maybe_auto_recover(fault())
    assert isolated.state.read_text(encoding="utf-8") == "{broken"


def test_cooldown_attempt_budget_and_observed_recovery_are_separate(
    isolated, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        recovery,
        "plan",
        lambda name: recovery.RecoveryPlan(name, "start", "test", True),
    )

    def execute(plan):
        calls.append(isolated.clock[0])
        recovery._note(
            "svc", attempts=len(calls), last_attempt=isolated.clock[0], pending=True
        )
        return {"ok": True, "pid": 123}

    monkeypatch.setattr(recovery, "execute", execute)
    for attempt in range(3):
        for _ in range(3):
            watcher.maybe_auto_recover(fault())
        assert len(calls) == attempt + 1
        isolated.clock[0] += 91
        watcher.maybe_auto_recover(fault())
        for _ in range(5):
            watcher.maybe_auto_recover(fault())
        assert len(calls) == attempt + 1  # still in cooldown
        isolated.clock[0] += 601
    for _ in range(10):
        watcher.maybe_auto_recover(fault())
    assert len(calls) == 3  # exhausted this incident, no repeated restart loop
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(events) == 3 and all(event["ok"] is False for event in events)
    watcher.maybe_auto_recover({"svc": {"state": "OK"}})
    assert (
        json.loads(isolated.state.read_text(encoding="utf-8"))["svc"]["attempts"] == 0
    )


def test_unavailable_recovery_and_opt_out_cannot_start_services(isolated, monkeypatch):
    monkeypatch.setattr(
        recovery, "execute", lambda plan: pytest.fail("unexpected start")
    )
    for _ in range(4):
        watcher.maybe_auto_recover(
            {"svc": {"state": "UNOBSERVABLE", "recovery": {"available": False}}}
        )
    before = isolated.state.read_bytes()
    monkeypatch.setenv("EIDOS_AUTO_RECOVER", "0")
    watcher.maybe_auto_recover(fault())
    assert isolated.state.read_bytes() == before


def test_two_manual_callers_only_launch_once(isolated, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    entered, release = threading.Event(), threading.Event()
    launched = []
    monkeypatch.setattr(
        recovery,
        "ACTIONS",
        {"svc": {"root": "repo", "script": ("start.py",), "kind": "python"}},
    )
    monkeypatch.setattr(
        recovery,
        "preflight",
        lambda name: {
            "healthy": bool(launched),
            "ports": {},
            "conflict": False,
            "owned_by_self": False,
        },
    )

    def popen(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        launched.append(321)
        return SimpleNamespace(pid=321)

    monkeypatch.setattr(recovery.subprocess, "Popen", popen)
    plan = recovery.RecoveryPlan("svc", "start", "controlled launch", True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(recovery.execute, plan)
        try:
            assert entered.wait(2)
            second = pool.submit(recovery.execute, plan)
        finally:
            release.set()
        assert first.result(timeout=3)["pid"] == 321
        assert second.result(timeout=3)["skipped"] is True
    assert launched == [321]
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(event["phase"] == "attempt" for event in events) == 1


def test_failed_state_publication_preserves_old_budget_and_releases_ownership(
    isolated, monkeypatch
):
    from framework import artifacts

    original = artifacts.os.replace
    before = json.dumps({"svc": {"attempts": 3}}).encode()
    isolated.state.write_bytes(before)
    with monkeypatch.context() as patch:
        patch.setattr(
            artifacts.os,
            "replace",
            lambda *args: (_ for _ in ()).throw(
                OSError("controlled publication failure")
            ),
        )
        with pytest.raises(OSError, match="publication"):
            recovery._note("svc", attempts=0)
    assert isolated.state.read_bytes() == before
    assert artifacts.os.replace is original
    recovery._note("svc", retained=True)
    assert json.loads(isolated.state.read_text(encoding="utf-8"))["svc"] == {
        "attempts": 3,
        "retained": True,
    }


def controlled_launcher(monkeypatch):
    launched = []
    monkeypatch.setattr(
        recovery,
        "ACTIONS",
        {"runtime_18434": {"root": "repo", "script": ("start.py",), "kind": "python"}},
    )
    monkeypatch.setattr(
        recovery,
        "preflight",
        lambda name: {
            "healthy": False,
            "ports": {},
            "conflict": False,
            "owned_by_self": False,
        },
    )
    monkeypatch.setattr(
        recovery.subprocess,
        "Popen",
        lambda *args, **kwargs: launched.append(321) or SimpleNamespace(pid=321),
    )
    plan = recovery.RecoveryPlan("runtime_18434", "start", "controlled launch", True)
    monkeypatch.setattr(recovery, "plan", lambda name: plan)
    return plan, launched


def test_post_launch_publication_failure_retains_durable_reservation(
    isolated, monkeypatch
):
    plan, launched = controlled_launcher(monkeypatch)
    original = recovery._write_state

    def fail_after_launch(*args, **kwargs):
        if launched:
            raise OSError("controlled result publication failure")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(recovery, "_write_state", fail_after_launch)
        with pytest.raises(OSError, match="publication"):
            recovery.execute(plan)
    reserved = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert reserved["in_flight"] is True and reserved["attempts"] == 1
    assert recovery.execute(plan)["skipped"] is True
    assert launched == [321]


def test_loading_window_shared_by_manual_and_automatic_recovery(isolated, monkeypatch):
    plan, launched = controlled_launcher(monkeypatch)
    assert recovery.execute(plan)["ok"] is True
    isolated.clock[0] += 250
    assert recovery.execute(plan)["skipped"] is True
    watcher.maybe_auto_recover(
        {"runtime_18434": {"state": "ALARM", "recovery": {"available": True}}}
    )
    assert launched == [321]


def test_guard_rejections_do_not_exhaust_automatic_launch_budget(isolated, monkeypatch):
    _, launched = controlled_launcher(monkeypatch)
    states = lambda: {
        "runtime_18434": {"state": "ALARM", "recovery": {"available": True}}
    }
    for _ in range(3):
        watcher.maybe_auto_recover(states())
    assert len(launched) == 1
    isolated.clock[0] += 301
    watcher.maybe_auto_recover(states())  # actual failure, exponential cooldown starts
    isolated.clock[0] += 301
    for _ in range(4):
        watcher.maybe_auto_recover(states())  # too soon for the inner guard
    assert len(launched) == 1
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert row["attempts"] == 1 and row["last_attempt"] == 10000
    isolated.clock[0] += 601
    watcher.maybe_auto_recover(states())
    assert len(launched) == 2


@pytest.mark.parametrize(
    "row",
    [
        {"attempts": -1},
        {"attempts": True},
        {"attempts": "0"},
        {"failures": -3},
        {"streak": 1.5},
        {"last_attempt": -1},
        {"last_attempt": "0"},
        {"last_attempt": True},
        {"last_attempt": float("nan")},
        {"verified_at": float("inf")},
        {"pending": 1},
        {"in_flight": "false"},
        {"ok": None},
    ],
)
def test_invalid_recovery_budget_cannot_launch_or_be_overwritten(
    isolated, monkeypatch, row
):
    before = json.dumps({"runtime_18434": row}).encode()
    isolated.state.write_bytes(before)
    plan, launched = controlled_launcher(monkeypatch)
    with pytest.raises(ValueError):
        recovery.execute(plan)
    with pytest.raises(ValueError):
        watcher.maybe_auto_recover(fault())
    assert isolated.state.read_bytes() == before and not launched


def test_duplicate_recovery_keys_are_not_a_budget_reset(isolated, monkeypatch):
    before = b'{"runtime_18434":{"attempts":3,"attempts":0}}'
    isolated.state.write_bytes(before)
    plan, launched = controlled_launcher(monkeypatch)
    with pytest.raises(ValueError, match="duplicate"):
        recovery.execute(plan)
    assert isolated.state.read_bytes() == before and not launched


def test_failed_launch_reservation_prevents_process_start(isolated, monkeypatch):
    plan, launched = controlled_launcher(monkeypatch)
    monkeypatch.setattr(
        recovery,
        "_write_state",
        lambda *args: (_ for _ in ()).throw(OSError("reservation failure")),
    )
    with pytest.raises(OSError, match="reservation"):
        recovery.execute(plan)
    assert not launched and not isolated.state.exists()


def test_log_write_failure_is_visible_and_retains_launch_reservation(
    isolated, monkeypatch
):
    plan, launched = controlled_launcher(monkeypatch)
    isolated.log.mkdir()  # an unwriteable log target, not a real service fault
    with pytest.raises(OSError):
        recovery.execute(plan)
    assert launched == [321]
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert row["in_flight"] is True and row["attempts"] == 1


@pytest.mark.parametrize("healthy", [True, False])
def test_manual_verification_then_automatic_tick_has_one_terminal(
    isolated, monkeypatch, healthy
):
    plan, launched = controlled_launcher(monkeypatch)
    monkeypatch.setattr(recovery, "ENDPOINTS", {"runtime_18434": ("test:a", "test:b")})
    monkeypatch.setattr(recovery, "_answers", lambda url: healthy)
    assert recovery.execute(plan)["ok"] is True
    assert (
        recovery.verify("runtime_18434", timeout=2, interval=1)["verified"] is healthy
    )
    watcher.maybe_auto_recover(
        {
            "runtime_18434": {
                "state": "OK" if healthy else "ALARM",
                "recovery": {"available": True},
            }
        }
    )
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert row["pending"] is False and row["failures"] == (0 if healthy else 1)
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(event["phase"] in {"verified", "failed"} for event in events) == 1
    assert launched == [321]


def test_automatic_settlement_first_cannot_double_count_manual_verification(
    isolated, monkeypatch
):
    plan, _ = controlled_launcher(monkeypatch)
    monkeypatch.setattr(recovery, "ENDPOINTS", {"runtime_18434": ("test:a",)})
    monkeypatch.setattr(recovery, "_answers", lambda url: False)
    assert recovery.execute(plan)["ok"] is True
    fired = []

    def sleep(delay):
        isolated.clock[0] += delay
        if not fired:
            fired.append(True)
            watcher.maybe_auto_recover({"runtime_18434": {"state": "ALARM"}})

    monkeypatch.setattr(recovery.time, "sleep", sleep)
    assert (
        recovery.verify("runtime_18434", timeout=300, interval=300)["verified"] is False
    )
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert row["failures"] == 1
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(event["phase"] in {"verified", "failed"} for event in events) == 1


def test_old_observer_cannot_clear_a_new_launch(isolated, monkeypatch):
    plan, launched = controlled_launcher(monkeypatch)
    recovery.execute(plan)
    first = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"][
        "attempt_id"
    ]
    assert recovery.finish_attempt("runtime_18434", first, False) is True
    isolated.clock[0] += 1201
    recovery.execute(plan)
    assert recovery.finish_attempt("runtime_18434", first, True) is False
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert (
        row["attempt_id"] != first and row["pending"] is True and row["attempts"] == 2
    )
    assert len(launched) == 2


@pytest.mark.parametrize("healthy", [True, False])
def test_manual_http_result_requires_verified_health(monkeypatch, healthy):
    from tools import serve_site

    sent = []
    monkeypatch.setattr(
        recovery,
        "plan",
        lambda name: recovery.RecoveryPlan(name, "start", "test", True),
    )
    monkeypatch.setattr(
        recovery, "execute", lambda plan: {"ok": True, "attempted": True, "pid": 321}
    )
    monkeypatch.setattr(recovery, "verify", lambda name: {"verified": healthy})
    handler = SimpleNamespace(
        path="/api/restart/svc", _send=lambda result, **kwargs: sent.append(result)
    )
    serve_site.Handler.do_POST(handler)
    assert sent[0]["ok"] is healthy and sent[0]["attempted"] is True


def test_terminal_event_survives_state_commit_failure_without_duplicate(
    isolated, monkeypatch
):
    plan, _ = controlled_launcher(monkeypatch)
    recovery.execute(plan)
    token = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"][
        "attempt_id"
    ]
    with monkeypatch.context() as patch:
        patch.setattr(
            recovery,
            "_write_state",
            lambda *args: (_ for _ in ()).throw(OSError("terminal state failure")),
        )
        with pytest.raises(OSError, match="terminal state"):
            recovery.finish_attempt("runtime_18434", token, False)
    assert (
        json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"][
            "pending"
        ]
        is True
    )
    # First recorded outcome wins even if another observer now sees a different state.
    assert recovery.finish_attempt("runtime_18434", token, True) is True
    row = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"]
    assert row["pending"] is False and row["failures"] == 1 and row["ok"] is False
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(event["phase"] in {"verified", "failed"} for event in events) == 1


def test_terminal_log_publication_failure_preserves_journal_and_pending(
    isolated, monkeypatch
):
    from framework import artifacts

    plan, _ = controlled_launcher(monkeypatch)
    recovery.execute(plan)
    token = json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"][
        "attempt_id"
    ]
    before = isolated.log.read_bytes()
    original = artifacts.os.replace

    def fail_log(source, target):
        if str(target) == str(isolated.log):
            raise OSError("journal publication failure")
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(artifacts.os, "replace", fail_log)
        with pytest.raises(OSError, match="journal"):
            recovery.finish_attempt("runtime_18434", token, False)
    assert isolated.log.read_bytes() == before
    assert (
        json.loads(isolated.state.read_text(encoding="utf-8"))["runtime_18434"][
            "pending"
        ]
        is True
    )
    recovery.finish_attempt("runtime_18434", token, False)
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(events) == 2


def test_concurrent_journal_writers_preserve_all_events(isolated):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda number: recovery.log_terminal(str(number), "recovered"), range(8)
            )
        )
    events = [
        json.loads(line)
        for line in isolated.log.read_text(encoding="utf-8").splitlines()
    ]
    assert {event["service"] for event in events} == {
        str(number) for number in range(8)
    }
