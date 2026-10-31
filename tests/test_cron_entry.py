"""Local schedules share project runtime configuration and stay silent when healthy."""
import subprocess
import json
import pytest
import os
import sys
from pathlib import Path


def test_runtime_config_is_parsed_without_executing_batch_commands(tmp_path,monkeypatch):
    from tools.cron_entry import runtime
    (tmp_path/'scripts').mkdir()
    (tmp_path/'scripts/monitor.env').write_text('set "PYTHON=C:/project/python.exe"\nset QUARTO_BIN=C:/quarto.exe\necho forbidden\n')
    monkeypatch.delenv('EIDOS_PYTHON',raising=False)
    result=runtime(tmp_path)
    assert result['PYTHON']=='C:/project/python.exe' and result['QUARTO_BIN']=='C:/quarto.exe'


def test_healthy_watchdog_is_quiet_and_records_success(tmp_path,monkeypatch,capsys):
    from tools import cron_entry,bounded_process
    monkeypatch.setattr(cron_entry,'ROOT',tmp_path)
    monkeypatch.setattr(cron_entry,'runtime',lambda:{'PYTHON':'project-python'})
    monkeypatch.setattr(bounded_process,'run_tree',lambda *a,**kw:subprocess.CompletedProcess([],0,'',''))
    assert cron_entry.main(['watchdog'])==0
    assert capsys.readouterr().out==''
    assert (tmp_path/'docs/status/cron-watchdog.json').is_file()


def test_hidden_startup_entry_quotes_paths_with_spaces(tmp_path):
    from tools.install_autostart import startup_script
    text=startup_script(tmp_path/'research project'/'eidos-monitor.vbs')
    assert ', 0, False' in text and 'q &' in text and 'research project' in text


def test_interpreter_assignment_quotes_batch_metacharacters():
    from tools.install_autostart import runtime_assignment
    assert runtime_assignment('C:/Research & Development/python.exe') == 'set "PYTHON=C:/Research & Development/python.exe"\n'
    with pytest.raises(ValueError):
        runtime_assignment('C:/literal%name/python.exe')


@pytest.mark.parametrize('payload', ['not json', '[]', '{}', '{"boundaries": [], "regressions": [], "findings": []}',
                                    '{"boundaries": {"x": {"ok": true}}, "regressions": [], "findings": "bad"}'])
def test_zero_exit_with_invalid_contract_output_is_rejected(tmp_path,monkeypatch,payload):
    from tools import cron_entry,bounded_process
    monkeypatch.setattr(cron_entry,'ROOT',tmp_path)
    monkeypatch.setattr(cron_entry,'runtime',lambda:{'PYTHON':'project-python'})
    monkeypatch.setattr(bounded_process,'run_tree',lambda *a,**kw:subprocess.CompletedProcess([],0,payload,''))
    assert cron_entry.main(['contracts']) == 1
    assert json.loads((tmp_path/'docs/status/cron-contracts.json').read_text())['ok'] is False


def test_regressions_cannot_borrow_a_zero_exit_code(tmp_path,monkeypatch):
    from tools import cron_entry,bounded_process
    payload=json.dumps({'boundaries':{'x':{'ok':False}},'regressions':['x: now missing'],'findings':[]})
    monkeypatch.setattr(cron_entry,'ROOT',tmp_path)
    monkeypatch.setattr(cron_entry,'runtime',lambda:{'PYTHON':'project-python'})
    monkeypatch.setattr(bounded_process,'run_tree',lambda *a,**kw:subprocess.CompletedProcess([],0,payload,''))
    assert cron_entry.main(['contracts']) == 1


def test_existing_scheduler_jobs_keep_their_names_and_original_scripts(tmp_path):
    from tools.install_hermes_cron import install
    home=tmp_path/'hermes';folder=home/'scripts';folder.mkdir(parents=True)
    for name in ('eidos_watchdog.py','eidos_contracts.py'):
        (folder/name).write_bytes(b'# old EIDOS shim\n')
    root=tmp_path/'repo'
    assert install(home,root)==['eidos_watchdog.py','eidos_contracts.py']
    assert install(home,root)==[]
    assert len(list((root/'.scratch/cron-backups').rglob('*.py')))==2
    assert 'cron_entry.py' in (folder/'eidos_watchdog.py').read_text()


