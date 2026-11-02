"""The VRAM budget must be the configured one, not the class default.

`can_load` compared against `self.VRAM_BUDGET_GB` while `__init__` stored the
configured value in `self.vram_budget`; a manager built for an 8 GB card therefore
admitted a 12 GB plan. These tests pin the arithmetic in both directions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.inference import ModelManager


def test_configured_budget_is_honoured():
    # llama3.1:8b is registered at 5.0 GB (q4_k_m), so 4 GB must refuse and 6 GB admit.
    assert ModelManager({"vram_budget_gb": 4}).can_load("llama3.1:8b") is False
    assert ModelManager({"vram_budget_gb": 6}).can_load("llama3.1:8b") is True


def test_large_model_is_rejected_at_12gb():
    assert ModelManager({"vram_budget_gb": 12}).can_load("llama3.1:70b") is False


def test_already_used_vram_counts_against_the_budget():
    manager = ModelManager({"vram_budget_gb": 12})
    manager.vram_used_gb = 8.0
    assert manager.can_load("llama3.1:8b") is False  # 8 + 9 > 12
