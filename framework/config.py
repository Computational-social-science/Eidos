"""The framework's declared policy, read from `configs/global/framework.yaml`.

Until now that file was documentation: nothing loaded it, and it drifted — it still named the
framework `global_research_framework`, claimed version 4.0, and kept a vector-store memory block
that had been removed. A file that looks like configuration and is read by nobody is a false
statement about how the system works.

This module makes it real for the values that matter to behaviour (the VRAM budget today), and
`tests/test_framework_config.py` holds the rest of the file to the code: model names, mutex pairs,
probe size, absence of absolute paths, absence of a deleted memory layer.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "configs" / "global" / "framework.yaml"


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    import yaml

    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def global_config(path: str | os.PathLike | None = None) -> dict:
    """The whole document, with the `framework:` root unwrapped."""
    document = _load(str(path or DEFAULT_PATH))
    return document.get("framework", document)


def get(dotted: str, default=None, path: str | os.PathLike | None = None):
    """`get("inference.vram_budget_gb")` — a dotted read with an explicit fallback."""
    node = global_config(path)
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def reset_cache() -> None:
    _load.cache_clear()
