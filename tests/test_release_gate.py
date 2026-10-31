"""A release rehearsal owns its workspace, never an existing research project."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import importlib.util

import pytest

from tools import release_gate


@pytest.fixture
def rehearsal(tmp_path, monkeypatch):
    monkeypatch.setattr(release_gate, 'ROOT', tmp_path)
    monkeypatch.setattr(release_gate, 'TEMPLATE', tmp_path/'template')
    status=tmp_path/'docs/status';status.mkdir(parents=True)
    (tmp_path/'docs/DEMO_COVERAGE.json').write_text('{"demo":6}')
    sentinels=[status/'_release_rehearsal/research.txt',
               tmp_path/'projects/onboard_rehearsal/project.yaml']
    for path in sentinels:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('existing research',encoding='utf-8')
    destinations=[]

    def run(argv, cwd, timeout=900):
        if 'tools/bootstrap_project.py' in argv:
            dest=Path(argv[argv.index('--dest')+1]);dest.mkdir(parents=True,exist_ok=True)
            destinations.append(dest)
        return subprocess.CompletedProcess(argv,0,'ok','')

    monkeypatch.setattr(release_gate,'_run',run)
    from framework.validity import ScientificValidityGate
    monkeypatch.setattr(ScientificValidityGate,'run',lambda self:SimpleNamespace(passed=True,details={}))
    return tmp_path,sentinels,destinations,run


def test_rehearsal_preserves_existing_project_and_status_directory(rehearsal):
    root,sentinels,destinations,_=rehearsal
    assert release_gate.main([])==0
    assert all(p.read_text()=='existing research' for p in sentinels)
    assert len(destinations)==1 and not destinations[0].parent.exists()


def test_overlapping_rehearsals_have_separate_owned_workspaces(rehearsal,monkeypatch):
    _,sentinels,destinations,run=rehearsal
    barrier=threading.Barrier(2)

    def overlap(argv,cwd,timeout=900):
        result=run(argv,cwd,timeout)
        if 'tools/bootstrap_project.py' in argv:barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(release_gate,'_run',overlap)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _:release_gate.main([]),range(2)))==[0,0]
    assert len(set(destinations))==2
    assert all(not p.parent.exists() for p in destinations)
    assert all(p.read_text()=='existing research' for p in sentinels)


def test_keep_retains_only_the_new_owned_workspace(rehearsal,capsys):
    _,sentinels,destinations,_=rehearsal
    assert release_gate.main(['--keep'])==0
    assert all(p.read_text()=='existing research' for p in sentinels)
    assert destinations[0].is_dir()
    assert str(destinations[0].parent) in capsys.readouterr().out


def test_scaffold_failure_does_not_execute_a_missing_project(rehearsal,monkeypatch):
    _,_,_,run=rehearsal

    def fail_scaffold(argv,cwd,timeout=900):
        assert 'build_evidence.py' not in argv,'failed scaffold must not be executed'
        if 'tools/bootstrap_project.py' in argv:return subprocess.CompletedProcess(argv,1,'','scaffold failed')
        return run(argv,cwd,timeout)

    monkeypatch.setattr(release_gate,'_run',fail_scaffold)
    assert release_gate.main([])==1


def test_failed_coverage_producer_cannot_reuse_a_cached_passing_count(rehearsal,monkeypatch):
    _,_,_,run=rehearsal

    def failed_coverage(argv,cwd,timeout=900):
        if 'tools/demo_coverage.py' in argv:return subprocess.CompletedProcess(argv,1,'','producer failed')
        return run(argv,cwd,timeout)

    monkeypatch.setattr(release_gate,'_run',failed_coverage)
    assert release_gate.main([])==1


def test_replaced_workspace_is_preserved_even_at_the_same_path(tmp_path):
    from tools.owned_workspace import owned_workspace
    displaced=tmp_path/'displaced'
    with pytest.raises(RuntimeError,match='replaced rehearsal workspace'):
        with owned_workspace(tmp_path,prefix='owned-') as workspace:
            workspace.rename(displaced)
            workspace.mkdir()
            (workspace/'research.txt').write_text('replacement research')
    assert (workspace/'research.txt').read_text()=='replacement research'
    assert displaced.is_dir()


def test_workspace_is_cleaned_after_a_failed_body(tmp_path):
    from tools.owned_workspace import owned_workspace
    with pytest.raises(ValueError,match='experiment failed'):
        with owned_workspace(tmp_path,prefix='owned-') as workspace:
            (workspace/'partial.txt').write_text('partial')
            raise ValueError('experiment failed')
    assert not workspace.exists()


def test_real_vacuous_control_preserves_existing_projects_and_runs_concurrently(tmp_path,monkeypatch):
    source=Path(__file__).resolve().parents[1]/'reference/demo_quantitative/show_vacuous.py'
    spec=importlib.util.spec_from_file_location('vacuous_control',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    sentinels=[tmp_path/'docs/status/_vacuous_demo/research.txt',
               tmp_path/'projects/vacuous_demo/project.yaml']
    for path in sentinels:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('existing research')
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _:module.main(),range(2)))==[0,0]
    assert all(p.read_text()=='existing research' for p in sentinels)
    assert not list((tmp_path/'docs/status').glob('_vacuous_demo-*'))


def test_rehearsal_process_tree_forwards_environment_and_utf8(tmp_path):
    import sys
    run=release_gate._run([sys.executable,'-c',
                          'import os;print(os.environ["EIDOS_ROOT"]);print("科学 → µ")'],tmp_path,30)
    assert run.returncode==0,run.stderr
    assert run.stdout.splitlines()==[str(release_gate.ROOT),'科学 → µ']
