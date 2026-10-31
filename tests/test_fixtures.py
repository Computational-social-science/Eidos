"""Every gate check must have a fixture that trips it, and one that must not.

The audit is the test: it fails if a fixture rejects for the wrong reason, if a check has no
fixture, or if the clean control is rejected. Running it from pytest keeps it in the commit gate.
"""

from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_check_has_a_fixture_that_trips_it():
    run = subprocess.run([sys.executable, "tools/audit_fixtures.py"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "S1-S12 each trip once" in run.stdout


def test_the_clean_fixture_is_not_rejected():
    run = subprocess.run([sys.executable, "tools/audit_fixtures.py", "--verbose"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    line = [l for l in run.stdout.splitlines() if l.startswith("clean")][0]
    assert "PASS" in line and "ok" in line, line


def test_additional_unrelated_failure_is_not_a_passing_fixture(tmp_path,monkeypatch):
    from tools import audit_fixtures
    (tmp_path/'docs').mkdir()
    monkeypatch.setattr(audit_fixtures,'ROOT',tmp_path)
    expected=audit_fixtures.EXPECTED
    def fake(name):
        verdict,code=expected[name]
        checks={code} if code else set()
        if name=='s10_statistics_rejected':
            checks.add('S3')
        return verdict,checks,[]
    monkeypatch.setattr(audit_fixtures,'run_one',fake)
    assert audit_fixtures.main([])==1
    record=json.loads((tmp_path/'docs/FIXTURES.json').read_text())
    assert len(record['required_checks'])==12
    assert not next(r for r in record['fixtures'] if r['fixture']=='s10_statistics_rejected')['ok']


def test_missing_s10_cannot_hide_behind_old_s1_to_s9_coverage(tmp_path,monkeypatch):
    from tools import audit_fixtures
    (tmp_path/'docs').mkdir()
    monkeypatch.setattr(audit_fixtures,'ROOT',tmp_path)
    expected=audit_fixtures.EXPECTED
    def fake(name):
        verdict,code=expected[name]
        return verdict,({code} if code and code!='S10' else set()),[]
    monkeypatch.setattr(audit_fixtures,'run_one',fake)
    assert audit_fixtures.main([])==1
    record=json.loads((tmp_path/'docs/FIXTURES.json').read_text())
    assert 'S10' not in record['covered'] and not record['ok']
