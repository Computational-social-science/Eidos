"""The project's gate entry point: run the agent with an interpreter that can speak MCP.

`agent.py` needs `fastmcp`. The sampler does not carry it, so on a developer machine the gate would fail
for the wrong reason — the code is fine, the interpreter is not. This wrapper re-execs into the project's
reproduction venv when the import is missing, and does nothing when it is present (CI installs fastmcp, so
there it runs directly).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _has_fastmcp() -> bool:
    try:
        import fastmcp  # noqa: F401
        return True
    except ImportError:
        return False


def _venv_python() -> Path | None:
    for candidate in (REPO / ".venv-repro" / "Scripts" / "python.exe",
                      REPO / ".venv-repro" / "bin" / "python"):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    if _has_fastmcp():
        from agent import main as agent_main
        return agent_main()
    python = _venv_python()
    if python is None:
        print("FAIL fastmcp is not importable and .venv-repro has no interpreter")
        return 2
    print(f"re-exec under {python}")
    env = dict(os.environ)
    env["VIRTUAL_ENV"] = str(python.parent.parent)
    return subprocess.run([str(python), str(HERE / "agent.py")], cwd=str(HERE), env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
