"""Trusted, model-free producer for the installed availability repair campaign.

Run with the normal candidate interpreter and -I. This producer executes checks;
the generic ledger separately verifies integrity. It is not hostile-code sandboxing.
"""
from __future__ import annotations

import argparse
import ast
import base64
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
import urllib.request
import zipfile

from framework.artifacts import atomic_output, output_lock
from framework.subprocesses import run_tree


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def put(path: Path, value) -> None:
    body = value if isinstance(value, bytes) else encoded(value)
    with path.open('xb') as stream:
        stream.write(body)


def replace(path: Path, body: bytes) -> None:
    with atomic_output(path) as temporary:
        temporary.write_bytes(body)


@contextmanager
def trial_selection(project: Path, previous: bytes, selected: bytes):
    path = project / '.eidos/runtime-pin.json'
    with output_lock(project / '.eidos/runtime-pin'):
        if path.read_bytes() != previous:
            raise ValueError('Cannot replace an unrelated project selection')
        replace(path, selected)
    try:
        yield
    finally:
        with output_lock(project / '.eidos/runtime-pin'):
            actual = path.read_bytes()
            if actual == selected:
                replace(path, previous)
            elif actual != previous:
                raise ValueError('Cleanup refused to overwrite an unrelated project selection')


@contextmanager
def adopted_guard(project: Path, incident: str):
    from framework import feedback
    try:
        yield
    except BaseException:
        if feedback.status(project, incident)['state'] in ('ADOPTED', 'REPLAY_FAILED'):
            feedback.revert(project, incident)
        raise


def verify_inputs(inputs: dict) -> None:
    for name, digest in inputs.items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError('Protected campaign input changed: ' + name)


def probe_verdict(row: dict, folder: Path, mode: str) -> str:
    if mode == 'inherited':
        if not all((folder / name).is_file() for name in ('descendant-ready', 'client-finished')):
            raise ValueError('Both entry witnesses are required; unentered checks are not defects')
        if row['exit'] == 124:
            return 'FAIL'
    if row['exit'] != 0:
        raise ValueError('Probe did not finish observably: ' + str(row['exit']))
    value = json.loads(row['stdout'])
    expected = {'available': mode == 'inherited', 'descendant_running_after_probe': False}
    return 'PASS' if value == expected else 'FAIL'


def origin_verdict(row: dict, folder: Path, inherited: bool) -> str:
    if inherited:
        if not all((folder / name).is_file() for name in ('descendant-ready', 'client-finished')):
            raise ValueError('Original owner did not reach both entry witnesses')
        if row['exit'] == 124:
            return 'FAIL'
    if row['exit'] != 0:
        raise ValueError('Original owner did not execute observably')
    value = json.loads(row['stdout'])
    return 'PASS' if value['result'][0] == 'PASS' and value['descendant_running_after_contract'] is False else 'FAIL'


def helpers(oracle: Path, fixture: Path):
    spec = importlib.util.spec_from_file_location('qualified_probe_oracle', oracle)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = fixture.read_text(encoding='utf-8')
    selected = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
                and n.name in {'fake_ollama', 'process_alive'}]
    if len(selected) != 2 or any(n.decorator_list or n.args.defaults or any(n.args.kw_defaults) for n in selected):
        raise ValueError('Unexpected trusted probe fixture')
    scope = vars(module).copy()
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(fixture), 'exec'), scope)
    alive = ast.get_source_segment(text, next(n for n in selected if n.name == 'process_alive'))
    return module.identity, scope['fake_ollama'], alive


