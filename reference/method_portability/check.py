"""Standalone stdlib harness for a fresh, offline Linux numerical-method replay.

The caller supplies a pinned public Python image and an out-of-band input hash.
This script never downloads anything and never runs a language model.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import ntpath
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

IMAGE = 'public.ecr.aws/docker/library/python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337'
TARGET = {'python': '3.12.16', 'numpy': '2.5.4', 'os': 'linux', 'architecture': 'x86_64'}
RESPONSE = 'reference/rsi_bootstrap/recorded_trials/rsi-retrieval-feedback-v1/retrieval-feedback-1/response.json'
RESPONSE_SHA = '173cbf478e059a16fb9fe8ed2b5f4ba5213b4f034240c47b6c9154e10999e13a'
PROFILE = 'method-offline-cp312-linux-amd64-v1'
SHA = re.compile('[a-f0-9]{64}')
TMPFS='rw,exec,nosuid,nodev,size=1073741824,mode=1777'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()


def same(left,right) -> bool:
    return json.dumps(left,sort_keys=True,allow_nan=False)==json.dumps(right,sort_keys=True,allow_nan=False)


def strict_json(raw: bytes):
    if len(raw) > 131072:
        raise ValueError('Protocol JSON exceeds 128 KiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate protocol field')
            result[key] = value
        return result
    def forbidden(_):
        raise ValueError('Nonfinite protocol number')
    def number(value):
        result = float(value)
        if not math.isfinite(result): raise ValueError('Overflowing protocol number')
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=forbidden, parse_float=number)
    except RecursionError as error:
        raise ValueError('Excessive protocol nesting') from error


def safe_relative(name: str) -> str:
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or PurePosixPath(name).as_posix() != name
            or any(part in {'', '.', '..'} for part in name.split('/'))):
        raise ValueError('Unsafe or noncanonical relative path')
    return name


def inventory(folder: Path) -> set[str]:
    files = set()
    for path in folder.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('Only regular artifact files/directories are allowed')
        if path.is_file(): files.add(path.relative_to(folder).as_posix())
    return files


def assert_owned(item: dict, cid: str, owner: str):
    if (not isinstance(cid,str) or not SHA.fullmatch(cid) or not isinstance(owner,str)
            or not re.fullmatch('[a-f0-9]{32}',owner)
            or item.get('Id')!=cid or item.get('Name')!='/eidos-method-offline-'+owner[:16]
            or item.get('Config',{}).get('Labels',{}).get('eidos.owner')!=owner):
        raise ValueError('Container identity is not owned by this attempt')


def validate_image(image: dict) -> str:
    """Registry manifest identity and local image/config identity are distinct."""
    image_id=image.get('Id')
    if (not isinstance(image_id,str) or not re.fullmatch('sha256:[a-f0-9]{64}',image_id)
            or IMAGE not in image.get('RepoDigests',[]) or image.get('Os')!='linux'
            or image.get('Architecture')!='amd64' or image.get('Config',{}).get('Entrypoint') not in (None,[])
            or 'PYTHON_VERSION='+TARGET['python'] not in image.get('Config',{}).get('Env',[])):
        raise ValueError('Public image reference/platform/runtime differs')
    return image_id


def validate_container(item: dict, cid: str, owner: str, expected: str, input_path: Path, output_path: Path, image_id: str):
    assert_owned(item,cid,owner)
    host=item['HostConfig'];config=item['Config']
    if (not isinstance(image_id,str) or not re.fullmatch('sha256:[a-f0-9]{64}',image_id)
            or item.get('Image')!=image_id or config.get('Image')!=IMAGE
            or config.get('Labels',{}).get('eidos.input-sha256')!=expected
            or config.get('Cmd')!=['python','-I','/input/check.py','--input','/input','--sha256',expected,'--output','/out']
            or host.get('NetworkMode')!='none' or host.get('ReadonlyRootfs') is not True
            or host.get('Privileged') is not False or host.get('Memory')!=2147483648
            or host.get('NanoCpus')!=2000000000 or host.get('PidsLimit')!=128 or host.get('Init') is not True
            or host.get('CapDrop')!=['ALL'] or host.get('CapAdd') not in (None,[])
            or host.get('SecurityOpt') not in (['no-new-privileges'],['no-new-privileges=true'])
            or host.get('Tmpfs')!={'/tmp':TMPFS}):
        raise ValueError('Container image, command or isolation settings differ')
    mounts=item['Mounts']
    if len(mounts)!=2:raise ValueError('Unexpected container mounts')
    mapped={mount['Destination']:mount for mount in mounts}
    if set(mapped)!={'/input','/out'}:raise ValueError('Input/output mounts differ')
    for destination,path,writable in (('/input',input_path,False),('/out',output_path,True)):
        mount=mapped[destination]
        observed=mount['Source'].replace('\\','/');declared=str(path).replace('\\','/')
        if re.match('[A-Za-z]:/',declared): observed,declared=ntpath.normcase(observed),ntpath.normcase(declared)
        if mount['Type']!='bind' or mount['RW'] is not writable or observed!=declared:
            raise ValueError('Container mount source/access differs')


def source_payloads(raw: bytes, files: dict) -> dict:
    if len(raw) > 8*1024*1024: raise ValueError('Source ZIP exceeds limit')
    pending = {}
    folded = set()
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.infolist()) > 64: raise ValueError('Too many source files')
        for info in archive.infolist():
            name = safe_relative(info.filename)
            kind = stat.S_IFMT(info.external_attr >> 16)
            if (info.is_dir() or kind not in (0, stat.S_IFREG) or info.flag_bits & 1
                    or name.casefold() in folded or info.file_size > 2*1024*1024):
                raise ValueError('Nonregular, duplicate or oversized archive member')
            folded.add(name.casefold())
            with archive.open(info) as stream: data = stream.read(2*1024*1024+1)
            total += len(data)
            if (len(data) != info.file_size or total > 8*1024*1024
                    or name not in files or sha(data) != files[name]):
                raise ValueError('Archive member does not match the manifest')
            pending[name] = data
    if set(pending) != set(files): raise ValueError('Source archive inventory differs')
    return pending


def extract_sources(raw: bytes, files: dict, destination: Path):
    if destination.exists(): raise FileExistsError('Source destination already exists')
    pending=source_payloads(raw,files)
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in pending.items():
        path = destination/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(data)


def read_input(folder: Path, expected: str) -> dict:
    if not isinstance(expected, str) or not SHA.fullmatch(expected): raise ValueError('Input pin is required')
    raw = (folder/'input.json').read_bytes()
    if sha(raw) != expected: raise ValueError('Input descriptor changed')
    value = strict_json(raw)
    fields = {'schema','profile','run_id','image','target','wheel','sources','files','response_path',
              'response_sha256','source_zip_sha256','source_zip_size','harness_sha256','requirements_sha256',
              'new_model_inference'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['schema'] != 'eidos.method-offline-input.v1' or value['profile'] != PROFILE
            or value['image'] != IMAGE or value['target'] != TARGET
            or value['new_model_inference'] is not False
            or not isinstance(value['run_id'], str) or not re.fullmatch('[a-f0-9]{32}',value['run_id'])
            or value['response_path'] != RESPONSE or value['response_sha256'] != RESPONSE_SHA):
        raise ValueError('Unsupported input schema/profile')
    wheel = value['wheel']
    if (not isinstance(wheel, dict) or set(wheel) != {'version','filename','url','sha256','size'}
            or wheel['version'] != TARGET['numpy'] or not isinstance(wheel['filename'], str)
            or not re.fullmatch(r'numpy-2\.5\.4-cp312-cp312-manylinux_[a-zA-Z0-9_.]+x86_64\.whl',wheel['filename'])
            or type(wheel['size']) is not int or not 1 <= wheel['size'] <= 64*1024*1024
            or not isinstance(wheel['sha256'], str) or not SHA.fullmatch(wheel['sha256'])):
        raise ValueError('Unsupported wheel descriptor')
    for key in ('sources','files'):
        table = value[key]
        if not isinstance(table, dict) or not 1 <= len(table) <= 64: raise ValueError('Invalid source inventory')
        for name,digest in table.items():
            safe_relative(name)
            if not isinstance(digest,str) or not SHA.fullmatch(digest): raise ValueError('Invalid source hash')
    if (RESPONSE in value['sources'] or value['files'] != {**value['sources'], RESPONSE: RESPONSE_SHA}
            or 'uv.lock' not in value['sources']): raise ValueError('Source/response identities differ')
    required = f"numpy=={wheel['version']} --hash=sha256:{wheel['sha256']}\n".encode()
    expected_files = {'input.json','source.zip','requirements.txt','check.py','wheels/'+wheel['filename']}
    if inventory(folder) != expected_files: raise ValueError('Input file inventory differs')
    if (hash_file(folder/'source.zip') != value['source_zip_sha256']
            or (folder/'source.zip').stat().st_size != value['source_zip_size']
            or (folder/'requirements.txt').read_bytes() != required
            or sha(required) != value['requirements_sha256']
            or hash_file(folder/'check.py') != value['harness_sha256']
            or hash_file(Path(__file__).resolve()) != value['harness_sha256']
            or hash_file(folder/'wheels'/wheel['filename']) != wheel['sha256']
            or (folder/'wheels'/wheel['filename']).stat().st_size != wheel['size']):
        raise ValueError('Input payload differs from its frozen descriptor')
    return value


ENTRY = '''import importlib.metadata,json,platform,sys
from pathlib import Path
source=Path(sys.argv[1]);manifest=json.loads(Path(sys.argv[2]).read_bytes());mode=sys.argv[3]
sys.path.insert(0,str(source))
from reference.numerical_method_tools import runner
if runner.source_snapshot()!=manifest["sources"]:raise ValueError("Curated source closure differs")
if mode=="environment":
 print(json.dumps({"python":platform.python_version(),"numpy":runner.np.__version__,"executable":sys.executable,"prefix":sys.prefix,"base_prefix":sys.base_prefix,"user_site_enabled":__import__("site").ENABLE_USER_SITE,"distributions":sorted([{"name":d.metadata["Name"].lower(),"version":d.version} for d in importlib.metadata.distributions()],key=lambda d:d["name"])}))
elif mode=="bind":
 record=runner.verify(Path(sys.argv[4]))
 print(json.dumps({"run_id":record["run_id"],"record_sha256":runner.sha(runner.encoded(record)),"files":record["files"],"source_sha256":record["source_sha256"],"response_sha256":record["response_sha256"],"proposal":record["proposal"],"tool":record["tool"]}))
else:
 sys.argv=["numerical-method-tool"]+sys.argv[4:]
 raise SystemExit(runner.main())
'''


def validate_execution(output: Path, manifest: dict, binding: dict) -> dict:
    """Check artifacts against the fresh reader's captured, verified identities."""
    expected_proposal={'status':'DEVELOPMENT_NONCONFORMING','points_evaluated':23,'joint_points':0,'accepted':False}
    expected_tool={'status':'DEVELOPMENT_CONFORMING','points_evaluated':23,'joint_points':23,'accepted':True}
    record_raw=(output/'record.json').read_bytes();record=strict_json(record_raw)
    if (sha(record_raw)!=binding['record_sha256'] or record['run_id']!=binding['run_id']
            or record['source_sha256']!=manifest['sources'] or binding['source_sha256']!=manifest['sources']
            or record['files']!=binding['files'] or record['response_sha256']!=RESPONSE_SHA
            or binding['response_sha256']!=RESPONSE_SHA or record['method_id']!='log1mexp-v1'
            or record['new_model_inference'] is not False or record['scientific_promotion'] is not False
            or record['scientific_rsi']!='NOT_DEMONSTRATED' or record['sealed_evaluation']!='NOT_RUN'):
        raise ValueError('Reader binding and execution identity disagree')
    for key,expected_value in (('proposal',expected_proposal),('tool',expected_tool)):
        if (json.dumps(record[key],sort_keys=True)!=json.dumps(expected_value,sort_keys=True)
                or json.dumps(binding[key],sort_keys=True)!=json.dumps(expected_value,sort_keys=True)):
            raise ValueError('Actual outcomes disagree with the declared comparison')
    for name,digest in binding['files'].items():
        safe_relative(name)
        if not isinstance(digest,str) or not SHA.fullmatch(digest): raise ValueError('Invalid reader artifact pin')
        if hash_file(output/name)!=digest: raise ValueError('Execution artifact changed after reader verification')
    if inventory(output)!=set(binding['files'])|{'record.json'}:
        raise ValueError('Execution artifact inventory differs')
    return record


