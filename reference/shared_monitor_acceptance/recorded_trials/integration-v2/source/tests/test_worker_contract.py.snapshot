"""Reject inconsistent observations before they can become central registrations."""
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_installed_cli import initialise, python_entry


def response_worker(monkeypatch, mutate):
    from framework import monitor_registry, worker_observation

    def invoke(command, **kwargs):
        project = Path(command[command.index('--project') + 1])
        nonce = command[command.index('--nonce') + 1]
        value = worker_observation.observe(project, nonce)
        value['operation'] = 'observe'
        mutate(value)
        value['observed_at'] = datetime.now(timezone.utc).isoformat()
        return subprocess.CompletedProcess(command, 0, json.dumps(value), '')

    monkeypatch.setattr(monitor_registry, 'run_tree', invoke)


def test_worker_timeout_is_structured_refusal_and_creates_no_registration(tmp_path, monkeypatch):
    from framework import monitor_registry
    project = tmp_path / 'study'
    initialise(project, tmp_path)

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 5, output='partial private output')

    monkeypatch.setattr(monitor_registry, 'run_tree', timeout)
    monitor = tmp_path / 'control'
    code, value = python_entry('enroll', '--project', str(project), '--monitor-root', str(monitor), '--json')
    assert code == 4 and value['status'] == 'REFUSED'
    assert 'partial private output' not in json.dumps(value)
    assert not monitor.exists()


def test_response_uuid_must_match_selected_workspace(tmp_path, monkeypatch):
    from framework.monitor_registry import query_worker
    project = tmp_path / 'study'
    initialise(project, tmp_path)
    response_worker(monkeypatch, lambda value: value['project'].update(id='0' * 32))
    with pytest.raises(ValueError, match='identity'):
        query_worker(project, Path(sys.executable))


@pytest.mark.parametrize('change', [
    {'status': 'invented'},
    {'execution_status': 'invented'},
    {'status': 'PASS', 'execution_status': 'FAIL', 'scientific_status': 'UNRUN'},
    {'status': 'PASS', 'execution_status': 'FAIL', 'scientific_status': 'PASS'},
    {'status': 'FAIL', 'execution_status': 'PASS', 'scientific_status': 'PASS'},
    *[{'status': 'PASS', 'execution_status': 'PASS', 'scientific_status': status}
      for status in ('FAIL', 'BLOCKED', 'REFUSED', 'OPEN', 'STALE')],
])
def test_invalid_or_contradictory_run_is_rejected(tmp_path, monkeypatch, change):
    from framework.monitor_registry import query_worker
    project = tmp_path / 'study'
    initialise(project, tmp_path)

    def mutate(value):
        value['run'].update(change)
        value['scientific_status'] = value['run']['scientific_status']

    response_worker(monkeypatch, mutate)
    with pytest.raises(ValueError, match='status|acceptance'):
        query_worker(project, Path(sys.executable))


def test_top_level_science_cannot_override_run(tmp_path, monkeypatch):
    from framework.monitor_registry import query_worker
    project = tmp_path / 'study'
    initialise(project, tmp_path)
    response_worker(monkeypatch, lambda value: value.update(scientific_status='PASS'))
    with pytest.raises(ValueError, match='status'):
        query_worker(project, Path(sys.executable))


def test_changed_binding_cannot_report_scientific_pass(tmp_path, monkeypatch):
    from framework.monitor_registry import query_worker
    project = tmp_path / 'study'
    initialise(project, tmp_path)

    def mutate(value):
        value['binding']['state'] = 'CHANGED'
        value['run'].update(status='PASS', execution_status='PASS', scientific_status='PASS')
        value['scientific_status'] = 'PASS'

    response_worker(monkeypatch, mutate)
    with pytest.raises(ValueError, match='status|acceptance'):
        query_worker(project, Path(sys.executable))


def test_changed_binding_cannot_report_execution_only_pass(tmp_path, monkeypatch):
    from framework.monitor_registry import query_worker
    project = tmp_path / 'study'
    initialise(project, tmp_path)

    def mutate(value):
        value['binding']['state'] = 'CHANGED'
        value['run'].update(status='PASS', execution_status='PASS', scientific_status='UNRUN')

    response_worker(monkeypatch, mutate)
    with pytest.raises(ValueError, match='status|acceptance'):
        query_worker(project, Path(sys.executable))