def command(argv: list[str], cwd: Path, timeout=30, env=None) -> dict:
    try:
        p = run_tree(argv, cwd=cwd, timeout=timeout, env=env)
        return {'argv': argv, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    except subprocess.TimeoutExpired as error:
        def text(value):
            return value.decode('utf-8', 'replace') if isinstance(value, bytes) else value or ''
        return {'argv': argv, 'exit': 124, 'stdout': text(error.output), 'stderr': text(error.stderr)}


def cli(project: Path, *args: str) -> dict:
    row = command([sys.executable, '-I', '-X', 'utf8', '-m', 'framework.cli',
                   *args, '--project', str(project), '--json'], project)
    value = json.loads(row['stdout'])
    if row['exit'] not in (0, 4) or value.get('status') not in {'INITIALIZED', 'EXPORTED', 'REFUSED'}:
        raise ValueError('Unexpected initialization/check/export result: ' + str(row))
    return {'command': row, 'result': value}


def history(project: Path) -> bytes:
    paths = (project / '.eidos/runs').glob('*.json')
    return encoded({p.name: sha(p.read_bytes()) for p in sorted(paths)
                    if re.fullmatch('[0-9a-f]{32}\\.json', p.name)})


def selected_python(config: dict, arm: str) -> Path:
    return Path(config['workers'][arm])


def evaluate(config: dict, arm: str, stage: str, *, fault=False) -> dict:
    verify_inputs(config['protected'])
    output = Path(config['workspace']) / ('execution-' + stage + '-' + uuid.uuid4().hex)
    output.mkdir()
    identity, fake, alive = helpers(Path(config['oracle']), Path(config['fixture']))
    worker = selected_python(config, arm)
    wheel = Path(config['wheels'][arm])
    before = identity(worker, wheel, output)
    rows, checks = {}, {}
    for mode, name in [('inherited', 'inherited_pipe'), ('failure', 'nonzero_cli'), ('missing', 'missing_cli')]:
        folder = output / mode
        fake(folder, mode)
        if fault and mode == 'inherited':
            # Prespecified failure control: real CLI exits nonzero after both
            # entry witnesses; the fixed acceptance expectation is unchanged.
            with (folder / 'list').open('a', encoding='utf-8') as stream:
                stream.write('\nraise SystemExit(3)\n')
        inputs = {p.name: sha(p.read_bytes()) for p in folder.iterdir() if p.is_file()}
        code = ('import json,os\nfrom pathlib import Path\nfrom framework.inference import ModelManager\n'
                + alive + '\nvalue=ModelManager().ollama_available\n'
                'marker=Path("descendant-ready")\n'
                'running=process_alive(int(marker.read_text())) if marker.exists() else False\n'
                'print(json.dumps({"available":value,"descendant_running_after_probe":running}),flush=True)')
        row = command([str(worker), '-I', '-X', 'utf8', '-c', code], folder, 7,
                      dict(os.environ, PATH=str(folder), PYTHONIOENCODING='utf-8'))
        assert inputs == {name: sha((folder / name).read_bytes()) for name in inputs}
        row['input_sha256'] = inputs
        put(folder / 'command.json', row)
        verdict = probe_verdict(row, folder, mode)
        rows[name] = row
        checks[name] = {'executed': True, 'status': verdict}
    origin_code = '''import ast,json,os,sys
from pathlib import Path
body=Path(sys.argv[1]).read_text(encoding='utf-8-sig')
nodes=[n for n in ast.parse(body).body if isinstance(n,ast.FunctionDef) and n.name=='audit_inference']
assert len(nodes)==1
nodes[0].decorator_list=[]
scope={};exec(compile(ast.Module(body=nodes,type_ignores=[]),sys.argv[1],'exec'),scope)
'''
    origin_code += alive + '''
value=scope['audit_inference']()
p=Path('caller-entry-pids.log')
pids=p.read_text().splitlines() if p.exists() else []
print(json.dumps({'result':value,'descendant_running_after_contract':any(process_alive(int(pid)) for pid in pids)}))
'''
    for mode in ('failure', 'inherited'):
        folder = output / ('origin-' + mode)
        fake(folder, mode)
        if mode == 'inherited':
            script = folder / 'list'
            text = script.read_text(encoding='utf-8')
            text = text.replace("Path('client-finished').write_text('root exiting')",
                                "Path('caller-entry-pids.log').open('a').write(Path('descendant-ready').read_text()+'\\n')\n"
                                "Path('client-finished').write_text('root exiting')")
            script.write_text("from pathlib import Path\nPath('descendant-ready').unlink(missing_ok=True)\n"
                              "Path('client-finished').unlink(missing_ok=True)\n" + text, encoding='utf-8')
        fake_inputs = {p.name: sha(p.read_bytes()) for p in folder.iterdir() if p.is_file()}
        row = command([str(worker), '-I', '-X', 'utf8', '-c', origin_code,
                       str(Path(config['project']) / 'tools/audit_chains.py')], folder, 20,
                      dict(os.environ, PATH=str(folder), PYTHONIOENCODING='utf-8'))
        assert fake_inputs == {name: sha((folder / name).read_bytes()) for name in fake_inputs}
        row['input_sha256'] = fake_inputs
        put(folder / 'command.json', row)
        verdict = origin_verdict(row, folder, mode == 'inherited')
        if mode == 'failure':
            checks['origin_contract'] = {'executed': True, 'status': verdict}
        elif verdict != 'PASS':
            checks['inherited_pipe']['status'] = 'FAIL'
    after = identity(worker, wheel, output)
    assert before == after, 'Installed SDK/dependencies changed during execution'
    verify_inputs(config['protected'])
    result = {'schema': 'eidos.repair-check.v1', 'project_id': config['project_id'],
              'protocol_sha256': config['protocol_sha256'], 'artifact_sha256': sha(wheel.read_bytes()),
              'run_id': uuid.uuid4().hex, 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'stage': stage, 'origin_sha256': config['protocol']['origin_sha256'], 'checks': checks,
              'fault_injection': fault, 'identity_before': before, 'identity_after': after,
              'raw_execution': str(output), 'producer_sha256': sha(Path(__file__).read_bytes())}
    if stage == 'replay':
        result['pin_sha256'] = sha((Path(config['project']) / '.eidos/runtime-pin.json').read_bytes())
    put(output / 'check.json', result)
    return result


def receipt(config: dict, kind: str, *, artifacts=None, **details) -> dict:
    from framework import feedback
    folder = Path(config['workspace']) / 'receipts'
    folder.mkdir(exist_ok=True)
    refs = {}
    for role, body in (artifacts or {}).items():
        raw = body if isinstance(body, bytes) else encoded(body)
        name = sha(raw) + '.data'
        path = folder / name
        if not path.exists():
            put(path, raw)
        assert path.read_bytes() == raw
        refs[role] = {'path': name, 'sha256': sha(raw)}
    value = {'schema': 'eidos.repair-receipt.v1', 'incident_id': config['incident_id'],
             'project_id': config['project_id'], 'protocol_sha256': config['protocol_sha256'],
             'kind': kind, 'details': details, 'artifacts': refs}
    path = folder / (kind + '-' + uuid.uuid4().hex + '.json')
    put(path, value)
    verify_inputs(config['protected'])
    result = feedback.record(Path(config['project']), config['incident_id'], path)
    put(folder / (path.stem + '-result.json'), result)
    return result


def control_wheel(baseline: Path, output: Path) -> None:
    """A deliberate no-fix control: unchanged old SDK with a distinct dev version."""
    with zipfile.ZipFile(baseline) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    old = next(n.rsplit('/', 1)[0] for n in members if n.endswith('.dist-info/METADATA'))
    new = 'eidos-0.5.0.dev0.dist-info'
    members = {n.replace(old + '/', new + '/', 1): body for n, body in members.items()
               if n != old + '/RECORD'}
    name = new + '/METADATA'
    header, separator, body = members[name].partition(b'\r\n\r\n')
    if not separator:
        header, separator, body = members[name].partition(b'\n\n')
    assert separator and len(re.findall(rb'(?m)^Version: 0[.]4[.]12\r?$', header)) == 1
    header = re.sub(rb'(?m)^(Version: )0[.]4[.]12(\r?)$', rb'\g<1>0.5.0.dev0\2', header)
    members[name] = header + separator + body
    record = io.StringIO(newline='')
    writer = csv.writer(record, lineterminator='\n')
    for name, body in sorted(members.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b'=').decode()
        writer.writerow((name, 'sha256=' + digest, len(body)))
    writer.writerow((new + '/RECORD', '', ''))
    members[new + '/RECORD'] = record.getvalue().encode()
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)


