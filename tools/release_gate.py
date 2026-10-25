"""Rehearse onboarding before a release claims to enable it.

The mission is that this framework can take a new project from nothing to a checked verdict. That
is a claim about the framework, so it is exactly the kind of claim a release must re-earn rather
than remember. This gate does it the way a newcomer would:

1. scaffold a project from the template into a temporary directory
2. run its measurement
3. run Gate S on it and require PASS
4. run the template's own rejection demo and require a rejection

    python tools/release_gate.py           # exit 0 = the framework can still onboard
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMPLATE = ROOT / "reference" / "demo_onboarding"


def _run(cmd: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    # The template locates the framework by walking up, which fails for a rehearsal outside the
    # repository; EIDOS_ROOT states it explicitly, exactly as a real external project would.
    env = dict(os.environ, EIDOS_ROOT=str(ROOT))
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def _note(proc: subprocess.CompletedProcess, last: bool = True) -> str:
    out = (proc.stdout or proc.stderr or "").strip().splitlines()
    if not out:
        return ""
    return (out[-1] if last else out[0])[:100]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    # Inside the repository and ignored by git: a rehearsal on another drive cannot be described
    # relative to the registry, and an absolute root there would violate the project rule.
    tmp = ROOT / "docs" / "status" / "_release_rehearsal"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    project = tmp / "onboard_rehearsal"
    steps: list[tuple[str, bool, str]] = []
    try:
        copy = _run([sys.executable, "tools/bootstrap_project.py",
                     "--name", "onboard_rehearsal", "--dest", str(project), "--no-register"], ROOT, 120)
        steps.append(("scaffold from template", copy.returncode == 0, _note(copy, last=False)))

        measure = _run([sys.executable, "build_evidence.py"], project, 900)
        steps.append(("measure", measure.returncode == 0, _note(measure, last=False)))

        if measure.returncode == 0:
            from framework.validity import ScientificValidityGate
            gate = ScientificValidityGate(project, register=project / "analysis" / "CLAIMS.yaml",
                                          document=project / "docs" / "REPORT.md")
            result = gate.run()
            findings = len((getattr(result, "details", {}) or {}).get("findings", []))
            steps.append(("Gate S on the scaffold", result.passed, f"{findings} finding(s)"))

        reject = _run([sys.executable, "show_rejection.py"], TEMPLATE, 300)
        steps.append(("template rejects a lie (S9)", reject.returncode == 0, _note(reject)))
    finally:
        # A rehearsal must leave no registration behind: a registry entry pointing at a deleted
        # directory makes every later load_projects() fail, which is how this was found.
        shutil.rmtree(ROOT / "projects" / "onboard_rehearsal", ignore_errors=True)
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)

    for name, ok, note in steps:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<28} {note[:90]}")
    failed = [n for n, ok, _ in steps if not ok]
    if failed:
        print(f"\n[FAIL] onboarding rehearsal failed: {', '.join(failed)}")
        return 1
    print("\n[OK] a new project still reaches a checked verdict from the template")
    return 0


if __name__ == "__main__":
    sys.exit(main())
