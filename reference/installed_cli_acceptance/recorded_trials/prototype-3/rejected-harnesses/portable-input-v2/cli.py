"""Finite installed-console acceptance using a synthetic Gate S fixture."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

import yaml


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--expected-version',required=True)
    args=parser.parse_args()
    if sys.prefix==sys.base_prefix or not sys.flags.isolated or sys.flags.optimize:
        raise RuntimeError('Use an isolated non-optimized invocation in a dedicated installed venv')
    if importlib.metadata.version('eidos')!=args.expected_version:
        raise RuntimeError('Wrong installed version')
    console=Path(sys.prefix)/('Scripts/eidos.exe' if os.name=='nt' else 'bin/eidos')
    if not console.is_file():raise RuntimeError('Missing installed console entry')
    args.out.mkdir(parents=True,exist_ok=False)
    work=Path(tempfile.mkdtemp(prefix='eidos-cli-console-'))
    environment=os.environ.copy()
    for name in ('PYTHONPATH','PYTHONHOME'):environment.pop(name,None)
    environment['EIDOS_TEST_PRIVATE_MARKER']='do-not-export-environment-value'
    records=[]

    def cli(label,action,project,expected=0,*extra):
        result=subprocess.run([str(console),action,'--project',str(project),'--json',*extra],
            cwd=work,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        (args.out/(label+'.stdout')).write_text(result.stdout,encoding='utf-8')
        (args.out/(label+'.stderr')).write_text(result.stderr,encoding='utf-8')
        if result.returncode!=expected:raise RuntimeError(label+': unexpected exit '+str(result.returncode)+': '+result.stdout[-500:])
        value=json.loads(result.stdout)
        if value.get('operation')!=action or value.get('schema')!='eidos.cli-result.v1':
            raise RuntimeError('Wrong structured result contract')
        records.append({'case':label,'exit_code':result.returncode,'status':value['status'],
                        'scientific_status':value.get('scientific_status')})
        return value

    def configure(project,**values):
        path=project/'.eidos/project.yaml';config=yaml.safe_load(path.read_text(encoding='utf-8'))
        config.update(values)
        path.write_text(yaml.safe_dump(config),encoding='utf-8')

    def science(name,inputs):
        project=work/name;shutil.copytree(args.fixture,project)
        cli(name+'-init','init',project)
        (project/'gate.py').write_text('print("synthetic validator completed")',encoding='utf-8')
        configure(project,gate_command=['{python}','-m','gate'],validity_inputs=inputs,
                  validity_document='docs/MANUSCRIPT.html')
        return project

    project=work/'study';project.mkdir()
    (project/'private.txt').write_text('do-not-export-private-data',encoding='utf-8')
    cli('init','init',project)
    assert cli('initial-refusal','check',project,4)['scientific_status']=='UNRUN'
    configure(project,gate_command=['{python}','-c','print("execution complete")'])
    assert cli('execution-only','check',project,0,'--execution-only')['scientific_status']=='UNRUN'
    configure(project,expects=['missing-output.json'])
    assert cli('missing-output','check',project,1,'--execution-only')['status']=='FAIL'
    bundle=work/'feedback.zip'
    cli('feedback','feedback',project,0,'--message','synthetic failure','--out',str(bundle))
    body=bundle.read_bytes()
    with zipfile.ZipFile(bundle) as archive:
        assert set(archive.namelist())=={'feedback.json','manifest.json'}
        payload=archive.read('feedback.json');manifest=json.loads(archive.read('manifest.json'))
        assert manifest['files']['feedback.json']==hashlib.sha256(payload).hexdigest()
        assert b'do-not-export-private-data' not in payload
        assert b'do-not-export-environment-value' not in payload
    cli('feedback-overwrite','feedback',project,4,'--message','do not overwrite','--out',str(bundle))
    assert bundle.read_bytes()==body
    assert cli('missing-manuscript','report',project,4,'--format','html')['status']=='REFUSED'

    project=science('scientific',['gate.py'])
    accepted=cli('scientific-pass','check',project)
    assert accepted['scientific_status']=='PASS'
    old_record=project/'.eidos/runs'/(accepted['run_id']+'.json');old_body=old_record.read_bytes()
    (project/'gate.py').write_text('raise SystemExit(1)',encoding='utf-8')
    assert cli('module-change','status',project)['status']=='STALE'
    assert cli('failed-worker','check',project,1)['status']=='FAIL'
    assert old_record.read_bytes()==old_body

    for change in ('seed','delivery','comment'):
        project=science('config-'+change,['gate.py'])
        assert cli(change+'-pass','check',project)['scientific_status']=='PASS'
        if change=='seed':configure(project,seed=999)
        elif change=='delivery':configure(project,delivery={'output_dir':'new-output'})
        else:
            path=project/'.eidos/project.yaml'
            path.write_text(path.read_text(encoding='utf-8')+'\n# new bytes\n',encoding='utf-8')
        assert cli(change+'-change','status',project)['status']=='STALE'

    project=science('undeclared-module',[])
    (project/'gate.py').write_text('from pathlib import Path;Path("executed.txt").touch()',encoding='utf-8')
    assert cli('undeclared-refusal','check',project,4)['status']=='REFUSED'
    assert not (project/'executed.txt').exists()

    project=science('bad-evidence',['gate.py'])
    assert cli('evidence-baseline','check',project)['scientific_status']=='PASS'
    path=project/'data/evidence.json';value=json.loads(path.read_text(encoding='utf-8'))
    value['cross_arm']['separated']=False;path.write_text(json.dumps(value),encoding='utf-8')
    assert cli('evidence-change','status',project)['status']=='STALE'
    assert cli('wrong-science','check',project,1)['scientific_status']=='FAIL'

    record={'schema':'eidos.installed-cli-acceptance.v1','status':'PASS','unreleased':True,
            'sdk_version':args.expected_version,'platform':sys.platform,'python':sys.version,
            'prefix':sys.prefix,'console':str(console),'cases':records,'generated':datetime.now(timezone.utc).isoformat(),
            'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Synthetic installed console controls; not a research lifecycle, generic agent, monitor enrollment, new-machine or RSI qualification'}
    (args.out/'record.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
