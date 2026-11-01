"""Stdlib-only ownership of short-lived Windows Jobs / POSIX process groups."""
from __future__ import annotations

from collections.abc import Mapping
import errno
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


class ProcessContainmentError(OSError):
    """The runner could not establish or verify its own execution boundary."""


def validate_timeout(timeout: float) -> None:
    if (isinstance(timeout, bool) or not isinstance(timeout, (float, int))
            or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("timeout must be a finite positive number")


def _worker_result(args, report, helper_code, stdout, stderr):
    if helper_code != 0 or not isinstance(report, dict):
        raise ProcessContainmentError("execution helper failed: " + stderr)
    if report.get("state") == "launch_error":
        code = report.get("errno")
        raise OSError(code if type(code) is int else errno.EIO,
                      report.get("message", "worker launch failed"), report.get("filename"))
    if report.get("state") != "complete" or type(report.get("returncode")) is not int:
        raise ProcessContainmentError(report.get("message", "execution containment failed"))
    return subprocess.CompletedProcess(args, report["returncode"], stdout, stderr)


def _windows(args: list[str], cwd: Path, timeout: float,
             env: Mapping[str, str] | None) -> subprocess.CompletedProcess:
    helper = Path(__file__).with_name("_windows_job.py")
    with tempfile.TemporaryDirectory(prefix="eidos-process-status-") as temporary:
        status = Path(temporary) / "status.json"
        command = [sys.executable, "-I", "-X", "utf8", str(helper), str(status), *args]
        try:
            result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:
            # Killing this helper closes its sole Job handle and inherited workers.
            raise subprocess.TimeoutExpired(args, timeout, output=exc.output, stderr=exc.stderr) from exc
        try:
            report = json.loads(status.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProcessContainmentError("execution helper did not publish its status; " + result.stderr) from exc
        return _worker_result(args, report, result.returncode, result.stdout, result.stderr)


def _posix(args: list[str], cwd: Path, timeout: float,
           env: Mapping[str, str] | None) -> subprocess.CompletedProcess:
    # Root process completion and pipe EOF are different events. A normal child
    # inheriting PIPE can keep communicate() waiting after the root exits. Spool
    # both streams to regular files and wait for the root independently.
    with (tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file,
          tempfile.TemporaryFile() as status_file):
        read_fd, write_fd = os.pipe()
        helper = Path(__file__).with_name("_posix_job.py")
        command = [sys.executable, "-I", "-X", "utf8", str(helper), str(read_fd), str(status_file.fileno()), *args]
        try:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stdout_file, stderr=stderr_file, start_new_session=True,
                                       pass_fds=(read_fd, status_file.fileno()))
        except BaseException:
            os.close(write_fd)
            raise
        finally:
            os.close(read_fd)
        expired = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            expired = True
        finally:
            os.close(write_fd)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exc:
                raise ProcessContainmentError("could not close owned process group") from exc
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired as exc:
                raise ProcessContainmentError("owned root did not exit during cleanup") from exc
        def captured(stream):
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(0)
            return stream.read(size).decode("utf-8", "replace")
        stdout, stderr = captured(stdout_file), captured(stderr_file)
        if expired:
            raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr)
        try:
            status_file.seek(0)
            report = json.load(status_file)
        except (OSError, ValueError) as exc:
            raise ProcessContainmentError("POSIX guardian did not publish its status; " + stderr) from exc
        if process.returncode != -signal.SIGKILL:
            raise ProcessContainmentError("guardian did not close its owned group: " + str(report))
        return _worker_result(args, report, 0, stdout, stderr)


def run_tree(args: list[str], *, cwd: Path, timeout: float,
             env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess:
    """Capture a bounded command and close its Job/group on every completion.

    Targets are trusted project commands, not sandboxed code. POSIX programs that
    deliberately detach from the group need a container/cgroup lifecycle instead.
    Persistent services must use a separate explicit service supervisor.
    """
    validate_timeout(timeout)
    if (not isinstance(args, list) or not args or not args[0]
            or not all(isinstance(arg, str) and "\0" not in arg for arg in args)):
        raise ValueError("command must be a nonempty argv list of strings without NUL")
    return _windows(args, cwd, timeout, env) if os.name == "nt" else _posix(args, cwd, timeout, env)
