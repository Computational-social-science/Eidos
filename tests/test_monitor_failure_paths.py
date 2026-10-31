"""A watchdog/reload must survive the failure it exists to handle."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from tools import serve_site


def test_stalled_sampler_reaches_process_exit(monkeypatch):
    monkeypatch.setitem(serve_site.STATE, "sampled", 0.0)
    monkeypatch.setattr(serve_site.time, "time", lambda: 1000.0)
    monkeypatch.setattr(serve_site.time, "sleep", lambda _: None)
    def exit_(code):
        raise SystemExit(code)
    monkeypatch.setattr(serve_site.os, "_exit", exit_)
    with pytest.raises(SystemExit) as exc:
        serve_site.stall_watchdog(limit=1, check_every=0)
    assert exc.value.code == 3


def test_failed_reload_preserves_working_module(tmp_path, monkeypatch):
    name = "eidos_reload_regression"
    path = tmp_path / f"{name}.py"
    path.write_text('def sample(): return "working"\ndef measure(): return "measured"\n', encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(serve_site.STATE, f"_mtime_{name}", raising=False)
    path.write_text('sample = None\nraise RuntimeError("broken update")\n', encoding="utf-8")
    selected = serve_site._reload_if_changed(module, path)
    assert selected.sample() == "working"
    assert sys.modules[name] is module


def test_complete_reload_replaces_module_and_behaviour(tmp_path, monkeypatch):
    name = "eidos_complete_reload"
    path = tmp_path / f"{name}.py"
    path.write_text('def sample(): return "old"\ndef measure(): return "old"\n', encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(serve_site.STATE, f"_mtime_{name}", raising=False)
    path.write_text('def sample(): return "new"\ndef measure(): return "new"\n', encoding="utf-8")
    selected = serve_site._reload_if_changed(module, path)
    assert selected.sample() == "new"
    assert sys.modules[name] is selected
    assert module.sample() == "old"
    assert serve_site._reload_if_changed(module, path).sample() == "new"
    path.write_text('raise RuntimeError("later broken edit")\n', encoding="utf-8")
    assert serve_site._reload_if_changed(module, path).sample() == "new"
    path.write_text('sample = None\n', encoding="utf-8")
    assert serve_site._reload_if_changed(module, path).sample() == "new"
