"""A cached scientific verdict must describe the inputs that were actually checked."""
import json
import subprocess
import threading

import pytest

from framework.project import ProjectSpec


def consumer(tmp_path):
    root = tmp_path / "consumer"
    (root / "docs").mkdir(parents=True)
    (root / "analysis").mkdir()
    (root / "analysis/CLAIMS.yaml").write_text(
        "claims:\n- id: C1\n  evidence:\n    file: docs/result.json\n", encoding="utf-8")
    (root / "docs/result.json").write_text('{"value": true}', encoding="utf-8")
    (root / "docs/REPORT.md").write_text("Original claim", encoding="utf-8")
    return ProjectSpec("example", root, ["python", "gate.py"],
                       validity_register="analysis/CLAIMS.yaml",
                       validity_document="docs/REPORT.md", expected_gate_s="PASS")


def snapshot(spec, root):
    from tools.consumer_snapshot import capture_inputs, registry_digest
    return {"consumer_snapshot": {"schema": 1, "registry_digest": registry_digest({spec.name: spec})},
            "consumers": [{"name": spec.name, "gate_s": "PASS",
                           "input_digest": capture_inputs(spec, root)["digest"]}]}


@pytest.mark.parametrize("target", ["docs/result.json", "docs/REPORT.md", "analysis/CLAIMS.yaml"])
def test_changed_declared_input_revokes_old_verdict(tmp_path, target):
    from tools.consumer_snapshot import snapshot_state
    spec = consumer(tmp_path)
    saved = snapshot(spec, tmp_path)
    assert snapshot_state(saved, {spec.name: spec}, tmp_path)["stale"] == []
    path = spec.root / target
    path.write_text(path.read_text(encoding="utf-8") + "\nchanged", encoding="utf-8")
    assert spec.name in snapshot_state(saved, {spec.name: spec}, tmp_path)["stale"]


def test_registration_and_missing_checkout_cannot_reuse_pass(tmp_path):
    from dataclasses import replace
    from tools.consumer_snapshot import snapshot_state
    spec = consumer(tmp_path)
    saved = snapshot(spec, tmp_path)
    other = replace(spec, name="new-consumer")
    assert "new-consumer" in snapshot_state(saved, {spec.name: spec, other.name: other}, tmp_path)["stale"]
    changed = replace(spec, expected_gate_s="FAIL")
    assert spec.name in snapshot_state(saved, {spec.name: changed}, tmp_path)["stale"]
    missing = replace(spec, root=tmp_path / "absent", available=False)
    assert spec.name in snapshot_state(saved, {spec.name: missing}, tmp_path)["stale"]
    assert spec.name in snapshot_state(saved, {}, tmp_path)["stale"]


def test_gate_code_and_missing_binding_revoke_pass(tmp_path):
    from tools.consumer_snapshot import snapshot_state
    spec = consumer(tmp_path)
    saved = snapshot(spec, tmp_path)
    (tmp_path / "framework").mkdir()
    (tmp_path / "framework/gates.py").write_text("changed = True", encoding="utf-8")
    assert spec.name in snapshot_state(saved, {spec.name: spec}, tmp_path)["stale"]
    assert spec.name in snapshot_state({"consumers": saved["consumers"]}, {spec.name: spec}, tmp_path)["stale"]


def test_outside_project_reference_is_not_read(tmp_path):
    from tools.consumer_snapshot import capture_inputs
    spec = consumer(tmp_path)
    (spec.root / "analysis/CLAIMS.yaml").write_text("evidence:\n  file: ../outside.json\n", encoding="utf-8")
    result = capture_inputs(spec, tmp_path)
    assert result["digest"] is None and "outside" in result["error"]


@pytest.mark.parametrize("kind", ["support", "reproduction"])
def test_implicit_record_paths_use_the_gate_filename_normalization(tmp_path, kind):
    from tools.consumer_snapshot import capture_inputs
    spec = consumer(tmp_path)
    fields = "support: required" if kind == "support" else "reproduction: paper/1"
    (spec.root / "analysis/CLAIMS.yaml").write_text(f"claims:\n- id: C/1\n  {fields}\n", encoding="utf-8")
    path = (tmp_path / "artifacts/literature/support/C_1.json" if kind == "support"
            else spec.root / "artifacts/reproduction/paper_1.json")
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    before = capture_inputs(spec, tmp_path)["digest"]
    path.write_text('{"verdict":"FAIL"}', encoding="utf-8")
    assert before != capture_inputs(spec, tmp_path)["digest"]


