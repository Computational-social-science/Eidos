from pathlib import Path
import sys,json,hashlib
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from reference.rsi_bootstrap import c0
from framework.artifacts import atomic_output
folder=Path(sys.argv[1]).resolve()
if folder != root/'.scratch/quality/c0-sciencersi-v2': raise RuntimeError('Unexpected trial')
run_id,expected_protocol=sys.argv[2:4]
owner=json.loads((folder/'run-claim/owner.json').read_text(encoding='utf-8'))
if owner['run_id']!=run_id: raise RuntimeError('Evaluator is not the trial owner')
protocol_raw=(folder/'protocol.json').read_bytes()
if hashlib.sha256(protocol_raw).hexdigest()!=expected_protocol: raise RuntimeError('Protocol changed')
response_raw=(folder/'response.json').read_bytes()
raw=json.loads(response_raw)
for module in (c0,c0.grader,c0.expressions):
    if Path(module.__file__).resolve().parent != root/'reference/rsi_bootstrap':
        raise RuntimeError('Loaded numerical source is outside the frozen project')
if c0.PROMPT != json.loads(protocol_raw)['system']: raise RuntimeError('Prompt differs')
content=raw['choices'][0]['message'].get('content') or ''
result=c0.run_once(lambda prompt:content)
result['run_id']=run_id
result['recorded_response_sha256']=hashlib.sha256(response_raw).hexdigest()
result['protocol_sha256']=expected_protocol
if (folder/'response.json').read_bytes()!=response_raw or (folder/'protocol.json').read_bytes()!=protocol_raw:
    result.update(status='INPUT_CHANGED',retained_for_development=False)
result['transport_scope']='Replay of one recorded real-model response; outer controller attests inference separately'
with atomic_output(folder/'core-result.json') as temporary:
    temporary.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'conforming':result.get('candidate_conforming_points')}))
