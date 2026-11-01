import json
from pathlib import Path
import sys
import subprocess
import uuid

root=Path.cwd()
sys.path.insert(0,str(root))
from framework.subprocesses import run_tree
from framework.artifacts import atomic_output

profiles={'c0':'c0-decoder-probe-v1'}
if len(sys.argv) not in {1,2}: raise RuntimeError('Unexpected pilot arguments')
profile=sys.argv[1] if len(sys.argv)==2 else 'c0'
if profile not in profiles: raise RuntimeError('Unknown preregistered pilot profile')
folder=root/'.scratch/quality'/profiles[profile]
run_id=uuid.uuid4().hex
def admit(record):
    with atomic_output(folder/('launcher-'+run_id+'.json')) as temporary:
        temporary.write_bytes((json.dumps(record,indent=2)+'\n').encode())
    owner=folder/'run-claim/owner.json'
    if owner.is_file() and json.loads(owner.read_text(encoding='utf-8')).get('run_id')==run_id:
        with atomic_output(folder/'outcome.json') as temporary:
            temporary.write_bytes((json.dumps(record,indent=2)+'\n').encode())
expected_controller="e9aee50943d5689374b817ef8af95953a524341b328247576d5156f05528328b"
import hashlib
if hashlib.sha256((root/'.scratch/quality/decoder_probe_controller.py').read_bytes()).hexdigest()!=expected_controller: raise RuntimeError('Controller changed before launch')
command=[sys.executable,'-I','-X','utf8',str(root/'.scratch/quality/decoder_probe_controller.py'),'--owned-child',run_id,profile]
try:
    run=run_tree(command,cwd=root,timeout=510)
except subprocess.TimeoutExpired:
    record={'status':'OUTER_TIMEOUT','run_id':run_id,'scope':'Owned runner timed out after process-tree cleanup; no model qualification.'}
    admit(record)
    print(json.dumps(record));raise SystemExit(1)
(folder/('controller-'+run_id+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
if not (folder/'result.json').is_file():
    record={'status':'NO_RESULT','run_id':run_id,'exit_code':run.returncode};admit(record)
    print(json.dumps(record));raise SystemExit(1)
result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
if result.get('run_id')!=run_id:
    record={'status':'NOT_OWNER','run_id':run_id,'exit_code':run.returncode};admit(record)
    print(json.dumps(record));raise SystemExit(1)
protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
accepted=(run.returncode==0 and result['status']=='COMPLETE' and result['monitor_stopped'] is True
          and result['correct']==len(protocol['cases'])
          and result['existing_service_preserved'] is True and not result['resource_errors'] and not result['sampling_errors']
          and [row['id'] for row in result['rows']]==[row['id'] for row in protocol['cases']]
          and result['owned_server_exit_code'] is not None
          and result['model_sha256_after']==protocol['model']['sha256'])
record={'status':'COMPLETE' if accepted else result['status'] if result['status']!='COMPLETE' else 'NOT_ACCEPTED','accepted':accepted,'run_id':run_id,'exit_code':run.returncode,'decoder_controls_passed':result['correct']==len(protocol['cases']),'correct':result['correct'],
                  'cases':result['completed_cases'],'existing_service_preserved':result['existing_service_preserved'],
                  'promotion':False}
admit(record);print(json.dumps(record))
raise SystemExit(0 if accepted else 1)
