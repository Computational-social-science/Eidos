"""Offline protocol controls; Docker and model services are not called here."""
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import shutil
import zipfile

import pytest

from reference.method_portability import check, prepare


def test_lock_resolution_selects_linux312_not_older_same_tag():
    wheel = prepare.select_wheel(prepare.ROOT/'uv.lock')
    assert wheel['version'] == '2.5.4'
    assert '-cp312-cp312-manylinux_' in wheel['filename']
    assert wheel['filename'].endswith('x86_64.whl')
    assert wheel['sha256'] == 'fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a'


@pytest.mark.parametrize('name', ['', '../bad', '/tmp/x', 'C:/x', 'a\\b', 'a//b', './a', 'a/../b', 'a/.', 'a\x00b'])
def test_unsafe_relative_path(name):
    with pytest.raises(ValueError): check.safe_relative(name)


def zipped(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in entries: archive.writestr(name, data)
    return buffer.getvalue()


def test_extract_verified_sources_only(tmp_path):
    raw = zipped([('folder/a.py', b'trusted source')])
    files = {'folder/a.py': check.sha(b'trusted source')}
    check.extract_sources(raw, files, tmp_path/'source')
    assert (tmp_path/'source/folder/a.py').read_bytes() == b'trusted source'
    with pytest.raises(FileExistsError): check.extract_sources(raw, files, tmp_path/'source')


@pytest.mark.parametrize('kind', ['traversal','duplicate','symlink','unlisted','hash','missing'])
def test_bad_archive_refused_before_writing(tmp_path, kind):
    files = {'a.py': check.sha(b'one')}
    if kind == 'traversal': raw = zipped([('../a.py', b'one')])
    elif kind == 'duplicate':
        with pytest.warns(UserWarning,match='Duplicate name'):raw = zipped([('a.py', b'one'), ('a.py', b'one')])
    elif kind == 'symlink':
        info = zipfile.ZipInfo('a.py'); info.create_system=3; info.external_attr=(stat.S_IFLNK | 0o777)<<16
        raw = zipped([(info, b'one')])
    elif kind == 'unlisted': raw = zipped([('a.py', b'one'), ('extra.py', b'two')])
    elif kind == 'hash': raw = zipped([('a.py', b'altered')])
    else: raw = zipped([])
    with pytest.raises(ValueError): check.extract_sources(raw, files, tmp_path/'source')
    assert not (tmp_path/'source').exists()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    wheel = prepare.select_wheel(prepare.ROOT/'uv.lock')
    wheel = {**wheel, 'sha256': check.sha(b'synthetic-wheel'), 'size':len(b'synthetic-wheel')}
    monkeypatch.setattr(prepare, 'select_wheel', lambda _: copy.deepcopy(wheel))
    path = tmp_path/wheel['filename'];path.write_bytes(b'synthetic-wheel')
    output = tmp_path/'input'
    manifest = prepare.run(path, output)
    return output, manifest


def test_preparation_is_exact_and_explicit(prepared):
    output, manifest = prepared
    digest = check.sha((output/'input.json').read_bytes())
    value = check.read_input(output, digest)
    assert value == manifest
    assert manifest['response_sha256'] == check.RESPONSE_SHA
    assert manifest['new_model_inference'] is False
    assert 'uv.lock' in manifest['sources']
    assert len(manifest['files']) == len(manifest['sources'])+1


@pytest.mark.parametrize('kind', ['wheel','requirements','harness','extra','manifest','pin','zip'])
def test_changed_input_refused(prepared, kind):
    output, manifest = prepared
    digest = check.sha((output/'input.json').read_bytes())
    if kind == 'wheel': (output/'wheels'/manifest['wheel']['filename']).write_bytes(b'wrong')
    elif kind == 'requirements': (output/'requirements.txt').write_text('numpy\n',encoding='utf-8')
    elif kind == 'harness': (output/'check.py').write_text('print("fake")',encoding='utf-8')
    elif kind == 'extra': (output/'unlisted.txt').write_bytes(b'extra')
    elif kind == 'manifest': (output/'input.json').write_bytes(b'{}')
    elif kind == 'pin': digest='0'*64
    else: (output/'source.zip').write_bytes(b'wrong')
    with pytest.raises(ValueError): check.read_input(output, digest)


def test_wrong_wheel_and_existing_output_refused(tmp_path):
    wheel=tmp_path/'wrong.whl';wheel.write_bytes(b'not a wheel')
    with pytest.raises(ValueError): prepare.run(wheel,tmp_path/'new')
    assert not (tmp_path/'new').exists()
    with pytest.raises(FileExistsError): prepare.run(wheel,tmp_path)


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e400}'])
def test_strict_protocol_json(raw):
    with pytest.raises(ValueError): check.strict_json(raw)


def test_ambiguous_lock_is_refused(tmp_path):
    text=(prepare.ROOT/'uv.lock').read_text(encoding='utf-8')
    # Duplicating the NumPy3.12 package is not a valid unique resolution.
    start=text.index('[[package]]\nname = "numpy"\nversion = "2.5.4"')
    end=text.index('[[package]]',start+1)
    path=tmp_path/'uv.lock';path.write_text(text+'\n'+text[start:end],encoding='utf-8')
    with pytest.raises(ValueError):prepare.select_wheel(path)