def test_invalid_second_job_cannot_partially_install_the_first(tmp_path):
    from tools.install_hermes_cron import install
    home=tmp_path/'hermes';folder=home/'scripts';folder.mkdir(parents=True)
    original=b'# old EIDOS shim\n'
    (folder/'eidos_watchdog.py').write_bytes(original)
    (folder/'eidos_contracts.py').write_bytes(b'# unrelated user script\n')
    with pytest.raises(ValueError):
        install(home,tmp_path/'repo')
    assert (folder/'eidos_watchdog.py').read_bytes()==original


@pytest.mark.parametrize('exit_code',[0,7])
def test_scheduler_shim_isolates_project_from_preloaded_foreign_tools(tmp_path,exit_code):
    from tools.install_hermes_cron import shim
    project=tmp_path/'research project';(project/'tools').mkdir(parents=True)
    (project/'tools/helper.py').write_text('MARKER="project"\n')
    entry=project/'tools/cron_entry.py'
    entry.write_text('''import sys,json,os,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def runtime(): return {'PYTHON':sys.executable}
if __name__=='__main__':
    from tools.helper import MARKER
    code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).resolve().parents[1]))+');from tools.helper import MARKER;print(MARKER)'
    child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if child.returncode: raise SystemExit(child.stderr)
    console=__import__('ctypes').windll.kernel32.GetConsoleWindow() if os.name=='nt' else None
    print(json.dumps({'marker':MARKER,'descendant':child.stdout.strip(),'isolated':sys.flags.isolated,'utf8':sys.flags.utf8_mode,'kind':sys.argv[1],'console_window':console,'message':'科学 → µ'},ensure_ascii=False))
''',encoding='utf-8')
    with entry.open('a',encoding='utf-8') as stream:
        stream.write(f"if __name__=='__main__': raise SystemExit({exit_code})\n")
    foreign=tmp_path/'foreign';(foreign/'tools').mkdir(parents=True)
    (foreign/'tools/__init__.py').write_text('MARKER="scheduler"\n')
    launcher=tmp_path/'scheduler.py';launcher.write_text(shim('watchdog',project),encoding='utf-8')
    env=os.environ.copy();env['PYTHONPATH']=str(foreign)
    run=subprocess.run([sys.executable,'-c',
                        'import tools,runpy,sys;runpy.run_path(sys.argv[1],run_name="__main__")',str(launcher)],
                       cwd=tmp_path,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',
                       timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert run.returncode==exit_code,run.stderr
    data=json.loads(run.stdout)
    assert data['marker']=='project' and data['kind']=='watchdog'
    assert data['descendant']=='project'
    assert data['isolated']==1 and data['utf8']==1 and data['message']=='科学 → µ'
    if os.name=='nt':assert data['console_window']==0


def test_real_cron_configuration_can_load_with_foreign_tools_already_imported(tmp_path):
    foreign=tmp_path/'foreign';(foreign/'tools').mkdir(parents=True)
    (foreign/'tools/__init__.py').write_text('MARKER="scheduler"\n')
    env=os.environ.copy();env.update(PYTHONPATH=str(foreign),EIDOS_PYTHON=sys.executable)
    entry=Path(__file__).resolve().parents[1]/'tools/cron_entry.py'
    code=('import tools,runpy,sys;assert tools.MARKER=="scheduler";'
          'ns=runpy.run_path(sys.argv[1],run_name="_eidos_scheduler_config");'
          'assert ns["runtime"]()["PYTHON"]==sys.executable;print("configuration-ready")')
    run=subprocess.run([sys.executable,'-c',code,str(entry)],cwd=tmp_path,env=env,
                       capture_output=True,text=True,encoding='utf-8',timeout=30,
                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert run.returncode==0,run.stderr
    assert run.stdout.strip()=='configuration-ready'
