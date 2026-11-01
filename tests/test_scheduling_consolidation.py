"""Avoid duplicate work while preserving negative health evidence and real errors."""

from datetime import datetime, timezone, timedelta
import json
import subprocess
from types import SimpleNamespace

import pytest


def test_watchdog_notifies_incident_changes_and_recovery_without_faking_health(
    tmp_path, monkeypatch, capsys
):
    from tools import cron_entry, bounded_process

    monkeypatch.setattr(cron_entry, "ROOT", tmp_path)
    monkeypatch.setattr(cron_entry, "runtime", lambda: {"PYTHON": "project-python"})
    state = {"healthy": False, "key": "same-outage", "problem": "sample is 300s old"}

    def run(*args, **kwargs):
        healthy = state["healthy"]
        return subprocess.CompletedProcess(
            args,
            0 if healthy else 1,
            json.dumps(
                {
                    "schema": 1,
                    "check_completed": True,
                    "healthy": healthy,
                    "incident_key": state["key"],
                    "verdict": "OK" if healthy else "STALE",
                    "problems": [] if healthy else [state["problem"]],
                }
            ),
            "",
        )

    monkeypatch.setattr(bounded_process, "run_tree", run)
    assert cron_entry.main(["watchdog"]) == 0
    assert "ALARM" in capsys.readouterr().out
    receipt = tmp_path / "docs/status/cron-watchdog.json"
    saved = json.loads(receipt.read_text())
    assert (
        saved["ok"] is False
        and saved["execution_ok"] is True
        and saved["exit_code"] == 1
    )
    state["problem"] = "sample is 600s old"
    assert cron_entry.main(["watchdog"]) == 0 and capsys.readouterr().out == ""
    assert json.loads(receipt.read_text())["health"]["problems"] == [
        "sample is 600s old"
    ]
    state["key"] = "another-outage"
    assert cron_entry.main(["watchdog"]) == 0 and "ALARM" in capsys.readouterr().out
    state.update(healthy=True, key="healthy")
    assert cron_entry.main(["watchdog"]) == 0 and "RECOVERED" in capsys.readouterr().out
    assert cron_entry.main(["watchdog"]) == 0 and capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "output,code",
    [
        ("", 0),
        ("[]", 0),
        ('{"healthy":true}', 0),
        (
            json.dumps(
                {
                    "schema": 1,
                    "check_completed": True,
                    "healthy": False,
                    "problems": ["bad"],
                    "incident_key": "bad",
                }
            ),
            0,
        ),
    ],
)
def test_invalid_watchdog_output_remains_an_execution_failure(
    tmp_path, monkeypatch, output, code
):
    from tools import cron_entry, bounded_process

    monkeypatch.setattr(cron_entry, "ROOT", tmp_path)
    monkeypatch.setattr(cron_entry, "runtime", lambda: {"PYTHON": "project-python"})
    monkeypatch.setattr(
        bounded_process,
        "run_tree",
        lambda *a, **k: subprocess.CompletedProcess(a, code, output, ""),
    )
    assert cron_entry.main(["watchdog"]) == 1
    data = json.loads((tmp_path / "docs/status/cron-watchdog.json").read_text())
    assert data["ok"] is False and data["execution_ok"] is False


def test_watchdog_json_distinguishes_stale_data_and_preserves_cli_failure(
    tmp_path, monkeypatch, capsys
):
    from tools import watchdog

    monkeypatch.setattr(watchdog, "CURRENT", tmp_path / "current.json")
    monkeypatch.setattr(watchdog, "STATE", tmp_path / "watchdog.json")
    monkeypatch.setattr(watchdog, "LOG", tmp_path / "watchdog.log")
    current = tmp_path / "current.json"

    def sample(seconds, seq):
        current.write_text(
            json.dumps(
                {
                    "ts": (
                        datetime.now(timezone.utc) - timedelta(seconds=seconds)
                    ).isoformat(),
                    "seq": seq,
                    "overall": "OK",
                }
            )
        )

    sample(300, 1)
    assert watchdog.main(["--json"]) == 1
    first = json.loads(capsys.readouterr().out)
    sample(600, 1)
    assert watchdog.main(["--json"]) == 1
    second = json.loads(capsys.readouterr().out)
    assert first["incident_key"] == second["incident_key"] and first["healthy"] is False
    sample(0, 2)
    assert watchdog.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["healthy"] is True


