"""Disposable, resource-bounded pilot. Run only through framework.run_tree."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import psutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

root=Path.cwd()
profiles={"c0":("c0-sciencersi-v1","a93d0e8e04482b9ed3c7d4b09e40c54c4a52211dfd4d08c084091678af493dab")}
if len(sys.argv)!=4 or sys.argv[1]!='--owned-child' or not __import__('re').fullmatch('[0-9a-f]{32}',sys.argv[2]) or sys.argv[3] not in profiles:
    raise RuntimeError('Use the owned runner; direct launch is refused')
sys.path.insert(0,str(root))
from framework.artifacts import atomic_output

profile_name,expected_protocol=profiles[sys.argv[3]]
folder=root/'.scratch/quality'/profile_name
run_id=sys.argv[2]
claim=folder/'run-claim'
try: claim.mkdir()
except FileExistsError: raise SystemExit('Pilot already claimed; non-owner cannot publish a result')
(claim/'owner.json').write_text(json.dumps({'run_id':run_id,'pid':os.getpid(),
    'started':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
protocol_path=folder/'protocol.json'
protocol_raw=protocol_path.read_bytes()
protocol=json.loads(protocol_raw)
protocol_sha=hashlib.sha256(protocol_raw).hexdigest()
if protocol_sha!=expected_protocol:
    raise RuntimeError('Pilot protocol changed')
if (folder/'result.json').exists(): raise RuntimeError('Previous pilot result must be preserved')
policy=protocol['resource_policy']
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
quiet=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
stop=threading.Event()
samples=[]
resource_errors=[]
sampling_errors=[]
server=None
thread=None
port=None
deadline=time.monotonic()+policy['total_timeout_seconds']
result={'kind':'eidos.c0.sciencersi.development-trial-result','generated':datetime.now(timezone.utc).isoformat(),
        'run_id':run_id,
        'protocol_sha256':protocol_sha,'protocol':protocol,'rows':[],'status':'UNOBSERVED',
        'scientific_authority':False,'promotion':False}
controller_sha=hashlib.sha256(Path(__file__).read_text(encoding='utf-8-sig').encode()).hexdigest()
result['controller_sha256_lf']=controller_sha
continuity=[]

def request(path, body=None, timeout=3):
    data=json.dumps(body).encode() if body is not None else None
    message=urllib.request.Request(path,data=data,headers={'Content-Type':'application/json'})
    with opener.open(message,timeout=timeout) as response: return json.load(response)

def timed_model_request(path, payload, seconds):
    expired=threading.Event()
    finished=threading.Event()
    timer_errors=[]
    def expire():
        if finished.is_set(): return
        expired.set()
        try:
            if server is not None and server.poll() is None: server.terminate()
        except OSError:
            timer_errors.append('Owned request process termination failed')
    timer=threading.Timer(seconds,expire)
    timer.daemon=True
    started=time.monotonic()
    timer.start()
    try:
        response=request(path,payload,seconds)
        if expired.is_set() or time.monotonic()-started>seconds:
            raise TimeoutError('Request wall deadline exceeded')
        return response
    finally:
        finished.set()
        timer.cancel()
        timer.join(timeout=8)
        if timer.is_alive() or timer_errors:
            raise RuntimeError('Request deadline watchdog did not finish cleanly')

def gpu():
    run=subprocess.run([protocol['nvidia_smi'],'--query-gpu=uuid,memory.total,memory.used,memory.free,utilization.gpu',
                        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=quiet)
    if run.returncode!=0: raise RuntimeError('GPU telemetry command failed')
    rows=[line.split(',') for line in run.stdout.splitlines() if line.strip()]
    if len(rows)!=1 or len(rows[0])!=5: raise RuntimeError('Expected exactly one observable GPU')
    identity,total,used,free,utilization=[part.strip() for part in rows[0]]
    values=[float(value) for value in [total,used,free,utilization]]
    if not all(__import__('math').isfinite(value) and value>=0 for value in values):
        raise RuntimeError('Invalid GPU sample')
    return {'ts':datetime.now(timezone.utc).isoformat(),'uuid':identity,
            **dict(zip(['total_mib','used_mib','free_mib','utilization_percent'],values))}

def existing_service(expected=None):
    front=request('http://127.0.0.1:8090/health',timeout=1)
    engine=request('http://127.0.0.1:8081/health',timeout=1)
    models=request('http://127.0.0.1:8081/v1/models',timeout=1)
    if front.get('status')!='ok' or front.get('model')!='StartLux-Decision-v1.1-4B-AutoThink-GGUF' or engine.get('status')!='ok':
        raise RuntimeError('Existing front door or real model engine is unhealthy')
    listeners={row.pid for row in psutil.net_connections(kind='tcp')
               if row.status==psutil.CONN_LISTEN and row.laddr.port==8081 and row.pid}
    if len(listeners)!=1: raise RuntimeError('Existing engine process attribution is ambiguous')
    process=psutil.Process(next(iter(listeners)))
    arguments=process.cmdline()
    paths=[arguments[i+1] for i,arg in enumerate(arguments[:-1]) if arg in {'-m','--model'}]
    if len(paths)!=1: raise RuntimeError('Existing engine model path is unobservable')
    path=str(Path(paths[0]).resolve())
    records=models.get('data',[])
    if len(records)!=1 or str(Path(records[0]['id']).resolve())!=path or Path(path).name!='StartLux-Decision-v1.1-4B-AutoThink-Q8_0.gguf':
        raise RuntimeError('Existing engine model identity differs from its actual process')
    identity={'pid':process.pid,'created':process.create_time(),'executable':process.exe(),
              'model_path':path,'context':records[0].get('meta',{}).get('n_ctx')}
    if expected is not None and identity!=expected: raise RuntimeError('Existing engine process/model changed')
    return identity

def monitor(baseline):
    checked=0.0
    while not stop.is_set():
        try:
            sample=gpu();samples.append(sample)
            if sample['uuid']!=baseline['uuid'] or sample['free_mib']<policy['minimum_free_during_mib'] or sample['used_mib']-baseline['used_mib']>policy['maximum_increment_mib']:
                resource_errors.append('System-wide GPU headroom exceeded; do not attribute this difference solely to the pilot.')
                if server is not None and server.poll() is None: server.terminate()
                return
            if time.monotonic()-checked>=5:
                identity=existing_service(result['existing_service_before'])
                continuity.append({'ts':datetime.now(timezone.utc).isoformat(),'identity':identity,'front_and_engine_healthy':True})
                checked=time.monotonic()
            if time.monotonic()>deadline:
                resource_errors.append('Overall pilot deadline exceeded')
                if server is not None and server.poll() is None: server.terminate()
                return
        except Exception as exc:
            sampling_errors.append(type(exc).__name__+': '+str(exc))
            if server is not None and server.poll() is None: server.terminate()
            return
        stop.wait(0.5)

try:
    baseline=gpu();samples.append(baseline);result['gpu_initial']=baseline
    existing=existing_service()
    result['existing_service_before']=existing
    if baseline['free_mib']<policy['minimum_free_before_mib']:
        result['status']='RESOURCE_BUSY';raise RuntimeError('Insufficient reserved GPU headroom; no model launched')
    for name,expected in protocol['source_sha256_lf'].items():
        if hashlib.sha256((root/name).read_text(encoding='utf-8-sig').encode()).hexdigest()!=expected:
            raise RuntimeError('Locked task source changed')
    with Path(protocol['server']['path']).open('rb') as handle:
        if hashlib.file_digest(handle,'sha256').hexdigest()!=protocol['server']['sha256']:
            raise RuntimeError('Server executable changed')
    model=Path(protocol['model']['path'])
    before_stat=model.stat()
    if before_stat.st_size!=protocol['model']['bytes']: raise RuntimeError('Model size changed')
    with model.open('rb') as handle:
        if hashlib.file_digest(handle,'sha256').hexdigest()!=protocol['model']['sha256']:
            raise RuntimeError('Model bytes changed')
    existing_service(existing)
    fresh=gpu();samples.append(fresh)
    if fresh['uuid']!=baseline['uuid'] or fresh['free_mib']<policy['minimum_free_before_mib']:
        result['status']='RESOURCE_BUSY';raise RuntimeError('Current GPU headroom changed before launch; no model launched')
    baseline=fresh;result['gpu_before']=baseline
    if time.monotonic()>deadline: raise TimeoutError('Pilot deadline reached before launch')
    with socket.socket() as selector:
        selector.bind(('127.0.0.1',0));port=selector.getsockname()[1]
    alias='eidos-c0-sciencersi-'+run_id
    command=[protocol['server']['path'],'-m',str(model),'--host','127.0.0.1','--port',str(port),
             '--alias',alias,'-c',str(policy['context']),'-ngl',str(policy['gpu_layers']),
             '-t',str(policy['threads']),'-tb',str(policy['threads']),'-np','1','-b','256','-ub','128',
             '--no-kv-offload','--no-op-offload','--no-mmproj','--no-webui','--reasoning','off',
             '--reasoning-budget','0','--flash-attn','on']
    environment={key:value for key,value in os.environ.items() if not key.startswith('LLAMA_')}
    environment['CUDA_VISIBLE_DEVICES']='0'
    result['command']=command
    with (folder/'server.log').open('xb') as output:
        server=subprocess.Popen(command,cwd=folder,env=environment,stdin=subprocess.DEVNULL,
            stdout=output,stderr=subprocess.STDOUT,
            creationflags=quiet|(subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0))
        result['owned_server_pid']=server.pid
        thread=threading.Thread(target=monitor,args=(baseline,),daemon=True);thread.start()
        load_started=time.monotonic()
        endpoint=f'http://127.0.0.1:{port}'
        while time.monotonic()-load_started<policy['load_timeout_seconds']:
            if resource_errors or sampling_errors or server.poll() is not None:
                raise RuntimeError('Owned server ended or telemetry/headroom failed during load')
            try:
                health=request(endpoint+'/health',timeout=1)
                if health.get('status')=='ok': break
            except (urllib.error.URLError,TimeoutError): pass
            stop.wait(0.5)
        else: raise TimeoutError('Owned model load deadline exceeded')
        identities=request(endpoint+'/v1/models')
        if alias not in {row.get('id') for row in identities.get('data',[])}:
            raise RuntimeError('Endpoint does not identify the owned model alias')
        result['identity_response']=identities
        result['load_seconds']=time.monotonic()-load_started
        print('OWNED_MODEL_READY',round(result['load_seconds'],2),flush=True)
        payload={'model':alias,'temperature':0,'top_p':0.9,'seed':19,'max_tokens':768,
                 'stream':False,'response_format':{'type':'json_object'},
                 'chat_template_kwargs':{'enable_thinking':False},
                 'messages':[{'role':'user','content':protocol['system']}]}
        started=time.monotonic()
        response=timed_model_request(endpoint+'/v1/chat/completions',payload,policy['request_timeout_seconds'])
        elapsed=time.monotonic()-started
        with atomic_output(folder/'response.json') as temporary:
            temporary.write_text(json.dumps(response,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        result['model_response']=response
        result['request']=payload
        from framework.subprocesses import run_tree
        response_sha=hashlib.sha256((folder/'response.json').read_bytes()).hexdigest()
        evaluated=run_tree([sys.executable,'-I','-X','utf8',str(root/'.scratch/quality/c0_science_evaluate.py'),str(folder),run_id,protocol_sha],
                           cwd=root,timeout=policy['evaluator_timeout_seconds'])
        (folder/'evaluation.log').write_text(evaluated.stdout+evaluated.stderr,encoding='utf-8')
        if evaluated.returncode!=0: raise RuntimeError('Evaluator process failed')
        core=json.loads((folder/'core-result.json').read_text(encoding='utf-8'))
        if (core.get('recorded_response_sha256')!=response_sha or core.get('run_id')!=run_id
                or core.get('protocol_sha256')!=protocol_sha):
            raise RuntimeError('Evaluator response/run/protocol binding differs')
        if core['status'] not in {'DEVELOPMENT_CONFORMING','DEVELOPMENT_NONCONFORMING','INVALID_RESPONSE'}:
            raise RuntimeError('Evaluator did not produce an admissible development verdict')
        result['core']=core
        result['rows'].append({'id':'c0-log1mexp','correct':core['status']=='DEVELOPMENT_CONFORMING',
                               'core_status':core['status'],'seconds':elapsed})
        result['actual_model_inference']=True
        print('C0_RESPONSE',core['status'],round(elapsed,2),flush=True)
        if time.monotonic()>deadline: raise TimeoutError('Last response exceeded the pilot deadline')
        result['status']='COMPLETE'
except BaseException as exc:
    result['error']=type(exc).__name__+': '+str(exc)
    if result['status']!='RESOURCE_BUSY': result['status']='ABORTED_RESOURCE' if resource_errors or sampling_errors else 'INCOMPLETE'
finally:
    stop.set()
    if server is not None and server.poll() is None:
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill();server.wait(timeout=3)
    if thread is not None: thread.join(timeout=12)
    result['monitor_stopped']=thread is None or not thread.is_alive()
    if thread is not None and thread.is_alive(): result['status']='INCOMPLETE_MONITOR'
    if (resource_errors or sampling_errors) and result['status']=='COMPLETE': result['status']='ABORTED_RESOURCE'
    result['resource_errors']=resource_errors;result['sampling_errors']=sampling_errors
    result['gpu_samples']=samples
    result['existing_service_continuity']=continuity
    result['correct']=sum(row['correct'] for row in result['rows'])
    result['completed_cases']=len(result['rows'])
    result['owned_server_exit_code']=server.poll() if server is not None else None
    try:
        result['existing_service_after']=existing_service(result.get('existing_service_before'))
        result['existing_service_preserved']='existing_service_before' in result and result['existing_service_after']==result['existing_service_before']
    except Exception as exc: result['existing_service_preserved']=False;result['existing_service_error']=str(exc)
    if not result['existing_service_preserved'] and result['status']=='COMPLETE': result['status']='INCOMPLETE_SERVICE_REGRESSION'
    if protocol_path.read_bytes()!=protocol_raw: result['status']='INPUT_CHANGED'
    if hashlib.sha256(Path(__file__).read_text(encoding='utf-8-sig').encode()).hexdigest()!=controller_sha:
        result['status']='INPUT_CHANGED'
    for name,expected in protocol['source_sha256_lf'].items():
        if hashlib.sha256((root/name).read_text(encoding='utf-8-sig').encode()).hexdigest()!=expected:
            result['status']='INPUT_CHANGED'
    if 'model' in globals():
        with model.open('rb') as handle: result['model_sha256_after']=hashlib.file_digest(handle,'sha256').hexdigest()
        if result['model_sha256_after']!=protocol['model']['sha256']: result['status']='INPUT_CHANGED'
    if time.monotonic()>deadline and result['status']=='COMPLETE': result['status']='INCOMPLETE_DEADLINE'
    if (resource_errors or sampling_errors) and result['status']=='COMPLETE': result['status']='ABORTED_RESOURCE'
    result['finished']=datetime.now(timezone.utc).isoformat()
    with atomic_output(folder/'result.json') as temporary:
        temporary.write_bytes((json.dumps(result,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps({'status':result['status'],'correct':result['correct'],'cases':result['completed_cases'],
                      'existing_service_preserved':result['existing_service_preserved'],'promotion':False}),flush=True)
raise SystemExit(0 if result['status']=='COMPLETE' else 1)
