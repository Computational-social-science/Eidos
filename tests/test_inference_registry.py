"""Registry integrity: one entry per model, and the decision operator is a service.

A duplicate key in the `MODEL_REGISTRY` dict literal is silently collapsed by Python:
the last definition wins. That happened here — a `STARTLUX` entry was overridden by a
later `CPU` entry for the same name, so the scheduler would have tried to spawn a
local llama.cpp process for a model that only exists as a service. The AST test below
sees the duplicate because the parser does; runtime inspection cannot.
"""

import ast
import pytest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.inference import ModelManager, ModelProvider, StageAwareScheduler

SOURCE = ROOT / "framework" / "inference" / "__init__.py"


def _registry_keys() -> list[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ModelManager":
            for item in node.body:
                if (isinstance(item, ast.Assign)
                        and any(getattr(t, "id", None) == "MODEL_REGISTRY" for t in item.targets)
                        and isinstance(item.value, ast.Dict)):
                    return [str(k.value) for k in item.value.keys
                            if isinstance(k, ast.Constant)]
    raise AssertionError("MODEL_REGISTRY not found in ModelManager")


def test_registry_has_no_duplicate_keys():
    keys = _registry_keys()
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    assert not duplicates, f"duplicate model keys silently override each other: {duplicates}"


def test_decision_operator_is_a_service_not_a_local_process():
    spec = ModelManager.MODEL_REGISTRY["StartLux-Decision-4B-Q8_0"]
    assert spec.provider is ModelProvider.STARTLUX
    assert spec.path.startswith("http"), "an external operator must carry its URL"


def test_d1_is_no_longer_a_framework_model():
    """The owner's decision: StartLux replaces d1-3B everywhere in this framework."""
    assert "d1-3B-BF16" not in ModelManager.MODEL_REGISTRY
    for stage, models in StageAwareScheduler.STAGE_MODELS.items():
        assert "d1-3B-BF16" not in models, f"d1-3B-BF16 still routed at stage {stage!r}"


class RecordingManager:
    def __init__(self, success=()):
        self.success=set(success)
        self.calls=[]
    def load_model(self, name):
        self.calls.append(name)
        return name in self.success


def test_scientific_stages_cannot_borrow_readiness_from_unqualified_candidates():
    manager=RecordingManager({'llama3.1:8b'})
    scheduler=StageAwareScheduler(manager)
    assert not scheduler.prepare_stage('hypothesis_generation')
    assert manager.calls==[]
    assert scheduler.describe_stage('hypothesis_generation')['task_qualification']=='UNQUALIFIED'


def test_draft_preparation_stops_after_one_available_alternative():
    manager=RecordingManager({'llama3.1:8b','qwen2.5:14b'})
    scheduler=StageAwareScheduler(manager)
    assert scheduler.prepare_stage('hypothesis_generation',allow_unqualified_draft=True)
    assert manager.calls==['llama3.1:8b']
    assert scheduler.describe_stage('hypothesis_generation')['scientific_authority'] is False


def test_execution_and_scientific_gates_do_not_load_a_decision_model():
    manager=RecordingManager()
    scheduler=StageAwareScheduler(manager)
    for stage in ('experiment_execution','evaluation_gates'):
        assert scheduler.prepare_stage(stage)
        assert scheduler.get_stage_models(stage)==[]
    assert manager.calls==[]
    with pytest.raises(ValueError):
        scheduler.prepare_stage('misspelled_stage')
    with pytest.raises(ValueError):
        scheduler.cleanup_stage('misspelled_stage')
    assert not scheduler.prepare_stage('hypothesis_generation',allow_unqualified_draft='false')


def test_inference_audit_detects_full_decision_model_name_leaking_into_generation(monkeypatch):
    from framework import inference
    from tools import audit_chains
    class Manager:
        def __init__(self, config):
            self.vram_budget=config['vram_budget_gb']
        def can_load(self, name):
            return self.vram_budget>=5
    class LeakingScheduler:
        def get_stage_models(self, stage):
            if stage in ('experiment_execution','evaluation_gates'):
                return []
            return ['StartLux-Decision-4B-Q8_0']
        def describe_stage(self, stage):
            return {'task_qualification':'UNQUALIFIED'}
    monkeypatch.setattr(inference,'ModelManager',Manager)
    monkeypatch.setattr(inference,'create_stage_scheduler',lambda config:LeakingScheduler())
    assert audit_chains.audit_inference()[0]=='FAIL'