def test_changed_input_card_withdraws_cached_pass(tmp_path):
    from tools.dashboard import consumer_strip
    spec = consumer(tmp_path)
    html = consumer_strip({"stale_consumers": [spec.name], "consumers": [
        {"name": spec.name, "root": str(spec.root), "gate_s": "PASS", "expected": "PASS"}]})
    assert 'data-stale="1"' in html and "cached verdict withdrawn" in html


def test_changed_inputs_during_audit_are_not_bound_to_old_pass(tmp_path, monkeypatch):
    from tools import build_pipeline
    import framework.project as project
    spec = consumer(tmp_path)
    monkeypatch.setattr(project, "load_projects", lambda **kw: {spec.name: spec})
    def audit(*args, **kwargs):
        (spec.root / "docs/result.json").write_text("false", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, '{"status":"PASS"}', "")
    monkeypatch.setattr(build_pipeline.subprocess, "run", audit)
    row = build_pipeline.consumers()[0]
    assert row["gate_s"] == "ERROR" and row["input_digest"] is None


def test_unsafe_inputs_prevent_the_audit_from_reading_them(tmp_path, monkeypatch):
    from tools import build_pipeline
    import framework.project as project
    spec = consumer(tmp_path)
    (spec.root / "analysis/CLAIMS.yaml").write_text("evidence:\n  file: ../outside.json\n", encoding="utf-8")
    monkeypatch.setattr(project, "load_projects", lambda *a, **kw: {spec.name: spec})
    def forbidden(*args, **kwargs):
        pytest.fail("unsafe input was passed to the audit")
    monkeypatch.setattr(build_pipeline.subprocess, "run", forbidden)
    assert build_pipeline.consumers()[0]["gate_s"] == "ERROR"
    from tools import build_site
    monkeypatch.setattr(build_site, "ROOT", tmp_path)
    assert build_site.registry()[0]["gate_s"] == "ERROR"


def test_exact_declared_shared_input_is_bound_but_other_external_files_are_rejected(tmp_path):
    from dataclasses import replace
    from tools.consumer_snapshot import capture_inputs
    spec = consumer(tmp_path)
    (tmp_path / "shared.json").write_text("{}", encoding="utf-8")
    (spec.root / "analysis/CLAIMS.yaml").write_text("evidence:\n  file: ../shared.json\n", encoding="utf-8")
    allowed = replace(spec, validity_external_inputs=["../shared.json"])
    before = capture_inputs(allowed, tmp_path)["digest"]
    assert before and capture_inputs(spec, tmp_path)["digest"] is None
    (tmp_path / "shared.json").write_text("false", encoding="utf-8")
    assert capture_inputs(allowed, tmp_path)["digest"] != before


def test_aliases_are_bounded_and_repeated_handles_retain_mtime(tmp_path):
    import os
    from tools.consumer_snapshot import capture_inputs
    spec = consumer(tmp_path)
    record = spec.root / "artifacts/reproduction/paper.json"
    record.parent.mkdir(parents=True)
    record.write_text("{}", encoding="utf-8")
    (spec.root / "analysis/CLAIMS.yaml").write_text(
        "loop: &loop {nested: *loop}\nclaims:\n- id: C1\n  reproduction: paper\n"
        "  evidence: {file: artifacts/reproduction/paper.json}\n", encoding="utf-8")
    before = capture_inputs(spec, tmp_path)["digest"]
    assert before
    os.utime(record, ns=(record.stat().st_atime_ns, record.stat().st_mtime_ns + 2_000_000_000))
    assert before != capture_inputs(spec, tmp_path)["digest"]


