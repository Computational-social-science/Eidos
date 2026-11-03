"""Shared project state, independent of CLI and monitor transport adapters."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys

import yaml

from framework.consumer_snapshot import capture_inputs
from framework.project import load_project

SCHEMA = 'eidos.project-workspace.v1'


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def version() -> str:
    return importlib.metadata.version('eidos')


def runtime_identity() -> dict:
    distributions=sorted((str(d.metadata.get('Name','')).lower(),d.version)
                         for d in importlib.metadata.distributions())
    return {'python':sys.version,'executable':str(Path(sys.executable).resolve()),
            'eidos_version':version(),
            'distributions_sha256':sha(json.dumps(distributions).encode())}


def load_workspace(project: Path):
    folder=project/'.eidos'
    path=folder/'project.yaml'
    raw=yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(raw,dict) or raw.get('schema')!=SCHEMA:
        raise ValueError('Unsupported project workspace; run eidos init for a new workspace')
    if not isinstance(raw.get('project_id'),str) or not re.fullmatch('[0-9a-f]{32}',raw['project_id']):
        raise ValueError('Invalid project identity')
    spec=load_project(path)
    if spec.root.resolve()!=project:
        raise ValueError('Workspace root differs from the selected project')
    return folder,raw,spec


def cached_status(project: Path) -> dict:
    folder,config,spec=load_workspace(project)
    if not (folder/'latest.json').exists():
        return {'status':'UNRUN','project':spec.name,'scientific_status':'UNRUN'}
    pointer=json.loads((folder/'latest.json').read_text(encoding='utf-8'))
    if not isinstance(pointer,dict):raise ValueError('Invalid latest-run reference')
    run_id=pointer.get('run_id')
    if not isinstance(run_id,str) or not re.fullmatch('[0-9a-f]{32}',run_id):
        raise ValueError('Invalid latest-run reference')
    body=(folder/'runs'/(run_id+'.json')).read_bytes()
    if pointer.get('sha256')!=sha(body):raise ValueError('Stored run bytes differ from the latest-run reference')
    value=json.loads(body)
    if not isinstance(value,dict):raise ValueError('Invalid stored run object')
    if value.get('run_id')!=run_id or value.get('project_id')!=config['project_id']:
        raise ValueError('Run identity differs from this project')
    current=capture_inputs(spec)
    if (not current['digest'] or current['digest']!=value.get('input_digest')
            or value.get('runtime_identity')!=runtime_identity()):
        value.update(previous_status=value['status'],status='STALE',scientific_status='STALE',
                     reason=current['error'] or 'Declared inputs changed; run eidos check again')
    return value
