"""A project states only what differs; the global policy supplies the rest.

ARCHITECTURE §1.1 claimed this inheritance long before it existed. These tests pin the merge: nested
keys merge, the project wins, lists are replaced rather than concatenated (a project that redefines
`inference.models` means its list), and the global document is never mutated.
"""

from __future__ import annotations

from pathlib import Path

from framework import config
from framework.project import load_project


def test_nested_merge_keeps_siblings_and_lets_the_project_win():
    base = {"inference": {"vram_budget_gb": 10.5, "max_concurrent": 1}, "name": "Eidos"}
    merged = config.deep_merge(base, {"inference": {"vram_budget_gb": 6}})
    assert merged["inference"] == {"vram_budget_gb": 6, "max_concurrent": 1}
    assert merged["name"] == "Eidos"
    assert base["inference"]["vram_budget_gb"] == 10.5      # base untouched


def test_lists_are_replaced_not_concatenated():
    base = {"inference": {"models": [{"name": "A"}]}}
    merged = config.deep_merge(base, {"inference": {"models": [{"name": "B"}]}})
    assert merged["inference"]["models"] == [{"name": "B"}]


def test_a_project_yaml_carries_overrides(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "project.yaml").write_text(
        "name: demo\n"
        "root: .\n"
        "gate_command: ['true']\n"
        "overrides:\n"
        "  inference:\n"
        "    vram_budget_gb: 6\n"
        "  gates:\n"
        "    s4_probe:\n"
        "      promotion_threshold: 0.95\n", encoding="utf-8")
    spec = load_project(project / "project.yaml")
    effective = spec.effective_config()
    assert effective["inference"]["vram_budget_gb"] == 6
    assert effective["inference"]["max_concurrent"] == 1          # inherited
    assert effective["gates"]["s4_probe"]["promotion_threshold"] == 0.95
    assert effective["gates"]["s4_probe"]["cases"] == 15          # inherited
    assert config.global_config()["inference"]["vram_budget_gb"] == 10.5


def test_a_project_without_overrides_gets_the_global_policy(tmp_path):
    project = tmp_path / "plain"
    project.mkdir()
    (project / "project.yaml").write_text(
        "name: plain\nroot: .\ngate_command: ['true']\n", encoding="utf-8")
    spec = load_project(project / "project.yaml")
    assert spec.overrides == {}
    assert spec.effective_config()["inference"]["vram_budget_gb"] == 10.5