def test_manual_refresh_does_not_overlap_background_reverification(
    tmp_path, monkeypatch
):
    from tools import serve_site
    import framework.project as project

    spec = SimpleNamespace(available=True, gate_command=["worker"], root=tmp_path)
    monkeypatch.setattr(project, "load_projects", lambda **kw: {"p": spec})
    monkeypatch.setattr(
        project, "run_command", lambda *a, **kw: pytest.fail("overlapping gate started")
    )
    with serve_site.PIPELINE_LOCK:
        assert serve_site.refresh_project("p")["busy"] is True
    assert serve_site.REFRESH_LOCKS["p"].acquire(blocking=False)
    serve_site.REFRESH_LOCKS["p"].release()


def test_unchanged_verified_consumers_are_reused_without_renewing_timestamps(
    tmp_path, monkeypatch
):
    from tools import build_pipeline, consumer_snapshot
    import framework.project as project

    spec = SimpleNamespace()
    monkeypatch.setattr(
        consumer_snapshot,
        "capture_inputs",
        lambda *a: {"digest": "same", "error": None},
    )
    monkeypatch.setattr(project, "load_projects", lambda **kw: {"p": spec})
    monkeypatch.setattr(
        build_pipeline.subprocess,
        "run",
        lambda *a, **kw: pytest.fail("redundant consumer check"),
    )
    cached = {
        "name": "p",
        "gate_s": "PASS",
        "input_digest": "same",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    assert build_pipeline.consumers(cached=[cached]) == [cached]


@pytest.mark.parametrize("seq", [None, 0, False, -1, "2"])
def test_watchdog_cannot_call_an_invalid_sequence_healthy(
    tmp_path, monkeypatch, capsys, seq
):
    from tools import watchdog

    monkeypatch.setattr(watchdog, "CURRENT", tmp_path / "current.json")
    monkeypatch.setattr(watchdog, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(watchdog, "LOG", tmp_path / "log.jsonl")
    (tmp_path / "current.json").write_text(
        json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), "seq": seq, "overall": "OK"}
        )
    )
    assert watchdog.main(["--json"]) == 1
    assert json.loads(capsys.readouterr().out)["healthy"] is False


