"""Central observation must remain responsive and never promote stale workers."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import stat
import threading
import time

import pytest


def registration(root, project_id):
    worker = {'python': sys.version, 'executable': str(Path(sys.executable).resolve()),
              'eidos_version': '0.5.0', 'distributions_sha256': 'a' * 64,
              'prefix': str(root / ('env-' + project_id[:1])),
              'sdk_source_sha256': 'b' * 64, 'sdk_module_count': 50, 'installation_mode': 'installed'}
    value = {'schema': 'eidos.monitor-registration.v1', 'project_id': project_id,
             'name': 'same_name', 'project_root': str(root / project_id),
             'python': sys.executable, 'expected_worker': worker}
    path = root / '.eidos-monitor/registrations' / (project_id + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, value


def observation(record):
    return {'schema': 'eidos.worker-observation.v1', 'status': 'OBSERVED',
            'project': {'id': record['project_id'], 'name': record['name'], 'root': record['project_root']},
            'worker': record['expected_worker'].copy(), 'observed_at': datetime.now(timezone.utc).isoformat(),
            'binding': {'state': 'STABLE'}, 'scientific_status': 'PASS',
            'run': {'run_id': 'c' * 32, 'recorded_at': '2026-11-01T00:00:00+00:00',
                    'eidos_version': '0.5.0', 'input_digest': 'd' * 64,
                    'status': 'PASS', 'execution_status': 'PASS', 'scientific_status': 'PASS'}}


def until(observer, predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = observer.poll()
        if predicate(value):
            return value
        time.sleep(.01)
    raise AssertionError('Expected worker observation did not arrive')


def test_two_workers_are_isolated_and_observation_preserves_scientific_time(tmp_path, monkeypatch):
    from tools import worker_monitor
    records = [registration(tmp_path, character * 32)[1] for character in ('a', 'b')]
    by_path = {item['project_root']: item for item in records}
    calls = []

    def query(project, python, timeout):
        calls.append((str(project), str(python)))
        return observation(by_path[str(project)])

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: len(value['projects']) == 2 and all(row['monitor_status'] == 'OBSERVED' for row in value['projects']))
        assert len(calls) == 2
        assert len({row['project_id'] for row in value['projects']}) == 2
        assert all(row['run']['recorded_at'] == '2026-11-01T00:00:00+00:00' for row in value['projects'])
        assert len({row['worker']['prefix'] for row in value['projects']}) == 2


def test_blocked_worker_does_not_block_poll_or_another_worker(tmp_path, monkeypatch):
    from tools import worker_monitor
    records = [registration(tmp_path, character * 32)[1] for character in ('a', 'b')]
    by_path = {item['project_root']: item for item in records}
    entered, release = threading.Event(), threading.Event()

    def query(project, python, timeout):
        if str(project) == records[0]['project_root']:
            entered.set()
            release.wait(5)
            raise ValueError('private worker error')
        return observation(by_path[str(project)])

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    observer = worker_monitor.WorkerMonitor(tmp_path, max_workers=2)
    try:
        observer.poll()
        assert entered.wait(2)
        value = until(observer, lambda value: any(row['monitor_status'] == 'OBSERVED' for row in value['projects']))
        assert {row['monitor_status'] for row in value['projects']} == {'PENDING', 'OBSERVED'}
        release.set()
        value = until(observer, lambda value: any(row['monitor_status'] == 'UNAVAILABLE' for row in value['projects']))
        assert 'private worker error' not in json.dumps(value)
    finally:
        release.set()
        observer.close()


def test_runtime_pin_mismatch_withdraws_scientific_acceptance(tmp_path, monkeypatch):
    from tools import worker_monitor
    _, record = registration(tmp_path, 'a' * 32)

    def query(*args, **kwargs):
        value = observation(record)
        value['worker']['sdk_source_sha256'] = 'f' * 64
        return value

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] != 'PENDING')
        row = value['projects'][0]
        assert row['monitor_status'] == 'STALE' and row['scientific_status'] == 'STALE'
        assert row['run']['scientific_status'] == 'PASS'  # historical reference, not effective acceptance


def test_registration_changed_in_flight_cannot_publish_old_acceptance(tmp_path, monkeypatch):
    from tools import worker_monitor
    path, record = registration(tmp_path, 'a' * 32)

    def query(*args, **kwargs):
        changed = json.loads(path.read_text(encoding='utf-8'))
        changed['expected_worker']['sdk_source_sha256'] = 'f' * 64
        path.write_text(json.dumps(changed), encoding='utf-8')
        return observation(record)

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] == 'STALE')
        assert value['projects'][0]['scientific_status'] != 'PASS'


def test_removed_registration_cannot_leave_a_green_project(tmp_path, monkeypatch):
    from tools import worker_monitor
    path, record = registration(tmp_path, 'a' * 32)
    monkeypatch.setattr(worker_monitor, 'query_worker', lambda *args, **kwargs: observation(record))
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] == 'OBSERVED')
        path.unlink()
        assert observer.poll()['projects'] == []


def test_malformed_registration_does_not_hide_a_valid_worker(tmp_path, monkeypatch):
    from tools import worker_monitor
    _, record = registration(tmp_path, 'a' * 32)
    path, _ = registration(tmp_path, 'b' * 32)
    path.write_text('{broken', encoding='utf-8')
    monkeypatch.setattr(worker_monitor, 'query_worker', lambda *args, **kwargs: observation(record))
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] == 'OBSERVED')
        assert value['registration_errors'] and len(value['projects']) == 1


def test_collector_filters_unknown_worker_payload_fields(tmp_path, monkeypatch):
    from tools import worker_monitor
    _, record = registration(tmp_path, 'a' * 32)

    def query(*args, **kwargs):
        value = observation(record)
        value['private_log'] = 'private marker'
        value['worker']['private_env'] = 'private marker'
        value['run']['stdout'] = 'private marker'
        return value

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] == 'OBSERVED')
        assert 'private marker' not in json.dumps(value)


def test_delayed_completed_observation_does_not_get_a_fresh_verdict(tmp_path, monkeypatch):
    from tools import worker_monitor
    _, record = registration(tmp_path, 'a' * 32)

    def query(*args, **kwargs):
        value = observation(record)
        value['observed_at'] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        return value

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] != 'PENDING')
        assert value['projects'][0]['monitor_status'] == 'STALE'
        assert value['projects'][0]['scientific_status'] == 'STALE'


def test_due_workers_cannot_starve_projects_waiting_for_first_observation(tmp_path, monkeypatch):
    from tools import worker_monitor
    records = [registration(tmp_path, character * 32)[1] for character in ('a', 'b', 'c')]
    by_path = {item['project_root']: item for item in records}
    calls = []

    def query(project, *args, **kwargs):
        calls.append(str(project))
        return observation(by_path[str(project)])

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path, max_workers=1, interval=.0001) as observer:
        until(observer, lambda value: len(calls) >= 3)
        assert len(set(calls[:3])) == 3


def test_registry_parent_rebound_outside_control_root_is_refused(tmp_path, monkeypatch):
    from tools import worker_monitor
    control, external = tmp_path / 'control', tmp_path / 'external'
    _, record = registration(external, 'a' * 32)
    calls = []
    monkeypatch.setattr(worker_monitor, 'query_worker', lambda *args, **kwargs: calls.append(args) or observation(record))
    with worker_monitor.WorkerMonitor(control) as observer:
        observer.folder.parent.mkdir(parents=True)
        try:
            observer.folder.symlink_to(external / '.eidos-monitor/registrations', target_is_directory=True)
        except OSError as error:
            pytest.skip('Host cannot create registry symlink control: ' + type(error).__name__)
        with pytest.raises(ValueError, match='escapes'):
            observer.poll()
        assert not calls


def test_special_registration_file_is_rejected_before_read(tmp_path, monkeypatch):
    from tools import worker_monitor
    from types import SimpleNamespace
    path, _ = registration(tmp_path, 'a' * 32)
    original_stat = Path.stat
    original_read = Path.read_bytes
    reads = []

    def special(selected, *args, **kwargs):
        if selected == path:
            return SimpleNamespace(st_mode=stat.S_IFIFO, st_size=0, st_dev=1, st_ino=1)
        return original_stat(selected, *args, **kwargs)

    def read(selected, *args, **kwargs):
        if selected == path:
            reads.append(selected)
            raise AssertionError('Reading a special registration can block the sampler')
        return original_read(selected, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', special)
    monkeypatch.setattr(Path, 'read_bytes', read)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = observer.poll()
        assert value['registration_errors'] and not reads


def test_nonfinite_worker_metadata_cannot_break_other_projects(tmp_path, monkeypatch):
    from tools import worker_monitor
    records = [registration(tmp_path, character * 32)[1] for character in ('a', 'b')]
    by_path = {item['project_root']: item for item in records}

    def query(project, *args, **kwargs):
        value = observation(by_path[str(project)])
        if str(project) == records[0]['project_root']:
            value['run']['recorded_at'] = float('nan')
        return value

    monkeypatch.setattr(worker_monitor, 'query_worker', query)
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: len(value['projects']) == 2 and all(row['monitor_status'] != 'PENDING' for row in value['projects']))
        assert {row['monitor_status'] for row in value['projects']} == {'UNAVAILABLE', 'OBSERVED'}


def test_deep_json_registration_is_isolated_from_valid_workers(tmp_path, monkeypatch):
    from tools import worker_monitor
    _, record = registration(tmp_path, 'a' * 32)
    path, _ = registration(tmp_path, 'b' * 32)
    path.write_text('[' * 10000 + '0' + ']' * 10000, encoding='utf-8')
    monkeypatch.setattr(worker_monitor, 'query_worker', lambda *args, **kwargs: observation(record))
    with worker_monitor.WorkerMonitor(tmp_path) as observer:
        value = until(observer, lambda value: value['projects'] and value['projects'][0]['monitor_status'] == 'OBSERVED')
        assert len(value['projects']) == 1 and value['registration_errors']