def test_containment_failure_does_not_disclose_worker_stderr(tmp_path, monkeypatch):
    from framework import monitor_registry
    from framework.subprocesses import ProcessContainmentError
    project = tmp_path / 'study'
    initialise(project, tmp_path)

    def failed(command, **kwargs):
        raise ProcessContainmentError('private worker stderr marker')

    monkeypatch.setattr(monitor_registry, 'run_tree', failed)
    code, value = python_entry('enroll', '--project', str(project), '--monitor-root', str(tmp_path / 'control'), '--json')
    assert code == 4 and value['status'] == 'REFUSED'
    assert 'private worker stderr marker' not in json.dumps(value)


def test_symlinked_interpreter_entry_is_preserved_for_launch(tmp_path, monkeypatch):
    from framework import monitor_registry, worker_observation
    project = tmp_path / 'study'
    initialise(project, tmp_path)
    executable = tmp_path / 'env' / ('Scripts' if os.name == 'nt' else 'bin') / Path(sys.executable).name
    executable.parent.mkdir(parents=True)
    try:
        executable.symlink_to(sys.executable)
    except OSError as error:
        pytest.skip('Host cannot create the interpreter symlink control: ' + type(error).__name__)
    (executable.parent.parent / 'pyvenv.cfg').write_text('home = local-test-fixture\n', encoding='utf-8')
    commands = []

    def invoke(command, **kwargs):
        commands.append(command)
        value = worker_observation.observe(project, command[command.index('--nonce') + 1])
        value['operation'] = 'observe'
        value['worker']['prefix'] = str(executable.parent.parent)
        return subprocess.CompletedProcess(command, 0, json.dumps(value), '')

    monkeypatch.setattr(monitor_registry, 'run_tree', invoke)
    monitor_registry.query_worker(project, executable)
    assert commands[0][0] == str(executable.absolute())


def test_venv_entry_requires_matching_worker_prefix(tmp_path, monkeypatch):
    from framework.monitor_registry import query_worker
    assert (Path(sys.executable).parent.parent / 'pyvenv.cfg').is_file()
    project = tmp_path / 'study'
    initialise(project, tmp_path)
    response_worker(monkeypatch, lambda value: value['worker'].update(prefix=str(tmp_path / 'other-env')))
    with pytest.raises(ValueError, match='prefix|environment'):
        query_worker(project, Path(sys.executable))


def test_framework_import_graph_has_no_worker_cli_cycle():
    from tools import audit_coupling as audit
    files = list((audit.ROOT / 'framework').rglob('*.py'))
    known = {audit.module_name(path) for path in files}
    edges = {}
    for path in files:
        name = audit.module_name(path)
        visitor = audit.Imports(name)
        visitor.visit(ast.parse(path.read_text(encoding='utf-8')))
        edges[name] = {resolved for target, _, _ in visitor.found
                       if (resolved := audit.resolve(target, known)) and resolved != name}
    assert audit.tarjan(sorted(known), edges) == []


@pytest.mark.parametrize('metadata', [
    {'recorded_at': float('nan')}, {'recorded_at': '2026-11-01T00:00:00'},
    {'run_id': '../other'}, {'input_digest': 42}, {'eidos_version': []},
    {'previous_status': 'invented'},
])
def test_invalid_run_metadata_is_refused_at_worker_protocol_boundary(tmp_path, monkeypatch, metadata):
    from framework.monitor_registry import query_worker
    project = tmp_path / 'study'
    initialise(project, tmp_path)
    response_worker(monkeypatch, lambda value: value['run'].update(metadata))
    with pytest.raises(ValueError, match='metadata|identity|timestamp|status|digest|version'):
        query_worker(project, Path(sys.executable))


def test_deep_worker_json_is_structured_refusal(tmp_path, monkeypatch):
    from framework import monitor_registry
    project = tmp_path / 'study'
    initialise(project, tmp_path)
    monkeypatch.setattr(monitor_registry, 'run_tree', lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, '[' * 10000 + '0' + ']' * 10000, ''))
    code, value = python_entry('enroll', '--project', str(project), '--monitor-root', str(tmp_path / 'control'), '--json')
    assert code == 4 and value['status'] == 'REFUSED'
