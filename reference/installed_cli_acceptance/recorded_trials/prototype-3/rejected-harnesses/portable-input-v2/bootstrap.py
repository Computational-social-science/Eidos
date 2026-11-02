"""Offline bootstrap for the installed CLI controls in a disposable container."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    folder=Path('/input');output=Path('/out')
    body=(folder/'manifest.json').read_bytes()
    digest=lambda value:hashlib.sha256(value).hexdigest()
    if digest(body)!=args.manifest_sha256:raise ValueError('Manifest binding differs')
    expected=json.loads(body)

    def inventory():
        result={}
        for p in folder.rglob('*'):
            if p.is_symlink():raise ValueError('Symlink in acceptance input')
            if p.is_file() and p!=folder/'manifest.json':result[p.relative_to(folder).as_posix()]=digest(p.read_bytes())
        return result

    if inventory()!=expected:raise ValueError('Acceptance inputs differ')
    wheelhouse=Path('/wheels')
    wheel_before={p.name:digest(p.read_bytes()) for p in wheelhouse.iterdir() if p.is_file()}

    def run(name,command,code=0,timeout=120):
        result=subprocess.run(command,cwd='/tmp',capture_output=True,timeout=timeout)
        (output/(name+'.stdout')).write_bytes(result.stdout)
        (output/(name+'.stderr')).write_bytes(result.stderr)
        if result.returncode!=code:raise RuntimeError(name+': unexpected return '+str(result.returncode))
        return result.stdout

    run('venv',[sys.executable,'-I','-m','venv','/tmp/installed'])
    py='/tmp/installed/bin/python'
    run('dependencies',[py,'-I','-m','pip','install','--no-index','--find-links','/wheels','--only-binary=:all:',
                        '--require-hashes','-r','/input/core-requirements.txt'])
    run('wheel',[py,'-I','-m','pip','install','--no-index','--no-deps','/input/eidos-0.5.0-py3-none-any.whl'])
    run('pip-check',[py,'-I','-m','pip','check'])
    identity=json.loads(run('identity',[py,'-I','/input/numerical.py','--wheel','/input/eidos-0.5.0-py3-none-any.whl','--expected-version','0.5.0']))
    if identity['status']!='PASS':raise ValueError('Identity failed')
    refusal=run('optimization-refusal',[py,'-I','-O','/input/cli.py','--fixture','/input/fixture','--out','/out/refused','--expected-version','0.5.0'],code=1)
    if refusal.strip() or (output/'refused').exists():raise ValueError('Optimized driver was not refused before writes')
    actual=json.loads(run('cli',[py,'-I','/input/cli.py','--fixture','/input/fixture','--out','/out/cli-results','--expected-version','0.5.0']))
    if actual.get('status')!='PASS':raise ValueError('CLI checks failed')
    if inventory()!=expected or (folder/'manifest.json').read_bytes()!=body:raise ValueError('Acceptance inputs changed')
    if {p.name:digest(p.read_bytes()) for p in wheelhouse.iterdir() if p.is_file()}!=wheel_before:raise ValueError('Wheelhouse changed')
    record={'status':'PASS','network':'none','manifest_sha256':args.manifest_sha256,
            'identity_status':identity['status'],'wheel_sha256':identity['wheel_sha256'],
            'cli_cases':len(actual['cases']),'driver_sha256':actual['driver_sha256'],
            'optimization_refusal':'PASS','wheelhouse':wheel_before,
            'scope':'Same-host offline Linux normal installation and synthetic CLI controls; not RSI'}
    (output/'record.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
