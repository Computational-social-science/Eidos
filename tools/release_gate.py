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
import json
import os
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
    from tools.bounded_process import run_tree
    return run_tree(cmd,cwd=cwd,timeout=timeout,env=env)


def _note(proc: subprocess.CompletedProcess, last: bool = True) -> str:
    out = (proc.stdout or proc.stderr or "").strip().splitlines()
    if not out:
        return ""
    return (out[-1] if last else out[0])[:100]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--min-coverage", type=int, default=6,
                    help="capabilities a consumer must demonstrate before a release")
    args = ap.parse_args(argv)

    # Own a unique workspace. Never remove a pre-existing workspace or registration:
    # this invocation uses --no-register and therefore owns no registry entry.
    from tools.owned_workspace import owned_workspace
    steps: list[tuple[str, bool, str]] = []
    with owned_workspace(ROOT/'docs/status',prefix='_release_rehearsal-',keep=args.keep) as tmp:
        project = tmp / "onboard_rehearsal"
        copy = _run([sys.executable, "tools/bootstrap_project.py",
                     "--name", "onboard_rehearsal", "--dest", str(project), "--no-register"], ROOT, 120)
        steps.append(("scaffold from template", copy.returncode == 0, _note(copy, last=False)))

        if copy.returncode == 0:
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

        quant = ROOT / "reference" / "demo_quantitative"
        vacuous = _run([sys.executable, "show_vacuous.py"], quant, 300)
        steps.append(("a vacuous gate is refused", vacuous.returncode == 0, _note(vacuous)))

        coverage = _run([sys.executable, "tools/demo_coverage.py", "--json"], ROOT, 300)
        demo_cov = 0
        try:
            data = json.loads((ROOT / "docs" / "DEMO_COVERAGE.json").read_text(encoding="utf-8"))
            demo_cov = int(data.get("demo") or 0)
        except (OSError, json.JSONDecodeError):
            pass
        steps.append((f"demo coverage >= {args.min_coverage}", coverage.returncode == 0 and demo_cov >= args.min_coverage,
                      f"{demo_cov} capabilities demonstrated; producer exit {coverage.returncode}"))
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
