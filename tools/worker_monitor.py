"""Bounded, read-only project-worker aggregation for the existing local monitor."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
import uuid

from framework.artifacts import atomic_output
from framework.monitor_registry import (SCHEMA, WORKER_FIELDS, query_worker,
                                       registrations_dir, validate_run_metadata)
from framework.subprocesses import validate_timeout

RUN_FIELDS = ('run_id', 'recorded_at', 'eidos_version', 'status', 'execution_status',
              'scientific_status', 'previous_status', 'input_digest')


def _read_registration(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > 1024 * 1024:
        raise ValueError('Registration must be a bounded regular file')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError('Registration file identity changed')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            body = stream.read(1024 * 1024 + 1)
    finally:
        os.close(descriptor)
    if len(body) > 1024 * 1024:
        raise ValueError('Oversized registration')
    return body


def stale_view(value: dict | None, reason: str) -> dict:
    """Withdraw effective status while retaining historical run timestamps."""
    value = value or {}
    rows = [{**row, 'monitor_status': 'STALE', 'scientific_status': 'STALE', 'reason': reason}
            for row in value.get('projects', [])]
    return {**value, 'projects': rows, 'error': reason}


class WorkerMonitor:
    """One instance per monitor; poll never waits for a project subprocess.

    Each submitted query is bounded by the SDK process-tree timeout. The central
    cache is an observation, not an instruction to check, train or repair science.
    """

    def __init__(self, root: Path, *, max_workers: int = 4, interval: float = 30,
                 timeout: float = 5, stale_after: float = 90):
        if type(max_workers) is not int or not 1 <= max_workers <= 8:
            raise ValueError('Worker concurrency must be an integer from 1 to 8')
        for value in (interval, timeout, stale_after):
            validate_timeout(value)
        self.root = root.resolve()
        self.folder = registrations_dir(self.root)
        self.max_workers = max_workers
        self.interval = interval
        self.timeout = timeout
        self.stale_after = stale_after
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='project-observation')
        self._pending = {}
        self._rows = {}
        self._attempts = {}
        self._lock = threading.Lock()
        self._closed = False
        self._sequence = 0
        self._id = uuid.uuid4().hex

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _registrations(self):
        registrations_dir(self.root)  # Recheck parent binding on every poll.
        records, errors = {}, []
        for path in sorted(self.folder.glob('*.json')):
            try:
                if path.is_symlink() or not re.fullmatch('[0-9a-f]{32}', path.stem):
                    raise ValueError('Unsupported registration path')
                body = _read_registration(path)
                record = json.loads(body)
                if (not isinstance(record, dict) or record.get('schema') != SCHEMA
                        or record.get('project_id') != path.stem
                        or not isinstance(record.get('name'), str) or not record['name']
                        or not isinstance(record.get('expected_worker'), dict)
                        or any(key not in record['expected_worker'] for key in WORKER_FIELDS)):
                    raise ValueError('Invalid registration identity/pin')
                for field in ('project_root', 'python'):
                    if not isinstance(record.get(field), str) or not Path(record[field]).is_absolute():
                        raise ValueError('Worker paths must be explicit and absolute')
                records[path.stem] = (record, hashlib.sha256(body).hexdigest())
            except (OSError, ValueError, TypeError, RecursionError):
                errors.append({'registration': path.name, 'status': 'INVALID'})
        return records, errors

    @staticmethod
    def _base(record, digest):
        return {'project_id': record['project_id'], 'name': record['name'],
                'registration_sha256': digest, 'scientific_status': 'UNOBSERVABLE'}

    @staticmethod
    def _observation_age(stamp):
        observed = datetime.fromisoformat(stamp)
        if observed.tzinfo is None:
            raise ValueError('Worker timestamp requires a timezone')
        return (datetime.now(timezone.utc) - observed).total_seconds()

    def _result(self, record, digest, observation):
        row = self._base(record, digest)
        identity = observation['project']
        worker = {key: observation['worker'][key] for key in WORKER_FIELDS}
        run = {key: observation['run'][key] for key in RUN_FIELDS if key in observation['run']}
        validate_run_metadata(run)
        stable = (identity['id'] == record['project_id']
                  and identity['root'] == record['project_root']
                  and identity['name'] == record['name']
                  and worker == record['expected_worker']
                  and observation['binding']['state'] == 'STABLE'
                  and -30 <= self._observation_age(observation['observed_at']) <= self.stale_after)
        row.update(monitor_status='OBSERVED' if stable else 'STALE', worker=worker,
                   observed_at=observation['observed_at'], run=run,
                   scientific_status=run['scientific_status'] if stable else 'STALE')
        if not stable:
            row['reason'] = 'Worker identity/runtime/binding differs from its registration'
        json.dumps(row, allow_nan=False)  # A malformed worker cannot break the shared publication.
        return row

    def poll(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('Worker monitor is closed')
            registrations, errors = self._registrations()
            now = time.monotonic()
            for project_id, (future, record, digest) in list(self._pending.items()):
                if not future.done():
                    continue
                del self._pending[project_id]
                current = registrations.get(project_id)
                if current is None:
                    continue
                if current[1] != digest:
                    row = self._base(current[0], current[1])
                    row.update(monitor_status='STALE', scientific_status='STALE',
                               reason='Registration changed during worker observation')
                else:
                    try:
                        row = self._result(record, digest, future.result())
                    except Exception as error:
                        # Keep other projects observable; never relay arbitrary worker text.
                        row = self._base(record, digest)
                        row.update(monitor_status='UNAVAILABLE', reason='Worker observation failed: ' + type(error).__name__)
                self._rows[project_id] = row
                self._attempts[project_id] = (digest, now)
            for project_id in list(self._rows):
                if project_id not in registrations:
                    del self._rows[project_id]
                    self._attempts.pop(project_id, None)
            # Unseen projects precede repeats; oldest attempts precede newer ones.
            scheduled = sorted(registrations, key=lambda project_id:
                               (self._attempts.get(project_id, (None, -math.inf))[1], project_id))
            for project_id in scheduled:
                record, digest = registrations[project_id]
                if len(self._pending) >= self.max_workers:
                    break
                previous = self._attempts.get(project_id)
                if project_id not in self._pending and (
                        previous is None or previous[0] != digest or now - previous[1] >= self.interval):
                    future = self._executor.submit(query_worker, Path(record['project_root']),
                                                   Path(record['python']), timeout=self.timeout)
                    self._pending[project_id] = (future, record, digest)
            rows = []
            for project_id, (record, digest) in registrations.items():
                row = dict(self._rows.get(project_id, self._base(record, digest)))
                row.setdefault('monitor_status', 'PENDING')
                previous = self._attempts.get(project_id)
                old_observation = ('observed_at' in row and not
                                   -30 <= self._observation_age(row['observed_at']) <= self.stale_after)
                if old_observation or (previous and (
                        previous[0] != digest or now - previous[1] > self.stale_after)):
                    row.update(monitor_status='STALE', scientific_status='STALE',
                               reason='Observation expired or registration changed')
                rows.append(row)
            self._sequence += 1
            value = {'schema': 'eidos.worker-monitor.v1', 'observer_id': self._id,
                     'seq': self._sequence, 'sampled_at': datetime.now(timezone.utc).isoformat(),
                     'projects': rows, 'registration_errors': errors,
                     'scope': 'Read-only local worker observations; no research execution or scientific acceptance beyond referenced runs'}
            output = self.root / '.eidos-monitor/observations.json'
            if rows or errors or output.exists():
                with atomic_output(output) as temporary:
                    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            return value
