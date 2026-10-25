"""The two audits that ask whether the chain can say no.

Gate fixtures prove every check fires on a hand-built case. Mutation testing asks the other
question: is there a wrong register the gate accepts? Chain fixtures ask it one level up: does a
gate that exits 0 without producing an artefact count as approval?
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True,
                          text=True, timeout=300)


def test_no_wrong_register_passes():
    run = _run("tools/fuzz_register.py")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "no wrong register passes" in run.stdout


def test_chain_consumers_behave_as_declared():
    run = _run("tools/audit_chain_fixtures.py")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "vacuous pass and a missing tool are both refused" in run.stdout


def test_a_dead_half_of_a_pair_is_named():
    run = _run("tools/audit_services.py")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "dead half is named" in run.stdout