def run(folder: Path, expected: str, output: Path) -> dict:
    begun = time.perf_counter()
    if sys.platform!='linux': raise ValueError('This worker requires the declared Linux container')
    if not output.is_dir() or any(output.iterdir()): raise ValueError('Output mount must be an existing empty directory')
    result = {'schema':'eidos.method-offline-result.v1','status':'RUNNING','runtime_accepted':False,
              'input_sha256':expected,'steps':[],'new_model_inference':False,
              'scientific_promotion':False,'scientific_rsi':'NOT_DEMONSTRATED','sealed_evaluation':'NOT_RUN'}
    def progress(): (output/'progress.json').write_bytes(encoded(result))
    progress()
    def deadline(_signal,_frame): raise TimeoutError('Whole harness deadline exceeded')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(180)
    try:
        manifest = read_input(folder,expected)
        if (sys.platform != 'linux' or platform.machine() != 'x86_64'
                or platform.python_version() != TARGET['python']): raise ValueError('Image runtime differs from target')
        result['input_run_id']=manifest['run_id'];result['source_sha256']=manifest['sources']
        with socket.socket() as probe:
            probe.settimeout(.3)
            try: probe.connect(('1.1.1.1',443))
            except OSError as error: result['network_probe']={'connected':False,'error_type':type(error).__name__,'errno':error.errno}
            else: raise ValueError('Outbound network unexpectedly reachable')
        work=Path(tempfile.mkdtemp(prefix='eidos-method-'))
        source=work/'source';extract_sources((folder/'source.zip').read_bytes(),manifest['files'],source)
        entry=work/'entry.py';entry.write_text(ENTRY,encoding='utf-8')
        environment={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(work/'home'),'LANG':'C.UTF-8',
                     'LC_ALL':'C.UTF-8','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1',
                     'PIP_CONFIG_FILE':'/dev/null','PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1'}
        (work/'home').mkdir()
        result['child_environment']=environment;result['entry_sha256']=sha(ENTRY.encode())
        def step(name,command,limit,expected_code=0):
            row={'name':name,'command':command,'status':'RUNNING','expected_exit_code':expected_code}
            result['steps'].append(row);progress();started=time.perf_counter()
            try:
                child=subprocess.run(command,cwd=source,env=environment,capture_output=True,timeout=limit)
                (output/(name+'.stdout.log')).write_bytes(child.stdout)
                (output/(name+'.stderr.log')).write_bytes(child.stderr)
                row.update(exit_code=child.returncode,wall_seconds=time.perf_counter()-started,
                           stdout_sha256=sha(child.stdout),stderr_sha256=sha(child.stderr))
                if child.returncode!=expected_code: raise ValueError('Unexpected exit: '+name)
                row['status']='COMPLETE';progress();return child.stdout
            except Exception as error:
                if isinstance(error,subprocess.TimeoutExpired):
                    for channel in ('stdout','stderr'):
                        partial=getattr(error,channel) or b''
                        (output/(name+'.'+channel+'.log')).write_bytes(partial)
                    row['exit_code']=None
                row.update(status='ERROR',wall_seconds=time.perf_counter()-started,error_type=type(error).__name__)
                progress();raise
        venv=work/'venv'
        step('venv',[sys.executable,'-I','-m','venv',str(venv)],30)
        python=str(venv/'bin/python')
        step('install',[python,'-I','-m','pip','--isolated','--disable-pip-version-check','install',
                        '--no-index','--no-deps','--require-hashes','--no-cache-dir','--only-binary',':all:',
                        '--find-links',str(folder/'wheels'),'-r',str(folder/'requirements.txt')],60)
        prefix=[python,'-I','-B',str(entry),str(source),str(folder/'input.json')]
        installed=strict_json(step('environment',prefix+['environment'],30))
        if (installed['python']!=TARGET['python'] or installed['numpy']!=TARGET['numpy']
                or installed['prefix']==installed['base_prefix'] or installed['user_site_enabled'] is not False
                or [d['name'] for d in installed['distributions']]!=['numpy','pip']):
            raise ValueError('Fresh venv has unexpected dependencies or identity')
        result['environment']=installed
        arguments=['--response',str(source/RESPONSE),'--method','log1mexp-v1']
        step('wrong-pin',prefix+['execute']+arguments+['--sha256','0'*64,'--output',str(output/'rejected')],30,1)
        if (output/'rejected').exists(): raise ValueError('Wrong pin published an output')
        produced=strict_json(step('execute',prefix+['execute']+arguments+['--sha256',RESPONSE_SHA,'--output',str(output/'execution')],30))
        verified=strict_json(step('verify',prefix+['verify','--verify',str(output/'execution')],30))
        if produced!=verified: raise ValueError('Fresh reader output differs')
        binding=strict_json(step('bind',prefix+['bind',str(output/'execution')],30))
        record=validate_execution(output/'execution',manifest,binding)
        expected_cli={'run_id':record['run_id'],'proposal':record['proposal'],'tool':record['tool'],
                      'new_model_inference':False,'scientific_rsi':'NOT_DEMONSTRATED'}
        if not same(produced,expected_cli) or not same(verified,expected_cli):
            raise ValueError('CLI/reader output contradicts the actual execution')
        read_input(folder,expected)
        if {n:hash_file(source/n) for n in manifest['files']}!=manifest['files']:
            raise ValueError('Extracted source/input changed during execution')
        result.update(status='COMPLETE',runtime_accepted=True,proposal=record['proposal'],tool=record['tool'],
                      execution_run_id=record['run_id'],execution_record_sha256=binding['record_sha256'],reader_binding=binding)
    except Exception as error:
        result.update(status='ERROR',error_type=type(error).__name__,error=str(error),runtime_accepted=False)
    result['wall_seconds']=time.perf_counter()-begun
    progress()
    if result['runtime_accepted']:
        validate_execution(output/'execution',manifest,binding)
        read_input(folder,expected)
        for row in result['steps']:
            if row['status']!='COMPLETE': raise ValueError('Incomplete command cannot publish acceptance')
            for channel in ('stdout','stderr'):
                if hash_file(output/(row['name']+'.'+channel+'.log'))!=row[channel+'_sha256']:
                    raise ValueError('Command log changed after capture')
        expected_outputs={'progress.json'}|{'execution/'+name for name in binding['files']}|{'execution/record.json'}
        expected_outputs|={row['name']+'.'+channel+'.log' for row in result['steps'] for channel in ('stdout','stderr')}
        if inventory(output)!=expected_outputs: raise ValueError('Unexpected output file cannot enter acceptance')
    result['files']={name:hash_file(output/name) for name in sorted(inventory(output))}
    with (output/'linux-result.json').open('xb') as stream:stream.write(encoded(result))
    signal.alarm(0)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.input.resolve(strict=True),args.sha256,args.output.resolve(strict=True))
    print(json.dumps({key:result.get(key) for key in ('status','runtime_accepted','execution_run_id','error_type')}))
    return 0 if result['runtime_accepted'] else 1


if __name__=='__main__': raise SystemExit(main())
