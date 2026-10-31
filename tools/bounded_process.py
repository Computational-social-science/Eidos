"""Run a short-lived tool in an owned process tree, including timeout cleanup."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from collections.abc import Mapping


def run_tree(args: list[str], *, cwd: Path, timeout: float,
             env: Mapping[str,str] | None = None) -> subprocess.CompletedProcess:
    if os.name == "nt":
        # The helper joins a kill-on-close Job before starting the requested tool.
        # Killing the helper therefore also kills tool/Lean/etc descendants.
        wrapper = Path(__file__).with_name("windows_job.py")
        return subprocess.run([sys.executable, str(wrapper), *args], cwd=cwd,
                              stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW, env=env)
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", start_new_session=True,
                               stdin=subprocess.DEVNULL, env=env)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
