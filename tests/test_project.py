"""Tests for framework.project -- the external project registry.

A registry that silently skips a missing checkout would hide a detached project,
and a runner that treats a crash as success would defeat the point of a gate. Both
are pinned below with a fake project, not just with the real one.
"""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.project import load_project, load_projects, run_command, _materialise


def _make_project(tmp_path: Path, gate_body: str = "raise SystemExit(0)", extra: str = "") -> Path:
    """Create projects/<name>/project.yaml plus its repo, and return the projects dir."""
    projects = tmp_path / "projects"
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "gate.py").write_text(textwrap.dedent(gate_body), encoding="utf-8")

    pdir = projects / "demo"
    pdir.mkdir(parents=True)
    (pdir / "project.yaml").write_text(
        textwrap.dedent(
            f"""
            name: demo
            root: ../../repo
            gate_command: ["{{python}}", "gate.py"]
            test_command: ["{{python}}", "-m", "pytest", "-q"]
            reports: ["docs/REPORT.html"]
            """
        ).lstrip()
        + extra,
        encoding="utf-8",
    )
    return projects


def test_load_project_resolves_relative_root(tmp_path):
    projects = _make_project(tmp_path)
    spec = load_project(projects / "demo" / "project.yaml")
    assert spec.name == "demo"
    assert spec.root == (tmp_path / "repo").resolve()
    assert spec.gate_command == ["{python}", "gate.py"]
    assert spec.reports == ["docs/REPORT.html"]


def test_missing_root_raises(tmp_path):
    projects = _make_project(tmp_path)
    (tmp_path / "repo").rename(tmp_path / "repo_moved")
    with pytest.raises(FileNotFoundError, match="root does not exist"):
        load_project(projects / "demo" / "project.yaml")


def test_list_tolerates_missing_root_but_marks_it(tmp_path):
    """Enumeration must survive a detached checkout; running it must not."""
    projects = _make_project(tmp_path)
    (tmp_path / "repo").rename(tmp_path / "repo_moved")

    specs = load_projects(projects, allow_missing=True)
    assert specs["demo"].available is False
    assert "checkout not found" in specs["demo"].missing_reason

    with pytest.raises(FileNotFoundError, match="cannot run"):
        run_command(specs["demo"], "gate")


def test_gate_command_must_be_a_list(tmp_path):
    projects = _make_project(tmp_path)
    cfg = projects / "demo" / "project.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            'gate_command: ["{python}", "gate.py"]', 'gate_command: "{python} gate.py"'
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be a list of arguments"):
        load_project(cfg)


def test_gate_command_is_required(tmp_path):
    projects = _make_project(tmp_path)
    cfg = projects / "demo" / "project.yaml"
    cfg.write_text(
        "\n".join(
            line for line in cfg.read_text(encoding="utf-8").splitlines()
            if not line.startswith("gate_command:")
        ) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'gate_command' is required"):
        load_project(cfg)


def test_duplicate_names_rejected(tmp_path):
    projects = _make_project(tmp_path)
    dup = projects / "other"
    dup.mkdir()
    (dup / "project.yaml").write_text(
        (projects / "demo" / "project.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate project name"):
        load_projects(projects)


def test_run_project_maps_exit_zero_to_pass(tmp_path):
    projects = _make_project(tmp_path)
    spec = load_project(projects / "demo" / "project.yaml")
    run = run_command(spec, "gate")
    assert run.status == "PASS"
    assert run.exit_code == 0


def test_run_project_maps_exit_one_to_fail(tmp_path):
    projects = _make_project(
        tmp_path,
        gate_body="import sys\nprint('gate says no')\nsys.exit(1)",
    )
    spec = load_project(projects / "demo" / "project.yaml")
    run = run_command(spec, "gate")
    assert run.status == "FAIL"
    assert run.exit_code == 1
    assert "gate says no" in run.stdout_tail


def test_run_project_maps_other_exit_to_error(tmp_path):
    projects = _make_project(tmp_path, gate_body="raise SystemExit(4)")
    spec = load_project(projects / "demo" / "project.yaml")
    run = run_command(spec, "gate")
    assert run.status == "ERROR"
    assert run.exit_code == 4


def test_python_placeholder_uses_the_running_interpreter(tmp_path):
    body = (
        "import sys, pathlib\n"
        "pathlib.Path('interp.txt').write_text(sys.executable)\n"
        "raise SystemExit(0)\n"
    )
    projects = _make_project(tmp_path, gate_body=body)
    spec = load_project(projects / "demo" / "project.yaml")
    run_command(spec, "gate")
    recorded = (tmp_path / "repo" / "interp.txt").read_text(encoding="utf-8")
    assert recorded == sys.executable


def test_materialise_leaves_other_arguments_untouched():
    assert _materialise(["{python}", "-m", "pytest"]) == [sys.executable, "-m", "pytest"]


def test_exec_undeclared_command_is_a_configuration_error(tmp_path):
    """An absent render_command must raise, not silently do nothing."""
    projects = _make_project(tmp_path)
    spec = load_project(projects / "demo" / "project.yaml")
    with pytest.raises(ValueError, match="declares no render_command"):
        run_command(spec, "render")


def test_exec_runs_the_declared_test_command(tmp_path):
    projects = _make_project(tmp_path)
    repo = tmp_path / "repo"
    (repo / "check.py").write_text(
        "import pathlib\npathlib.Path('ran.txt').write_text('yes')\n", encoding="utf-8"
    )
    cfg = projects / "demo" / "project.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            'test_command: ["{python}", "-m", "pytest", "-q"]',
            'test_command: ["{python}", "check.py"]',
        ),
        encoding="utf-8",
    )
    run = run_command(load_project(cfg), "test")
    assert run.status == "PASS"
    assert (repo / "ran.txt").read_text(encoding="utf-8") == "yes"
