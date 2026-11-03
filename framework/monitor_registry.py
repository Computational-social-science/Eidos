"""Explicit local project enrollment; the central store never owns research files."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from framework.artifacts import atomic_output, output_lock
from framework.subprocesses import run_tree, validate_timeout
from framework.project_state import load_workspace, sha

SCHEMA='eidos.monitor-registration.v1'
WORKER_FIELDS=('python','executable','eidos_version','distributions_sha256','prefix',
               'sdk_source_sha256','sdk_module_count','installation_mode')


def validate_run_metadata(run: dict) -> None:
    """Validate only public receipt metadata, independently of transport success."""
    for field, pattern in (('run_id', '[0-9a-f]{32}'), ('input_digest', '[0-9a-f]{64}')):
        if field in run and not (field == 'input_digest' and run[field] is None):
            if not isinstance(run[field], str) or not re.fullmatch(pattern, run[field]):
                raise ValueError('Invalid worker run metadata identity/digest')
    if 'recorded_at' in run:
        if not isinstance(run['recorded_at'], str):
            raise ValueError('Worker run timestamp metadata must be a string')
        stamp = datetime.fromisoformat(run['recorded_at'])
        if stamp.tzinfo is None:
            raise ValueError('Worker run timestamp requires a timezone')
    if 'eidos_version' in run and (not isinstance(run['eidos_version'], str) or not run['eidos_version']):
        raise ValueError('Worker run version metadata is invalid')
    if 'previous_status' in run and run['previous_status'] not in (
            'UNRUN', 'PASS', 'FAIL', 'ERROR', 'SKIP', 'REFUSED', 'BLOCKED', 'OPEN', 'STALE'):
        raise ValueError('Worker previous status is invalid')
    if run.get('status') != 'UNRUN' and any(
            field not in run for field in ('run_id', 'recorded_at', 'eidos_version', 'input_digest')):
        raise ValueError('Worker run identity/timestamp/version metadata is incomplete')
    if run.get('status') == 'PASS' and run.get('input_digest') is None:
        raise ValueError('Worker acceptance requires a bound input digest')


def registrations_dir(monitor_root: Path) -> Path:
    root=monitor_root.resolve()
    if (root.is_relative_to(Path(sys.prefix).resolve())
            or root.is_relative_to(Path(__file__).resolve().parent)):
        raise ValueError('Monitor state must be outside the SDK environment/package')
    folder=root/'.eidos-monitor/registrations'
    if not folder.resolve().is_relative_to(root):raise ValueError('Monitor registry escapes its selected root')
    return folder


def query_worker(project: Path,python: Path,timeout: float=5) -> dict:
    """Ask only for observation, never a research/check/render operation."""
    validate_timeout(timeout)
    project=project.resolve();python=Path(os.path.abspath(python))
    if not python.is_file():raise ValueError('Selected worker Python is missing')
    folder,configuration,spec=load_workspace(project)
    configuration_digest=sha((folder/'project.yaml').read_bytes())
    nonce=uuid.uuid4().hex
    started=datetime.now(timezone.utc)
    command=[str(python),'-I','-X','utf8','-m','framework.cli','observe',
             '--project',str(project),'--nonce',nonce,'--json']
    try:
        result=run_tree(command,cwd=project,timeout=timeout,
                        env=dict(os.environ,PYTHONIOENCODING='utf-8'))
    except subprocess.TimeoutExpired:
        raise ValueError('Worker observation timed out') from None
    except OSError:
        raise ValueError('Worker observation could not be contained/launched') from None
    if result.returncode:raise ValueError('Worker observation refused: exit '+str(result.returncode))
    if len(result.stdout.encode('utf-8'))>1024*1024:raise ValueError('Worker response exceeds the protocol size limit')
    try:
        value=json.loads(result.stdout)
    except RecursionError:
        raise ValueError('Worker JSON nesting exceeds the supported protocol depth') from None
    if (not isinstance(value,dict) or value.get('schema')!='eidos.worker-observation.v1'
            or value.get('status')!='OBSERVED' or value.get('operation')!='observe'
            or value.get('nonce')!=nonce):
        raise ValueError('Unsupported or rebound worker observation')
    identity=value.get('project');worker=value.get('worker');run=value.get('run')
    if not all(isinstance(item,dict) for item in (identity,worker,run)):
        raise ValueError('Incomplete worker observation')
    if (not isinstance(identity.get('id'),str) or not re.fullmatch('[0-9a-f]{32}',identity['id'])
            or not isinstance(identity.get('name'),str) or not identity['name']
            or identity['id']!=configuration['project_id'] or identity['name']!=spec.name
            or Path(identity.get('root','')).resolve()!=project):
        raise ValueError('Worker project identity differs from the selected project')
    for field in WORKER_FIELDS:
        if field not in worker:raise ValueError('Incomplete worker identity')
    if Path(worker['executable']).resolve()!=python.resolve():raise ValueError('Worker interpreter identity differs')
    if not all(isinstance(worker[field],str) and worker[field] for field in
               ('python','executable','prefix','eidos_version')):
        raise ValueError('Malformed worker runtime identity')
    expected_prefix=python.parent.parent
    if ((expected_prefix/'pyvenv.cfg').is_file()
            and Path(worker['prefix']).resolve()!=expected_prefix.resolve()):
        raise ValueError('Worker prefix differs from the selected virtual environment')
    if (type(worker['sdk_module_count']) is not int or worker['sdk_module_count']<=0
            or worker['installation_mode'] not in ('installed','editable')
            or any(not isinstance(worker[field],str) or not re.fullmatch('[0-9a-f]{64}',worker[field])
                   for field in ('sdk_source_sha256','distributions_sha256'))):
        raise ValueError('Malformed worker source/metadata identity')
    stamp=datetime.fromisoformat(value.get('observed_at',''))
    ended=datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.timestamp()<started.timestamp()-30 or stamp.timestamp()>ended.timestamp()+30:
        raise ValueError('Worker observation timestamp is outside the request window')
    if not isinstance(value.get('binding'),dict) or value['binding'].get('state') not in ('STABLE','CHANGED','UNOBSERVABLE'):
        raise ValueError('Worker binding state is missing')
    if run.get('scientific_status') not in ('UNRUN','PASS','FAIL','BLOCKED','REFUSED','OPEN','STALE'):
        raise ValueError('Worker scientific status is invalid')
    statuses={'UNRUN','PASS','FAIL','ERROR','SKIP','REFUSED','BLOCKED','OPEN','STALE'}
    if run.get('status') not in statuses or run.get('execution_status') not in statuses:
        raise ValueError('Worker execution/overall status is invalid')
    if value.get('scientific_status')!=run['scientific_status']:
        raise ValueError('Worker scientific status differs from its run')
    if run['status']=='PASS' and (run['execution_status']!='PASS'
            or value['binding']['state']!='STABLE'):
        raise ValueError('Worker overall acceptance contradicts execution/binding status')
    if run['scientific_status']!='UNRUN' and run['status']!=run['scientific_status']:
        raise ValueError('Worker scientific status contradicts its overall status')
    validate_run_metadata(run)
    if sha((folder/'project.yaml').read_bytes())!=configuration_digest:
        raise ValueError('Project identity/configuration changed during observation')
    return value


def enroll(project: Path,monitor_root: Path,python: Path | None=None,*,replace_runtime: bool=False) -> dict:
    project=project.resolve();python=Path(os.path.abspath(python or sys.executable))
    folder=registrations_dir(monitor_root)
    value=query_worker(project,python)
    if value['binding']['state']!='STABLE':raise ValueError('Cannot pin an unstable worker observation')
    identity=value['project'];worker={key:value['worker'][key] for key in WORKER_FIELDS}
    path=folder/(identity['id']+'.json')
    folder.mkdir(parents=True,exist_ok=True)
    status='ENROLLED'
    with output_lock(folder,timeout=5):
        if path.is_symlink():raise ValueError('Symlinked monitor registration is unsupported')
        old=None
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(old,dict) or old.get('schema')!=SCHEMA
                    or old.get('project_id')!=identity['id'] or old.get('project_root')!=str(project)):
                raise ValueError('Existing registration belongs to another project/root')
            runtime_changed=old.get('python')!=str(python) or old.get('expected_worker')!=worker
            if runtime_changed and not replace_runtime:
                raise ValueError('Runtime pin changed; validate it before using --replace-runtime')
            if not runtime_changed and old.get('name')==identity['name']:
                status='ALREADY_ENROLLED'
        if status=='ENROLLED':
            now=datetime.now(timezone.utc).isoformat()
            record={'schema':SCHEMA,'project_id':identity['id'],'project_root':str(project),
                    'name':identity['name'],'python':str(python),'expected_worker':worker,
                    'created_at':old.get('created_at',now) if old else now,'updated_at':now,
                    'scope':'Explicit local runtime/source binding; no experiment execution or remote attestation'}
            with atomic_output(path) as temporary:
                temporary.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return {'status':status,'project':identity['name'],'project_id':identity['id'],
            'registration':str(path),'scientific_status':'UNRUN',
            'scope':'Monitor enrollment only; scientific acceptance is a separate operation'}