@pytest.fixture
def execution(tmp_path):
    archive=prepare.ROOT/'reference/numerical_method_tools/recorded_trials/compiler-v1/run'
    output=tmp_path/'execution';shutil.copytree(archive,output)
    record=check.strict_json((output/'record.json').read_bytes())
    binding={key:record[key] for key in ('run_id','files','source_sha256','response_sha256','proposal','tool')}
    binding['record_sha256']=check.hash_file(output/'record.json')
    return output,{'sources':record['source_sha256']},binding


def test_reader_handoff_validates_captured_memory_identity(execution):
    output,manifest,binding=execution
    assert check.validate_execution(output,manifest,binding)['tool']['joint_points']==23


@pytest.mark.parametrize('kind',['record','payload','extra','typed_score','sources','binding'])
def test_reader_handoff_cannot_absorb_changed_artifact(execution,kind):
    output,manifest,binding=execution
    if kind=='record':(output/'record.json').write_bytes(b'{}')
    elif kind=='payload':(output/'tool-evaluation.json').write_bytes(b'{}')
    elif kind=='extra':(output/'extra.txt').write_bytes(b'unlisted')
    elif kind=='typed_score':binding['tool']['accepted']=1
    elif kind=='sources':manifest['sources']={}
    else:binding['record_sha256']='0'*64
    with pytest.raises(ValueError):check.validate_execution(output,manifest,binding)


def test_boolean_verdict_is_not_an_integer():
    assert not check.same({'accepted':True},{'accepted':1})


def container_observation():
    cid='a'*64;owner='b'*32;pin='c'*64
    item={'Id':cid,'Name':'/eidos-method-offline-'+owner[:16],'Image':'sha256:'+'e'*64,
          'Config':{'Image':check.IMAGE,'Labels':{'eidos.owner':owner,'eidos.input-sha256':pin},
                    'Cmd':['python','-I','/input/check.py','--input','/input','--sha256',pin,'--output','/out']},
          'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'Memory':2147483648,
                        'NanoCpus':2000000000,'PidsLimit':128,'Init':True,'CapDrop':['ALL'],'CapAdd':None,
                        'SecurityOpt':['no-new-privileges'],'Tmpfs':{'/tmp':check.TMPFS}},
          'Mounts':[{'Type':'bind','Destination':'/input','Source':'/host/input','RW':False},
                    {'Type':'bind','Destination':'/out','Source':'/host/output','RW':True}]}
    return item,cid,owner,pin


def test_owned_isolated_container_observation():
    item,cid,owner,pin=container_observation()
    check.validate_container(item,cid,owner,pin,Path('/host/input'),Path('/host/output'),'sha256:'+'e'*64)


@pytest.mark.parametrize('kind',['id','owner','name','image','network','writable_root','privileged',
                                 'memory','cpu','pids','capabilities','security','input_rw','wrong_mount','command'])
def test_unowned_or_unisolated_container_refused(kind):
    item,cid,owner,pin=container_observation()
    if kind=='id':item['Id']='d'*64
    elif kind=='owner':item['Config']['Labels']['eidos.owner']='d'*32
    elif kind=='name':item['Name']='/legacy-service'
    elif kind=='image':item['Image']='sha256:'+'d'*64
    elif kind=='network':item['HostConfig']['NetworkMode']='host'
    elif kind=='writable_root':item['HostConfig']['ReadonlyRootfs']=False
    elif kind=='privileged':item['HostConfig']['Privileged']=True
    elif kind=='memory':item['HostConfig']['Memory']=0
    elif kind=='cpu':item['HostConfig']['NanoCpus']=0
    elif kind=='pids':item['HostConfig']['PidsLimit']=0
    elif kind=='capabilities':item['HostConfig']['CapAdd']=['SYS_ADMIN']
    elif kind=='security':item['HostConfig']['SecurityOpt']=[]
    elif kind=='input_rw':item['Mounts'][0]['RW']=True
    elif kind=='wrong_mount':item['Mounts'][0]['Source']='/home/secrets'
    else:item['Config']['Cmd']=['unrelated-command']
    with pytest.raises(ValueError):check.validate_container(item,cid,owner,pin,Path('/host/input'),Path('/host/output'),'sha256:'+'e'*64)


def test_manifest_digest_and_config_id_are_distinct_bindings():
    image={'Id':'sha256:'+'e'*64,'RepoDigests':[check.IMAGE],'Os':'linux','Architecture':'amd64',
           'Config':{'Entrypoint':None,'Env':['PYTHON_VERSION='+check.TARGET['python']]}}
    image_id=check.validate_image(image)
    assert image_id!=check.IMAGE.rsplit('@',1)[1]
    item,cid,owner,pin=container_observation()
    check.validate_container(item,cid,owner,pin,Path('/host/input'),Path('/host/output'),image_id)
    for key,value in [('RepoDigests',[]),('Architecture','arm64'),('Id','not-a-digest')]:
        changed=copy.deepcopy(image);changed[key]=value
        with pytest.raises(ValueError):check.validate_image(changed)
