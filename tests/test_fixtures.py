"""Every gate check must have a fixture that trips it, and one that must not.

The audit is the test: it fails if a fixture rejects for the wrong reason, if a check has no
fixture, or if the clean control is rejected. Running it from pytest keeps it in the commit gate.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_check_has_a_fixture_that_trips_it():
    run = subprocess.run([sys.executable, "tools/audit_fixtures.py"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "S1-S9 each trip once" in run.stdout


def test_the_clean_fixture_is_not_rejected():
    run = subprocess.run([sys.executable, "tools/audit_fixtures.py", "--verbose"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    line = [l for l in run.stdout.splitlines() if l.startswith("clean")][0]
    assert "PASS" in line and "ok" in line, line
