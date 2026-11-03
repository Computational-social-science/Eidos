"""A shared monitor observes project workers without running their research."""
import json
from pathlib import Path
import re
import sys

import pytest

from test_installed_cli import initialise, configure, python_entry, scientific_fixture


NONCE='a'*32


def observe(project):
    return python_entry('observe','--project',str(project),'--nonce',NONCE,'--json')


def bytes_in(project):
    return {p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}


def test_observe_unrun_project_reports_current_worker_and_never_executes(tmp_path,monkeypatch):
    from framework import cli, project_state
    project=tmp_path/'study';initialise(project,tmp_path)
    before=bytes_in(project)
    def forbidden(*args,**kwargs):raise AssertionError('Observation must never run research')
    monkeypatch.setattr(cli,'run_command',forbidden)
    code,value=observe(project)
    assert code==0 and value['schema']=='eidos.worker-observation.v1'
    assert value['status']=='OBSERVED' and value['nonce']==NONCE
    assert re.fullmatch('[0-9a-f]{32}',value['project']['id'])
    assert value['project']['root']==str(project.resolve())
    assert value['run']['status']=='UNRUN' and value['run']['scientific_status']=='UNRUN'
    assert value['worker']['executable']==str(Path(sys.executable).resolve())
    assert value['worker']['prefix']==str(Path(sys.prefix).resolve())
    assert re.fullmatch('[0-9a-f]{64}',value['worker']['sdk_source_sha256'])
    assert value['binding']['state']=='STABLE' and bytes_in(project)==before


def test_observe_keeps_execution_and_science_distinct_without_exposing_logs(tmp_path,monkeypatch):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','print("private-worker-log")'])
    python_entry('check','--project',str(project),'--execution-only','--json')
    monkeypatch.setenv('EIDOS_PRIVATE_ENV','private-environment-marker')
    before=bytes_in(project)
    code,value=observe(project)
    assert code==0 and value['run']['status']=='PASS'
    assert value['run']['execution_status']=='PASS' and value['run']['scientific_status']=='UNRUN'
    assert value['worker']['eidos_version']==value['run']['eidos_version']
    assert value['run']['recorded_at']<=value['observed_at']
    assert 'private-worker-log' not in json.dumps(value) and 'private-environment-marker' not in json.dumps(value)
    assert bytes_in(project)==before


def test_observe_changed_evidence_withdraws_science_and_preserves_original_run(tmp_path):
    project=tmp_path/'study'
    scientific_fixture(project,tmp_path,['{python}','-c','print("validated fixture")'])
    _,accepted=python_entry('check','--project',str(project),'--json')
    record=project/'.eidos/runs'/(accepted['run_id']+'.json');before=record.read_bytes()
    (project/'data/input.json').write_text('{"version":2}',encoding='utf-8')
    code,value=observe(project)
    assert code==0 and value['run']['status']=='STALE'
    assert value['run']['scientific_status']=='STALE' and record.read_bytes()==before


def test_configuration_changed_during_observation_cannot_retain_pass(tmp_path,monkeypatch):
    from framework import cli, project_state
    project=tmp_path/'study'
    scientific_fixture(project,tmp_path,['{python}','-c','print("validated fixture")'])
    python_entry('check','--project',str(project),'--json')
    original=project_state.cached_status
    def change(selected):
        value=original(selected)
        path=selected/'.eidos/project.yaml'
        path.write_text(path.read_text(encoding='utf-8')+'\n# changed while observing\n',encoding='utf-8')
        return value
    monkeypatch.setattr(project_state,'cached_status',change)
    code,value=observe(project)
    assert code==0 and value['binding']['state']=='CHANGED'
    assert value['run']['status']=='STALE' and value['run']['scientific_status']=='STALE'


def test_run_changed_after_status_read_cannot_retain_pass(tmp_path,monkeypatch):
    from framework import cli, project_state
    project=tmp_path/'study'
    scientific_fixture(project,tmp_path,['{python}','-c','print("validated fixture")'])
    _,accepted=python_entry('check','--project',str(project),'--json')
    original=project_state.cached_status
    def change(selected):
        value=original(selected)
        record=selected/'.eidos/runs'/(accepted['run_id']+'.json')
        record.write_bytes(record.read_bytes()+b' ')
        return value
    monkeypatch.setattr(project_state,'cached_status',change)
    code,value=observe(project)
    assert code==0 and value['binding']['state']=='CHANGED'
    assert value['run']['status']=='STALE' and value['run']['scientific_status']=='STALE'


def test_current_worker_change_after_cached_status_withdraws_pass(tmp_path,monkeypatch):
    from framework import cli, project_state
    project=tmp_path/'study'
    scientific_fixture(project,tmp_path,['{python}','-c','print("validated fixture")'])
    python_entry('check','--project',str(project),'--json')
    baseline=project_state.runtime_identity();calls=[]
    def runtime():
        calls.append(None)
        return baseline if len(calls)<3 else {**baseline,'distributions_sha256':'0'*64}
    monkeypatch.setattr(project_state,'runtime_identity',runtime)
    code,value=observe(project)
    assert code==0 and value['binding']['state']=='CHANGED'
    assert value['run']['scientific_status']=='STALE'


def test_observing_a_failed_run_is_successful_observation_not_science_pass(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','raise SystemExit(1)'])
    assert python_entry('check','--project',str(project),'--execution-only','--json')[0]==1
    code,value=observe(project)
    assert code==0 and value['status']=='OBSERVED'
    assert value['run']['execution_status']=='FAIL' and value['run']['scientific_status']=='UNRUN'


@pytest.mark.parametrize('nonce',['invalid','../escape','b'*33])
def test_invalid_observation_nonce_is_a_structured_refusal(tmp_path,nonce):
    project=tmp_path/'study';initialise(project,tmp_path)
    code,value=python_entry('observe','--project',str(project),'--nonce',nonce,'--json')
    assert code==4 and value['status']=='REFUSED'


def test_corrupt_run_is_refused_instead_of_reported_as_observed_pass(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','print("complete")'])
    _,result=python_entry('check','--project',str(project),'--execution-only','--json')
    record=project/'.eidos/runs'/(result['run_id']+'.json')
    record.write_bytes(record.read_bytes()+b' ')
    code,value=observe(project)
    assert code==4 and value['status']=='REFUSED'
