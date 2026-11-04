"""Project-local access to EIDOS execution, scientific checks and local feedback."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid
import zipfile

import yaml

from framework.artifacts import atomic_output, output_lock
from framework.consumer_snapshot import capture_inputs
from framework.command_inputs import python_entry
from framework.project import run_command
from framework.subprocesses import validate_timeout

from framework.project_state import (
    SCHEMA, sha as _sha, version as _version,
    runtime_identity as _runtime_identity, load_workspace as _workspace,
    cached_status as _status,
)
PLACEHOLDER='''"""Replace this placeholder with your independent research validator."""
import sys
print("REFUSED: configure a research validator and its expected evidence before acceptance.")
sys.exit(4)
'''
GUIDE='''# EIDOS project workspace

Your research files and environment stay in this project. Edit project.yaml to
declare the validator command, required evidence, claim register and document.
The starter validator deliberately refuses acceptance until configured.

Run `eidos check --project ..` from this folder or select the project root from
any directory. `--execution-only` checks the command/output contract without
claiming scientific acceptance. Imported validator helpers and data/configuration
manifests belong in validity_inputs. The validator must verify underlying data
and provenance. `eidos feedback` exports local metadata, never uploads it.
'''


def _initialize(project: Path,name: str | None) -> dict:
    if name is None:
        name=re.sub('[^a-z0-9_]','_',project.name.lower()).strip('_') or 'study'
        if not name[0].isalpha():name='study_'+name
    if not re.fullmatch('[a-z][a-z0-9_]*',name):
        raise ValueError('Project name must use lowercase letters, digits and underscores')
    project.mkdir(parents=True,exist_ok=True)
    folder=project/'.eidos'
    folder.mkdir(exist_ok=False)
    config={'schema':SCHEMA,'project_id':uuid.uuid4().hex,'name':name,'root':'..',
            'gate_command':['{python}','.eidos/validate.py'],
            'exit_statuses':{4:'REFUSED'},'expects':[],
            'validity_register':'analysis/CLAIMS.yaml','validity_document':'docs/REPORT.md',
            'validity_inputs':['.eidos/validate.py'],'numerics':'optional',
            'delivery':{'manuscript_dir':'manuscript','output_dir':'outputs','render_inputs':[]}}
    # The configuration is the commit marker. An interrupted initialization is
    # retained for inspection and never silently overwrites an existing folder.
    for name,body in [('validate.py',PLACEHOLDER),('README.md',GUIDE),
                      ('project.yaml',yaml.safe_dump(config,sort_keys=False))]:
        with (folder/name).open('x',encoding='utf-8',newline='\n') as stream:stream.write(body)
    return {'status':'INITIALIZED','project':config['name'],'project_id':config['project_id'],
            'configuration':str(folder/'project.yaml'),'scientific_status':'UNRUN'}


def _publish_run(folder: Path,value: dict) -> None:
    value.update(run_id=uuid.uuid4().hex,recorded_at=datetime.now(timezone.utc).isoformat(),
                 eidos_version=_version())
    body=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with atomic_output(folder/'runs'/(value['run_id']+'.json')) as temporary:
        temporary.write_bytes(body)
    with atomic_output(folder/'latest.json') as temporary:
        temporary.write_text(json.dumps({'run_id':value['run_id'],'sha256':_sha(body)})+'\n',encoding='utf-8')


def _execution_inputs(spec,configuration: Path) -> dict:
    """Bind immutable producer inputs; only explicitly declared outputs may change."""
    snapshot=capture_inputs(spec,details=True)
    if snapshot['digest'] is None:return snapshot
    outputs=set()
    for relative in spec.expects:
        path=(spec.root/relative).resolve()
        if not path.is_relative_to(spec.root.resolve()):
            raise ValueError('Expected outputs must remain inside the selected project')
        outputs.add(str(path))
    entry=python_entry(spec.gate_command,spec.validity_inputs,'gate','validity_inputs')
    required=[*spec.validity_inputs,*([entry] if entry else [])]
    immutable={str((spec.root/name).resolve()) for name in required}
    immutable.add(str(configuration.resolve()))
    if spec.validity_register:immutable.add(str((spec.root/spec.validity_register).resolve()))
    for name in required:
        if not (spec.root/name).is_file():raise ValueError('Declared execution input is missing: '+name)
    files={name:value for name,value in snapshot['files'].items() if name not in outputs or name in immutable}
    files[str(configuration.resolve())]={'sha256':_sha(configuration.read_bytes())}
    body=json.dumps({'files':files,'command':spec.gate_command},sort_keys=True).encode()
    return {'digest':_sha(body),'error':None}


def _check(project: Path,execution_only: bool,timeout: float) -> dict:
    validate_timeout(timeout)
    folder,config,spec=_workspace(project)
    with output_lock(folder/'runs',timeout=timeout):
        runtime_before=_runtime_identity()
        execution_before=_execution_inputs(spec,folder/'project.yaml')
        if execution_before['digest'] is None:
            raise ValueError('Execution inputs are not observable: '+str(execution_before['error']))
        run=run_command(spec,'gate',timeout=timeout)
        execution_after=_execution_inputs(spec,folder/'project.yaml')
        value={'project':spec.name,'project_id':config['project_id'],'status':run.status,
               'execution_status':run.status,'scientific_status':'UNRUN','execution':run.as_dict()}
        before=capture_inputs(spec)
        runtime_after=_runtime_identity()
        execution_changed=execution_before!=execution_after or runtime_before!=runtime_after
        if run.status=='PASS' and execution_changed:
            value.update(status='STALE',scientific_status='STALE',reason='Declared inputs changed during execution')
        if run.status=='PASS' and not execution_only and not execution_changed:
            register=project/spec.validity_register
            documents=[project/n.strip() for n in spec.validity_document.split(',') if n.strip()]
            if (not spec.validity_register or not spec.validity_document or not register.is_file()
                    or not all(p.is_file() for p in documents) or before['digest'] is None):
                value.update(status='REFUSED',reason='A readable claim register, document and observable inputs are required')
            else:
                from framework.validity import ScientificValidityGate
                result=ScientificValidityGate(project,register=register,document=documents).run()
                value.update(status=result.status,scientific_status=result.status,scientific=result.details)
        after=capture_inputs(spec)
        runtime_final=_runtime_identity()
        if run.status=='PASS' and (before!=after or runtime_final!=runtime_after):
            value.update(status='STALE',scientific_status='STALE',reason='Inputs changed during scientific verification')
        value['input_digest']=after['digest'] if before==after and not execution_changed and runtime_final==runtime_after else None
        value['runtime_identity']=runtime_final
        _publish_run(folder,value)
    return value


def _report(project: Path,format: str) -> dict:
    folder,config,spec=_workspace(project)
    delivery=config.get('delivery')
    if not isinstance(delivery,dict):raise ValueError('Configure delivery in .eidos/project.yaml')
    if not (project/delivery.get('manuscript_dir','manuscript')/'index.qmd').is_file():
        return {'status':'REFUSED','reason':'Create and configure manuscript/index.qmd before rendering',
                'scientific_status':'UNRUN'}
    from framework.quarto_bridge import QuartoBridge
    arguments={k:v for k,v in delivery.items() if k in {'manuscript_dir','output_dir','render_inputs','quarto'}}
    arguments['project_root']=str(project)
    result=QuartoBridge(arguments).render(format=format)
    return {'status':'PASS' if result['success'] else 'FAIL','delivery':result,
            'scientific_status':'UNRUN','scope':'Technical delivery; scientific acceptance is a separate check'}


def _feedback(project: Path,message: str,output: Path) -> dict:
    folder,config,spec=_workspace(project)
    if not message.strip():raise ValueError('Describe the observed problem')
    body=(json.dumps({'schema':'eidos.feedback.v1','incident_id':uuid.uuid4().hex,
        'project_id':config['project_id'],'project':spec.name,'eidos_version':_version(),
        'python_version':sys.version.split()[0],'message':message,
        'configuration_sha256':_sha((folder/'project.yaml').read_bytes()),
        'state':'DETECTED','scope':'Local metadata only; no data/logs/environment or automatic upload'},indent=2)+'\n').encode()
    manifest=(json.dumps({'schema':'eidos.feedback-manifest.v1','files':{'feedback.json':_sha(body)}},indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents an export from replacing an earlier bundle.
    with output.open('xb') as stream:
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr('feedback.json',body)
            bundle.writestr('manifest.json',manifest)
    return {'status':'EXPORTED','path':str(output),'sha256':_sha(output.read_bytes()),'uploaded':False}


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(prog='eidos-agent',description='EIDOS Agent: project-local research execution, evidence checks and delivery')
    sub=parser.add_subparsers(dest='action',required=True)
    for action in ['init','check','status','report','feedback','observe','enroll']:
        p=sub.add_parser(action)
        p.add_argument('--project',type=Path,default=Path.cwd())
        p.add_argument('--json',action='store_true')
        if action=='init':p.add_argument('--name')
        if action=='observe':p.add_argument('--nonce')
        if action=='enroll':
            p.add_argument('--monitor-root',type=Path,required=True)
            p.add_argument('--python',type=Path)
            p.add_argument('--replace-runtime',action='store_true')
        if action=='check':
            p.add_argument('--execution-only',action='store_true')
            p.add_argument('--timeout',type=float,default=900)
        if action=='report':p.add_argument('--format',choices=['all','html','pdf','docx'],default='all')
        if action=='feedback':
            p.add_argument('--message',required=True)
            p.add_argument('--out',type=Path,required=True)
    incident=sub.add_parser('incident',help='Local hash-bound repair lifecycle; no automatic upload/install')
    verbs=incident.add_subparsers(dest='incident_action',required=True)
    for verb in ('create','record','status','adopt','revert','close'):
        p=verbs.add_parser(verb)
        p.add_argument('--project',type=Path,default=Path.cwd())
        p.add_argument('--json',action='store_true')
        if verb=='create':
            p.add_argument('--message',required=True)
            p.add_argument('--protocol',type=Path,required=True)
            p.add_argument('--feedback-bundle',type=Path)
        else:p.add_argument('--incident',required=True)
        if verb=='record':p.add_argument('--receipt',type=Path,required=True)
        if verb=='adopt':p.add_argument('--python',type=Path,required=True)
    args=parser.parse_args(argv)
    query_succeeded=False
    try:
        project=args.project.resolve()
        if args.action=='incident':
            from framework import feedback
            verb=args.incident_action
            if verb=='create':value=feedback.create(project,args.message,args.protocol,feedback_bundle=args.feedback_bundle)
            elif verb=='record':value=feedback.record(project,args.incident,args.receipt)
            elif verb=='adopt':value=feedback.adopt(project,args.incident,args.python)
            elif verb=='revert':value=feedback.revert(project,args.incident)
            elif verb=='close':value=feedback.close(project,args.incident)
            else:
                value=feedback.status(project,args.incident)
                query_succeeded=True
        elif args.action=='init':value=_initialize(project,args.name)
        elif args.action=='check':value=_check(project,args.execution_only,args.timeout)
        elif args.action=='status':
            value=_status(project)
            query_succeeded=True
        elif args.action=='observe':
            from framework.worker_observation import observe
            value=observe(project,args.nonce)
            query_succeeded=True
        elif args.action=='enroll':
            from framework.monitor_registry import enroll
            value=enroll(project,args.monitor_root,args.python,replace_runtime=args.replace_runtime)
        elif args.action=='report':value=_report(project,args.format)
        else:value=_feedback(project,args.message,args.out.resolve())
    except (OSError,ValueError,TypeError,yaml.YAMLError) as error:
        value={'status':'REFUSED','reason':str(error),'scientific_status':'UNRUN'}
    value.setdefault('schema','eidos.cli-result.v1')
    value['operation']=args.action+'.'+args.incident_action if args.action=='incident' else args.action
    if args.json:print(json.dumps(value,allow_nan=False))
    else:
        target=value.get('project')
        if isinstance(target,dict):target=target.get('name')
        print(value['status']+': '+str(value.get('reason') or value.get('path') or target or args.action))
        if 'scientific_status' in value:print('Scientific check: '+value['scientific_status'])
    if query_succeeded:return 0
    return {'PASS':0,'INITIALIZED':0,'EXPORTED':0,'ENROLLED':0,'ALREADY_ENROLLED':0,
            'REFUSED':4,'BLOCKED':4,'STALE':3,'OPEN':3}.get(value['status'],1)


if __name__=='__main__':raise SystemExit(main())
