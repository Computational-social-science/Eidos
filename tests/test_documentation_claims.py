"""The README may not name a library the project does not use.

It claimed LangGraph orchestration for the whole life of v4.x while no module imported it and
`pyproject.toml` did not declare it. That is the same defect Gate S rejects in a manuscript — a
sentence that does not resolve to an artefact — committed by the framework's own front page.
"""

from __future__ import annotations

import ast
import pathlib
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAIMED = ("langgraph", "langchain", "hydra", "chromadb")


def _declared() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = set()
    for spec in project.get("dependencies", []) + [
            item for extra in project.get("optional-dependencies", {}).values() for item in extra]:
        base = spec.split("[")[0]
        for sep in (">=", "==", "<", ">", "~=", "!=", ";"):
            base = base.split(sep)[0]
        names.add(base.strip().lower())
    return names


def _imported() -> set[str]:
    found = set()
    for folder in ("framework", "tools"):
        for path in (ROOT / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update(alias.name.split(".")[0].lower() for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    found.add(node.module.split(".")[0].lower())
    return found


ABSENCE = ("removed", "deleted", "absent", "retired", "no agent graph", "not in the code", "never wired",
           "does not", "there is no")


def _pages() -> list[pathlib.Path]:
    return [ROOT / "README.md"] + sorted((ROOT / "docs").glob("*.md"))


@pytest.mark.parametrize("library", CLAIMED)
def test_a_named_library_is_used_or_said_to_be_absent(library):
    declared, imported = _declared(), _imported()
    for page in _pages():
        text = page.read_text(encoding="utf-8")
        low = text.lower()
        start = 0
        while (hit := low.find(library, start)) >= 0:
            window = low[max(0, hit - 800):hit + 800]
            page_declares = "status: removed" in low or "status: absent" in low
            assert page_declares or any(word in window for word in ABSENCE), (
                f"{page.name} names {library!r} without saying it is absent; either the project "
                f"uses it (declare and import it) or the sentence must state that it does not")
            start = hit + len(library)



def test_the_core_dependencies_are_declared():
    # framework/__init__.py imports numpy; a "core" that cannot import itself is not core.
    declared = _declared()
    assert {"numpy", "matplotlib", "pyyaml"} <= declared
