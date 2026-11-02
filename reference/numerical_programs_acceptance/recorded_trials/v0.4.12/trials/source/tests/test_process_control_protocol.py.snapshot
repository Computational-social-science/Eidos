"""Control-channel failures must never be interpreted as a worker's verdict."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from framework import _process_tree as runner


@pytest.mark.parametrize("report", [None, "not JSON", {}, {"state": "complete", "returncode": True},
                                   {"state": "containment_error", "message": "job refused"}])
def test_missing_malformed_or_failed_helper_status_is_an_error(tmp_path, monkeypatch, report):
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    def helper(command, **kwargs):
        if report is not None:
            Path(command[5]).write_text(report if isinstance(report, str) else json.dumps(report))
        return subprocess.CompletedProcess(command, 0, "worker stdout", "worker stderr")
    monkeypatch.setattr(subprocess, "run", helper)
    with pytest.raises(runner.ProcessContainmentError):
        runner._windows([sys.executable, "-c", "pass"], tmp_path, 2, None)


def test_setup_failure_never_starts_the_worker(tmp_path, monkeypatch):
    from framework import _windows_job as helper
    status = tmp_path / "status.json"
    monkeypatch.setattr(sys, "argv", ["helper", str(status), "worker"])
    def denied():
        raise OSError("fixture Job assignment refused")
    monkeypatch.setattr(helper, "own_job", denied)
    def unexpected(*args, **kwargs):
        raise AssertionError("worker started before containment")
    monkeypatch.setattr(subprocess, "run", unexpected)
    assert helper.main() == 0  # Control transport success; scientific verdict is absent.
    assert json.loads(status.read_text())["state"] == "containment_error"


def test_real_worker_receives_closed_stdin_and_an_explicit_environment(tmp_path):
    import os
    environment = os.environ.copy()
    environment["EIDOS_PROCESS_FIXTURE"] = "configured"
    command = [sys.executable, "-c", "import sys,os;print(repr(sys.stdin.read()));print(os.environ['EIDOS_PROCESS_FIXTURE'])"]
    result = runner.run_tree(command, cwd=tmp_path, timeout=10, env=environment)
    assert result.returncode == 0 and result.args == command
    assert result.stdout.splitlines() == ["''", "configured"]


@pytest.mark.skipif(sys.platform != "win32", reason="real legacy Windows helper CLI")
def test_source_helper_cli_keeps_its_command_and_exit_status(tmp_path):
    helper = Path(__file__).resolve().parents[1] / "tools/windows_job.py"
    result = subprocess.run([sys.executable, str(helper), sys.executable, "-c", "print('worker');raise SystemExit(7)"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 7 and result.stdout.strip() == "worker"
