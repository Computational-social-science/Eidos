"""Prepare an explicit, pinned input bundle; never download or launch Docker."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import urlsplit
import uuid
import zipfile

from packaging.markers import Marker

from . import check
from reference.numerical_method_tools import runner

ROOT=Path(__file__).resolve().parents[2]


def select_wheel(lock: Path) -> dict:
    value=tomllib.loads(Path(lock).read_text(encoding='utf-8'))
    target={'implementation_name':'cpython','implementation_version':check.TARGET['python'],
            'os_name':'posix','platform_machine':'x86_64','platform_release':'','platform_system':'Linux',
            'platform_version':'','python_full_version':check.TARGET['python'],'platform_python_implementation':'CPython',
            'python_version':'3.12','sys_platform':'linux','extra':''}
    packages=[]
    for package in value['package']:
        if package['name']=='numpy' and (not package.get('resolution-markers')
                or any(Marker(marker).evaluate(environment=target) for marker in package['resolution-markers'])):
            packages.append(package)
    if len(packages)!=1 or packages[0]['version']!=check.TARGET['numpy']:
        raise ValueError('Lock resolution differs from this explicit target profile')
    candidates=[]
    for wheel in packages[0]['wheels']:
        parsed=urlsplit(wheel['url']);name=Path(parsed.path).name
        if '-cp312-cp312-manylinux_' in name and name.endswith('x86_64.whl'):
            if (parsed.scheme!='https' or parsed.hostname!='files.pythonhosted.org'
                    or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
                    or not re.fullmatch('sha256:[a-f0-9]{64}',wheel['hash'])
                    or type(wheel['size']) is not int or not 1<=wheel['size']<=64*1024*1024):
                raise ValueError('Wheel source/hash/size is not qualified')
            candidates.append({'version':packages[0]['version'],'filename':name,'url':wheel['url'],
                               'sha256':wheel['hash'].split(':',1)[1],'size':wheel['size']})
    if len(candidates)!=1: raise ValueError('Target wheel is missing or ambiguous')
    return candidates[0]


def run(wheel_path: Path, output: Path) -> dict:
    output=Path(output).resolve()
    if output.exists(): raise FileExistsError('Input destination must be new')
    sources=runner.source_snapshot()
    wheel=select_wheel(ROOT/'uv.lock')
    wheel_path=Path(wheel_path).resolve(strict=True)
    if (not wheel_path.is_file() or wheel_path.name!=wheel['filename']
            or wheel_path.stat().st_size!=wheel['size'] or check.hash_file(wheel_path)!=wheel['sha256']):
        raise ValueError('Provided wheel differs from the target lock pin')
    files={**sources,check.RESPONSE:check.RESPONSE_SHA}
    payloads={}
    source_data={}
    for name,digest in files.items():
        check.safe_relative(name);path=ROOT/name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(ROOT): raise ValueError('Source escapes project')
        data=path.read_bytes()
        if check.sha(data)!=digest: raise ValueError('Source/response changed')
        source_data[name]=data
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(source_data.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    payloads['source.zip']=stream.getvalue()
    check.source_payloads(payloads['source.zip'],files)
    payloads['requirements.txt']=f"numpy=={wheel['version']} --hash=sha256:{wheel['sha256']}\n".encode()
    payloads['check.py']=Path(check.__file__).read_bytes()
    payloads['wheels/'+wheel['filename']]=wheel_path.read_bytes()
    if (len(payloads['wheels/'+wheel['filename']])!=wheel['size']
            or check.sha(payloads['wheels/'+wheel['filename']])!=wheel['sha256']):
        raise ValueError('Provided wheel changed during preparation')
    manifest={'schema':'eidos.method-offline-input.v1','profile':check.PROFILE,'run_id':uuid.uuid4().hex,
              'image':check.IMAGE,'target':check.TARGET,'wheel':wheel,'sources':sources,'files':files,
              'response_path':check.RESPONSE,'response_sha256':check.RESPONSE_SHA,'new_model_inference':False,
              'source_zip_sha256':check.sha(payloads['source.zip']),'source_zip_size':len(payloads['source.zip']),
              'harness_sha256':check.sha(payloads['check.py']),'requirements_sha256':check.sha(payloads['requirements.txt'])}
    if sources!=runner.source_snapshot(): raise ValueError('Source changed during preparation')
    output.mkdir(parents=True,exist_ok=False)
    for name,data in payloads.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as file:file.write(data)
    if (sources!=runner.source_snapshot()
            or Path(check.__file__).read_bytes()!=payloads['check.py']
            or any((output/name).read_bytes()!=data for name,data in payloads.items())):
        raise ValueError('Published inputs changed; no terminal manifest is written')
    with (output/'input.json').open('xb') as file:file.write(check.encoded(manifest))
    check.read_input(output,check.sha((output/'input.json').read_bytes()))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--wheel-info',action='store_true')
    args=parser.parse_args()
    try:
        if args.wheel_info:
            if args.wheel or args.output: raise ValueError('Wheel info is a separate command')
            print(json.dumps(select_wheel(ROOT/'uv.lock')));return 0
        if args.wheel is None or args.output is None: raise ValueError('Explicit wheel and new output are required')
        result=run(args.wheel,args.output)
        print(json.dumps({'run_id':result['run_id'],'input_sha256':check.hash_file(args.output/'input.json'),
                          'image':result['image'],'new_model_inference':False}));return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(1,f'Offline preparation refused: {error}\n')


if __name__=='__main__':raise SystemExit(main())
