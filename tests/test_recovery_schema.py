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
