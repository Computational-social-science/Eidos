"""A watchdog/reload must survive the failure it exists to handle."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from tools import serve_site


def test_stalled_sampler_reaches_process_exit(monkeypatch):
    monkeypatch.setitem(serve_site.STATE, "sampled", 0.0)
    monkeypatch.setattr(serve_site.time, "time", lambda: 1000.0)
    monkeypatch.setattr(serve_site.time, "sleep", lambda _: None)
    def exit_(code):
        raise SystemExit(code)
    monkeypatch.setattr(serve_site.os, "_exit", exit_)
    with pytest.raises(SystemExit) as exc:
        serve_site.stall_watchdog(limit=1, check_every=0)
    assert exc.value.code == 3


def test_failed_reload_preserves_working_module(tmp_path, monkeypatch):
    name = "eidos_reload_regression"
    path = tmp_path / f"{name}.py"
    path.write_text('def sample(): return "working"\ndef measure(): return "measured"\n', encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(serve_site.STATE, f"_mtime_{name}", raising=False)
    path.write_text('sample = None\nraise RuntimeError("broken update")\n', encoding="utf-8")
    selected = serve_site._reload_if_changed(module, path)
    assert selected.sample() == "working"
    assert sys.modules[name] is module


def test_complete_reload_replaces_module_and_behaviour(tmp_path, monkeypatch):
    name = "eidos_complete_reload"
    path = tmp_path / f"{name}.py"
    path.write_text('def sample(): return "old"\ndef measure(): return "old"\n', encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(serve_site.STATE, f"_mtime_{name}", raising=False)
    path.write_text('def sample(): return "new"\ndef measure(): return "new"\n', encoding="utf-8")
    selected = serve_site._reload_if_changed(module, path)
    assert selected.sample() == "new"
    assert sys.modules[name] is selected
    assert module.sample() == "old"
    assert serve_site._reload_if_changed(module, path).sample() == "new"
    path.write_text('raise RuntimeError("later broken edit")\n', encoding="utf-8")
    assert serve_site._reload_if_changed(module, path).sample() == "new"
    path.write_text('sample = None\n', encoding="utf-8")
    assert serve_site._reload_if_changed(module, path).sample() == "new"


@pytest.mark.parametrize('value,reference',[(1,None),(None,0),(float('nan'),0),
                                          (float('inf'),0),('invalid',0)])
def test_unusable_signal_values_are_explicitly_unobservable(value,reference):
    from tools import watch_pipeline
    assert watch_pipeline.classify({'value':value,'reference':reference,'direction':'max'})==('UNOBSERVABLE',None)


def test_optional_package_probe_does_not_enable_a_disabled_user_site(tmp_path,monkeypatch):
    import site
    from tools import watch_pipeline
    name='eidos_disabled_user_site_fixture'
    (tmp_path/(name+'.py')).write_text('VALUE=1\n')
    monkeypatch.setattr(site,'getusersitepackages',lambda:str(tmp_path))
    monkeypatch.setattr(sys,'path',list(sys.path))
    before=list(sys.path)
    visible,_=watch_pipeline._has_module(name)
    assert not visible
    assert sys.path==before


@pytest.mark.parametrize('invalid',[None,float('nan'),float('inf'),'invalid'])
def test_sample_reads_running_marker_once_and_serializes_invalid_measurements(tmp_path,monkeypatch,invalid):
    import json
    from tools import watch_pipeline
    monkeypatch.setattr(watch_pipeline,'measure',lambda:{'probe':{
        'value':invalid,'reference':0,'direction':'max','source':'isolated fixture'}})
    monkeypatch.setattr(watch_pipeline,'STATUS',tmp_path)
    for name in ('CURRENT','HISTORY','ALARMS','FAULTS','RECOVERY_STATE'):
        monkeypatch.setattr(watch_pipeline,name,tmp_path/(name.lower()+'.json'))
    monkeypatch.setattr(watch_pipeline,'maybe_auto_recover',lambda states:states)
    monkeypatch.setattr(watch_pipeline.chain_states,'TIMELINE',tmp_path/'timeline.json')
    monkeypatch.setattr(watch_pipeline.chain_states,'observed',lambda:{})
    monkeypatch.setattr(watch_pipeline.chain_states,'append',lambda *args:[])
    calls=[]
    def age():
        calls.append(True)
        return 0.0 if len(calls)==1 else None
    monkeypatch.setattr(watch_pipeline.chain_states,'running_age',age)
    payload=watch_pipeline.sample(append=False)
    assert payload['live_run'] is True
    assert len(calls)==1
    assert payload['signals']['probe']['state']=='UNOBSERVABLE'
    json.dumps(payload,allow_nan=False)


def test_legacy_nonfinite_payload_values_are_gaps_with_diagnostics():
    import json
    from tools import watch_pipeline
    original={'history':[{'values':{'probe':float('nan')}}],
              'alarms':[{'value':float('inf')}],
              'chain_meta':{'gates':{'age_s':float('-inf')}}}
    result=watch_pipeline._json_safe_payload(original)
    json.dumps(result,allow_nan=False)
    assert result['history'][0]['values']['probe'] is None
    assert result['alarms'][0]['value'] is None
    assert result['chain_meta']['gates']['age_s'] is None
    assert {r['raw'] for r in result['json_normalization']}=={'nan','inf','-inf'}
    assert original['alarms'][0]['value']==float('inf')
