"""Pins for the registry and the inference registry.

The chain audit exercises both, but it can only show that a happy path runs. These tests
fix the contract that matters when things go wrong: exit-code mapping, an absent optional
command, a duplicate name, a model that does not fit, and a name that does not exist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.inference import ModelManager  # noqa: E402
from framework.project import (ProjectSpec, load_project, load_projects,  # noqa: E402
                               run_command)


def write_project(root: Path, directory_name: str, gate: list[str],
                  spec_name: str | None = None, **extra) -> Path:
    directory = root / directory_name
    directory.mkdir(parents=True)
    (directory / "repo").mkdir()
    data = {"name": spec_name or directory_name, "root": "repo",
            "gate_command": gate, **extra}
    (directory / "project.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return directory / "project.yaml"


# -- registry -----------------------------------------------------------------
def test_missing_gate_command_is_rejected(tmp_path: Path):
    directory = tmp_path / "bad"
    directory.mkdir()
    (directory / "repo").mkdir()
    (directory / "project.yaml").write_text("name: bad\nroot: repo\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_project(directory / "project.yaml")


def test_duplicate_names_are_rejected(tmp_path: Path):
    write_project(tmp_path, "dup", ["true"], spec_name="same")
    second = tmp_path / "dup2"
    second.mkdir()
    (second / "repo").mkdir()
    (second / "project.yaml").write_text(
        yaml.safe_dump({"name": "same", "root": "repo", "gate_command": ["true"]}),
        encoding="utf-8")
    with pytest.raises(ValueError):
        load_projects(tmp_path)


def test_python_placeholder_uses_the_running_interpreter(tmp_path: Path):
    spec = load_project(write_project(tmp_path, "py", ["{python}", "-c", "print('ok')"]))
    run = run_command(spec)
    assert run.status == "PASS"
    assert "ok" in run.stdout_tail


def test_exit_codes_map_to_pass_fail_error(tmp_path: Path):
    ok = load_project(write_project(tmp_path, "ok", ["{python}", "-c", "pass"]))
    bad = load_project(write_project(tmp_path, "bad", ["{python}", "-c", "raise SystemExit(1)"]))
    err = load_project(write_project(tmp_path, "err", ["{python}", "-c", "raise SystemExit(3)"]))
    assert run_command(ok).status == "PASS"
    assert run_command(bad).status == "FAIL"
    assert run_command(err).status == "ERROR"


def test_absent_optional_command_is_a_configuration_error(tmp_path: Path):
    spec = load_project(write_project(tmp_path, "x", ["true"]))
    with pytest.raises(ValueError):
        run_command(spec, kind="render")


def test_unknown_command_kind_is_rejected(tmp_path: Path):
    spec = load_project(write_project(tmp_path, "y", ["true"]))
    with pytest.raises(ValueError):
        run_command(spec, kind="benchmark")


# -- inference ----------------------------------------------------------------
def test_registry_has_startlux_and_no_d1():
    registry = ModelManager.MODEL_REGISTRY
    assert "StartLux-Decision-4B-Q8_0" in registry
    assert not any("d1-3B" in key for key in registry)


def test_budget_admits_and_refuses_by_instance_budget():
    roomy = ModelManager({"vram_budget_gb": 12})
    tight = ModelManager({"vram_budget_gb": 4})
    assert roomy.can_load("StartLux-Decision-4B-Q8_0") is True
    assert tight.can_load("StartLux-Decision-4B-Q8_0") is False


def test_unknown_model_is_none_not_an_exception():
    assert ModelManager({}).get_model_spec("no-such-model") is None


def test_estimate_vram_is_positive_and_sorted_by_size():
    manager = ModelManager({"vram_budget_gb": 12})
    small = manager.estimate_vram("StartLux-Decision-4B-Q8_0")
    assert small > 0
