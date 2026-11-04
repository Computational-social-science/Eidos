"""Replay the private availability-probe counterfactual in two installed SDKs."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import zipfile
from email.parser import BytesParser

from framework.subprocesses import run_tree


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], cwd: Path, timeout: float = 30, env=None):
    return run_tree(command, cwd=cwd, timeout=timeout, env=env)


def controller_identity() -> dict:
    sdk = Path(inspect.getfile(run_tree)).resolve().parent
    return {'python': sys.version, 'executable': sys.executable, 'prefix': sys.prefix,
            'sdk_origin': str(sdk),
            'sdk': {p.relative_to(sdk).as_posix(): sha(p) for p in sdk.rglob('*.py')},
            'packages': sorted((str(d.metadata.get('Name', '')).lower(), d.version)
                               for d in importlib.metadata.distributions())}


def identity(worker: Path, wheel: Path, output: Path) -> dict:
    code = '''import sys,json,hashlib,importlib.metadata as m
from pathlib import Path
import framework.inference as inference
base=Path(inference.__file__).resolve().parents[2]
sdk={p.relative_to(base).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (base/'framework').rglob('*.py')}
packages=sorted((str(d.metadata.get('Name','')).lower(),d.version,hashlib.sha256((d.read_text('METADATA') or '').encode()).hexdigest(),hashlib.sha256((d.read_text('RECORD') or '').encode()).hexdigest()) for d in m.distributions())
dist=m.distribution('eidos')
direct=json.loads(dist.read_text('direct_url.json') or '{}')
print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'version':dist.version,'name':dist.metadata['Name'],'distribution_count':sum(str(d.metadata.get('Name','')).lower()=='eidos' for d in m.distributions()),'editable':bool(direct.get('dir_info',{}).get('editable',False)),'distribution_module':str(dist.locate_file('framework/inference/__init__.py')),'module':inference.__file__,'sdk':sdk,'packages':packages}))
'''
    result = run([str(worker), '-I', '-X', 'utf8', '-c', code], output)
    if result.returncode:
        raise RuntimeError('Worker identity failed: ' + result.stderr)
    value = json.loads(result.stdout)
    if Path(value['prefix']).resolve() != worker.parent.parent.resolve():
        raise ValueError('Worker interpreter escaped the selected environment prefix')
    if Path(value['executable']).resolve() != worker.resolve():
        raise ValueError('Worker executable identity changed')
    if not Path(value['module']).resolve().is_relative_to(Path(value['prefix']).resolve()):
        raise ValueError('Worker imported source outside its installed prefix')
    if value['editable'] or value['distribution_count'] != 1:
        raise ValueError('Worker must have one normal, noneditable EIDOS distribution')
    if Path(value['module']).resolve() != Path(value['distribution_module']).resolve():
        raise ValueError('Worker module does not originate from its installed distribution')
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [n for n in names if n.count('/') == 1 and n.endswith('.dist-info/METADATA')]
        if len(set(names)) != len(names) or len(metadata_names) != 1:
            raise ValueError('Ambiguous wheel inventory/metadata')
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if (len(metadata.get_all('Name', [])) != 1 or len(metadata.get_all('Version', [])) != 1
                or metadata['Name'].lower() != 'eidos' or value['name'].lower() != 'eidos'
                or metadata['Version'] != value['version']):
            raise ValueError('Installed distribution differs from selected wheel metadata')
        expected = {name: hashlib.sha256(archive.read(name)).hexdigest()
                    for name in archive.namelist() if name.startswith('framework/') and name.endswith('.py')}
    if value['sdk'] != expected:
        raise ValueError('Installed SDK differs from the complete selected wheel inventory')
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True,
                        help='Prepared env-old/env-new; results must not exist')
    parser.add_argument('--fixture', type=Path, required=True,
                        help='Pinned test_inference_probe_lifetime.py or exact snapshot')
    parser.add_argument('--old-wheel', type=Path, required=True)
    parser.add_argument('--new-wheel', type=Path, required=True)
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error('Optimized assertion execution is not qualified')
    workspace = args.workspace.resolve()
    fixture = args.fixture.resolve()
    wheels = {'old': args.old_wheel.resolve(), 'new': args.new_wheel.resolve()}
    if not all(p.is_file() for p in [fixture, *wheels.values()]):
        parser.error('Missing fixture or immutable wheel')
    fixture_bytes = fixture.read_bytes()
    fixture_before = hashlib.sha256(fixture_bytes).hexdigest()
    driver_before = sha(Path(__file__))
    controller_before = controller_identity()
    output = workspace / 'results'
    output.mkdir(exist_ok=False)
    # Read only two explicitly selected fixture functions; no pytest dependency
    # and no execution of the supplied test module's top-level statements.
    text = fixture_bytes.decode('utf-8')
    tree = ast.parse(text)
    names = {'fake_ollama', 'process_alive'}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(selected) != len(names) or {n.name for n in selected} != names:
        parser.error('Incomplete private fixture')
    if any(n.decorator_list or n.args.defaults or any(n.args.kw_defaults) for n in selected):
        parser.error('Fixture helper decorators/default expressions are unsupported')
    scope = dict(globals())
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(fixture), 'exec'), scope)
    alive_source = ast.get_source_segment(text, next(n for n in selected if n.name == 'process_alive'))
    make_fake = scope['fake_ollama']
    wheel_before = {arm: sha(path) for arm, path in wheels.items()}
    identities = {}
    cases = {}
    for arm, wheel in wheels.items():
        relative = 'Scripts/python.exe' if os.name == 'nt' else 'bin/python'
        worker = workspace / ('env-' + arm) / relative
        if not worker.is_file():
            raise ValueError('Missing prepared worker environment: ' + arm)
        identities[arm] = {'before': identity(worker, wheel, output)}
        cases[arm] = {}
        for mode in ('inherited', 'failure', 'missing'):
            folder = output / (arm + '-' + mode)
            make_fake(folder, mode)
            fake_inputs = {p.name: sha(p) for p in folder.iterdir() if p.is_file()}
            code = ('import json,os\nfrom pathlib import Path\n'
                    'from framework.inference import ModelManager\n' + alive_source +
                    '\nvalue=ModelManager().ollama_available\n'
                    'marker=Path("descendant-ready")\n'
                    'alive=process_alive(int(marker.read_text())) if marker.exists() else False\n'
                    'print(json.dumps({"available":value,"descendant_running_after_probe":alive}),flush=True)')
            try:
                result = run([str(worker), '-I', '-X', 'utf8', '-c', code], folder, 7,
                             dict(os.environ, PATH=str(folder)))
                row = {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
            except subprocess.TimeoutExpired as error:
                decode = lambda s: s.decode('utf-8', errors='replace') if isinstance(s, bytes) else s
                row = {'exit': 124, 'stdout': decode(error.stdout), 'stderr': decode(error.stderr)}
            (folder / 'command.json').write_text(json.dumps(row, indent=2) + '\n', encoding='utf-8')
            if fake_inputs != {name: sha(folder / name) for name in fake_inputs}:
                raise ValueError('Private CLI inputs changed during execution')
            row['fake_input_sha256'] = fake_inputs
            if mode == 'inherited' and (not (folder / 'descendant-ready').is_file()
                                        or not (folder / 'client-finished').is_file()):
                raise ValueError('Both inherited-pipe entry witnesses are required: ' + arm)
            if arm == 'old' and mode == 'inherited':
                if (row['exit'] != 124 or not (folder / 'descendant-ready').is_file()
                        or not (folder / 'client-finished').is_file()):
                    raise ValueError('Old defect was not independently reproduced with both entry witnesses')
            else:
                if row['exit'] or json.loads(row['stdout']) != {
                        'available': mode == 'inherited', 'descendant_running_after_probe': False}:
                    raise ValueError('Private probe or inner ownership contract failed: ' + arm + '/' + mode)
            cases[arm][mode] = row
        identities[arm]['after'] = identity(worker, wheel, output)
        if identities[arm]['before'] != identities[arm]['after']:
            raise ValueError('Installed SDK/dependency metadata changed during measurement')
    if wheel_before != {arm: sha(path) for arm, path in wheels.items()}:
        raise ValueError('Wheel inputs changed')
    if fixture_before != sha(fixture) or driver_before != sha(Path(__file__)):
        raise ValueError('Fixture or driver changed during measurement')
    controller_after = controller_identity()
    if controller_before != controller_after:
        raise ValueError('Controller SDK/runtime metadata changed during measurement')
    record = {'schema': 'eidos.inference-probe-installed.v1', 'status': 'PASS',
              'scope': 'Same-host installed private CLI controls; no host Ollama contact, production recovery, real-model research or scientific RSI claim',
              'driver_sha256': driver_before, 'fixture_sha256': fixture_before,
              'wheel_sha256': wheel_before, 'identities': identities, 'cases': cases,
              'controller': {'before': controller_before, 'after': controller_after}}
    (output / 'record.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'record': str(output / 'record.json'), 'wheel_sha256': wheel_before}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
