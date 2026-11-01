"""Actual compiler/replay CLI controls, without any model generation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from reference.numerical_method_tools import compiler, runner


def response_file(tmp_path, program=None, raw=None):
    if raw is None:
        raw = json.dumps({'program': program or {'loss': {'input': 'x'}, 'gradient': {'const': 0}},
                          'explanation': 'Synthetic negative control, not a model response.'})
    path = tmp_path/'response.json'
    path.write_text(json.dumps({'choices': [{'message': {'content': raw}}]}), encoding='utf-8')
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_separate_repair_preserves_failed_proposal(tmp_path):
    source, digest = response_file(tmp_path)
    output = tmp_path/'run'
    result = runner.run(source, digest, 'log1mexp-v1', output)
    assert result['proposal']['joint_points'] == 0
    assert result['tool']['joint_points'] == 23
    assert result['tool']['accepted'] is True
    assert result['scientific_rsi'] == 'NOT_DEMONSTRATED'
    assert result['new_model_inference'] is False
    assert (output/'response.json').read_bytes() == source.read_bytes()
    assert runner.verify(output)['tool']['accepted'] is True


def test_malformed_content_has_no_invented_numeric_zero(tmp_path):
    source, digest = response_file(tmp_path, raw='not a valid proposal')
    result = runner.run(source, digest, 'log1mexp-v1', tmp_path/'run')
    assert result['proposal']['status'] == 'INVALID_RESPONSE'
    assert result['proposal']['joint_points'] is None
    assert result['proposal']['points_evaluated'] == 0


@pytest.mark.parametrize('gradient', ['-exp(-x)/(-expm1(-x))', '0', 'exp(-x)/(1-exp(-x))'])
def test_wrong_derivatives_cannot_pass(gradient):
    method = compiler.load_method('log1mexp-v1')
    tree = compiler.compile_formulas(method['loss'], gradient)
    scored = runner.assess(json.dumps({'program': tree, 'explanation': 'Broken control'}))
    assert scored['summary']['accepted'] is False
    assert scored['summary']['joint_points'] < 23


def test_source_change_and_wrong_hash_do_not_publish(tmp_path, monkeypatch):
    source, digest = response_file(tmp_path)
    with pytest.raises(ValueError): runner.run(source, '0'*64, 'log1mexp-v1', tmp_path/'wrong')
    assert not (tmp_path/'wrong').exists()
    original = runner.source_snapshot
    calls = []
    def changing():
        value = original()
        calls.append(None)
        if len(calls) > 1: value['uv.lock'] = '0'*64
        return value
    monkeypatch.setattr(runner, 'source_snapshot', changing)
    with pytest.raises(ValueError): runner.run(source, digest, 'log1mexp-v1', tmp_path/'changed')
    assert not (tmp_path/'changed').exists()


def test_existing_destination_and_input_alias_refused(tmp_path):
    source, digest = response_file(tmp_path)
    for destination in (source, tmp_path):
        with pytest.raises((FileExistsError, ValueError)):
            runner.run(source, digest, 'log1mexp-v1', destination)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_input_changed_during_publication_has_no_terminal_success(tmp_path, monkeypatch):
    source, digest = response_file(tmp_path)
    original = Path.open
    output = tmp_path/'run'
    def changing(path, *args, **kwargs):
        if path == output/'tool-evaluation.json':
            source.write_bytes(b'changed after evaluation')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', changing)
    with pytest.raises(ValueError, match='during publication'):
        runner.run(source, digest, 'log1mexp-v1', output)
    assert output.exists() and not (output/'record.json').exists()


def test_reference_convergence_failure_cannot_publish(tmp_path, monkeypatch):
    source, digest = response_file(tmp_path)
    original = runner.grader.reference
    def divergent(case, precision=420):
        value = original(case, precision=precision)
        if precision == 520: value['loss'] *= 2
        return value
    monkeypatch.setattr(runner.grader, 'reference', divergent)
    with pytest.raises(ValueError, match='convergence'):
        runner.run(source, digest, 'log1mexp-v1', tmp_path/'run')
    assert not (tmp_path/'run').exists()


def test_source_change_during_verify_is_refused(tmp_path, monkeypatch):
    source, digest = response_file(tmp_path)
    output = tmp_path/'run'
    runner.run(source, digest, 'log1mexp-v1', output)
    original = runner.source_snapshot
    calls = []
    def changing():
        value = original()
        calls.append(None)
        if len(calls) > 1: value['uv.lock'] = '0'*64
        return value
    monkeypatch.setattr(runner, 'source_snapshot', changing)
    with pytest.raises(ValueError, match='during verification'): runner.verify(output)


def test_payload_changed_during_publication_has_no_terminal_receipt(tmp_path, monkeypatch):
    source, digest = response_file(tmp_path)
    output = tmp_path/'run'
    original = Path.open
    def changing(path, *args, **kwargs):
        # The first source snapshot is written after the evaluation payloads.
        if path.suffix == '.snapshot' and (output/'proposal-evaluation.json').exists():
            with original(output/'proposal-evaluation.json', 'wb') as stream:
                stream.write(b'changed while later files were being published')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', changing)
    with pytest.raises(ValueError, match='Published payload differs'):
        runner.run(source, digest, 'log1mexp-v1', output)
    assert not (output/'record.json').exists()


def test_payload_changed_during_verify_is_refused(tmp_path, monkeypatch):
    source, digest = response_file(tmp_path)
    output = tmp_path/'run'
    runner.run(source, digest, 'log1mexp-v1', output)
    original = runner.assess
    def changing(raw):
        result = original(raw)
        (output/'source/uv.lock.snapshot').write_bytes(b'changed after initial verification')
        return result
    monkeypatch.setattr(runner, 'assess', changing)
    with pytest.raises(ValueError, match='during verification'): runner.verify(output)


@pytest.mark.parametrize('kind', ['raw', 'core', 'program', 'inventory', 'coherent_fake_score',
                                 'core_status', 'core_sources', 'core_prompt', 'typed_verdict'])
def test_altered_receipt_cannot_verify(tmp_path, kind):
    source, digest = response_file(tmp_path)
    output = tmp_path/'run'
    runner.run(source, digest, 'log1mexp-v1', output)
    receipt = json.loads((output/'record.json').read_bytes())
    if kind == 'raw': (output/'response.json').write_text('{}', encoding='utf-8')
    elif kind == 'core': (output/'tool-evaluation.json').write_text('{}', encoding='utf-8')
    elif kind == 'program': (output/'method-program.json').write_text('{}', encoding='utf-8')
    elif kind == 'inventory': (output/'unlisted.txt').write_text('unexpected', encoding='utf-8')
    elif kind == 'coherent_fake_score':
        receipt['tool']['joint_points'] = 22
        (output/'record.json').write_text(json.dumps(receipt), encoding='utf-8')
    elif kind == 'typed_verdict':
        receipt['tool']['accepted'] = 1
        (output/'record.json').write_text(json.dumps(receipt), encoding='utf-8')
    else:
        path = output/'proposal-evaluation.json'
        value = json.loads(path.read_bytes())
        if kind == 'core_status':
            value['core']['status'] = 'DEVELOPMENT_CONFORMING'
            value['core']['candidate_conforming_points'] = 23
        elif kind == 'core_sources': value['core']['source_after'] = {}
        else: value['core']['prompt'] = 'Fabricated task'
        path.write_text(json.dumps(value), encoding='utf-8')
        receipt['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (output/'record.json').write_text(json.dumps(receipt), encoding='utf-8')
    with pytest.raises(ValueError): runner.verify(output)


def test_actual_cli(tmp_path):
    source, digest = response_file(tmp_path)
    result = subprocess.run([sys.executable, '-m', 'reference.numerical_method_tools',
                             '--response', str(source), '--sha256', digest, '--method', 'log1mexp-v1',
                             '--output', str(tmp_path/'cli')], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['tool']['accepted'] is True
    verified = subprocess.run([sys.executable, '-m', 'reference.numerical_method_tools',
                               '--verify', str(tmp_path/'cli')], capture_output=True, text=True, timeout=30)
    assert verified.returncode == 0, verified.stderr