def test_refresh_available_project_with_an_unrelated_missing_checkout(tmp_path, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from tools import serve_site
    import framework.project as project
    spec = consumer(tmp_path)
    missing = replace(spec, name="missing", available=False)
    def load(*args, **kwargs):
        assert kwargs.get("allow_missing") is True
        return {spec.name: spec, missing.name: missing}
    monkeypatch.setattr(project, "load_projects", load)
    monkeypatch.setattr(project, "run_command", lambda *a, **kw: SimpleNamespace(status="PASS", stdout_tail=""))
    monkeypatch.setattr(serve_site, "run_pipeline", lambda **kw: subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(serve_site, "current_consumer_html", lambda: "checked")
    assert serve_site.refresh_project(spec.name)["ok"] is True


def test_one_unknown_consumer_does_not_hide_another_known_failure(tmp_path, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from tools import watch_pipeline
    from tools.consumer_snapshot import capture_inputs, registry_digest
    import framework.project as project
    import framework.quarto_bridge as bridge
    spec = consumer(tmp_path)
    failed = replace(spec, name="known-failure")
    specs = {spec.name: spec, failed.name: failed}
    saved = snapshot(spec, tmp_path)
    saved["consumers"].append({"name": failed.name, "gate_s": "FAIL",
                               "input_digest": capture_inputs(failed, tmp_path)["digest"]})
    saved["consumer_snapshot"]["registry_digest"] = registry_digest(specs)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/pipeline.json").write_text(json.dumps(saved), encoding="utf-8")
    specs[spec.name] = replace(spec, notes="changed after verification")
    monkeypatch.setattr(project, "load_projects", lambda **kw: specs)
    monkeypatch.setattr(watch_pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(watch_pipeline, "STATUS", tmp_path / "docs/status")
    monkeypatch.setattr(watch_pipeline, "http_json", lambda *a, **kw: (200, {"status": "ok"}))
    monkeypatch.setattr(watch_pipeline, "http_status", lambda *a, **kw: 200)
    monkeypatch.setattr(watch_pipeline, "_has_module", lambda *a: (True, "stub"))
    monkeypatch.setattr(bridge, "QuartoBridge", lambda *a: SimpleNamespace(quarto_available=True))
    measured = watch_pipeline.measure()
    assert measured["consumer_verdicts"]["value"] == 1
    assert measured["consumer_snapshot"]["value"] is None


def test_failed_atomic_publish_preserves_previous_snapshot(tmp_path, monkeypatch):
    from tools import consumer_snapshot
    target = tmp_path / "pipeline.json"
    target.write_text('{"previous": true}', encoding="utf-8")
    def fail(*args):
        raise PermissionError("locked")
    monkeypatch.setattr(consumer_snapshot.os, "replace", fail)
    with pytest.raises(PermissionError):
        consumer_snapshot.atomic_json(target, {"new": True})
    assert json.loads(target.read_text()) == {"previous": True}
    assert len(list(tmp_path.iterdir())) == 1


def test_reconciliation_is_single_flight_and_reports_failure(monkeypatch):
    from tools import serve_site
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setitem(serve_site.STATE, "last_reconcile", 0.0)
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return subprocess.CompletedProcess(args, 2, "", "error")
    monkeypatch.setattr(serve_site, "run_pipeline", slow)
    worker = serve_site.queue_reconciliation({"stale": ["example"]}, cooldown=0)
    try:
        assert entered.wait(2)
        assert serve_site.queue_reconciliation({"stale": ["example"]}, cooldown=0) is None
    finally:
        release.set()
        worker.join(5)
    assert "failed" in serve_site.STATE["reconcile_note"]


def test_reconciliation_timeout_releases_lock(monkeypatch):
    from tools import serve_site
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args, 300)
    monkeypatch.setattr(serve_site, "run_pipeline", timeout)
    worker = serve_site.queue_reconciliation({"stale": ["example"]}, cooldown=0)
    worker.join(5)
    assert "TimeoutExpired" in serve_site.STATE["reconcile_note"]
    assert serve_site.PIPELINE_LOCK.acquire(blocking=False)
    serve_site.PIPELINE_LOCK.release()


def test_self_audit_summary_reads_actual_schema():
    from tools.build_pipeline import audit_summary
    result = audit_summary({"self_gate_s": {"status": "PASS"}, "gate_s": {"fixture_status": "PASS"},
                            "chains": {"total": 11}, "tests": {"passed": 23, "failed": 2}})
    assert result == {"gate_s": "PASS", "fixture_status": "PASS", "chains": 11, "tests": 23}


def test_timeout_kills_a_real_descendant_not_only_its_parent(tmp_path):
    import sys
    import time
    from tools.bounded_process import run_tree
    ready, leaked = tmp_path / "ready", tmp_path / "leaked"
    child = tmp_path / "child.py"
    child.write_text("import time\nfrom pathlib import Path\n"
                     f"Path({str(ready)!r}).write_text('ready')\n"
                     "time.sleep(3)\n"
                     f"Path({str(leaked)!r}).write_text('leaked')\n", encoding="utf-8")
    parent = tmp_path / "parent.py"
    parent.write_text("import subprocess, sys, time\n"
                      f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
                      "time.sleep(30)\n", encoding="utf-8")
    with pytest.raises(subprocess.TimeoutExpired):
        run_tree([sys.executable, str(parent)], cwd=tmp_path, timeout=2)
    assert ready.exists(), "descendant must have actually started"
    time.sleep(1.5)
    assert not leaked.exists(), "descendant survived the timeout"