def baseline_pin(config: dict, arm: str) -> bytes:
    identity, _, _ = helpers(Path(config['oracle']), Path(config['fixture']))
    observed = identity(selected_python(config, arm), Path(config['wheels'][arm]), Path(config['workspace']))
    modules = {n.removeprefix('framework/'): value for n, value in observed['sdk'].items()}
    packages = [(row[0], row[1]) for row in observed['packages']]
    return encoded({'schema': 'eidos.project-runtime-pin.v1', 'project_id': config['project_id'],
                    'incident_id': config['incident_id'], 'version': observed['version'],
                    'python': str(selected_python(config, arm)), 'prefix': observed['prefix'],
                    'artifact_sha256': sha(Path(config['wheels'][arm]).read_bytes()),
                    'sdk_source_sha256': sha(json.dumps(modules, sort_keys=True, separators=(',', ':')).encode()),
                    'sdk_module_count': len(modules), 'distributions_sha256': sha(json.dumps(packages).encode()),
                    'adopted_at': datetime.now(timezone.utc).isoformat(),
                    'selection_scope': 'Explicit on-demand campaign selection, not resident-service migration'})


def preparation_inputs(project: Path, workspace: Path, oracle: Path, fixture: Path) -> tuple[dict, dict]:
    """Refuse existing research workspaces and qualify inputs before side effects.

    Resume uses the existing sealed campaign branch instead. A configured study
    needs a separate explicit handoff; never replace or run its gate here.
    """
    folder = project / '.eidos'
    if folder.exists() or folder.is_symlink():
        raise ValueError('Existing EIDOS workspace requires its sealed campaign or an explicit separate handoff')
    wheels = {arm: str((workspace / 'wheels' / name).resolve()) for arm, name in
              [('old', 'eidos-0.4.12-py3-none-any.whl'), ('bad', 'eidos-0.5.0.dev0-py3-none-any.whl'),
               ('new', 'eidos-0.5.0-py3-none-any.whl')]}
    workers = {arm: workspace / ('env-' + arm) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
               for arm in wheels}
    origin = project / 'tools/audit_chains.py'
    inputs = [Path(__file__).resolve(), Path(__file__).with_name('publication_identity.py').resolve(),
              oracle, fixture, origin, *(Path(p) for p in wheels.values())]
    if not all(path.is_file() for path in [*inputs, *workers.values()]):
        raise ValueError('Missing preparation input; no project has been initialized or checked')
    if not origin.resolve().is_relative_to(project):
        raise ValueError('Preparation origin escapes the selected project')
    if origin.resolve() != Path(os.path.abspath(origin)):
        raise ValueError('Preparation origin is redirected; the repair ledger requires an ordinary file path')
    owners = [node for node in ast.parse(origin.read_text(encoding='utf-8-sig')).body
              if isinstance(node, ast.FunctionDef) and node.name == 'audit_inference']
    if len(owners) != 1:
        raise ValueError('Preparation input lacks its unique original audit_inference owner')
    protected = {str(path): sha(path.read_bytes()) for path in inputs}
    identity, _, _ = helpers(oracle, fixture)
    for arm, worker in workers.items():
        identity(worker, Path(wheels[arm]), workspace)
    verify_inputs(protected)
    return wheels, protected


