"""Explicit, integrity-checked Python research deliveries. No execution during export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile

from framework.artifacts import output_lock

UV_VERSION = '0.12.17'
RESERVED = {'Dockerfile', 'docker-compose.yml', '.dockerignore', 'README.md',
            'package-manifest.json', 'eidos-reproduce.py', 'execution-record.json',
            '.eidos-execution.lock', '.eidos-record.tmp'}


def relative_name(value: str) -> str:
    if not isinstance(value,str) or not value or '\\' in value or ':' in value:
        raise ValueError('expected a portable project-relative path')
    path=PurePosixPath(value)
    if any(ord(c)<32 or c in '<>"|?*' for c in value):
        raise ValueError('nonportable path character')
    if path.is_absolute() or any(p in ('','.', '..') for p in value.split('/')):
        raise ValueError('path escapes or aliases the project')
    if any(p.startswith('.') and p!='.python-version' for p in path.parts):
        raise ValueError('hidden files must not enter research deliveries')
    if any(p.endswith(('.', ' ')) or p.split('.')[0].upper() in
           {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
           for p in path.parts):
        raise ValueError('nonportable Windows path alias')
    return path.as_posix()


def unique_paths(paths: list[str]) -> None:
    keys=[p.casefold() for p in paths]
    if len(keys)!=len(set(keys)) or any(a.startswith(b+'/') for a in keys for b in keys if a!=b):
        raise ValueError('case-insensitive or file/directory path collision')


def source_file(root: Path, name: str) -> Path:
    path=root/name
    if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent):
        raise ValueError('symlink or external source: '+name)
    if not path.is_file():
        raise ValueError('missing input file: '+name)
    return path


RUNNER = '''"""Run a declared reproduction and validator; success is not scientific certification."""
import hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parent
os.chdir(root)
manifest_bytes=(root/'package-manifest.json').read_bytes()
manifest_digest=hashlib.sha256(manifest_bytes).hexdigest()
manifest=json.loads(manifest_bytes)
def require(ok,message):
    if not ok: raise SystemExit(message)
def checked(name):
    path=root/name
    require(path.resolve().is_relative_to(root) and not any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent),'external or linked path: '+name)
    return path
for name,digest in manifest['sha256'].items():
    path=checked(name)
    require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'input checksum mismatch: '+name)
for name in manifest['outputs']+['execution-record.json']:
    path=checked(name)
    require(not path.exists(),'refusing pre-existing output: '+name)
try:
    claim=os.open(root/'.eidos-execution.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
except FileExistsError:
    raise SystemExit('package copy already claimed; use a fresh copy')
with os.fdopen(claim,'w') as stream:
    stream.write(str(os.getpid()))
for key in ('command','verify_command'):
    command=manifest[key]
    result=subprocess.run([sys.executable,*command[1:]],cwd=root)
    require(result.returncode==0,key+' failed with exit '+str(result.returncode))
outputs={}
for name in manifest['outputs']:
    path=checked(name)
    require(path.is_file(),'missing required output: '+name)
    outputs[name]=hashlib.sha256(path.read_bytes()).hexdigest()
# An executed command must not silently replace its declared inputs.
for name,digest in manifest['sha256'].items():
    path=checked(name)
    require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'input changed during execution: '+name)
require((root/'package-manifest.json').read_bytes()==manifest_bytes,'manifest changed during execution')
record={k:manifest[k] for k in ('seed','seed_reason','data_version','config_version','command','verify_command')}
record.update(generated=datetime.now(timezone.utc).isoformat(),python=sys.version,executable=sys.executable,outputs=outputs,
              manifest_sha256=manifest_digest,
              scope='Declared commands and output integrity only; not independent scientific certification.')
temporary=root/'.eidos-record.tmp'
with temporary.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(record,indent=2)+'\\n')
os.replace(temporary,root/'execution-record.json')
print('Declared reproduction and validation completed')
'''


def build(root: Path, output: Path, name: str, spec: dict) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',name):
        raise ValueError('package name must be a single portable directory name')
    if not isinstance(spec,dict):
        raise ValueError('executable_package declaration required')
    files=spec.get('files')
    if not isinstance(files,list) or not files or len(files)!=len(set(files)):
        raise ValueError('declare unique input files')
    files=[relative_name(p) for p in files]
    if not {'pyproject.toml','uv.lock'}<=set(files):
        raise ValueError('pyproject.toml and uv.lock are required')
    if set(files)&RESERVED or any(p.startswith('binder/') for p in files):
        raise ValueError('input collides with generated delivery files; rename it explicitly')
    for key in ('seed','data_version','config_version'):
        if key not in spec or (key!='seed' and (not isinstance(spec[key],str) or not spec[key].strip())):
            raise ValueError('required provenance: '+key)
    if type(spec['seed']) is not int and not (spec['seed'] is None and isinstance(spec.get('seed_reason'),str) and spec['seed_reason'].strip()):
        raise ValueError('declare an integer seed, or null with seed_reason')
    outputs=spec.get('outputs')
    if not isinstance(outputs,list) or not outputs or len(outputs)!=len(set(outputs)):
        raise ValueError('declare unique required outputs')
    outputs=[relative_name(p) for p in outputs]
    if set(outputs)&(set(files)|RESERVED) or any(p.startswith('binder/') for p in outputs):
        raise ValueError('outputs collide with inputs or delivery metadata')
    unique_paths([*files,*outputs,*RESERVED,'binder/requirements.txt','binder/runtime.txt','binder/postBuild'])
    if any(p.casefold().startswith('binder/') for p in files+outputs):
        raise ValueError('binder is a generated directory')
    for key in ('command','verify_command'):
        command=spec.get(key)
        if (not isinstance(command,list) or len(command)<2 or command[0]!='python'
                or not all(isinstance(v,str) and v and '\x00' not in v for v in command)
                or command[1] not in files or not command[1].endswith('.py')):
            raise ValueError(key+' must invoke a declared Python script without a shell')
    extras=spec.get('extras',[])
    if not isinstance(extras,list) or not all(isinstance(v,str) and re.fullmatch(r'[a-zA-Z0-9_-]+',v) for v in extras):
        raise ValueError('invalid optional dependency extras')
    root=root.resolve();output=output.resolve()
    payloads={p:source_file(root,p).read_bytes() for p in files}
    sync='uv sync --locked --no-dev --python 3.12' + ''.join(' --extra '+v for v in extras)
    payloads.update({
        'eidos-reproduce.py':RUNNER.encode(),
        'Dockerfile':('FROM python:3.12-slim-bookworm\n'
                      f'COPY --from=ghcr.io/astral-sh/uv:{UV_VERSION} /uv /usr/local/bin/uv\n'
                      'WORKDIR /workspace\nCOPY . .\nENV UV_PYTHON_DOWNLOADS=never\n'
                      f'RUN {sync}\nCMD ["uv","run","--no-sync","python","eidos-reproduce.py"]\n').encode(),
        'docker-compose.yml':b'services:\n  research:\n    build: .\n',
        '.dockerignore':b'.venv\n.git\n__pycache__\n',
        'binder/requirements.txt':f'uv=={UV_VERSION}\n'.encode(),
        'binder/runtime.txt':b'python-3.12\n',
        'binder/postBuild':('#!/bin/bash\nset -euo pipefail\n'+sync+'\n').encode(),
        'README.md':('''# Declared research reproduction

Run `uv sync --locked --no-dev --python 3.12` (append the extras below), then
`uv run --no-sync python eidos-reproduce.py`. Or use `docker build -t eidos-research .`
and `docker run --rm eidos-research`. Docker Compose: `docker compose run --rm research`.
Use `docker create` / `docker cp` to retain generated outputs before removing a container.

The runner refuses changed inputs, pre-existing outputs, failed reproduction or
validator commands, missing outputs and input changes during execution. Start a
fresh copy for each run. execution-record.json records output hashes and provenance.
The manifest detects accidental changes; it is not a signed security attestation.
The declared seed and versions are recorded, not enforced inside arbitrary research code.

Binder configuration installs the same locked environment. From a Binder terminal
run `uv run --no-sync python eidos-reproduce.py`. A remote Binder launch is not
validated by package generation. Its notebook server environment is separate.

Python 3.12 and uv are external requirements for local use. Quarto, TeX, GPU drivers,
external services and data not listed in the manifest are not bundled. Projects
requiring them must provision and qualify them before claiming end-to-end execution.

Install command: `'''+sync+'`\n').encode(),
    })
    manifest={k:spec[k] for k in ('seed','data_version','config_version','command','verify_command')}
    manifest.update(schema=1,outputs=outputs,extras=extras,seed_reason=spec.get('seed_reason'),
                    sha256={p:hashlib.sha256(b).hexdigest() for p,b in sorted(payloads.items())})
    payloads['package-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.mkdir(parents=True,exist_ok=True)
    target=output/name
    with output_lock(output):
        if target.exists():
            raise FileExistsError(target)
        with tempfile.TemporaryDirectory(dir=output,prefix='.package-') as temporary:
            stage=Path(temporary)/name;stage.mkdir()
            for path,body in payloads.items():
                destination=stage/path;destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(body)
            (stage/'binder/postBuild').chmod(0o755)
            if any(source_file(root,p).read_bytes()!=payloads[p] for p in files):
                raise ValueError('source changed during package generation')
            stage.rename(target)
    return {'success':True,'execution_verified':False,'package_dir':str(target),
            'artifacts':sorted(payloads),'instructions':(target/'README.md').read_text(encoding='utf-8')}
