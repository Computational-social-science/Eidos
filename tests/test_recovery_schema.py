"""The recovery log is a schema, not free text: writers are checked, readers can trust them."""

import pytest

import framework.recovery as recovery


def test_an_attempt_must_name_the_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "LOG", tmp_path / "recoveries.jsonl")
    with pytest.raises(ValueError, match="pid"):
        recovery._log("svc", "start", "attempt", True)


def test_a_terminal_row_must_carry_an_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "LOG", tmp_path / "recoveries.jsonl")
    with pytest.raises(ValueError, match="outcome"):
        recovery._log("svc", "verify", "verified", True)


def test_log_terminal_derives_ok(tmp_path, monkeypatch):
    import json
    log = tmp_path / "recoveries.jsonl"
    monkeypatch.setattr(recovery, "LOG", log)
    recovery.log_terminal("svc", "recovered")
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["phase"] == "verified" and row["ok"] is True and row["outcome"] == "recovered"


def test_a_port_that_already_has_a_listener_is_not_started_on_twice(tmp_path, monkeypatch):
    """Five llama-server processes accumulated on :18434 because each attempt started a new one."""
    monkeypatch.setattr(recovery, "LOG", tmp_path / "recoveries.jsonl")
    monkeypatch.setattr(recovery, "STATE", tmp_path / "recovery_state.json")
    monkeypatch.setattr(recovery, "preflight", lambda service: {
        "service": service, "healthy": False, "conflict": False, "owned_by_self": True,
        "ports": {"18434": {"pid": 4242, "name": "llama-server.exe"}},
    })
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    plan = recovery.RecoveryPlan("runtime_18434", "start", "description", True)
    result = recovery.execute(plan)
    assert result["skipped"] is True and result["ok"] is False
    assert "already held" in result["reason"]


def test_preflight_reads_the_machine_without_raising():
    """It probes ports and process names on every recovery attempt; an UnboundLocalError there made
    every repair fail before it started, and the traceback pointed at a variable that looked local."""
    report = recovery.preflight("decision_service")
    assert report["service"] == "decision_service"
    assert "ports" in report and "healthy" in report
