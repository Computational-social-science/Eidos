"""The policy file must agree with the code, or it is decoration.

`configs/global/framework.yaml` claimed to be the framework's configuration while nothing loaded
it: it named the framework `global_research_framework`, said version 4.0, kept a vector-store
memory block that had been deleted, and pointed at `E:/2026-AI4S/bootloops` — an absolute path that
would break on any other machine. These tests are the mechanism that stops that happening again.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from framework import config
from framework.inference import ModelManager


@pytest.fixture(scope="module")
def policy():
    return config.global_config()


def test_the_file_names_the_framework_it_configures(policy):
    assert policy["name"] == "Eidos"
    assert "global_research_framework" not in str(policy)


def test_the_version_is_not_duplicated(policy):
    """pyproject.toml is the single source; a second literal is a second truth."""
    assert "version" not in policy
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert re.search(r'^version = "', pyproject.read_text(encoding="utf-8"), re.M)


def test_no_absolute_paths(policy):
    """A clone on another machine must not inherit this machine's drive letters."""
    offenders = []

    def walk(node, trail="framework"):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{trail}[{i}]")
        elif isinstance(node, str) and re.match(r"^([A-Za-z]:[\\/]|/|\\\\)", node):
            # `/artifacts/...` is a repository-relative JSON pointer, not a filesystem path.
            if not node.startswith("/artifacts/"):
                offenders.append(f"{trail} = {node}")

    walk(policy)
    assert offenders == []


def test_the_deleted_memory_layer_stays_deleted(policy):
    assert "memory" not in policy
    assert policy["knowledge"]["vector_store"] is False


def test_every_declared_model_exists_in_the_registry(policy):
    registry = ModelManager.MODEL_REGISTRY
    declared = {m["name"] for m in policy["inference"]["models"]}
    assert declared <= set(registry), f"undeclared in code: {declared - set(registry)}"
    for entry in policy["inference"]["models"]:
        spec = registry[entry["name"]]
        assert entry["vram_gb"] == pytest.approx(spec.vram_gb, abs=0.05), entry["name"]
        if "context" in entry:
            assert entry["context"] == spec.context_window, entry["name"]


def test_the_mutex_pairs_are_symmetric_in_the_policy(policy):
    pairs = {m["name"]: set(m.get("mutex_with") or []) for m in policy["inference"]["models"]}
    for name, partners in pairs.items():
        for partner in partners:
            assert name in pairs.get(partner, set()), f"{name} excludes {partner}, not the reverse"


def test_the_budget_is_the_one_the_manager_uses(policy):
    assert policy["inference"]["vram_budget_gb"] == policy["hardware"]["vram_budget_gb"]
    assert ModelManager().vram_budget == policy["inference"]["vram_budget_gb"]
    assert ModelManager({"vram_budget_gb": 4}).vram_budget == 4     # explicit still wins


def test_the_probe_size_matches_the_fixtures(policy):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import probe_s4

    declared = policy["gates"]["s4_probe"]
    assert declared["cases"] == len(probe_s4.CASES)
    assert declared["promotion_threshold"] == 0.90


def test_the_verifiers_section_names_what_the_code_does(policy):
    verifiers = policy["verifiers"]
    assert verifiers["citations"]["tool"] == "proofpath"
    assert verifiers["statistics"]["tool"] == "academic-research-kernel"
    assert verifiers["support"]["backend"] is None            # no accessible tool exists
    assert verifiers["pointers"]["rules"]["statistics"] == "stat_recompute.json"
