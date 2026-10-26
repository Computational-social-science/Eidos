"""The VRAM contract: two mutually exclusive models cannot be resident together.

The plan (§5) requires a hard mutex between ScienceRSI-8b and StartLux-Decision-4B, and a unit test
that both footprints cannot be resident at once. The model file is absent, so the test asserts the
*contract*: with two declared partners, loading one makes the other unloadable even when the budget
would allow both. An asymmetric declaration is refused outright.
"""

from __future__ import annotations

import pytest

from framework.inference import ModelManager, ModelProvider, ModelSize, ModelSpec


@pytest.fixture()
def pair(monkeypatch):
    a = ModelSpec("A", ModelProvider.OLLAMA, ModelSize.MEDIUM, "a", 3.0, 8192,
                  mutex_with=("B",))
    b = ModelSpec("B", ModelProvider.OLLAMA, ModelSize.MEDIUM, "b", 3.0, 8192,
                  mutex_with=("A",))
    registry = dict(ModelManager.MODEL_REGISTRY)
    registry.update({"A": a, "B": b})
    monkeypatch.setattr(ModelManager, "MODEL_REGISTRY", registry)
    return registry


def test_both_models_fit_the_budget_but_not_together(pair):
    manager = ModelManager({"vram_budget_gb": 10.5})
    # Simulate A resident (no server is started: this is the accounting layer).
    manager.loaded_models["A"] = {"vram_gb": 3.0, "last_used": 0.0}
    manager.vram_used_gb = 3.0

    assert manager.vram_used_gb + manager.estimate_vram("B") <= manager.vram_budget
    assert manager.mutex_partners_loaded("B") == ["A"]
    assert manager.can_load("B") is False


def test_an_asymmetric_mutex_is_refused(pair, monkeypatch):
    pair["C"] = ModelSpec("C", ModelProvider.OLLAMA, ModelSize.MEDIUM, "c", 1.0, 8192,
                          mutex_with=("A",))
    with pytest.raises(ValueError, match="does not exclude C"):
        ModelManager.validate_registry()


def test_a_mutex_with_an_unknown_model_is_refused(pair):
    pair["D"] = ModelSpec("D", ModelProvider.OLLAMA, ModelSize.MEDIUM, "d", 1.0, 8192,
                          mutex_with=("nope",))
    with pytest.raises(ValueError, match="unknown model"):
        ModelManager.validate_registry()


def test_a_symmetric_pair_validates(pair):
    ModelManager.validate_registry()          # the fixture pair is symmetric
