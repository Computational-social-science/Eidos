"""Explicit central enrollment preserves independent project ownership."""
import json
from pathlib import Path
import sys

from test_installed_cli import initialise, configure, python_entry


def enroll(project,monitor,*extra):
    return python_entry('enroll','--project',str(project),'--monitor-root',str(monitor),'--json',*extra)


def test_enrollment_observes_without_running_research_and_keeps_state_central(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    configure(project,['{python}','-c','from pathlib import Path;Path("research-executed").touch()'])
    monitor=tmp_path/'control'
    code,value=enroll(project,monitor)
    assert code==0 and value['status']=='ENROLLED'
    assert not (project/'research-executed').exists()
    path=monitor/'.eidos-monitor/registrations'/(value['project_id']+'.json')
    record=json.loads(path.read_text(encoding='utf-8'))
    assert record['project_root']==str(project.resolve())
    # Resolving a POSIX venv symlink selects the base interpreter and loses its
    # environment. Enrollment must retain the launch entry and actual prefix.
    assert record['python']==str(Path(sys.executable).absolute())
    assert Path(record['expected_worker']['prefix']).resolve()==Path(sys.prefix).resolve()
    assert record['expected_worker']['eidos_version']=='0.5.0'
    assert not (project/'.eidos/monitor').exists()


def test_repeated_identical_enrollment_is_idempotent(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    monitor=tmp_path/'control'
    code,first=enroll(project,monitor);assert code==0
    path=Path(first['registration']);before=path.read_bytes()
    code,again=enroll(project,monitor)
    assert code==0 and again['status']=='ALREADY_ENROLLED'
    assert path.read_bytes()==before


def test_same_display_names_do_not_merge_two_projects(tmp_path):
    monitor=tmp_path/'control'
    ids=[]
    for name in ('a','b'):
        project=tmp_path/name;initialise(project,tmp_path)
        code,value=enroll(project,monitor)
        assert code==0;ids.append(value['project_id'])
    assert len(set(ids))==2
    assert len(list((monitor/'.eidos-monitor/registrations').glob('*.json')))==2


def test_runtime_pin_cannot_silently_change_on_reenrollment(tmp_path):
    project=tmp_path/'study';initialise(project,tmp_path)
    monitor=tmp_path/'control'
    code,value=enroll(project,monitor);assert code==0
    path=Path(value['registration']);record=json.loads(path.read_text(encoding='utf-8'))
    record['expected_worker']['sdk_source_sha256']='0'*64
    path.write_text(json.dumps(record),encoding='utf-8');before=path.read_bytes()
    code,refused=enroll(project,monitor)
    assert code==4 and refused['status']=='REFUSED'
    assert path.read_bytes()==before
    code,updated=enroll(project,monitor,'--replace-runtime')
    assert code==0 and updated['status']=='ENROLLED'
    assert json.loads(path.read_text())['expected_worker']['sdk_source_sha256']!='0'*64


def test_copied_project_id_cannot_replace_another_root_even_with_runtime_flag(tmp_path):
    import shutil
    project=tmp_path/'study';initialise(project,tmp_path)
    monitor=tmp_path/'control'
    _,first=enroll(project,monitor)
    clone=tmp_path/'clone';shutil.copytree(project,clone)
    code,value=enroll(clone,monitor,'--replace-runtime')
    assert code==4 and value['status']=='REFUSED'
    assert json.loads(Path(first['registration']).read_text())['project_root']==str(project.resolve())
