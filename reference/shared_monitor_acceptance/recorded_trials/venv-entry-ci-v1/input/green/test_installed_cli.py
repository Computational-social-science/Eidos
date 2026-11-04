"""User journeys for project-local reuse, without a source checkout or model service.

RED logs are retained before production edits. This repository requires green
commit hooks, so the first checkpoint commit follows GREEN rather than bypassing
the hooks to commit a deliberately failing suite.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import runpy
from pathlib import Path
import sys
import tomllib
import zipfile
from contextlib import redirect_stdout

import yaml
import pytest

from framework.subprocesses import run_tree


def cli(*arguments: str, cwd: Path):
    coverage=['-m','coverage','run','--parallel-mode','--source=framework.cli,framework.consumer_snapshot'] if os.environ.get('EIDOS_CLI_COVERAGE')=='1' else []
    return run_tree([sys.executable,*coverage,'-m','framework.cli',*arguments],cwd=cwd,timeout=15)


def payload(result):
    assert result.stdout.strip(), result.stderr
    value=json.loads(result.stdout)
    assert isinstance(value,dict)
    return value


def initialise(project: Path, caller: Path):
    result=cli('init','--project',str(project),'--name','my_study','--json',cwd=caller)
    assert result.returncode==0, result.stderr
    return payload(result)


def configure(project: Path, command: list[str], expects=None):
    path=project/'.eidos/project.yaml'
    value=yaml.safe_load(path.read_text(encoding='utf-8'))
    value.update(gate_command=command,expects=expects or [])
    path.write_text(yaml.safe_dump(value),encoding='utf-8')


def test_installed_console_entry_is_declared():
    root=Path(__file__).resolve().parents[1]
    metadata=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))
    assert metadata['project'].get('scripts',{}).get('eidos')=='framework.cli:main'


def test_help_needs_neither_models_nor_source_tools(tmp_path):
    result=cli('--help',cwd=tmp_path)
    assert result.returncode==0, result.stderr
    assert all(word in result.stdout for word in ['init','check','report','feedback','status'])


def test_init_keeps_existing_research_files_and_uses_project_local_registry(tmp_path):
    project=tmp_path/'existing study';project.mkdir()
    data=project/'data.bin';data.write_bytes(b'original private data')
    result=initialise(project,tmp_path)
    assert result['status']=='INITIALIZED'
    assert data.read_bytes()==b'original private data'
    spec=yaml.safe_load((project/'.eidos/project.yaml').read_text(encoding='utf-8'))
    assert (project/'.eidos'/spec['root']).resolve()==project.resolve()
    assert not (tmp_path/'projects').exists()


def test_reinitialization_refuses_without_overwriting(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    before={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
    result=cli('init','--project',str(project),'--json',cwd=tmp_path)
    assert result.returncode!=0
    assert payload(result)['status']=='REFUSED'
    assert before=={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}


def test_placeholder_validator_cannot_be_a_scientific_pass(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    result=cli('check','--project',str(project),'--json',cwd=tmp_path)
    assert result.returncode==4
    value=payload(result)
    assert value['status']=='REFUSED' and value['scientific_status']=='UNRUN'


def test_successful_command_without_claim_register_is_not_scientifically_accepted(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','print("finished")'])
    result=cli('check','--project',str(project),'--json',cwd=tmp_path)
    assert result.returncode==4
    value=payload(result)
    assert value['execution_status']=='PASS' and value['scientific_status']=='UNRUN'
    assert value['status']=='REFUSED'


def test_execution_only_preserves_required_output_refusal(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','print("finished")'],['missing.json'])
    result=cli('check','--project',str(project),'--execution-only','--json',cwd=tmp_path)
    assert result.returncode==1
    assert payload(result)['status']=='FAIL'


def test_execution_only_success_does_not_claim_scientific_validation(tmp_path):
    project=tmp_path/'研究 study';initialise(project,tmp_path)
    configure(project,['{python}','-c','from pathlib import Path;Path("evidence.json").write_text("{}")'],['evidence.json'])
    result=cli('check','--project',str(project),'--execution-only','--json',cwd=tmp_path)
    assert result.returncode==0, result.stderr
    value=payload(result)
    assert value['status']=='PASS' and value['execution_status']=='PASS'
    assert value['scientific_status']=='UNRUN'


def test_status_before_a_run_is_explicitly_unrun(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    result=cli('status','--project',str(project),'--json',cwd=tmp_path)
    assert result.returncode==0, result.stderr
    assert payload(result)['status']=='UNRUN'


def test_report_without_manuscript_is_refused(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    result=cli('report','--project',str(project),'--json',cwd=tmp_path)
    assert result.returncode==4
    assert payload(result)['status']=='REFUSED'
    assert not (project/'outputs').exists()


def test_default_feedback_is_local_metadata_without_data_or_environment(tmp_path,monkeypatch):
    project=tmp_path/'study';initialise(project,tmp_path)
    (project/'private.txt').write_text('private-content-marker',encoding='utf-8')
    monkeypatch.setenv('EIDOS_FIXTURE_SECRET','private-secret-marker')
    output=tmp_path/'feedback.zip'
    result=cli('feedback','--project',str(project),'--message','validator rejected a run',
               '--out',str(output),'--json',cwd=tmp_path)
    assert result.returncode==0, result.stderr
    assert payload(result)['status']=='EXPORTED'
    with zipfile.ZipFile(output) as bundle:
        assert set(bundle.namelist())=={'feedback.json','manifest.json'}
        bodies=b'\n'.join(bundle.read(n) for n in bundle.namelist())
        assert b'private-content-marker' not in bodies and b'private-secret-marker' not in bodies
        manifest=json.loads(bundle.read('manifest.json'))
        assert manifest['files']['feedback.json']==hashlib.sha256(bundle.read('feedback.json')).hexdigest()


def test_feedback_cannot_overwrite_an_existing_bundle(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    output=tmp_path/'feedback.zip';output.write_bytes(b'prior delivery')
    result=cli('feedback','--project',str(project),'--message','failure','--out',str(output),'--json',cwd=tmp_path)
    assert result.returncode!=0
    assert payload(result)['status']=='REFUSED'
    assert output.read_bytes()==b'prior delivery'


def scientific_fixture(project: Path,caller: Path,command: list[str],expects=None):
    # Reuse the established clean Gate S fixture; these tests exercise orchestration,
    # not a second implementation of scientific validity.
    write=runpy.run_path(str(Path(__file__).with_name('test_validity.py')))['write_project']
    write(project)
    (project/'data/input.json').write_text('{"version":1}',encoding='utf-8')
    initialise(project,caller)
    configure(project,command,expects)
    path=project/'.eidos/project.yaml';value=yaml.safe_load(path.read_text(encoding='utf-8'))
    value.update(validity_document='docs/MANUSCRIPT.html',validity_inputs=['.eidos/validate.py','data/input.json'])
    path.write_text(yaml.safe_dump(value),encoding='utf-8')


def test_scientific_pass_is_withdrawn_when_declared_input_changes(tmp_path):
    project=tmp_path/'study'
    scientific_fixture(project,tmp_path,['{python}','-c','print("independent fixture validated")'])
    checked=cli('check','--project',str(project),'--json',cwd=tmp_path)
    assert checked.returncode==0,checked.stdout+checked.stderr
    assert payload(checked)['scientific_status']=='PASS'
    (project/'data/input.json').write_text('{"version":2}',encoding='utf-8')
    observed=payload(cli('status','--project',str(project),'--json',cwd=tmp_path))
    assert observed['status']=='STALE' and observed['previous_status']=='PASS'


def test_data_changed_during_execution_cannot_bind_an_old_result_to_new_inputs(tmp_path):
    project=tmp_path/'study'
    command=['{python}','-c',
             'from pathlib import Path;p=Path("data/input.json");old=p.read_text();p.write_text("changed after reading");print(old)']
    scientific_fixture(project,tmp_path,command)
    checked=cli('check','--project',str(project),'--json',cwd=tmp_path)
    assert checked.returncode==3,checked.stdout+checked.stderr
    value=payload(checked)
    assert value['status']=='STALE' and value['scientific_status']!='PASS'
    assert payload(cli('status','--project',str(project),'--json',cwd=tmp_path))['status']=='STALE'


def test_declared_output_generation_is_distinct_from_input_mutation(tmp_path):
    project=tmp_path/'study'
    command=['{python}','-c','from pathlib import Path;p=Path("data/evidence.json");p.write_text(p.read_text())']
    scientific_fixture(project,tmp_path,command,['data/evidence.json'])
    checked=cli('check','--project',str(project),'--json',cwd=tmp_path)
    assert checked.returncode==0,checked.stdout+checked.stderr
    assert payload(checked)['scientific_status']=='PASS'


def test_new_runtime_distribution_withdraws_a_cached_result(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','print("completed")'])
    checked=cli('check','--project',str(project),'--execution-only','--json',cwd=tmp_path)
    assert checked.returncode==0
    distribution=tmp_path/'eidos_fixture_addon-1.0.dist-info';distribution.mkdir()
    (distribution/'METADATA').write_text('Metadata-Version: 2.1\nName: eidos-fixture-addon\nVersion: 1.0\n',encoding='utf-8')
    observed=payload(cli('status','--project',str(project),'--json',cwd=tmp_path))
    assert observed['status']=='STALE'


def test_status_configuration_error_is_a_nonzero_structured_result(tmp_path):
    result=cli('status','--project',str(tmp_path/'missing'),'--json',cwd=tmp_path)
    assert result.returncode==4
    assert payload(result)['status']=='REFUSED'


def test_malformed_latest_pointer_is_refused_as_json(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    (project/'.eidos/latest.json').write_text('[]',encoding='utf-8')
    result=cli('status','--project',str(project),'--json',cwd=tmp_path)
    assert result.returncode==4
    assert payload(result)['status']=='REFUSED'


def test_edited_run_cannot_turn_execution_only_into_a_scientific_pass(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','print("completed")'])
    result=payload(cli('check','--project',str(project),'--execution-only','--json',cwd=tmp_path))
    path=project/'.eidos/runs'/(result['run_id']+'.json')
    edited=json.loads(path.read_text(encoding='utf-8'));edited['scientific_status']='PASS'
    path.write_text(json.dumps(edited),encoding='utf-8')
    observed=cli('status','--project',str(project),'--json',cwd=tmp_path)
    assert observed.returncode==4
    assert payload(observed)['status']=='REFUSED'


def python_entry(*arguments):
    """The in-process entry used by a Python agent must obey the same result contract."""
    from framework.cli import main
    output=io.StringIO()
    with redirect_stdout(output):code=main(list(arguments))
    return code,json.loads(output.getvalue())


def test_python_agent_entry_preserves_cwd_and_keeps_failed_run_history(tmp_path):
    project=tmp_path/'agent study';original_cwd=Path.cwd()
    args=['--project',str(project),'--json']
    code,created=python_entry('init',*args)
    assert code==0 and created['status']=='INITIALIZED'
    assert python_entry('check',*args)[0]==4
    configure(project,['{python}','-c','print("validated execution")'])
    code,accepted=python_entry('check',*args,'--execution-only')
    assert code==0 and accepted['scientific_status']=='UNRUN'
    before=(project/'.eidos/runs'/(accepted['run_id']+'.json')).read_bytes()
    configure(project,['{python}','-c','raise SystemExit(1)'])
    code,rejected=python_entry('check',*args,'--execution-only')
    assert code==1 and rejected['status']=='FAIL'
    assert rejected['run_id']!=accepted['run_id']
    assert (project/'.eidos/runs'/(accepted['run_id']+'.json')).read_bytes()==before
    assert python_entry('status',*args)[1]['status']=='FAIL'
    assert python_entry('report',*args)[0]==4
    bundle=tmp_path/'agent-feedback.zip'
    assert python_entry('feedback',*args,'--message','failed validation','--out',str(bundle))[0]==0
    assert python_entry('feedback',*args,'--message','do not overwrite','--out',str(bundle))[0]==4
    assert Path.cwd()==original_cwd


def test_python_agent_entry_uses_independent_gate_s_and_withdraws_changed_inputs(tmp_path):
    project=tmp_path/'agent science'
    scientific_fixture(project,tmp_path,['{python}','-c','print("fixture checked")'])
    args=['--project',str(project),'--json']
    code,accepted=python_entry('check',*args)
    assert code==0 and accepted['scientific_status']=='PASS'
    evidence=project/'data/evidence.json';value=json.loads(evidence.read_text(encoding='utf-8'))
    value['cross_arm']['separated']=False;evidence.write_text(json.dumps(value),encoding='utf-8')
    assert python_entry('status',*args)[1]['status']=='STALE'
    code,rejected=python_entry('check',*args)
    assert code==1 and rejected['scientific_status']=='FAIL'


@pytest.mark.parametrize('change',['seed','delivery','formatting'])
def test_entire_owned_workspace_configuration_is_bound_to_cached_science(tmp_path,change):
    project=tmp_path/'science'
    scientific_fixture(project,tmp_path,['{python}','-c','print("fixture checked")'])
    args=['--project',str(project),'--json']
    code,value=python_entry('check',*args)
    assert code==0 and value['scientific_status']=='PASS'
    path=project/'.eidos/project.yaml'
    if change=='formatting':path.write_text(path.read_text(encoding='utf-8')+'\n# changed configuration bytes\n',encoding='utf-8')
    else:
        config=yaml.safe_load(path.read_text(encoding='utf-8'))
        if change=='seed':config['seed']=999
        else:config['delivery']['output_dir']='different-output'
        path.write_text(yaml.safe_dump(config),encoding='utf-8')
    observed=python_entry('status',*args)[1]
    assert observed['status']=='STALE'


def test_implicit_workspace_config_cannot_replace_explicit_module_inputs(tmp_path):
    project=tmp_path/'module science'
    scientific_fixture(project,tmp_path,['{python}','-m','gate'])
    marker=project/'executed.txt'
    (project/'gate.py').write_text('from pathlib import Path;Path("executed.txt").write_text("ran")',encoding='utf-8')
    path=project/'.eidos/project.yaml'
    config=yaml.safe_load(path.read_text(encoding='utf-8'))
    config['validity_inputs']=[]
    path.write_text(yaml.safe_dump(config),encoding='utf-8')
    code,value=python_entry('check','--project',str(project),'--json')
    assert code==4 and value['status']=='REFUSED'
    assert not marker.exists()


def test_explicit_module_code_is_accepted_and_its_changes_withdraw_pass(tmp_path):
    project=tmp_path/'module science'
    scientific_fixture(project,tmp_path,['{python}','-m','gate'])
    gate=project/'gate.py';gate.write_text('print("fixture checked")',encoding='utf-8')
    path=project/'.eidos/project.yaml'
    config=yaml.safe_load(path.read_text(encoding='utf-8'))
    config['validity_inputs']=['gate.py']
    path.write_text(yaml.safe_dump(config),encoding='utf-8')
    args=['--project',str(project),'--json']
    code,value=python_entry('check',*args)
    assert code==0 and value['scientific_status']=='PASS'
    gate.write_text('raise SystemExit(1)',encoding='utf-8')
    assert python_entry('status',*args)[1]['status']=='STALE'
