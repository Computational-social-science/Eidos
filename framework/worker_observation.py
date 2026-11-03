"""Read-only local worker observations for a separately owned shared monitor."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import uuid

from framework.consumer_snapshot import capture_inputs
from framework import project_state

SCHEMA='eidos.worker-observation.v1'


def sdk_source_identity() -> dict:
    """Bind framework Python bytes on disk, not a remote/runtime attestation."""
    root=Path(__file__).resolve().parent
    modules={}
    for path in sorted(root.rglob('*.py')):
        if path.is_symlink():raise ValueError('Symlinked SDK source is not observable')
        modules[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    if not modules:raise ValueError('SDK source is unavailable')
    body=json.dumps(modules,sort_keys=True,separators=(',',':')).encode()
    return {'sdk_source_sha256':hashlib.sha256(body).hexdigest(),'sdk_module_count':len(modules)}


def _file_digest(path: Path) -> str | None:
    try:
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    except FileNotFoundError:return None


def _run_reference(folder: Path) -> dict:
    try:body=(folder/'latest.json').read_bytes()
    except FileNotFoundError:return {'latest_sha256':None,'run_id':None,'run_sha256':None}
    pointer=json.loads(body)
    if not isinstance(pointer,dict):raise ValueError('Invalid latest-run reference')
    run_id=pointer.get('run_id')
    if not isinstance(run_id,str) or not re.fullmatch('[0-9a-f]{32}',run_id):
        raise ValueError('Invalid latest-run reference')
    return {'latest_sha256':hashlib.sha256(body).hexdigest(),'run_id':run_id,
            'run_sha256':_file_digest(folder/'runs'/(run_id+'.json'))}


def observe(project: Path,nonce: str | None=None) -> dict:
    """Inspect cached evidence currency; never execute a producer or Gate S."""
    if nonce is None:nonce=uuid.uuid4().hex
    if not isinstance(nonce,str) or not re.fullmatch('[0-9a-f]{32}',nonce):
        raise ValueError('Observation nonce must be 32 lowercase hexadecimal characters')
    project=project.resolve()
    folder,config,spec=project_state.load_workspace(project)

    def snapshot():
        return {'runtime':project_state.runtime_identity(),'sdk':sdk_source_identity(),
                'configuration':_file_digest(folder/'project.yaml'),
                'run_reference':_run_reference(folder),'inputs':capture_inputs(spec)}

    before=snapshot()
    value=project_state.cached_status(project)
    after=snapshot()
    binding='CHANGED' if before!=after else 'STABLE' if after['inputs']['digest'] else 'UNOBSERVABLE'
    # A monitor needs component states and identities, not stdout, stderr,
    # scientific claim text, configuration contents or environment values.
    allowed=('run_id','recorded_at','eidos_version','status','execution_status',
             'scientific_status','previous_status','input_digest')
    run={key:value[key] for key in allowed if key in value}
    run.setdefault('execution_status','UNRUN')
    if binding!='STABLE' and run.get('run_id'):
        run.update(previous_status=run['status'],status='STALE',scientific_status='STALE')
    distribution=importlib.metadata.distribution('eidos')
    origin=json.loads(distribution.read_text('direct_url.json') or '{}')
    worker={**after['runtime'],**after['sdk'],'prefix':str(Path(sys.prefix).resolve()),
            'installation_mode':'editable' if origin.get('dir_info',{}).get('editable') else 'installed'}
    return {'schema':SCHEMA,'status':'OBSERVED','nonce':nonce,
            'observed_at':datetime.now(timezone.utc).isoformat(),
            'project':{'id':config['project_id'],'name':spec.name,'root':str(project)},
            'worker':worker,'run':run,'scientific_status':run['scientific_status'],
            'binding':{'state':binding,'current_input_digest':after['inputs']['digest'],
                       'scope':'Before/after observation window, not scientific acceptance'},
            'scope':'Read-only local source/metadata and cached-verdict observation; no research execution or scientific acceptance beyond the referenced run'}
