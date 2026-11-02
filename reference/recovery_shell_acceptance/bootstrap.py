"""Offline installed-core replay inside an owned disposable Linux container."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def sha(body):
    return hashlib.sha256(body).hexdigest()


def inventory(folder, names):
    result = {}
    for name in names:
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Nonflat qualification member')
        path = folder/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Nonregular qualification input')
        result[name] = sha(path.read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true', required=True)
    parser.add_argument('--manifest-sha', required=True)
    args = parser.parse_args()
    folder, output = Path('/input'), Path('/out')
    body = (folder/'manifest.json').read_bytes()
    if sha(body) != args.manifest_sha:
        raise ValueError('Pinned input manifest differs')
    manifest = json.loads(body)
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid candidate version')
    wheel = f'eidos-{version}-py3-none-any.whl'
    names = {'offline.py', 'shell.py', 'numerical.py', 'lifecycle.py', 'core-requirements.txt', wheel}
    if (set(manifest['files']) != names
            or {p.name for p in folder.iterdir()} != names | {'manifest.json'}
            or inventory(folder, names) != manifest['files']):
        raise ValueError('Qualification input inventory/hash differs')
    wheel_names = {p.name for p in Path('/wheels').iterdir()}
    if wheel_names != set(manifest['wheels']) or inventory(Path('/wheels'), wheel_names) != manifest['wheels']:
        raise ValueError('Wheelhouse changed')
    def run(name, command, timeout):
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        (output/(name+'.stdout')).write_bytes(result.stdout)
        (output/(name+'.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError('Qualification command failed: '+name)
        return result.stdout
    started = time.monotonic()
    run('venv', [sys.executable, '-I', '-m', 'venv', '/tmp/candidate'], 30)
    python = '/tmp/candidate/bin/python'
    run('core-install', [python, '-I', '-m', 'pip', 'install', '--no-index', '--find-links', '/wheels',
                         '--only-binary=:all:', '--require-hashes', '-r', '/input/core-requirements.txt'], 90)
    run('sdk-install', [python, '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', '/input/'+wheel], 30)
    run('pip-check', [python, '-I', '-m', 'pip', 'check'], 30)
    (output/'bootstrap.json').write_text(json.dumps({'seconds': time.monotonic()-started,
        'runtime': sys.version, 'network': 'none', 'requirements_sha256': manifest['files']['core-requirements.txt']}, indent=2)+'\n')
    records = {}
    for name in ('shell', 'numerical', 'lifecycle'):
        command = [python, '-I', '-X', 'utf8', '/input/'+name+'.py']
        if name != 'lifecycle':
            command += ['--wheel', '/input/'+wheel, '--expected-version', version]
        if name == 'shell':
            command += ['--identity-driver', '/input/numerical.py',
                        '--identity-sha256', manifest['files']['numerical.py']]
        raw = run(name, command, 120)
        value = json.loads(raw)
        identity = value['identity'] if name == 'shell' else value
        if identity.get('sdk_version') != version:
            raise ValueError('Wrong executed SDK version')
        if name != 'lifecycle' and (value.get('status') != 'PASS'
                or identity.get('module_count') != 45 or identity.get('wheel_sha256') != manifest['files'][wheel]):
            raise ValueError('Wrong whole-wheel identity or failed case')
        records[name] = {'status': 'PASS', 'stdout_sha256': sha(raw)}
    if inventory(folder, names) != manifest['files'] or (folder/'manifest.json').read_bytes() != body:
        raise ValueError('Inputs changed during replay')
    if inventory(Path('/wheels'), wheel_names) != manifest['wheels']:
        raise ValueError('Wheelhouse changed during replay')
    campaign = output/'campaign';campaign.mkdir()
    (campaign/'campaign.json').write_text(json.dumps({
        'schema': 'eidos.installed-core-replay.v1', 'status': 'PASS',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'version': version,
        'manifest_sha256': args.manifest_sha, 'cases': records,
        'limits': 'Finite core/shell controls only; not a model, tracking, manuscript or hostile-code qualification.'}, indent=2)+'\n')


if __name__ == '__main__':
    main()
