import json
from pathlib import Path
import sys
import subprocess
import uuid

root=Path.cwd()
sys.path.insert(0,str(root))
from framework.subprocesses import run_tree
from framework.artifacts import atomic_output

profiles={'c0':'c0-qwen27b-v2'}
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
expected_controller="0393dc9cfe4b40db02ad9135654744861e00aaf8b83388de74791e6366578819"
import hashlib
if hashlib.sha256((root/'.scratch/quality/c0_qwen27b_v2_controller.py').read_bytes()).hexdigest()!=expected_controller: raise RuntimeError('Controller changed before launch')
profile_protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
proof_folder=root/'.scratch/quality/c0-decoder-probe-v2'
proof_raw=(proof_folder/'result.json').read_bytes()
if hashlib.sha256(proof_raw).hexdigest()!=profile_protocol['backend_proof']['result_sha256']:
    raise RuntimeError('Frozen backend proof differs')
proof=json.loads(proof_raw)
if proof['protocol_sha256']!=profile_protocol['backend_proof']['protocol_sha256'] or proof['correct']!=3 or not all(row['correct'] is True for row in proof['rows']):
    raise RuntimeError('Backend controls do not qualify this profile')
command=[sys.executable,'-I','-X','utf8',str(root/'.scratch/quality/c0_qwen27b_v2_controller.py'),'--owned-child',run_id,profile]
try:
    run=run_tree(command,cwd=root,timeout=960)
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
accepted=(result.get('decoder_contract_passed') is True and result.get('template_control',{}).get('passed') is True and run.returncode==0 and result['status']=='COMPLETE' and result['monitor_stopped'] is True
          and result['existing_service_preserved'] is True and not result['resource_errors'] and not result['sampling_errors']
          and [row['id'] for row in result['rows']]==[row['id'] for row in protocol['cases']]
          and result['owned_server_exit_code'] is not None
          and result['model_sha256_after']==protocol['model']['sha256'])
record={'status':'COMPLETE' if accepted else result['status'] if result['status']!='COMPLETE' else 'NOT_ACCEPTED','accepted':accepted,'run_id':run_id,'exit_code':run.returncode,'development_conforming':result['correct']==1,'correct':result['correct'],
                  'cases':result['completed_cases'],'existing_service_preserved':result['existing_service_preserved'],
                  'promotion':False}
admit(record);print(json.dumps(record))
raise SystemExit(0 if accepted else 1)
