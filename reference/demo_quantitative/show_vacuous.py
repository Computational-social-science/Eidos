"""Third act: a gate that exits 0 and produces nothing must not count as a pass.

The registry declares `expects: [docs/evidence.json, docs/results.html]`. This script builds a
local project whose gate command does nothing, runs it without global registration,
and expects FAIL. Existing projects and demonstration directories are never replaced.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in (HERE, *HERE.parents) if (p / "framework" / "project.py").is_file())
sys.path.insert(0,str(ROOT))

from framework.project import load_project, run_command
from tools.owned_workspace import owned_workspace


def main() -> int:
    with owned_workspace(ROOT/'docs/status',prefix='_vacuous_demo-') as tmp:
        spec=tmp/'project.yaml'
        spec.write_text('name: vacuous_demo\nroot: .\n'
                        'gate_command: ["{python}", "-c", "pass"]\n'
                        'expects: [docs/evidence.json]\n',encoding='utf-8')
        run=run_command(load_project(spec),timeout=30)
        print(f'{run.status} {run.name}: {run.stderr_tail}')
        rejected = run.status=='FAIL' and run.exit_code==0 and 'declared output missing' in run.stderr_tail
        print(f"\n{'[OK]' if rejected else '[FAIL]'} the vacuous pass was "
              f"{'refused' if rejected else 'accepted — that is a defect'}")
        return 0 if rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
