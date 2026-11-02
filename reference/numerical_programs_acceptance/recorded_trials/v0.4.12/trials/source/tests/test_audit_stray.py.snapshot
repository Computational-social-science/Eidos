"""External ownership blockers, visible shared-directory warnings and inspection errors.

The Windows path-mangling predicate is checked as text because native Win32
cannot create that colon name. Real CLI controls exercise ordinary names,
explicit ownership, shared-file preservation and bounded marker inspection.
"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_stray.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_stray", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_colon_name_is_flagged():
    tool = _load()
    assert tool._suspicious("E:2026-AI4SEidos") is True


def test_scratch_vocabulary_next_to_the_project_is_flagged(tmp_path):
    tool = _load()
    for name in (
        "tmp",
        "p2a_clone",
        "p2a-work",
        "_eidos",
        "stage_native",
        "tmp_p2a_full",
    ):
        (tmp_path / name).mkdir()
    (tmp_path / "Eidos").mkdir()
    (tmp_path / "surrogate_study").mkdir()

    findings = tool.scan([tmp_path])
    names = {item["name"] for item in findings}
    assert names == {
        "tmp",
        "p2a_clone",
        "p2a-work",
        "_eidos",
        "stage_native",
        "tmp_p2a_full",
    }


def test_a_clean_neighbourhood_produces_nothing(tmp_path):
    tool = _load()
    for name in ("Eidos", "bootloops", "surrogate_study", "null_study"):
        (tmp_path / name).mkdir()
    assert tool.scan([tmp_path]) == []


def test_the_scratch_directory_itself_is_excluded(tmp_path):
    tool = _load()
    project = tmp_path / "Eidos"
    (project / ".scratch").mkdir(parents=True)
    (project / ".scratch" / "tmp").mkdir()
    assert tool.scan([project], exclude=[project / ".scratch"]) == []


def _marker(directory, project):
    (directory / ".eidos-owner.json").write_text(
        json.dumps(
            {
                "schema": "eidos.scratch-owner.v1",
                "project_root": str(project.resolve()),
            }
        ),
        encoding="utf-8",
    )


def _cli(tmp_path, *arguments):
    project = tmp_path / "Eidos"
    tools = project / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TOOL, tools / "audit_stray.py")
    return subprocess.run(
        [
            sys.executable,
            str(tools / "audit_stray.py"),
            "--root",
            str(tmp_path),
            "--json",
            *arguments,
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_unowned_shared_tmp_does_not_prevent_a_commit(tmp_path):
    directory = tmp_path / "tmp"
    directory.mkdir()
    artifact = directory / "another-project.txt"
    artifact.write_bytes(b"preserve shared files")
    run = _cli(tmp_path)
    report = json.loads(run.stdout)
    assert run.returncode == 0
    assert report["status"] == "PASS"
    assert report["blocking_count"] == 0
    assert report["findings"][0]["attribution"] == "unattributed"
    assert artifact.read_bytes() == b"preserve shared files"


def test_explicit_owner_blocks_even_an_ordinary_directory_name(tmp_path):
    directory = tmp_path / "unremarkable"
    directory.mkdir()
    _marker(directory, tmp_path / "Eidos")
    run = _cli(tmp_path)
    report = json.loads(run.stdout)
    assert run.returncode == 1
    assert report["status"] == "FAIL" and report["blocking_count"] == 1
    assert report["findings"][0]["attribution"] == "project-marker"
    assert directory.is_dir()


def test_foreign_owner_takes_precedence_over_namespace_guess(tmp_path):
    directory = tmp_path / "_eidos"
    directory.mkdir()
    _marker(directory, tmp_path / "another-checkout")
    run = _cli(tmp_path)
    report = json.loads(run.stdout)
    assert run.returncode == 0
    assert report["findings"][0]["attribution"] == "other-project"
    assert report["findings"][0]["blocking"] is False


@pytest.mark.parametrize(
    "raw",
    [
        "{broken",
        '{"schema":"eidos.scratch-owner.v1","project_root":"relative"}',
        '{"schema":"eidos.scratch-owner.v1","project_root":""}',
        '{"schema":"eidos.scratch-owner.v1","project_root":42}',
        '{"schema":"eidos.scratch-owner.v1","project_root":"/a","project_root":"/b"}',
        '{"schema":true,"project_root":"/a"}',
    ],
)
def test_invalid_owner_never_becomes_clean(tmp_path, raw):
    directory = tmp_path / "ordinary"
    directory.mkdir()
    (directory / ".eidos-owner.json").write_text(raw, encoding="utf-8")
    run = _cli(tmp_path)
    assert run.returncode == 2
    assert json.loads(run.stdout)["status"] == "ERROR"


def test_explicit_namespace_is_a_policy_failure_not_a_creation_claim(tmp_path):
    (tmp_path / "_eidos").mkdir()
    run = _cli(tmp_path)
    report = json.loads(run.stdout)
    assert run.returncode == 1
    assert report["findings"][0]["attribution"] == "project-namespace-policy"


def test_only_the_current_project_path_mangle_is_attributed():
    tool = _load()
    assert tool.mangled_name(r"E:\2026-AI4S\Eidos") == "E:2026-AI4SEidos"
    assert tool.mangled_name(r"F:\other\research") != "E:2026-AI4SEidos"


def test_unreadable_scan_fails_instead_of_publishing_clean(
    tmp_path, monkeypatch, capsys
):
    tool = _load()

    def denied(*args, **kwargs):
        raise PermissionError("inspection denied")

    monkeypatch.setattr(tool, "scan", denied)
    assert tool.main(["--root", str(tmp_path), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"


def test_missing_explicit_root_is_not_an_empty_clean_scan(tmp_path):
    run = _cli(tmp_path, "--root", str(tmp_path / "missing"))
    assert run.returncode == 2
    assert json.loads(run.stdout)["status"] == "ERROR"


def test_marker_directory_is_an_inspection_error(tmp_path):
    directory = tmp_path / "ordinary"
    (directory / ".eidos-owner.json").mkdir(parents=True)
    run = _cli(tmp_path)
    assert run.returncode == 2
    assert json.loads(run.stdout)["status"] == "ERROR"


def test_oversized_marker_is_an_inspection_error(tmp_path):
    directory = tmp_path / "ordinary"
    directory.mkdir()
    (directory / ".eidos-owner.json").write_bytes(b"x" * 4097)
    run = _cli(tmp_path)
    assert run.returncode == 2
    assert json.loads(run.stdout)["status"] == "ERROR"


@pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="POSIX FIFO control; exercised on Linux"
)
def test_fifo_marker_is_rejected_without_blocking(tmp_path):
    directory = tmp_path / "ordinary"
    directory.mkdir()
    os.mkfifo(directory / ".eidos-owner.json")
    run = _cli(tmp_path)
    assert run.returncode == 2
    assert json.loads(run.stdout)["status"] == "ERROR"


def test_entry_metadata_error_is_not_silently_skipped(tmp_path, monkeypatch):
    tool = _load()
    directory = tmp_path / "ordinary"
    directory.mkdir()
    original = Path.stat

    def denied(path, *args, **kwargs):
        if path == directory:
            raise PermissionError("Entry metadata unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied)
    with pytest.raises(PermissionError, match="Entry metadata unavailable"):
        tool.scan([tmp_path], project=tmp_path / "Eidos")
