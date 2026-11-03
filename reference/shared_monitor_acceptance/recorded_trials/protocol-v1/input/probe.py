"""Finite same-host offline Linux venv-entry acceptance; no shared server or RSI."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def installed_identity(value):
    fields = ('sdk_version', 'wheel_sha256', 'wheel_name', 'installed_module',
              'prefix', 'source_sha256_raw', 'source_sha256_canonical_lf',
              'module_count', 'dependencies', 'dependency_metadata_sha256_lf',
              'all_installed_metadata_requirements_met')
    return {key: value[key] for key in fields}


def inventory(folder):
    result = {}
    for path in folder.rglob('*'):
        require(not path.is_symlink(), 'Symlinked acceptance input')
        if path.is_file() and path.name != 'manifest.json':
            result[path.relative_to(folder).as_posix()] = sha(path.read_bytes())
    return result


def inside_worker():
    from framework.monitor_registry import enroll, query_worker
    from framework.subprocesses import run_tree

    output = Path('/out')
    root = Path('/tmp/studies')
    monitor = Path('/tmp/control')
    worker = Path('/tmp/env-b/bin/python')
    require(worker.is_symlink(), 'This control requires an actual symlinked Linux venv entry')
    commands = []
    for suffix in ('a', 'b'):
        project = root / suffix
        python = Path('/tmp/env-' + suffix + '/bin/python')
        command = [str(python), '-I', '-m', 'framework.cli', 'init', '--project', str(project), '--name', 'same_name', '--json']
        result = run_tree(command, cwd='/tmp', timeout=20)
        (output / (suffix + '-init.stdout')).write_text(result.stdout, encoding='utf-8')
        (output / (suffix + '-init.stderr')).write_text(result.stderr, encoding='utf-8')
        require(result.returncode == 0, 'Installed initialization failed')
        (project / '.eidos/validate.py').write_text('from pathlib import Path\nPath("research-ran").touch()\n', encoding='utf-8')
        value = enroll(project, monitor, python)
        require(value['status'] == 'ENROLLED', 'Installed enrollment failed')
        registration = json.loads(Path(value['registration']).read_text(encoding='utf-8'))
        require(registration['python'] == str(python), 'Virtual-environment entry was rewritten')
        require(registration['expected_worker']['prefix'] == str(python.parent.parent), 'Worker prefix was rebound')
        require(registration['expected_worker']['installation_mode'] == 'installed', 'Editable worker accepted in installed probe')
        observation = query_worker(project, python)
        require(observation['run']['status'] == 'UNRUN', 'Observation changed research state')
        require(observation['binding']['state'] == 'STABLE', 'Observation binding is not stable')
        require(not (project / 'research-ran').exists(), 'Read-only enrollment executed the research producer')
        commands.append({'project_id': value['project_id'], 'registration': registration, 'observation': observation})
    require(commands[0]['project_id'] != commands[1]['project_id'], 'Two projects merged by display name')
    require(len(list((monitor / '.eidos-monitor/registrations').glob('*.json'))) == 2, 'Registration count differs')
    broken = run_tree([str(worker.resolve()), '-I', '-m', 'framework.cli', 'observe', '--project', str(root / 'b'), '--json'], cwd='/tmp', timeout=20)
    (output / 'resolved-entry-negative.stdout').write_text(broken.stdout, encoding='utf-8')
    (output / 'resolved-entry-negative.stderr').write_text(broken.stderr, encoding='utf-8')
    require(broken.returncode != 0, 'Broken resolved-entry control did not fail independently')
    record = {'status': 'PASS', 'observations': commands, 'resolved_entry_negative_exit': broken.returncode,
              'scope': 'Two real installed Linux venvs, same core dependencies, isolated project IDs and symlink launch; no aggregator/UI, independent-machine, scientific or RSI acceptance'}
    (output / 'worker-record.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


def bootstrap(manifest_sha):
    import subprocess
    source = Path('/input')
    output = Path('/out')
    body = (source / 'manifest.json').read_bytes()
    require(sha(body) == manifest_sha, 'Input manifest argument differs')
    expected = json.loads(body)
    require(inventory(source) == expected, 'Input inventory differs before execution')
    wheels = inventory(Path('/wheels'))

    def run(name, command, timeout=150):
        result = subprocess.run(command, cwd='/tmp', capture_output=True, timeout=timeout)
        (output / (name + '.stdout')).write_bytes(result.stdout)
        (output / (name + '.stderr')).write_bytes(result.stderr)
        require(result.returncode == 0, name + ': command failed, exit ' + str(result.returncode))
        return result.stdout

    identities = {}
    for suffix in ('a', 'b'):
        prefix = '/tmp/env-' + suffix
        py = prefix + '/bin/python'
        run(suffix + '-venv', [sys.executable, '-I', '-m', 'venv', prefix])
        run(suffix + '-dependencies', [py, '-I', '-m', 'pip', 'install', '--no-index', '--find-links', '/wheels', '--only-binary=:all:', '--require-hashes', '-r', '/input/core-requirements.txt'])
        run(suffix + '-wheel', [py, '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', '/input/eidos-0.5.0-py3-none-any.whl'])
        run(suffix + '-pip-check', [py, '-I', '-m', 'pip', 'check'])
        identities[suffix] = json.loads(run(suffix + '-identity-before', [py, '-I', '/input/numerical.py', '--wheel', '/input/eidos-0.5.0-py3-none-any.whl', '--expected-version', '0.5.0']))
        require(identities[suffix]['status'] == 'PASS', 'Initial installed identity failed')
    run('worker-probe', ['/tmp/env-a/bin/python', '-I', '/input/probe.py', '--inside-worker'], timeout=120)
    for suffix in ('a', 'b'):
        after = json.loads(run(suffix + '-identity-after', ['/tmp/env-' + suffix + '/bin/python', '-I', '/input/numerical.py', '--wheel', '/input/eidos-0.5.0-py3-none-any.whl', '--expected-version', '0.5.0']))
        require(after['status'] == 'PASS' and installed_identity(identities[suffix]) == installed_identity(after),
                'Installed identity changed during observation')
    require(inventory(source) == expected and inventory(Path('/wheels')) == wheels, 'Acceptance inputs changed')
    record = {'status': 'PASS', 'manifest_sha256': manifest_sha, 'input_files': expected, 'wheelhouse': wheels,
              'installed_identity_unchanged': True, 'scope': 'Same-host offline Linux worker protocol only'}
    (output / 'record.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    require(not sys.flags.optimize, 'Optimized acceptance is unsupported')
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside-worker', action='store_true')
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    if args.inside_worker:
        inside_worker()
    else:
        require(args.manifest_sha256 is not None, 'Manifest argument is required')
        bootstrap(args.manifest_sha256)
