"""The project's gate command: measure, then render. Both must succeed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script: str) -> int:
    proc = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE)
    return proc.returncode


if __name__ == "__main__":
    for script in ("build_evidence.py", "render_results.py"):
        code = run(script)
        if code != 0:
            raise SystemExit(code)
    raise SystemExit(0)
