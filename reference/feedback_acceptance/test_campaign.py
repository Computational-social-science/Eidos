"""Independent producer controls; deliberately malformed outcomes cannot become PASS."""

import importlib.util
import json
from pathlib import Path
import zipfile
from email.parser import BytesParser

import pytest


def producer():
    spec = importlib.util.spec_from_file_location('repair_campaign', Path(__file__).with_name('campaign.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unentered_timeout_is_not_a_reproduced_defect(tmp_path):
    with pytest.raises(ValueError, match='witness'):
        producer().probe_verdict({'exit': 124, 'stdout': ''}, tmp_path, 'inherited')


def test_claimed_success_with_a_live_descendant_is_rejected(tmp_path):
    for name in ('descendant-ready', 'client-finished'):
        (tmp_path / name).write_text('witness')
    row = {'exit': 0, 'stdout': json.dumps({'available': True, 'descendant_running_after_probe': True})}
    assert producer().probe_verdict(row, tmp_path, 'inherited') == 'FAIL'


def test_nonzero_cli_does_not_become_available(tmp_path):
    row = {'exit': 0, 'stdout': json.dumps({'available': True, 'descendant_running_after_probe': False})}
    assert producer().probe_verdict(row, tmp_path, 'failure') == 'FAIL'


def test_changed_protected_input_refuses_before_evaluation(tmp_path):
    p = tmp_path / 'fixture.py'
    p.write_bytes(b'protected')
    expected = {str(p): producer().sha(p.read_bytes())}
    p.write_bytes(b'changed')
    with pytest.raises(ValueError, match='Protected'):
        producer().verify_inputs(expected)


def test_no_fix_control_preserves_sdk_with_windows_metadata(tmp_path):
    old = tmp_path / 'old.whl'
    with zipfile.ZipFile(old, 'w') as archive:
        archive.writestr('eidos-0.4.12.dist-info/METADATA', b'Name: eidos\r\nVersion: 0.4.12\r\n\r\nHistorical README\r\n')
        archive.writestr('framework/inference/__init__.py', b'ORIGINAL_BUG=True\r\n')
    output = tmp_path / 'control.whl'
    producer().control_wheel(old, output)
    with zipfile.ZipFile(output) as archive:
        assert archive.read('framework/inference/__init__.py') == b'ORIGINAL_BUG=True\r\n'
        metadata = BytesParser().parsebytes(archive.read('eidos-0.5.0.dev0.dist-info/METADATA'))
        assert metadata['Version'] == '0.5.0.dev0'


def test_interrupted_bad_selection_restores_real_prior_bytes(tmp_path):
    folder = tmp_path / '.eidos'
    folder.mkdir()
    pin = folder / 'runtime-pin.json'
    pin.write_bytes(b'original pin')
    with pytest.raises(RuntimeError, match='unobserved'):
        with producer().trial_selection(tmp_path, b'original pin', b'bad pin'):
            assert pin.read_bytes() == b'bad pin'
            raise RuntimeError('unobserved probe')
    assert pin.read_bytes() == b'original pin'


def test_cleanup_never_clobbers_an_unrelated_new_pin(tmp_path):
    folder = tmp_path / '.eidos'
    folder.mkdir()
    pin = folder / 'runtime-pin.json'
    pin.write_bytes(b'prior')
    with pytest.raises(ValueError, match='unrelated'):
        with producer().trial_selection(tmp_path, b'prior', b'candidate'):
            pin.write_bytes(b'unrelated new selection')
    assert pin.read_bytes() == b'unrelated new selection'


def test_unobserved_post_adoption_probe_invokes_real_reversion(tmp_path, monkeypatch):
    from framework import feedback
    folder = tmp_path / '.eidos'
    folder.mkdir()
    pin = folder / 'runtime-pin.json'
    pin.write_bytes(b'adopted')
    monkeypatch.setattr(feedback, 'status', lambda *a: {'state': 'ADOPTED'})
    monkeypatch.setattr(feedback, 'revert', lambda *a: pin.write_bytes(b'prior'))
    with pytest.raises(RuntimeError, match='probe failed'):
        with producer().adopted_guard(tmp_path, 'a' * 32):
            raise RuntimeError('probe failed before any replay receipt')
    assert pin.read_bytes() == b'prior'


def test_original_owner_timeout_needs_trigger_entry(tmp_path):
    with pytest.raises(ValueError, match='witness'):
        producer().origin_verdict({'exit': 124, 'stdout': ''}, tmp_path, True)


def test_original_owner_pass_cannot_hide_a_leaked_descendant(tmp_path):
    for name in ('descendant-ready', 'client-finished'):
        (tmp_path / name).write_text('entered')
    row = {'exit': 0, 'stdout': json.dumps({'result': ['PASS', 'budget correct'],
                                         'descendant_running_after_contract': True})}
    assert producer().origin_verdict(row, tmp_path, True) == 'FAIL'


def preparation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import os
    module = producer()
    workspace, project = tmp_path / 'campaign', tmp_path / 'study'
    workspace.mkdir()
    project.mkdir()
    worker = workspace / 'env-new' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    monkeypatch.setattr(module, 'sys', SimpleNamespace(executable=str(worker)))
    def unexpected_gate(*args, **kwargs):
        raise AssertionError('Research gate executed before preparation was qualified')
    monkeypatch.setattr(module, 'cli', unexpected_gate)
    return module, SimpleNamespace(workspace=workspace, project=project,
                                  oracle=workspace / 'oracle.py', fixture=workspace / 'fixture.py')


def test_existing_scientific_workspace_refuses_without_running_its_gate(tmp_path, monkeypatch):
    module, args = preparation(tmp_path, monkeypatch)
    folder = args.project / '.eidos'
    folder.mkdir()
    original = b'gate_command: [python, expensive_research.py]\n'
    (folder / 'project.yaml').write_bytes(original)
    with pytest.raises(ValueError, match='Existing.*workspace'):
        module.prepare(args)
    assert (folder / 'project.yaml').read_bytes() == original
    assert sorted(p.name for p in folder.iterdir()) == ['project.yaml']


def test_missing_preparation_inputs_refuse_before_initialization(tmp_path, monkeypatch):
    module, args = preparation(tmp_path, monkeypatch)
    (args.project / 'data.bin').write_bytes(b'existing research data')
    with pytest.raises(ValueError, match='preparation input'):
        module.prepare(args)
    assert not (args.project / '.eidos').exists()
    assert (args.project / 'data.bin').read_bytes() == b'existing research data'


def preparation_files(args):
    import os
    for path in [args.oracle, args.fixture, *(args.workspace / 'wheels' / n for n in
                 ['eidos-0.4.12-py3-none-any.whl', 'eidos-0.5.0.dev0-py3-none-any.whl', 'eidos-0.5.0-py3-none-any.whl']),
                 *(args.workspace / ('env-' + arm) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                   for arm in ['old', 'bad', 'new'])]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'deliberately unqualified input')
    origin = args.project / 'tools/audit_chains.py'
    origin.parent.mkdir()
    origin.write_text('def audit_inference(): pass\n', encoding='utf-8')


def test_unqualified_installed_worker_refuses_before_initialization(tmp_path, monkeypatch):
    module, args = preparation(tmp_path, monkeypatch)
    preparation_files(args)
    def reject_identity(*args):
        raise ValueError('Installed identity mismatch')
    monkeypatch.setattr(module, 'helpers', lambda *args: (reject_identity, None, None))
    with pytest.raises(ValueError, match='identity mismatch'):
        module.prepare(args)
    assert not (args.project / '.eidos').exists()


def test_redirected_origin_refuses_before_initialization(tmp_path, monkeypatch):
    module, args = preparation(tmp_path, monkeypatch)
    preparation_files(args)
    origin = args.project / 'tools/audit_chains.py'
    target = args.project / 'real-owner.py'
    origin.rename(target)
    try:
        origin.symlink_to(target)
    except OSError as error:
        pytest.skip('Symlinks unavailable: ' + str(error))
    monkeypatch.setattr(module, 'helpers', lambda *args: (lambda *args: {}, None, None))
    with pytest.raises(ValueError, match='redirected'):
        module.prepare(args)
    assert not (args.project / '.eidos').exists()


def test_refused_initialization_cannot_continue_to_a_configured_gate(tmp_path, monkeypatch):
    module, args = preparation(tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'preparation_inputs', lambda *args: ({}, {}), raising=False)
    calls = []
    def refused_init(project, operation):
        calls.append(operation)
        assert operation == 'init', 'Configured research gate must not execute'
        return {'result': {'status': 'REFUSED'}}
    monkeypatch.setattr(module, 'cli', refused_init)
    with pytest.raises(ValueError, match='initialization was refused'):
        module.prepare(args)
    assert calls == ['init']


def completion(tmp_path, monkeypatch, state):
    from framework import feedback
    module, args = preparation(tmp_path, monkeypatch)
    protected = args.workspace / 'protected.txt'
    protected.write_bytes(b'sealed')
    config = {'project': str(args.project), 'workspace': str(args.workspace),
              'incident_id': '1' * 32, 'project_id': '2' * 32,
              'protocol_sha256': '3' * 64,
              'workers': {'new': module.sys.executable},
              'protected': {str(protected): module.sha(protected.read_bytes())}}
    (args.workspace / 'campaign.json').write_text(json.dumps(config), encoding='utf-8')
    (args.workspace / 'original-pin.json').write_bytes(b'previous pin')
    monkeypatch.setattr(feedback, 'status', lambda *args: {'state': state})
    return module, args, protected


def test_input_change_during_publication_refuses_before_release_record(tmp_path, monkeypatch):
    module, args, protected = completion(tmp_path, monkeypatch, 'VALIDATED')
    def changed_publication(config):
        protected.write_bytes(b'changed during network fetch')
        return {}
    def unexpected_release(*args, **kwargs):
        raise AssertionError('Release recorded with changed protected inputs')
    monkeypatch.setattr(module, 'publication_artifacts', changed_publication)
    monkeypatch.setattr(module, 'receipt', unexpected_release)
    with pytest.raises(ValueError, match='Protected'):
        module.finish(args)
    assert not (args.project / '.eidos').exists()


def test_input_change_before_closure_refuses_before_close(tmp_path, monkeypatch):
    from framework import feedback
    module, args, protected = completion(tmp_path, monkeypatch, 'REPLAYED')
    monkeypatch.setattr(module, 'publication_artifacts', lambda *args: {})
    def changed_replays(config):
        protected.write_bytes(b'changed after publication verification')
        return []
    def unexpected_close(*args):
        raise AssertionError('Closed with changed protected inputs')
    monkeypatch.setattr(module, 'recorded_replays', changed_replays)
    monkeypatch.setattr(feedback, 'close', unexpected_close)
    with pytest.raises(ValueError, match='Protected'):
        module.finish(args)
    assert not (args.project / '.eidos').exists()


def test_input_change_during_fetch_refuses_before_dynamic_helper_import(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import base64
    module, args, protected = completion(tmp_path, monkeypatch, 'VALIDATED')
    config = json.loads((args.workspace / 'campaign.json').read_bytes())
    wheel = args.workspace / 'candidate.whl'
    wheel.write_bytes(b'candidate')
    config.update(wheels={'new': str(wheel)}, protocol={'ci_workflows': ['ci', 'installed-sdk']})
    head, origin = 'b' * 40, 'a' * 40
    def fetched(url, output):
        if '/releases/tags/' in url:
            return {'assets': []}
        if '/git/ref/tags/' in url:
            return {'object': {'type': 'commit', 'sha': head}}
        if '/actions/runs?' in url:
            return {'workflow_runs': [{'name': name, 'head_sha': head, 'id': i,
                                      'status': 'completed', 'conclusion': 'success'}
                                     for i, name in enumerate(['ci', 'installed-sdk'])]}
        if '/contents/site/versions.json?' in url:
            return {'content': base64.b64encode(json.dumps([{'version': '0.5.0',
                                                             'source_commit': origin[:7]}]).encode()).decode()}
        if '/compare/' in url:
            protected.write_bytes(b'changed during ancestry fetch')
            return {'status': 'ahead', 'base_commit': {'sha': origin},
                    'merge_base_commit': {'sha': origin}, 'total_commits': 1,
                    'commits': [{'sha': head}]}
        raise AssertionError('Unexpected endpoint')
    def unexpected_import(*args):
        raise AssertionError('Dynamic helper imported with changed protected inputs')
    monkeypatch.setattr(module, 'fetch', fetched)
    monkeypatch.setattr(module, 'importlib', SimpleNamespace(util=SimpleNamespace(spec_from_file_location=unexpected_import)))
    with pytest.raises(ValueError, match='Protected'):
        module.publication_artifacts(config)
