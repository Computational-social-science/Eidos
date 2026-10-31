"""One scheduler loop, serialized ticks, and preserved historical failures."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tools import refresh_chains


@pytest.fixture
def scheduler(tmp_path,monkeypatch):
    status=tmp_path/'status';status.mkdir()
    monkeypatch.setattr(refresh_chains,'STATUS',status)
    monkeypatch.setattr(refresh_chains,'CHAINS',status/'chains.json')
    monkeypatch.setattr(refresh_chains,'HEARTBEAT',status/'scheduler.json')
    return status


@contextmanager
def held(directory):
    code=('import sys;from pathlib import Path;from framework.artifacts import output_lock;'
          '\nwith output_lock(Path(sys.argv[1]),timeout=0):\n'
          ' print("owned",flush=True);sys.stdin.readline()')
    child=subprocess.Popen([sys.executable,'-c',code,str(directory)],stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                           cwd=Path(__file__).resolve().parents[1],
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        assert child.stdout.readline().strip()=='owned'
        yield
    finally:
        child.communicate('release\n',timeout=10)
        assert child.returncode==0


def test_existing_os_loop_owner_prevents_a_second_loop(scheduler,monkeypatch):
    def forbidden(_):pytest.fail('a duplicate scheduler loop started')
    monkeypatch.setattr(refresh_chains.time,'sleep',forbidden)
    with held(scheduler/'scheduler-loop'):
        assert refresh_chains.main(['--loop'])==0


def test_concurrent_tick_cannot_run_or_overwrite_a_heartbeat(scheduler):
    path=scheduler/'scheduler.json';path.write_text('{"previous":true}')
    with held(scheduler/'scheduler-tick'):
        assert refresh_chains.main([])==75
    assert path.read_text()=='{"previous":true}'


def test_new_tick_preserves_failure_history_and_records_actual_runtime(scheduler):
    (scheduler/'chains.json').write_text(json.dumps({'chains':{'gates':{'ts':time.time()}}}))
    path=scheduler/'scheduler.json';path.write_text('{"ticks":19,"failures_total":7}')
    assert refresh_chains.main([])==0
    record=json.loads(path.read_text())
    assert record['ticks']==20 and record['failures_total']==7
    assert record['pid'] and record['python']==sys.executable


@pytest.mark.parametrize('args',[['--loop','--dry-run'],['--loop','--report'],['--interval','0']])
def test_incompatible_or_invalid_options_cannot_bypass_ownership(scheduler,args):
    with pytest.raises(SystemExit) as error:refresh_chains.main(args)
    assert error.value.code==2


def test_timed_out_chain_is_recorded_instead_of_losing_the_tick(scheduler,monkeypatch):
    from tools import bounded_process
    (scheduler/'chains.json').write_text(json.dumps({'chains':{'gates':{'ts':0}}}))
    def timeout(*args,**kwargs):raise subprocess.TimeoutExpired('worker',900)
    monkeypatch.setattr(bounded_process,'run_tree',timeout)
    assert refresh_chains.main([])==1
    record=json.loads((scheduler/'scheduler.json').read_text())
    assert record['failed']==['gates'] and record['ran'][0]['exit']==124
    assert record['failures_total']==1


@pytest.mark.parametrize('status,code',[('PASS',0),('SKIP',0),('FAIL',1),('ERROR',1)])
def test_structured_chain_status_is_preserved(scheduler,monkeypatch,capsys,status,code):
    from tools import bounded_process
    (scheduler/'chains.json').write_text(json.dumps({'chains':{'gates':{'ts':0}}}))
    def result(argv,**kwargs):
        return subprocess.CompletedProcess(argv,code,json.dumps([{'chain':'gates','status':status,'detail':'test'}]),'')
    monkeypatch.setattr(bounded_process,'run_tree',result)
    assert refresh_chains.main([])==(0 if code==0 else 1)
    record=json.loads((scheduler/'scheduler.json').read_text())
    assert record['ran'][0]['status']==status
    assert f'{status}  gates' in capsys.readouterr().out
    assert record['failed']==([] if code==0 else ['gates'])


@pytest.mark.parametrize('output',['not json','[]','[{"chain":"other","status":"PASS"}]',
                                   '[{"chain":"gates","status":"FAIL"}]'])
def test_invalid_or_contradictory_success_cannot_be_promoted(scheduler,monkeypatch,output):
    from tools import bounded_process
    monkeypatch.setattr(bounded_process,'run_tree',lambda argv,**kwargs:subprocess.CompletedProcess(argv,0,output,''))
    record=refresh_chains.run_chain('gates')
    assert record['status']=='ERROR' and record['exit']!=0


def test_fresh_heartbeat_cannot_hide_a_timed_out_chain_from_overall_state(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'tools'))
    from tools import watch_pipeline,status_view
    signals=watch_pipeline.scheduler_signals({'epoch':time.time(),'interval_min':10,'failed':['gates']})
    classified={name:{**row,'state':watch_pipeline.classify(row)[0]} for name,row in signals.items()}
    assert classified['scheduler']['state']=='OK'
    assert classified['scheduler_failures']['state']=='ALARM'
    assert status_view.derive(classified,{'gates':'PASS'})['overall']=='ALARM'
