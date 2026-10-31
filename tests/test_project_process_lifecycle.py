"""Only harmless, finite fixture workers are created by these lifecycle checks."""
from pathlib import Path
import subprocess
import sys
import time

import pytest

from framework.project import ProjectSpec, run_command


def project(tmp_path, *, parent_exits=False):
    child = tmp_path / "child.py"
    child.write_text(
        "from pathlib import Path\nimport os,time\n"
        "Path('child-started').write_text(str(os.getpid()))\n"
        "time.sleep(5)\nPath('late-result').write_text('after deadline')\n"
        "time.sleep(1)\n", encoding="utf-8")
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        "print('parent progress',flush=True)\n"
        "print('parent diagnostic',file=sys.stderr,flush=True)\n"
        "subprocess.Popen([sys.executable,'child.py'])\n"
        "while not Path('child-started').exists():time.sleep(.01)\n"
        + ("" if parent_exits else "time.sleep(20)\n"), encoding="utf-8")
    command = [sys.executable, str(parent)]
    return ProjectSpec("owned_fixture", tmp_path, command, test_command=command,
                       render_command=command)


@pytest.mark.parametrize("kind", ["gate", "test", "render"])
def test_timeout_stops_owned_descendants_and_preserves_both_streams(tmp_path, kind):
    spec = project(tmp_path)
    started = time.monotonic()
    result = run_command(spec, kind, timeout=3)
    assert result.status == "ERROR" and result.exit_code == 124
    assert time.monotonic() - started < 4.5
    assert (tmp_path / "child-started").exists()
    time.sleep(2.5)
    assert not (tmp_path / "late-result").exists(), "experiment survived its SDK deadline"
    assert "parent progress" in result.stdout_tail
    assert "parent diagnostic" in result.stderr_tail


def test_successful_parent_cannot_leave_owned_work_running(tmp_path):
    spec = project(tmp_path, parent_exits=True)
    result = run_command(spec, timeout=3)
    assert result.status == "PASS", result.as_dict()
    assert (tmp_path / "child-started").exists()
    time.sleep(5.2)
    assert not (tmp_path / "late-result").exists()


def test_containment_setup_failure_is_not_a_scientific_rejection(tmp_path, monkeypatch):
    import framework.subprocesses as processes
    if not hasattr(processes, "run_tree"):
        pytest.fail("installed SDK does not expose its own bounded runner")
    def unavailable(*args, **kwargs):
        raise processes.ProcessContainmentError("containment setup failed")
    monkeypatch.setattr(processes, "run_tree", unavailable)
    spec = ProjectSpec("containment_failure", tmp_path, [sys.executable, "-c", "pass"],
                       exit_statuses={125: "OPEN"})
    result = run_command(spec)
    assert result.status == "ERROR" and "containment setup" in result.stderr_tail


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_invalid_deadline_never_launches_the_worker(tmp_path, timeout):
    marker = tmp_path / "started"
    spec = ProjectSpec("invalid_deadline", tmp_path,
                       [sys.executable, "-c", f"from pathlib import Path;Path({str(marker)!r}).touch()"])
    with pytest.raises(ValueError, match="timeout"):
        run_command(spec, timeout=timeout)
    assert not marker.exists()


@pytest.mark.parametrize("mapping", [{7: "PASS"}, {-9: "OPEN"}, {124: "SKIP"}, {2: []}])
def test_direct_sdk_specs_cannot_relabel_execution_failures_as_acceptance(tmp_path, mapping):
    spec = ProjectSpec("bad_mapping", tmp_path, [sys.executable, "-c", "raise SystemExit(7)"],
                       exit_statuses=mapping)
    with pytest.raises(ValueError, match="exit_statuses"):
        run_command(spec)


def test_permission_failure_is_an_execution_error_not_a_missing_tool(tmp_path, monkeypatch):
    import framework.subprocesses as processes
    def denied(*args, **kwargs):
        raise PermissionError("fixture launch denied")
    monkeypatch.setattr(processes, "run_tree", denied)
    result = run_command(ProjectSpec("denied", tmp_path, [sys.executable, "-c", "pass"],
                                    exit_statuses={126: "OPEN"}))
    assert result.status == "ERROR" and result.exit_code == 126