def test_invalid_sequence_checkpoint_cannot_reset_stall_age_forever(
    tmp_path, monkeypatch, capsys
):
    from tools import watchdog

    monkeypatch.setattr(watchdog, "CURRENT", tmp_path / "current.json")
    monkeypatch.setattr(watchdog, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(watchdog, "LOG", tmp_path / "log.jsonl")
    (tmp_path / "current.json").write_text(
        json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), "seq": 2, "overall": "OK"}
        )
    )
    (tmp_path / "state.json").write_text('{"seq":2,"checked":"invalid"}')
    assert watchdog.main(["--json"]) == 1
    assert json.loads(capsys.readouterr().out)["healthy"] is False
    state = json.loads((tmp_path / "state.json").read_text())
    state["checked"] = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    (tmp_path / "state.json").write_text(json.dumps(state))
    assert watchdog.main(["--json"]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "STALE"


def test_same_kind_checks_cannot_complete_out_of_order(tmp_path, monkeypatch):
    import threading
    from tools import cron_entry, bounded_process

    monkeypatch.setattr(cron_entry, "ROOT", tmp_path)
    monkeypatch.setattr(cron_entry, "runtime", lambda: {"PYTHON": "project-python"})
    entered, release = threading.Event(), threading.Event()
    count = []

    def run(*args, **kwargs):
        count.append(1)
        entered.set()
        assert release.wait(5)
        return subprocess.CompletedProcess(
            args,
            1,
            json.dumps(
                {
                    "schema": 1,
                    "check_completed": True,
                    "healthy": False,
                    "verdict": "ALARM",
                    "problems": ["actual fault"],
                    "incident_key": "fault",
                }
            ),
            "",
        )

    monkeypatch.setattr(bounded_process, "run_tree", run)
    results = []
    worker = threading.Thread(
        target=lambda: results.append(cron_entry.main(["watchdog"]))
    )
    worker.start()
    try:
        assert entered.wait(2)
        assert cron_entry.main(["watchdog"]) == 75
        assert len(count) == 1
    finally:
        release.set()
        worker.join(5)
    assert results == [0]
    receipt = json.loads((tmp_path / "docs/status/cron-watchdog.json").read_text())
    assert receipt["ok"] is False and receipt["health"]["verdict"] == "ALARM"


@pytest.mark.parametrize(
    "healthy,verdict,code,problems", [(True, "ALARM", 0, []), (False, "OK", 1, ["bad"])]
)
def test_watchdog_verdict_must_agree_with_healthy(
    tmp_path, monkeypatch, healthy, verdict, code, problems
):
    from tools import cron_entry, bounded_process

    monkeypatch.setattr(cron_entry, "ROOT", tmp_path)
    monkeypatch.setattr(cron_entry, "runtime", lambda: {"PYTHON": "project-python"})
    payload = json.dumps(
        {
            "schema": 1,
            "check_completed": True,
            "healthy": healthy,
            "verdict": verdict,
            "problems": problems,
            "incident_key": "key",
        }
    )
    monkeypatch.setattr(
        bounded_process,
        "run_tree",
        lambda *a, **k: subprocess.CompletedProcess(a, code, payload, ""),
    )
    assert cron_entry.main(["watchdog"]) == 1


@pytest.mark.parametrize("verdict", [[], {}, None])
def test_nonstrings_in_watchdog_verdict_are_recorded_as_errors(
    tmp_path, monkeypatch, verdict
):
    from tools import cron_entry, bounded_process

    monkeypatch.setattr(cron_entry, "ROOT", tmp_path)
    monkeypatch.setattr(cron_entry, "runtime", lambda: {"PYTHON": "project-python"})
    payload = json.dumps(
        {
            "schema": 1,
            "check_completed": True,
            "healthy": True,
            "verdict": verdict,
            "problems": [],
            "incident_key": "key",
        }
    )
    monkeypatch.setattr(
        bounded_process,
        "run_tree",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, payload, ""),
    )
    assert cron_entry.main(["watchdog"]) == 1
    assert (
        json.loads((tmp_path / "docs/status/cron-watchdog.json").read_text())[
            "execution_ok"
        ]
        is False
    )


@pytest.mark.parametrize("digest,hours", [("changed", 0), ("same", 25)])
def test_changed_or_expired_consumers_are_rechecked(
    tmp_path, monkeypatch, digest, hours
):
    from framework.project import ProjectSpec
    from tools import build_pipeline, consumer_snapshot

    spec = ProjectSpec(
        "p",
        tmp_path,
        ["python", "gate.py"],
        validity_register="analysis/CLAIMS.yaml",
        validity_document="docs/REPORT.md",
        expected_gate_s="PASS",
    )
    monkeypatch.setattr(
        consumer_snapshot,
        "capture_inputs",
        lambda *a: {"digest": digest, "error": None},
    )
    calls = []

    def check(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(
            args, 1, json.dumps({"status": "FAIL", "findings": ["new finding"]}), ""
        )

    monkeypatch.setattr(build_pipeline.subprocess, "run", check)
    checked = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cached = {
        "name": "p",
        "gate_s": "PASS",
        "input_digest": "same",
        "checked_at": checked,
    }
    rows = build_pipeline.consumers({"p": spec}, cached=[cached])
    assert len(calls) == 1 and rows[0]["gate_s"] == "FAIL"
    assert rows[0]["checked_at"] != checked
