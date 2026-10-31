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


def test_required_numerics_blocks_a_successful_but_unsafe_consumer(tmp_path):
    projects = _make_project(tmp_path, extra="numerics: required\n")
    spec = load_project(projects / "demo/project.yaml")
    (spec.root / "unsafe.py").write_text(
        'import numpy as np\ndef log_softmax(z):\n'
        '    return z - np.log(np.exp(z).sum())\n', encoding="utf-8")
    result = run_command(spec)
    assert result.status == "FAIL"
    assert result.numerics["findings"]


def test_required_numerics_preserves_auditable_scope(tmp_path):
    projects = _make_project(tmp_path, extra="numerics: required\n")
    result = run_command(load_project(projects / "demo/project.yaml"))
    assert result.status == "PASS"
    assert result.numerics["kernel_regression"]["verdict"] == "PASS"
    assert "not certify" in result.numerics["scope"]


def test_misspelled_numerics_policy_is_not_ignored(tmp_path):
    projects = _make_project(tmp_path, extra="numerics: requried\n")
    with pytest.raises(ValueError, match="numerics"):
        load_project(projects / "demo/project.yaml")


@pytest.mark.parametrize("name", ["python", "python3", "python.exe"])
def test_generic_python_command_uses_the_selected_project_interpreter(name):
    assert _materialise([name, "gate.py"]) == [sys.executable, "gate.py"]


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


def test_validator_inputs_are_explicit_files_not_a_shell_string(tmp_path):
    projects=_make_project(tmp_path,extra='validity_inputs: "helper.py data.json"\n')
    with pytest.raises(ValueError,match='validity_inputs must be a list'):
        load_project(projects/'demo/project.yaml')


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


@pytest.mark.parametrize("code, expected", [(3, "OPEN"), (4, "REFUSED"), (5, "SKIP")])
def test_explicit_research_exit_vocabulary_is_preserved(tmp_path, code, expected):
    projects = _make_project(tmp_path, gate_body=f"raise SystemExit({code})",
                             extra='exit_statuses: {3: OPEN, 4: REFUSED, 5: SKIP}')
    spec = load_project(projects / "demo" / "project.yaml")
    result = run_command(spec)
    assert result.status == expected
    assert result.exit_code == code


def test_exit_mapping_cannot_turn_a_nonzero_exit_into_a_pass(tmp_path):
    projects = _make_project(tmp_path, extra='exit_statuses: {3: PASS}')
    with pytest.raises(ValueError, match="exit_statuses"):
        load_project(projects / "demo" / "project.yaml")


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


def test_test_command_does_not_have_to_produce_the_gates_research_outputs(tmp_path):
    projects=_make_project(tmp_path,extra='expects: [docs/evidence.json]\n')
    cfg=projects/'demo/project.yaml'
    cfg.write_text(cfg.read_text().replace('["{python}", "-m", "pytest", "-q"]',
                                          '["{python}", "-c", "pass"]'))
    result=run_command(load_project(cfg),'test')
    assert result.status=='PASS',result.stderr_tail


def test_missing_project_root_raises_locally_but_is_skippable_in_ci(tmp_path):
    """A detached checkout must not pass as audited locally, yet CI has no checkouts.

    The chain audit passes allow_missing=not STRICT_REGISTRY for exactly this reason; a
    FileNotFoundError escaping load_projects turned the CI audit job red on 2026-10-21.
    """
    import pytest
    from framework.project import load_projects

    proj = tmp_path / "ghost"
    proj.mkdir()
    (proj / "project.yaml").write_text(
        "name: ghost\nroot: ../../../nowhere\ngate_command: ['true']\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        load_projects(tmp_path)

    specs = load_projects(tmp_path, allow_missing=True)
    assert specs["ghost"].available is False
