"""Exercise CMD launchers with literal configuration and harmless stand-in tools."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(os.name!='nt',reason='real Windows CMD launcher acceptance')


@pytest.fixture(scope='module')
def configured_python(tmp_path_factory):
    env=tmp_path_factory.mktemp('runtime')/'python with spaces'
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(env)],check=True,
                   capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return env/'Scripts/python.exe'


@pytest.fixture
def project(tmp_path,configured_python):
    root=tmp_path/'research project & 科学'
    for name in ('tools','scripts'):(root/name).mkdir(parents=True,exist_ok=True)
    for name in ('cron_entry.py','bounded_process.py','windows_job.py','launch_runtime.py'):
        if (ROOT/'tools'/name).is_file():shutil.copy2(ROOT/'tools'/name,root/'tools'/name)
    for name in ('eidos-monitor.cmd','install-autostart.cmd'):
        shutil.copy2(ROOT/'scripts'/name,root/'scripts'/name)
    (root/'scripts/monitor.env').write_text(f'set "PYTHON={configured_python}"\n'
                                          'set "QUARTO_BIN=C:/quarto with spaces/quarto.exe"\n'
                                          'echo forbidden>injected.txt\n',encoding='utf-8')
    for name in ('monitor_supervisor.py','install_autostart.py'):
        (root/'tools'/name).write_text('import json,os,sys\nfrom pathlib import Path\n'
            'record={"python":sys.executable,"args":sys.argv[1:],"isolated":bool(sys.flags.isolated),'
            '"utf8":bool(sys.flags.utf8_mode),"pythonpath":os.environ.get("PYTHONPATH"),'
            '"pythonhome":os.environ.get("PYTHONHOME"),"quarto":os.environ.get("QUARTO_BIN")}\n'
            'Path("probe.json").write_text(json.dumps(record),encoding="utf-8")\n'
            'raise SystemExit(int(os.environ.get("EIDOS_FIXTURE_EXIT","0")))\n',encoding='utf-8')
    return root


def launch(root,script,*args,extra=None):
    environment=os.environ.copy();environment.pop('EIDOS_PYTHON',None)
    environment['PYTHON']=sys.executable
    environment['PYTHONUTF8']='1'
    if extra:environment.update(extra)
    # CMD /s consumes its own outer quotes; the launcher path is separately quoted.
    command='"'+os.environ['COMSPEC']+'" /d /s /c ""'+str(root/'scripts'/script)+'" '+subprocess.list2cmdline(list(args))+'"'
    return subprocess.run(command,cwd=root,env=environment,
                          capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def test_monitor_uses_configured_python_not_bootstrap_and_does_not_execute_env(project,configured_python):
    result=launch(project,'eidos-monitor.cmd')
    assert result.returncode==0,result.stderr
    record=json.loads((project/'probe.json').read_text(encoding='utf-8'))
    assert Path(record['python'])==configured_python
    assert record['isolated'] and record['utf8']
    assert record['quarto']=='C:/quarto with spaces/quarto.exe'
    assert not (project/'injected.txt').exists()


def test_check_is_a_real_isolated_non_service_child(project,configured_python):
    result=launch(project,'eidos-monitor.cmd','--check')
    assert result.returncode==0,result.stderr
    record=json.loads(result.stdout)
    assert Path(record['executable'])==configured_python
    assert record['isolated'] and record['utf8_mode'] and record['console_window']==0
    assert not record['pythonpath_present'] and not record['pythonhome_present']
    assert not (project/'probe.json').exists()


def test_invalid_python_home_and_path_are_not_forwarded(project,configured_python):
    result=launch(project,'eidos-monitor.cmd','--check',extra={'PYTHONHOME':'Z:/foreign-python','PYTHONPATH':'Z:/foreign-tools'})
    assert result.returncode==0,result.stderr
    record=json.loads(result.stdout)
    assert Path(record['executable'])==configured_python
    assert not record['pythonpath_present'] and not record['pythonhome_present']


@pytest.mark.parametrize('argument,forwarded',[('--no-start',['--no-start']),('remove',['--remove'])])
def test_installer_uses_same_runtime_without_touching_real_startup(project,configured_python,argument,forwarded):
    result=launch(project,'install-autostart.cmd',argument)
    assert result.returncode==0,result.stderr
    record=json.loads((project/'probe.json').read_text(encoding='utf-8'))
    assert Path(record['python'])==configured_python and record['args']==forwarded


def test_nonzero_child_exit_is_preserved(project):
    result=launch(project,'eidos-monitor.cmd',extra={'EIDOS_FIXTURE_EXIT':'7'})
    assert result.returncode==7,result.stderr


def test_missing_configured_python_fails_instead_of_silent_fallback(project):
    (project/'scripts/monitor.env').write_text('set "PYTHON=Z:/missing/python.exe"\n',encoding='utf-8')
    result=launch(project,'eidos-monitor.cmd')
    assert result.returncode!=0
    assert not (project/'probe.json').exists()


@pytest.mark.parametrize('flag',['--check','--help'])
def test_legacy_remove_does_not_discard_non_mutating_options(project,flag):
    result=launch(project,'install-autostart.cmd','remove',flag)
    assert result.returncode==0,result.stderr
    assert not (project/'probe.json').exists(),'diagnostic/help must not invoke the installer'
