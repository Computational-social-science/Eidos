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
