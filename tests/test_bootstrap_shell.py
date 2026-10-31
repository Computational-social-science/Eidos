"""Execute the compatibility shell entry point in an isolated copy of the repo."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def shell_repo(tmp_path):
    candidates = ([Path("C:/Program Files/Git/bin/bash.exe"),
                   Path("C:/Program Files/Git/usr/bin/bash.exe")]
                  if sys.platform == "win32" else [])
    bash = next((str(path) for path in candidates if path.is_file()), shutil.which("bash"))
    if not bash:
        pytest.skip("bootstrap compatibility tests require Bash")
    repo = tmp_path / "framework with spaces"
    (repo / "tools").mkdir(parents=True)
    (repo / "framework").mkdir()
    (repo / "bootstrap_project.sh").write_bytes(
        (ROOT / "bootstrap_project.sh").read_bytes().replace(b"\r\n", b"\n"))
    shutil.copy2(ROOT / "tools/bootstrap_project.py", repo / "tools/bootstrap_project.py")
    shutil.copy2(ROOT / "framework/project.py", repo / "framework/project.py")
    shutil.copytree(ROOT / "reference/demo_onboarding", repo / "reference/demo_onboarding",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return repo, bash


def shell_environment():
    env = dict(os.environ, PYTHON=sys.executable.replace("\\", "/"), PYTHONUTF8="1")
    # Resolve framework.project from the isolated checkout, even in a source-aware harness.
    env.pop("PYTHONPATH", None)
    return env


def run_shell(shell_repo, *args, env=None):
    repo, bash = shell_repo
    return subprocess.run([bash, str(repo / "bootstrap_project.sh"), *args],
                          cwd=repo.parent, env=env or shell_environment(), capture_output=True,
                          text=True, encoding="utf-8", timeout=30)


def snapshot(path):
    return {str(item.relative_to(path)): item.read_bytes()
            for item in path.rglob("*") if item.is_file()}


def test_shell_creates_the_canonical_registered_consumer(shell_repo):
    repo, _ = shell_repo
    result = run_shell(shell_repo, "study_2026")
    assert result.returncode == 0, result.stdout + result.stderr
    project = repo / "projects/study_2026"
    spec = yaml.safe_load((project / "project.yaml").read_text(encoding="utf-8"))
    assert (project / spec["root"]).resolve() == project.resolve()
    assert spec["gate_command"] == ["python", "build_evidence.py"]
    assert spec["expects"] == ["docs/evidence.json"]
    assert (project / "build_evidence.py").read_bytes() == (repo / "reference/demo_onboarding/build_evidence.py").read_bytes()
    assert not (project / "docs/evidence.json").exists(), "old measurement must not be inherited"
    assert not (project / "scripts/run_experiment.py").exists(), "no false-success experiment stub"
    assert not (project / "scripts/run_evaluation.py").exists(), "no false-success gate stub"


@pytest.mark.parametrize("name", ["../escape", "bad/name", r"bad\name", "..", ".", "Bad Name", "1study", "bad\nroot: elsewhere"])
def test_shell_rejects_unsafe_names_before_any_output(shell_repo, name):
    repo, _ = shell_repo
    before = snapshot(repo.parent)
    result = run_shell(shell_repo, name)
    assert result.returncode != 0, result.stdout + result.stderr
    assert snapshot(repo.parent) == before


@pytest.mark.parametrize("args", [[], ["study", "--force"], ["--force"], ["study", "--unknown"], ["study", "extra"]])
def test_invalid_shell_invocation_cannot_mutate_the_repo(shell_repo, args):
    repo, _ = shell_repo
    before = snapshot(repo)
    result = run_shell(shell_repo, *args)
    assert result.returncode != 0
    assert snapshot(repo) == before


def test_second_run_and_force_preserve_existing_work(shell_repo):
    repo, _ = shell_repo
    assert run_shell(shell_repo, "study").returncode == 0
    (repo / "projects/study/research.txt").write_text("irreplaceable research", encoding="utf-8")
    before = snapshot(repo / "projects")
    for args in (("study",), ("study", "--force")):
        result = run_shell(shell_repo, *args)
        assert result.returncode != 0
        assert snapshot(repo / "projects") == before


def test_selected_interpreter_failure_is_propagated(shell_repo):
    repo, _ = shell_repo
    env = shell_environment()
    result = run_shell(shell_repo, "study", env=dict(env, PYTHON="/no/such/python"))
    assert result.returncode != 0
    assert not (repo / "projects").exists()


def test_default_python_is_available_without_explicit_override(shell_repo):
    env = shell_environment()
    env.pop("PYTHON")
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    result = run_shell(shell_repo, "study", env=env)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("action", [["check", "unknown"], ["exec", "unknown", "gate"]])
def test_empty_or_unknown_registry_does_not_report_pass(shell_repo, action):
    repo, bash = shell_repo
    env = shell_environment()
    for populated in (False, True):
        if populated:
            assert run_shell(shell_repo, "study").returncode == 0
        result = subprocess.run(
            [bash, "-c", 'exec "$PYTHON" -m framework.project "$@"', "registry", *action],
            cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert result.returncode != 0
        assert "unknown project" in result.stderr
