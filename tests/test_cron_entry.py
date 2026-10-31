"""Local schedules share project runtime configuration and stay silent when healthy."""
import subprocess
import json
import pytest


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
