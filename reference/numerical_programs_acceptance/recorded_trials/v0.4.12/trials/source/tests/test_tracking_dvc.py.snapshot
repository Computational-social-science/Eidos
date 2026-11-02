"""Actual local DVC data, cache and remote; no public cloud or user repository."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("dvc")

from framework import tracking
from framework.subprocesses import run_tree


@pytest.fixture(scope="module")
def dvc_space(tmp_path_factory):
    base = tmp_path_factory.mktemp("tracking-dvc")
    root, remote = base / "project", base / "remote"
    root.mkdir()
    remote.mkdir()
    with pytest.MonkeyPatch.context() as environment:
        for variable, name in [
            ("DVC_GLOBAL_CONFIG_DIR", "global"),
            ("DVC_SYSTEM_CONFIG_DIR", "system"),
            ("DVC_SITE_CACHE_DIR", "site-cache"),
        ]:
            directory = base / name
            directory.mkdir()
            environment.setenv(variable, str(directory))
        environment.setenv("DVC_NO_ANALYTICS", "1")
        for arguments in [
            ("init", "--no-scm"),
            ("remote", "add", "-d", "storage", str(remote)),
        ]:
            result = run_tree(
                [sys.executable, "-m", "dvc", *arguments], cwd=root, timeout=60
            )
            assert result.returncode == 0, result.stderr
        yield root, remote


def test_actual_registered_hash_and_content_addressed_url(dvc_space):
    root, remote = dvc_space
    data = root / "mixed-lines.txt"
    data.write_bytes(b"alpha\r\nbeta\n")
    versioner = tracking.DVCDataVersioner(root)
    metadata = versioner.add(data.name)
    expected = hashlib.md5(data.read_bytes()).hexdigest()
    assert metadata == root / "mixed-lines.txt.dvc"
    assert versioner.get_file_hash(data) == expected
    url = versioner.get_data_url(data.name)
    assert Path(url) == remote / "files/md5" / expected[:2] / expected[2:]
    assert not Path(
        url
    ).exists()  # A locator alone never claims that remote data exists.
    versioner.push()
    assert Path(url).read_bytes() == data.read_bytes()


def test_changed_data_rejected_even_when_stat_cache_would_look_unchanged(dvc_space):
    import os

    root, _ = dvc_space
    data = root / "mutation.txt"
    data.write_bytes(b"111111\n")
    versioner = tracking.DVCDataVersioner(root)
    versioner.add(data)
    expected = hashlib.md5(data.read_bytes()).hexdigest()
    before = data.stat()
    data.write_bytes(b"222222\n")
    os.utime(data, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises((ValueError, tracking.TrackingOperationError)):
        versioner.get_file_hash(data)
    assert versioner.get_file_hash(data, require_clean=False) == expected


def test_remove_tracking_keeps_original_data(dvc_space):
    root, _ = dvc_space
    data = root / "keep-data.txt"
    data.write_bytes(b"scientific data must survive untracking\n")
    versioner = tracking.DVCDataVersioner(root)
    metadata = versioner.add(data)
    versioner.remove(data.name)
    assert not metadata.exists()
    assert data.read_bytes() == b"scientific data must survive untracking\n"


def test_directory_version_is_not_a_status_word(dvc_space):
    root, _ = dvc_space
    directory = root / "dataset"
    directory.mkdir()
    (directory / "part.txt").write_bytes(b"a,b\n1,2\n")
    versioner = tracking.DVCDataVersioner(root)
    metadata = versioner.add(directory)
    import yaml

    expected = yaml.safe_load(metadata.read_text(encoding="utf-8"))["outs"][0]["md5"]
    assert expected.endswith(".dir")
    assert versioner.get_file_hash(directory) == expected
    original_stat = (directory / "part.txt").stat()
    (directory / "part.txt").write_bytes(b"a,b\n3,4\n")
    import os

    os.utime(
        directory / "part.txt",
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    with pytest.raises((ValueError, tracking.TrackingOperationError)) as refusal:
        versioner.get_file_hash(directory)
    assert "changed" in str(refusal.value) or "uncached DVC verification" in getattr(
        refusal.value, "stderr", ""
    )


@pytest.mark.parametrize("outside", ["../outside.csv", Path("../outside.csv")])
def test_outside_target_refused_before_command(dvc_space, outside, monkeypatch):
    root, _ = dvc_space
    versioner = tracking.DVCDataVersioner(root)
    monkeypatch.setattr(
        versioner, "_command", lambda *args: pytest.fail("DVC must not launch")
    )
    with pytest.raises(ValueError, match="inside"):
        versioner.add(outside)


def test_utf8_named_pipeline_stages_have_stable_list_contract(tmp_path):
    (tmp_path / "dvc.yaml").write_text(
        "stages:\n  训练:\n    cmd: python train.py\n", encoding="utf-8"
    )
    assert tracking.DVCDataVersioner(tmp_path).get_pipeline_stages() == [
        {"name": "训练", "cmd": "python train.py"}
    ]
    (tmp_path / "dvc.yaml").write_text("", encoding="utf-8")
    assert tracking.DVCDataVersioner(tmp_path).get_pipeline_stages() == []
    (tmp_path / "dvc.yaml").write_text("stages: []", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        tracking.DVCDataVersioner(tmp_path).get_pipeline_stages()


def test_dataset_artifact_matches_tracked_bytes_and_explicit_run(
    dvc_space, monkeypatch
):
    pytest.importorskip("mlflow")
    root, _ = dvc_space
    monkeypatch.chdir(root)
    tracker = tracking.ExperimentTracker(
        {"project_root": str(root), "experiment_name": "data"}
    )
    run = tracker.start_run("snapshot")
    data = root / "logged.txt"
    data.write_bytes(b"fixed dataset\n")
    result = tracker.log_dataset(run, data.name, "qualification")
    assert result["dvc_md5"] == hashlib.md5(data.read_bytes()).hexdigest()
    assert result["data_sha256"] == hashlib.sha256(data.read_bytes()).hexdigest()
    paths = {
        item.path
        for item in tracker.client.list_artifacts(run.run_id, "datasets/qualification")
    }
    assert paths == {
        "datasets/qualification/logged.txt",
        "datasets/qualification/logged.txt.dvc",
    }
    local = tracker.client.download_artifacts(run.run_id, result["artifact"])
    assert Path(local).read_bytes() == data.read_bytes()
    receipt = tracker.client.download_artifacts(run.run_id, result["receipt_artifact"])
    assert json.loads(Path(receipt).read_text(encoding="utf-8"))["run_id"] == run.run_id
    tracker.end_run(run)


@pytest.mark.parametrize(
    "field,value", [("md5", "0" * 32), ("path", "another-dataset.txt"), ("size", True)]
)
def test_replaced_metadata_refuses_upload(dvc_space, monkeypatch, field, value):
    pytest.importorskip("mlflow")
    import yaml

    root, _ = dvc_space
    tracker = tracking.ExperimentTracker(
        {"project_root": str(root), "experiment_name": "races"}
    )
    run = tracker.start_run()
    data = root / ("race-" + field + ".txt")
    data.write_bytes(b"original data\n")
    original = tracking.DVCDataVersioner.get_file_hash

    def replace_metadata(versioner, path, **kwargs):
        result = original(versioner, path, **kwargs)
        metadata = Path(str(path) + ".dvc")
        content = yaml.safe_load(metadata.read_text(encoding="utf-8"))
        content["outs"][0][field] = value
        metadata.write_text(yaml.safe_dump(content), encoding="utf-8")
        return result

    monkeypatch.setattr(tracking.DVCDataVersioner, "get_file_hash", replace_metadata)
    with pytest.raises(ValueError, match="metadata"):
        tracker.log_dataset(run, data)
    assert tracker.client.list_artifacts(run.run_id) == []
    tracker.end_run(run, "failed")


def test_duplicate_stage_refused_but_yaml_merge_preserved(tmp_path):
    source = tmp_path / "dvc.yaml"
    source.write_text(
        "stages:\n  duplicate: {cmd: one}\n  duplicate: {cmd: two}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate"):
        tracking.DVCDataVersioner(tmp_path).get_pipeline_stages()
    source.write_text(
        "defaults: &defaults\n  cmd: original\nstages:\n  train:\n"
        "    <<: *defaults\n    cmd: override\n",
        encoding="utf-8",
    )
    assert tracking.DVCDataVersioner(tmp_path).get_pipeline_stages() == [
        {"cmd": "override", "name": "train"}
    ]
