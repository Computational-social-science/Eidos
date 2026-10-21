"""Chain resolution: a bare tool name is not a deployment.

Both defects these tests pin were found by running the audit against this host:
`ExperimentTracker` raised FileNotFoundError out of its constructor because `dvc`
was installed but not on PATH, and the Quarto bridge reported Quarto absent while
the binary sat in the toolchain. Each is a resolution bug, not a missing feature,
so the tests exercise the resolution itself rather than the tools.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework import quarto_bridge, tracking


def test_dvc_resolves_to_module_when_not_on_path(monkeypatch):
    monkeypatch.setattr(tracking.shutil, "which", lambda name: None)
    assert tracking.dvc_cmd() == [sys.executable, "-m", "dvc"]


def test_dvc_uses_path_when_present(monkeypatch):
    monkeypatch.setattr(tracking.shutil, "which", lambda name: "/usr/bin/dvc")
    assert tracking.dvc_cmd() == ["/usr/bin/dvc"]


def test_tracker_without_dvc_still_constructs(tmp_path, monkeypatch):
    """Data versioning is an add-on; its absence must not disable run logging."""
    pytest.importorskip("mlflow")
    monkeypatch.setattr(tracking, "DVC_AVAILABLE", False)
    tracker = tracking.ExperimentTracker(
        {"project_root": str(tmp_path), "experiment_name": "t"})
    assert tracker.dvc_available is False


def test_quarto_honours_quarto_bin(monkeypatch):
    """QUARTO_BIN is the first candidate; the probe must store what answered."""
    monkeypatch.setenv("QUARTO_BIN", sys.executable)
    bridge = quarto_bridge.QuartoBridge({"project_root": "."})
    assert bridge.quarto_available is True
    assert bridge.quarto_cmd == sys.executable


def test_quarto_absent_when_no_candidate(monkeypatch):
    monkeypatch.delenv("QUARTO_BIN", raising=False)
    monkeypatch.setattr(quarto_bridge.shutil, "which", lambda name: None)
    monkeypatch.setattr(quarto_bridge.QuartoBridge, "_quarto_candidates",
                        lambda self: iter(()))
    bridge = quarto_bridge.QuartoBridge({"project_root": "."})
    assert bridge.quarto_available is False
    assert bridge.quarto_cmd is None
