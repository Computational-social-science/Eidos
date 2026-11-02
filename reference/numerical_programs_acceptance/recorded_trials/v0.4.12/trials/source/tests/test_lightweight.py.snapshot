"""Eidos must stay lightweight: importing the registry may not pull a project's stack.

The registry is the framework's only production interface, and it is used from a
shell on machines that may not have torch, chromadb or mlflow. A stray top-level
import would turn `python -m framework.project list` into an install error on a
fresh clone, which is the opposite of a lightweight framework.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAVY = ("torch", "chromadb", "mlflow", "dvc", "pandas", "numpy",
         "sentence_transformers", "matplotlib", "scipy")


def test_registry_import_pulls_no_heavy_dependency():
    code = (
        "import sys\n"
        "import framework.project\n"
        f"heavy = [m for m in {HEAVY!r} if m in sys.modules]\n"
        "print(','.join(heavy))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, check=True,
    )
    assert proc.stdout.strip() == "", (
        f"importing framework.project pulled heavy dependencies: {proc.stdout.strip()}"
    )
