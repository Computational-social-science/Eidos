"""An exited worker or ambiguous response cannot serve as tracking evidence."""

import json
from pathlib import Path
import subprocess

import pytest

from framework import tracking


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {
            "kind": "eidos.tracking.operation",
            "operation": "another",
            "result": "unbound",
        },
    ],
)
def test_empty_or_unbound_worker_response_refused(tmp_path, monkeypatch, payload):
    def worker(arguments, **kwargs):
        if payload is not None:
            Path(arguments[-1]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(tracking, "run_tree", worker)
    with pytest.raises((ValueError, FileNotFoundError)):
        tracking._operation(tmp_path, "probe", 1)


def test_source_change_refuses_an_otherwise_successful_worker(tmp_path, monkeypatch):
    records = iter([{"source": "before"}, {"source": "after"}])
    monkeypatch.setattr(tracking, "_code_fingerprints", lambda: next(records))

    def worker(arguments, **kwargs):
        Path(arguments[-1]).write_text(
            json.dumps(
                {
                    "kind": "eidos.tracking.operation",
                    "operation": "probe",
                    "result": "looks successful",
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(tracking, "run_tree", worker)
    with pytest.raises(ValueError, match="source changed"):
        tracking._operation(tmp_path, "probe", 1)


def test_duplicate_yaml_refused_without_disabling_merges():
    with pytest.raises(ValueError, match="duplicate"):
        tracking._load_yaml("outs: [{md5: first, md5: second}]")


def test_template_snapshot_and_utf8_atomic_roundtrip(tmp_path):
    registry = tracking.ExperimentRegistry(None)
    source = {"params": {"seed": 19}, "note": "实验"}
    registry.register_template("template", source)
    source["params"]["seed"] = 99
    assert registry.templates["template"]["params"]["seed"] == 19
    destination = tmp_path / "template.json"
    registry.save_template("template", destination)
    restored = tracking.ExperimentRegistry(None)
    restored.load_template("restored", destination)
    assert restored.templates["restored"]["note"] == "实验"
    with pytest.raises(ValueError, match="Unknown"):
        registry.save_template("missing", destination)
    assert json.loads(destination.read_text(encoding="utf-8"))["params"]["seed"] == 19


@pytest.mark.parametrize("flag", ["MLFLOW_AVAILABLE", "DVC_AVAILABLE"])
def test_optional_dependency_is_skipped_before_spawning(flag, monkeypatch):
    from tools import audit_chains

    monkeypatch.setattr(tracking, flag, False)
    monkeypatch.setattr(
        tracking,
        "_operation",
        lambda *args, **kwargs: pytest.fail("worker must not start"),
    )
    with pytest.raises(ImportError, match="not installed"):
        audit_chains.audit_tracking()


@pytest.mark.parametrize(
    "uri", ["databricks", "databricks-uc", "https://tracking.example.invalid"]
)
def test_remote_tracking_locator_is_not_changed_into_a_local_path(tmp_path, uri):
    assert tracking._store_uri(uri, tmp_path) == uri
