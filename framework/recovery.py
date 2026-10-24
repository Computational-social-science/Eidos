"""Recovery actions, planned from a diagnosis — the second half of the loop.

Detection is not recovery. The watcher measures, `framework.diagnosis` names the failure,
and this module decides whether that failure has a **known, safe action** and runs it. The
three are kept in that order on purpose:

    measure -> diagnose -> plan -> execute -> measure again

A recovery is only offered when the diagnosis maps to an action here. Anything else stays
a human decision: an unknown failure with an automatic "restart everything" is worse than
no automation, because it hides the cause behind a green light.

    python -m framework.recovery            # list what can be recovered
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: Actions are declared by the *service* they repair, not by the symptom. One entry per
#: thing this machine can actually start; everything else is "not restartable" and says so.
ACTIONS = {
    "runtime_18434": {
        "description": "start the managed llama.cpp runtime on 127.0.0.1:18434",
        "script": ("hermes", "scripts", "start_local_runtime.py"),
        "env_root": "LOCALAPPDATA",
    },
}


@dataclass
class RecoveryPlan:
    service: str
    action: str
    description: str
    available: bool
    reason: str = ""


def plan(service: str) -> RecoveryPlan:
    """Map a failing service to an action, or say precisely why there is none."""
    spec = ACTIONS.get(service)
    if spec is None:
        return RecoveryPlan(service, "none", "", False, "no recovery action is declared")
    root = os.environ.get(spec["env_root"], "")
    if not root:
        return RecoveryPlan(service, service, spec["description"], False,
                            f"{spec['env_root']} is not set, so the script cannot be located")
    script = Path(root) / Path(*spec["script"])
    if not script.is_file():
        return RecoveryPlan(service, service, spec["description"], False,
                            f"start script not found: {script}")
    return RecoveryPlan(service, service, spec["description"], True)


def execute(plan_: RecoveryPlan) -> dict:
    """Run a plan. Returns what happened, never raises for an expected failure."""
    if not plan_.available:
        return {"ok": False, "error": plan_.reason}
    spec = ACTIONS[plan_.service]
    script = Path(os.environ[spec["env_root"]]) / Path(*spec["script"])
    try:
        proc = subprocess.Popen([sys.executable, str(script)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                close_fds=True)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "pid": proc.pid, "service": plan_.service,
            "action": plan_.action, "description": plan_.description}


if __name__ == "__main__":
    for name in ACTIONS:
        plan_ = plan(name)
        print(f"{name:16s} {'available' if plan_.available else 'unavailable':12s} "
              f"{plan_.description}{'' if plan_.available else ' — ' + plan_.reason}")
