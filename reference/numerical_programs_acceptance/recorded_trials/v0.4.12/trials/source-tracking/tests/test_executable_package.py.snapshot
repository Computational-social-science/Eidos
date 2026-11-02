import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from framework.quarto_bridge import QuartoBridge


def specification(tmp_path, monkeypatch):
    monkeypatch.setattr(QuartoBridge, '_check_quarto', lambda self: False)
    (tmp_path/'pyproject.toml').write_text('[project]\nname="package-probe"\nversion="0.1.0"\nrequires-python=">=3.12"\ndependencies=[]\n')
    (tmp_path/'uv.lock').write_text('version = 1\nrevision = 3\nrequires-python = ">=3.12"\n[[package]]\nname = "package-probe"\nversion = "0.1.0"\nsource = { virtual = "." }\n')
    (tmp_path/'run.py').write_text('from pathlib import Path\nPath("result.json").write_text("42")\n')
    (tmp_path/'check.py').write_text('from pathlib import Path\nraise SystemExit(0 if Path("result.json").read_text()=="42" else 1)\n')
    return {'project_root':str(tmp_path), 'executable_package':{
        'files':['pyproject.toml','uv.lock','run.py','check.py'],
        'command':['python','run.py'], 'verify_command':['python','check.py'],
        'outputs':['result.json'], 'seed':0, 'data_version':'synthetic-v1', 'config_version':'probe-v1'}}


def test_copied_package_executes_and_rejects_reuse(tmp_path, monkeypatch):
    config=specification(tmp_path,monkeypatch)
    package=QuartoBridge(config).build_executable_package('isolated')
    root=Path(package['package_dir'])
    result=subprocess.run([sys.executable,'eidos-reproduce.py'],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    record=json.loads((root/'execution-record.json').read_text())
    assert record['seed']==0 and record['outputs']['result.json']
    assert subprocess.run([sys.executable,'eidos-reproduce.py'],cwd=root,capture_output=True).returncode!=0
    assert not package['execution_verified']


def test_one_package_copy_cannot_execute_concurrently(tmp_path, monkeypatch):
    config=specification(tmp_path,monkeypatch)
    (tmp_path/'run.py').write_text('from pathlib import Path\nimport time\n'
                                 'with Path("calls").open("a") as f: f.write("run\\n")\n'
                                 'Path("started").touch()\n'
                                 'deadline=time.monotonic()+10\n'
                                 'while not Path("release").exists() and time.monotonic()<deadline: time.sleep(.01)\n'
                                 'Path("result.json").write_text("42")\n')
    root=Path(QuartoBridge(config).build_executable_package('isolated')['package_dir'])
    first=subprocess.Popen([sys.executable,'eidos-reproduce.py'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not (root/'started').exists() and first.poll() is None and time.monotonic()<deadline:
            time.sleep(.01)
        assert (root/'started').exists(),'first execution never started'
        second=subprocess.run([sys.executable,'eidos-reproduce.py'],cwd=root,capture_output=True,timeout=5)
        assert second.returncode!=0
        assert b'package copy already claimed' in second.stderr
        (root/'release').touch()
        stdout,stderr=first.communicate(timeout=5)
        assert first.returncode==0,(stdout,stderr)
        assert (root/'calls').read_text().splitlines()==['run']
    finally:
        (root/'release').touch()
        if first.poll() is None:
            first.kill();first.wait()


@pytest.mark.parametrize('failure',['mutation','missing_output','rejected_evidence','manifest_mutation'])
def test_runner_fails_closed(tmp_path, monkeypatch, failure):
    config=specification(tmp_path,monkeypatch)
    if failure=='missing_output':
        (tmp_path/'run.py').write_text('pass\n')
    if failure=='rejected_evidence':
        (tmp_path/'check.py').write_text('raise SystemExit(1)\n')
    if failure=='manifest_mutation':
        (tmp_path/'check.py').write_text('from pathlib import Path\nPath("package-manifest.json").write_text("{}")\n')
    root=Path(QuartoBridge(config).build_executable_package('isolated')['package_dir'])
    if failure=='mutation':
        (root/'run.py').write_text('pass\n')
    result=subprocess.run([sys.executable,'eidos-reproduce.py'],cwd=root,capture_output=True)
    assert result.returncode!=0
    assert not (root/'execution-record.json').exists()


@pytest.mark.parametrize('failure',['escape','secret','missing_lock','missing_seed','empty_command','existing_target',
                                   'reserved_alias','duplicate_alias','trailing_alias','ancestor_alias'])
def test_invalid_delivery_is_not_published(tmp_path,monkeypatch,failure):
    config=specification(tmp_path,monkeypatch)
    spec=config['executable_package']
    if failure=='escape':spec['files'].append('../outside.txt')
    if failure=='secret':spec['files'].append('.env')
    if failure=='missing_lock':spec['files'].remove('uv.lock')
    if failure=='missing_seed':spec.pop('seed')
    if failure=='empty_command':spec['command']=[]
    if failure=='reserved_alias':spec['outputs']=['Execution-Record.json']
    if failure=='duplicate_alias':spec['outputs']=['result.json','RESULT.json']
    if failure=='trailing_alias':spec['outputs']=['result.json.']
    if failure=='ancestor_alias':spec['outputs']=['data','data/result.json']
    target=tmp_path/'outputs/isolated'
    if failure=='existing_target':
        target.mkdir(parents=True);(target/'keep').write_text('research')
    with pytest.raises((ValueError,FileExistsError)):
        QuartoBridge(config).build_executable_package('isolated')
    if failure=='existing_target':assert (target/'keep').read_text()=='research'
    else:assert not target.exists()
