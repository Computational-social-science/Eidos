"""Pins for the two bridges that only the chain audit used to exercise.

`quarto_bridge` and `tracking` were "run" by the audit and tested by nothing: a change in
their resolution order would have shown up only if it broke a whole chain. These tests fix
the contract that matters -- how the executable is found -- without needing Quarto or DVC
to be installed.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.quarto_bridge import QuartoBridge
from framework import tracking


def test_dvc_cmd_falls_back_to_the_module_form(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert tracking.dvc_cmd() == [sys.executable, "-m", "dvc"]


def test_dvc_cmd_prefers_the_executable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/dvc")
    assert tracking.dvc_cmd() == ["/usr/bin/dvc"]


def test_quarto_bridge_uses_quarto_bin_when_it_answers(monkeypatch, tmp_path):
    # Exit zero alone is not a successful Quarto version probe.
    from framework import subprocesses
    import subprocess
    monkeypatch.setenv("QUARTO_BIN", sys.executable)
    monkeypatch.setattr(subprocesses, "run_tree", lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 0, "1.10.19\n", ""))
    bridge = QuartoBridge({"project_root": str(tmp_path)})
    assert bridge.quarto_available is True
    assert bridge.quarto_cmd == sys.executable


def test_quarto_bridge_reports_absence_instead_of_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(QuartoBridge, "_quarto_candidates", lambda self: iter(()))
    bridge = QuartoBridge({"project_root": str(tmp_path)})
    assert bridge.quarto_available is False
    assert bridge.quarto_cmd is None


def test_quarto_bridge_candidates_put_the_env_var_first(monkeypatch, tmp_path):
    monkeypatch.setenv("QUARTO_BIN", "/somewhere/quarto")
    bridge = QuartoBridge({"project_root": str(tmp_path)})
    first = next(iter(bridge._quarto_candidates()))
    assert first == "/somewhere/quarto"
