"""Regressions for false-green self-audits and unsafe onboarding."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools import bootstrap_project, record_self_audit


def _record():
    return {
        "chains": {"total": 1, "pass": 1, "skip": 0, "fail": 0},
        "coverage_total": 75,
        "gate_s": {"fixture_status": "PASS"},
        "self_gate_s": {"status": "PASS", "open_objections": 0},
        "exit_codes": {"chains": 0, "gate_s": 0, "self_gate_s": 0,
                       "tests": 0, "test_collection": 0},
    }


@pytest.mark.parametrize("stage", ["tests", "test_collection", "gate_s", "self_gate_s", "chains"])
def test_failed_measurement_cannot_pass_an_unchanged_baseline(tmp_path, monkeypatch, stage):
    record = _record()
    record["exit_codes"][stage] = 1
    out = tmp_path / "record.json"
    out.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(record_self_audit, "OUT", out)
    monkeypatch.setattr(record_self_audit, "collect", lambda: copy.deepcopy(record))
    assert record_self_audit.main(["--check"]) == 1


def test_failed_measurement_does_not_overwrite_last_record(tmp_path, monkeypatch):
    record = _record()
    record["exit_codes"]["tests"] = 1
    out = tmp_path / "record.json"
    out.write_text("last good evidence", encoding="utf-8")
    monkeypatch.setattr(record_self_audit, "OUT", out)
    monkeypatch.setattr(record_self_audit, "collect", lambda: record)
    assert record_self_audit.main([]) == 1
    assert out.read_text(encoding="utf-8") == "last good evidence"


def test_self_audit_records_actual_test_exit_and_counts(monkeypatch):
    def run(cmd, timeout=900):
        if "--collect-only" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "3 tests collected", "")
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "coverage", "")
        if "run" in cmd and "coverage" in cmd:
            assert "--source=framework" in cmd
            return subprocess.CompletedProcess(cmd, 1, "1 failed, 2 passed in 0.1s", "")
        if "report" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "TOTAL 100 25 75%", "")
        if "tools/audit_chains.py" in cmd:
            return subprocess.CompletedProcess(cmd, 0, '[{"status":"PASS"}]', "")
        return subprocess.CompletedProcess(cmd, 0, '{"status":"PASS","findings":[]}', "")
    monkeypatch.setattr(record_self_audit, "_run", run)
    record = record_self_audit.collect()
    assert record["exit_codes"]["tests"] == 1
    assert record["tests"]["passed"] == 2
    assert record["tests"]["failed"] == 1
    assert "1 failed" in record["diagnostics"]["tests"]


@pytest.mark.parametrize("summary, expected", [
    ("1 error in 0.1s", 1),
    ("2 errors in 0.1s", 2),
    ("3 passed in 0.1s", 0),
])
def test_self_audit_counts_singular_and_plural_errors(monkeypatch, summary, expected):
    def run(cmd, timeout=900):
        if "--collect-only" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "3 tests collected", "")
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "coverage unavailable")
        if "pytest" in cmd:
            return subprocess.CompletedProcess(cmd, 1 if expected else 0, "", summary)
        if "tools/audit_chains.py" in cmd:
            return subprocess.CompletedProcess(cmd, 0, '[{"status":"PASS"}]', "")
        return subprocess.CompletedProcess(cmd, 0, '{"status":"PASS","findings":[]}', "")

    monkeypatch.setattr(record_self_audit, "_run", run)
    record = record_self_audit.collect()
    assert record["tests"]["errors"] == expected
    assert record["exit_codes"]["tests"] == (1 if expected else 0)


@pytest.fixture
def bootstrap(tmp_path, monkeypatch):
    template = tmp_path / "template"
    (template / "docs").mkdir(parents=True)
    (template / "docs/evidence.json").write_text("stale", encoding="utf-8")
    (template / "README.md").write_text("template", encoding="utf-8")
    root = tmp_path / "framework"
    root.mkdir()
    monkeypatch.setattr(bootstrap_project, "ROOT", root)
    monkeypatch.setattr(bootstrap_project, "TEMPLATE", template)
    return root


@pytest.mark.parametrize("name", ["../escape", "bad/name", "bad\nroot: elsewhere", "Bad Name"])
def test_bootstrap_rejects_names_before_creating_files(bootstrap, tmp_path, name):
    dest = tmp_path / "study"
    assert bootstrap_project.main(["--name", name, "--dest", str(dest)]) != 0
    assert not dest.exists()


def test_bootstrap_preserves_existing_registration(bootstrap, tmp_path):
    spec = bootstrap / "projects/study/project.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("existing project", encoding="utf-8")
    dest = tmp_path / "study"
    assert bootstrap_project.main(["--name", "study", "--dest", str(dest)]) != 0
    assert spec.read_text(encoding="utf-8") == "existing project"
    assert not dest.exists()


def test_bootstrap_can_use_an_existing_empty_directory(bootstrap, tmp_path):
    dest = tmp_path / "study"
    dest.mkdir()
    assert bootstrap_project.main(["--name", "study", "--dest", str(dest)]) == 0
    assert (dest / "README.md").is_file()
    assert not (dest / "docs/evidence.json").exists()


def test_bootstrap_uses_cross_volume_root_helper(bootstrap, tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap_project, "_root_field", lambda dest, registry: "X:/study")
    dest = tmp_path / "study"
    assert bootstrap_project.main(["--name", "study", "--dest", str(dest)]) == 0
    spec = bootstrap / "projects/study/project.yaml"
    assert "X:/study" in spec.read_text(encoding="utf-8")


@pytest.mark.parametrize("directory", ["study # cohort", "研究 # 第二组", "study 'quoted'"])
def test_bootstrap_round_trips_valid_destination_paths(bootstrap, tmp_path, directory):
    dest = tmp_path / directory
    assert bootstrap_project.main(["--name", "study", "--dest", str(dest)]) == 0
    spec = bootstrap / "projects/study/project.yaml"
    registration = yaml.safe_load(spec.read_text(encoding="utf-8"))
    assert (spec.parent / registration["root"]).resolve() == dest.resolve()
    assert registration["gate_command"] == ["python", "build_evidence.py"]
    assert registration["test_command"] == ["python", "build_evidence.py"]
    assert registration["expects"] == ["docs/evidence.json"]
    assert registration["expected_gate_s"] == "PASS"
