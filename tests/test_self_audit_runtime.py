"""Self-audit owns its workers and reports timeouts without publishing success."""
import os
from pathlib import Path
import sys
import time
import subprocess

import pytest

from tools import record_self_audit as audit


def tree(marker,delay,keep_root=False):
    child=f'import time;from pathlib import Path;time.sleep({delay});Path({str(marker)!r}).write_text("late child")'
    parent=('import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);print("root started",flush=True)')
    if keep_root:parent+=';time.sleep(5)'
    return [sys.executable,'-c',parent]


def test_normal_audit_completion_closes_owned_descendants(tmp_path,monkeypatch):
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    marker=tmp_path/'late.txt'
    run=audit._run(tree(marker,.5),timeout=5)
    assert run.returncode==0 and 'root started' in run.stdout
    time.sleep(1.5)
    assert not marker.exists()


def test_audit_timeout_is_a_failed_result_and_closes_owned_descendants(tmp_path,monkeypatch):
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    marker=tmp_path/'late.txt'
    run=audit._run(tree(marker,2.2,True),timeout=1.5)
    assert run.returncode==124 and 'TIMEOUT' in run.stderr
    assert 'root started' in run.stdout
    time.sleep(2.5)
    assert not marker.exists()


def test_audit_capture_sets_child_utf8_without_changing_parent(tmp_path,monkeypatch):
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    monkeypatch.setenv('PYTHONIOENCODING','latin-1')
    run=audit._run([sys.executable,'-c','print("science \\u00b5")'],timeout=5)
    assert run.returncode==0 and run.stdout.strip()=='science µ'
    assert os.environ['PYTHONIOENCODING']=='latin-1'


def test_explicit_full_suite_budget_reaches_measurement(tmp_path,monkeypatch):
    seen=[]
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    monkeypatch.setattr(audit,'OUT',tmp_path/'SELF_AUDIT.json')
    monkeypatch.setattr(audit,'measure',lambda options:seen.append(options.test_timeout) or 0)
    assert audit.main(['--test-timeout','1800'])==0
    assert seen==[1800]


def test_actual_item_timings_are_retained_with_the_requested_budget(monkeypatch):
    def run(command,timeout=900):
        assert timeout==1800
        report=Path(next(arg.split('=',1)[1] for arg in command if arg.startswith('--junitxml=')))
        report.write_text('<testsuite><testcase classname="tests.example" name="fast" time="1.25"/><testcase classname="tests.example" name="slow" time="2.5"/></testsuite>')
        return subprocess.CompletedProcess(command,0,'2 passed','')
    monkeypatch.setattr(audit,'_run',run)
    _,execution=audit.execute_tests([sys.executable,'-m','pytest'],timeout=1800)
    assert execution['reported_items']==2
    assert execution['slowest_tests'][0]=={'test':'tests.example::slow','seconds':2.5}


@pytest.mark.parametrize('timeout',['0','-1','nan','inf'])
def test_invalid_full_suite_budget_is_refused_before_measurement(tmp_path,monkeypatch,timeout):
    monkeypatch.setattr(audit,'measure',lambda _:pytest.fail('Invalid timeout reached measurement'))
    with pytest.raises(SystemExit) as error:audit.main(['--test-timeout',timeout])
    assert error.value.code==2
