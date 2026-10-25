"""Sensing, trying and promoting are separate powers; these tests keep them separate.

No network and no installs: the fetcher is injected, and a try record is written by hand. What
is being tested is the contract — a pin only moves on evidence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import framework.updates as updates


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, "LOCK", tmp_path / "lock.json")
    monkeypatch.setattr(updates, "SENSE", tmp_path / "updates.json")
    monkeypatch.setattr(updates, "EVENTS", tmp_path / "updates.jsonl")
    monkeypatch.setattr(updates, "TRIES", tmp_path / "tries")
    updates.save_lock({"pins": {"dvc": {"version": "3.67.1"}}, "history": []})
    return tmp_path


def test_sense_reports_what_it_does_not_change(store):
    def fetch(url):
        if "pypi" in url:
            return {"info": {"version": "3.68.0"}}
        return {}

    report = updates.sense(fetch=fetch)
    assert report["items"]["dvc"]["state"] == "behind"
    assert report["items"]["dvc"]["available"] == "3.68.0"
    # the pin is untouched: sensing has no authority
    assert updates.load_lock()["pins"]["dvc"]["version"] == "3.67.1"


def test_sense_marks_an_unreachable_source_as_unknown(store):
    def fetch(url):
        raise TimeoutError("no route")

    report = updates.sense(fetch=fetch)
    assert report["items"]["dvc"]["state"] == "unknown"
    assert report["items"]["dvc"]["available"] is None


def test_offline_sense_asks_nobody(store):
    called = []
    report = updates.sense(fetch=lambda url: called.append(url) or {}, offline=True)
    assert called == []
    assert report["offline"] is True


def test_promote_refuses_without_a_passing_try(store):
    with pytest.raises(PermissionError, match="no passing try"):
        updates.promote("dvc", "3.68.0")


def test_promote_refuses_a_failed_try(store):
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.68.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.68.0", "ok": False}),
        encoding="utf-8")
    with pytest.raises(PermissionError):
        updates.promote("dvc", "3.68.0")


def test_promote_refuses_stale_evidence(store):
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    old = time.time() - updates.TRY_TTL - 60
    stamp = updates.datetime.datetime.fromtimestamp(old, updates.datetime.timezone.utc).isoformat()
    (updates.TRIES / "dvc-3.68.0.json").write_text(json.dumps(
        {"ts": stamp, "name": "dvc", "version": "3.68.0", "ok": True}), encoding="utf-8")
    with pytest.raises(PermissionError, match="no passing try"):
        updates.promote("dvc", "3.68.0")


def test_promote_moves_the_pin_and_records_history(store, monkeypatch):
    monkeypatch.setattr(updates, "_bump_framework", lambda kind, why: None)
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.68.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.68.0", "ok": True}), encoding="utf-8")
    pin = updates.promote("dvc", "3.68.0", note="test")
    assert pin["version"] == "3.68.0"
    lock = updates.load_lock()
    assert lock["pins"]["dvc"]["version"] == "3.68.0"
    assert lock["history"][-1]["from"]["version"] == "3.67.1"
    events = [json.loads(l) for l in updates.EVENTS.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["kind"] == "promote"


def test_rollback_restores_the_previous_pin(store, monkeypatch):
    monkeypatch.setattr(updates, "_bump_framework", lambda kind, why: None)
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.68.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.68.0", "ok": True}), encoding="utf-8")
    updates.promote("dvc", "3.68.0")
    pin = updates.rollback("dvc")
    assert pin["version"] == "3.67.1"
    assert updates.load_lock()["pins"]["dvc"]["version"] == "3.67.1"


def test_rollback_without_history_says_so(store):
    with pytest.raises(LookupError):
        updates.rollback("dvc")


def test_version_order_compares_the_numbers_not_the_strings(store):
    assert updates._compare("b11876", "b11671") == 1
    assert updates._compare("3.9.0", "3.10.0") == -1
    assert updates._compare("1.10.19", "1.10.19") == 0


def test_promote_refuses_a_downgrade(store):
    # A passing try proves the candidate runs; it does not prove it is newer.
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.67.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.67.0", "ok": True}), encoding="utf-8")
    with pytest.raises(PermissionError, match="older than the pinned"):
        updates.promote("dvc", "3.67.0")


def test_a_downgrade_can_be_intended(store):
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.67.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.67.0", "ok": True}), encoding="utf-8")
    pin = updates.promote("dvc", "3.67.0", note="3.67.1 breaks the render stage",
                          allow_downgrade=True)
    assert pin["version"] == "3.67.0"


def test_a_promotion_bumps_the_framework_minor(store, monkeypatch):
    monkeypatch.setattr(updates, "_bump_framework", lambda kind, why: f"minor:{kind}:{why}")
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.68.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.68.0", "ok": True}), encoding="utf-8")
    updates.promote("dvc", "3.68.0")
    assert updates.load_lock()["framework_version"]["version"].startswith("minor:minor")


def test_a_rollback_bumps_the_framework_patch(store, monkeypatch):
    calls = []
    monkeypatch.setattr(updates, "_bump_framework", lambda kind, why: calls.append(kind) or "x")
    updates.TRIES.mkdir(parents=True, exist_ok=True)
    (updates.TRIES / "dvc-3.68.0.json").write_text(json.dumps(
        {"ts": updates._now(), "name": "dvc", "version": "3.68.0", "ok": True}), encoding="utf-8")
    updates.promote("dvc", "3.68.0")
    updates.rollback("dvc")
    assert calls == ["minor", "patch"]


def test_a_redirected_lock_cannot_touch_the_real_version(store):
    # The guard that stopped a test run from bumping pyproject three times.
    assert updates._bump_framework("minor", "test") is None
