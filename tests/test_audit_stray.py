"""The stray-directory check must trip on the accident it was written for, and stay quiet otherwise.

The colon case cannot be created through the Win32 API (Python's os.mkdir raises WinError 123), which is
exactly why it survived on this machine — bash made it. The predicate is one string test, and the
creatable half of the vocabulary (`tmp`, `p2a_*`, `stage_*`) exercises the same code path, so the
control below uses those.
"""

import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_stray.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_stray", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_colon_name_is_flagged():
    tool = _load()
    assert tool._suspicious("E:2026-AI4SEidos") is True


def test_scratch_vocabulary_next_to_the_project_is_flagged(tmp_path):
    tool = _load()
    for name in ("tmp", "p2a_clone", "p2a-work", "_eidos", "stage_native", "tmp_p2a_full"):
        (tmp_path / name).mkdir()
    (tmp_path / "Eidos").mkdir()
    (tmp_path / "surrogate_study").mkdir()

    findings = tool.scan([tmp_path])
    names = {item["name"] for item in findings}
    assert names == {"tmp", "p2a_clone", "p2a-work", "_eidos", "stage_native", "tmp_p2a_full"}


def test_a_clean_neighbourhood_produces_nothing(tmp_path):
    tool = _load()
    for name in ("Eidos", "bootloops", "surrogate_study", "null_study"):
        (tmp_path / name).mkdir()
    assert tool.scan([tmp_path]) == []


def test_the_scratch_directory_itself_is_excluded(tmp_path):
    tool = _load()
    project = tmp_path / "Eidos"
    (project / ".scratch").mkdir(parents=True)
    (project / ".scratch" / "tmp").mkdir()
    assert tool.scan([project], exclude=[project / ".scratch"]) == []