def prepare(args) -> dict:
    from framework import feedback
    import yaml
    project, workspace = args.project.resolve(), args.workspace.resolve()
    expected = workspace / 'env-new' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if Path(os.path.abspath(sys.executable)) != expected:
        raise ValueError('Run preparation from its selected normal installed candidate interpreter')
    if (workspace / 'campaign.json').exists():
        config = json.loads((workspace / 'campaign.json').read_bytes())
        if config['project'] != str(project) or config['oracle'] != str(args.oracle.resolve()) or config['fixture'] != str(args.fixture.resolve()):
            raise ValueError('Resume targets another project or protected evaluator')
        verify_inputs(config['protected'])
        return advance_prepare(config)
    wheels, protected = preparation_inputs(project, workspace, args.oracle.resolve(), args.fixture.resolve())
    project.mkdir(exist_ok=True)
    initialized = cli(project, 'init')
    if initialized['result']['status'] != 'INITIALIZED':
        raise ValueError('Project initialization was refused; no configured research gate will be run')
    if (project / '.eidos/runtime-pin.json').exists():
        raise ValueError('Existing project pin is not a disposable campaign baseline')
    workspace.mkdir(exist_ok=True)
    record = cli(project, 'check')
    put(workspace / 'initial-refusal.json', record)
    assert json.loads(history(project)), 'Rollback must preserve nonempty actual run history'
    project_id = yaml.safe_load((project / '.eidos/project.yaml').read_bytes())['project_id']
    files = {'tools/audit_chains.py': sha((project / 'tools/audit_chains.py').read_bytes()),
             '.eidos/validate.py': sha((project / '.eidos/validate.py').read_bytes())}
    verify_inputs(protected)
    protocol = {'schema': 'eidos.repair-protocol.v1', 'project_id': project_id,
                'scope': 'Real EIDOS inherited-pipe software defect; private CLI fixtures and original routing oracle; no scientific acceptance',
                'required_checks': ['inherited_pipe', 'nonzero_cli', 'missing_cli', 'origin_contract'],
                'regression_check': 'inherited_pipe', 'require_rejection_control': True,
                'ci_workflows': ['ci', 'installed-sdk'], 'origin_files': files,
                'origin_sha256': sha(encoded(files)), 'protected_evaluator_inputs': protected,
                'seeds': 'Not applicable: deterministic process-lifetime and routing checks'}
    policy = workspace / 'protocol.json'
    put(policy, protocol)
    exported = cli(project, 'feedback', '--message', 'Actual inherited-pipe availability defect; retain original timeout and protected regression', '--out', str(workspace / 'feedback.zip'))
    put(workspace / 'feedback-export.json', exported)
    created = feedback.create(project, 'Inherited-pipe availability regression', policy,
                              feedback_bundle=workspace / 'feedback.zip')
    config = {'project': str(project), 'workspace': str(workspace), 'project_id': project_id,
              'incident_id': created['incident_id'], 'protocol': protocol, 'protocol_sha256': sha(policy.read_bytes()),
              'wheels': wheels, 'workers': {arm: str(workspace / ('env-' + arm) /
                           ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')) for arm in wheels},
              'protected': protected, 'oracle': str(args.oracle.resolve()), 'fixture': str(args.fixture.resolve())}
    put(workspace / 'campaign.json', config)
    return advance_prepare(config)


def advance_prepare(config: dict) -> dict:
    from framework import feedback
    project, workspace = Path(config['project']), Path(config['workspace'])
    wheels = config['wheels']
    state = feedback.status(project, config['incident_id'])['state']
    pin = project / '.eidos/runtime-pin.json'
    if not (workspace / 'original-pin.json').exists():
        if state != 'DETECTED' or pin.exists():
            raise ValueError('Cannot invent a missing prior pin for an advanced campaign')
        put(workspace / 'original-pin.json', baseline_pin(config, 'old'))
    prior = (workspace / 'original-pin.json').read_bytes()
    with output_lock(project / '.eidos/runtime-pin'):
        if not pin.exists() and state == 'DETECTED':
            replace(pin, prior)
        saved_bad = workspace / 'bad-pin.json'
        if state in ('CANDIDATE', 'REJECTED') and saved_bad.exists() and pin.read_bytes() == saved_bad.read_bytes():
            # The previous process may have died before its Python finally.
            replace(pin, prior)
            put(workspace / ('interrupted-selection-restored-' + uuid.uuid4().hex + '.json'),
                {'prior_sha256': sha(prior), 'restored_from': sha(saved_bad.read_bytes())})
        if pin.read_bytes() != prior:
            raise ValueError('Campaign must start or resume from its preserved baseline selection')
    if state == 'DETECTED':
        state = receipt(config, 'triage', classification='core')['state']
    if state == 'TRIAGED':
        result = evaluate(config, 'old', 'reproduction')
        state = receipt(config, 'reproduction', artifacts={'wheel': Path(wheels['old']).read_bytes(), 'check': result})['state']
    if not (workspace / 'bad-pin.json').exists():
        put(workspace / 'bad-pin.json', baseline_pin(config, 'bad'))
    bad_pin = (workspace / 'bad-pin.json').read_bytes()
    if state == 'REPRODUCED':
        state = receipt(config, 'candidate', artifacts={'wheel': Path(wheels['bad']).read_bytes()})['state']
    if state == 'CANDIDATE' and feedback.status(project, config['incident_id'])['candidate_sha256'] == sha(Path(wheels['bad']).read_bytes()):
        with trial_selection(project, prior, bad_pin):
            result = evaluate(config, 'bad', 'rejection')
            state = receipt(config, 'rejection', artifacts={'wheel': Path(wheels['bad']).read_bytes(), 'check': result,
                                                           'trial_pin': bad_pin})['state']
    if state == 'REJECTED':
        before = history(project)
        result = evaluate(config, 'old', 'rollback')
        state = receipt(config, 'rollback', artifacts={'wheel': Path(wheels['old']).read_bytes(), 'check': result,
                'pin_before': bad_pin, 'pin_after': pin.read_bytes(), 'history_before': before, 'history_after': history(project)})['state']
    if state == 'ROLLED_BACK':
        state = receipt(config, 'candidate', artifacts={'wheel': Path(wheels['new']).read_bytes()})['state']
    if state == 'CANDIDATE':
        result = evaluate(config, 'new', 'validation')
        state = receipt(config, 'validation', artifacts={'wheel': Path(wheels['new']).read_bytes(), 'check': result})['state']
    if state != 'VALIDATED':
        raise ValueError('Unexpected prepare/resume lifecycle state: ' + state)
    try:
        feedback.close(project, config['incident_id'])
    except ValueError as error:
        if not (workspace / 'premature-close-refused.json').exists():
            put(workspace / 'premature-close-refused.json', {'status': 'REFUSED', 'reason': str(error)})
    else:
        raise ValueError('Unpublished campaign was incorrectly closed')
    return feedback.status(project, config['incident_id'])


def fetch(url: str, output: Path) -> dict:
    request = urllib.request.Request(url, headers={'User-Agent': 'EIDOS-Repair-Qualification',
                                                  'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError('Remote publication record exceeds the bound')
    put(output, body)
    return json.loads(body)


def publication_artifacts(config: dict) -> dict:
    root = Path(config['workspace']) / 'publication'
    root.mkdir(exist_ok=True)
    remote = root / uuid.uuid4().hex
    remote.mkdir()
    api = 'https://api.github.com/repos/Computational-social-science/Eidos'
    release = fetch(api + '/releases/tags/v0.5.0', remote / 'release.json')
    ref = fetch(api + '/git/ref/tags/v0.5.0', remote / 'ref.json')
    tag = {'ref': ref}
    target = ref['object']
    if target['type'] == 'tag':
        tag['annotation'] = fetch(api + '/git/tags/' + target['sha'], remote / 'annotation.json')
        target = tag['annotation']['object']
    if target['type'] != 'commit':
        raise ValueError('Published tag does not target a commit')
    head = target['sha']
    ci = fetch(api + '/actions/runs?head_sha=' + head + '&per_page=100', remote / 'ci.json')
    source = fetch(api + '/contents/site/versions.json?ref=' + head, remote / 'history-envelope.json')
    versions = json.loads(base64.b64decode(source['content']))
    if versions[-1]['version'] != '0.5.0':
        raise ValueError('Release source history names another version')
    for name in config['protocol']['ci_workflows']:
        runs = [r for r in ci['workflow_runs'] if r['name'] == name and r['head_sha'] == head]
        latest = max(runs, key=lambda r: (r['id'], r.get('run_attempt', 1))) if runs else None
        if latest is None or latest['status'] != 'completed' or latest['conclusion'] != 'success':
            raise ValueError('Required real remote CI is not successful: ' + name)
    comparison = fetch(api + '/compare/' + versions[-1]['source_commit'] + '...' + head, remote / 'ancestry.json')
    if comparison['status'] not in ('identical', 'ahead'):
        raise ValueError('Release delivery does not descend from its recorded source')
    proof = {'schema': 'eidos.release-proof.v1', 'published': True,
             'artifact_sha256': sha(Path(config['wheels']['new']).read_bytes()), 'version': '0.5.0',
             'source_commit': versions[-1]['source_commit'], 'head_commit': head,
             'ci_head': head, 'ci_conclusion': 'success', 'tag': 'v0.5.0',
             'asset_name': 'eidos-0.5.0-py3-none-any.whl'}
    normalizer_path = Path(__file__).with_name('publication_identity.py')
    verify_inputs(config['protected'])
    spec = importlib.util.spec_from_file_location('qualified_publication_identity', normalizer_path)
    normalizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(normalizer)
    original_proof = proof
    proof = normalizer.canonical_source(proof, comparison)
    asset = next(a for a in release['assets'] if a['name'] == proof['asset_name'])
    with urllib.request.urlopen(asset['browser_download_url'], timeout=60) as response:
        downloaded = response.read(16 * 1024 * 1024 + 1)
    assert downloaded == Path(config['wheels']['new']).read_bytes(), 'Actual published bytes differ'
    put(remote / proof['asset_name'], downloaded)
    return {'wheel': downloaded, 'publication': proof, 'release': release, 'ci': ci, 'tag': tag,
            'normalization_input': original_proof, 'source_resolution': comparison,
            'normalizer_source': normalizer_path.read_bytes()}


def recorded_replays(config: dict) -> list[tuple[dict, dict]]:
    """Read only after the core has validated this journal and all its blobs."""
    folder = Path(config['project']) / '.eidos/incidents' / config['incident_id']
    events = json.loads((folder / 'journal.json').read_bytes())['events']
    rows = []
    for index, event in enumerate(events):
        if event['kind'] != 'replay':
            continue
        body = (folder / 'blobs' / event['artifacts']['check']).read_bytes()
        assert sha(body) == event['artifacts']['check']
        rows.append((json.loads(body), events[index + 1] if index + 1 < len(events) else {}))
    return rows


def finish(args) -> dict:
    from framework import feedback
    config = json.loads((args.workspace / 'campaign.json').read_bytes())
    verify_inputs(config['protected'])
    project = Path(config['project'])
    if Path(os.path.abspath(sys.executable)) != selected_python(config, 'new'):
        raise ValueError('Completion must run from the selected normal installed candidate')
    state = feedback.status(project, config['incident_id'])['state']
    if state == 'CLOSED':
        return feedback.status(project, config['incident_id'])
    if state not in ('VALIDATED', 'RELEASED', 'REVERTED', 'ADOPTED', 'REPLAY_FAILED', 'REPLAYED'):
        raise ValueError('Campaign is not ready for publication/adoption: ' + state)
    artifacts = publication_artifacts(config)
    verify_inputs(config['protected'])
    if state == 'VALIDATED':
        state = receipt(config, 'release', artifacts=artifacts)['state']
    previous = (args.workspace / 'original-pin.json').read_bytes()
    pin = project / '.eidos/runtime-pin.json'
    before = history(project)
    if state == 'REPLAY_FAILED':
        feedback.revert(project, config['incident_id'])
        state = 'REVERTED'
    replays = recorded_replays(config)
    if replays and not replays[-1][0].get('fault_injection') and any(
            row['status'] != 'PASS' for row in replays[-1][0]['checks'].values()):
        raise ValueError('An actual non-injected replay failed; investigation is required')
    if state != 'REPLAYED':
        feedback.adopt(project, config['incident_id'], selected_python(config, 'new'))
        with adopted_guard(project, config['incident_id']):
            controlled_reversion = any(check.get('fault_injection') is True and following.get('kind') == 'reversion'
                                       for check, following in replays)
            if not controlled_reversion:
                result = evaluate(config, 'new', 'replay', fault=True)
                receipt(config, 'replay', artifacts={'wheel': artifacts['wheel'], 'check': result,
                                                   'pin_after': pin.read_bytes()})
                assert feedback.status(project, config['incident_id'])['state'] == 'REPLAY_FAILED'
                feedback.revert(project, config['incident_id'])
                assert pin.read_bytes() == previous
                after = json.loads(history(project))
                assert all(after.get(k) == v for k, v in json.loads(before).items())
                put(args.workspace / ('actual-reversion-' + uuid.uuid4().hex + '.json'),
                    {'restored_pin_sha256': sha(previous), 'history_before': json.loads(before), 'history_after': after})
                feedback.adopt(project, config['incident_id'], selected_python(config, 'new'))
            result = evaluate(config, 'new', 'replay')
            receipt(config, 'replay', artifacts={'wheel': artifacts['wheel'], 'check': result,
                                               'pin_after': pin.read_bytes()})
            if feedback.status(project, config['incident_id'])['state'] != 'REPLAYED':
                raise ValueError('Fresh non-injected replay failed')
    verify_inputs(config['protected'])
    closed = feedback.close(project, config['incident_id'])
    assert closed['state'] == 'CLOSED' and closed['scientific_status'] == 'UNRUN'
    if not (args.workspace / 'closed.json').exists():
        put(args.workspace / 'closed.json', closed)
    verify_inputs(config['protected'])
    return closed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('control-wheel')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    for action in ('prepare', 'finish'):
        p = sub.add_parser(action)
        p.add_argument('--workspace', type=Path, required=True)
        if action == 'prepare':
            p.add_argument('--project', type=Path, required=True)
            p.add_argument('--oracle', type=Path, required=True)
            p.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error('Optimized assertion execution is not qualified')
    if args.action == 'control-wheel':
        control_wheel(args.baseline, args.output)
        result = {'control_wheel_sha256': sha(args.output.read_bytes())}
    else:
        result = prepare(args) if args.action == 'prepare' else finish(args)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
