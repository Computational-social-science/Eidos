"""Shared workers use their own view; a card cannot run a legacy consumer gate."""
import json
import threading
import time

from test_worker_monitor import observation, registration


def worker_row(tmp_path):
    _, record = registration(tmp_path, 'a' * 32)
    value = observation(record)
    return {'project_id': record['project_id'], 'name': record['name'],
            'monitor_status': 'OBSERVED', 'scientific_status': 'PASS',
            'worker': value['worker'], 'run': value['run'], 'observed_at': value['observed_at']}


def test_worker_cards_show_separate_execution_science_and_runtime(tmp_path):
    from tools import dashboard
    row = worker_row(tmp_path)
    row['scientific_status'] = 'STALE'
    row['monitor_status'] = 'STALE'
    markup = dashboard.worker_strip({'projects': [row], 'registration_errors': []})
    assert 'Execution: PASS' in markup and 'Science: STALE' in markup
    assert 'EIDOS 0.5.0' in markup and '2026-11-01T00:00:00+00:00' in markup
    assert 'data-worker-id=' in markup and 'data-consumer=' not in markup and 'data-refresh=' not in markup


def test_worker_names_and_fields_are_html_escaped(tmp_path):
    from tools import dashboard
    row = worker_row(tmp_path)
    row['name'] = '<img src=x onerror=alert(1)>'
    row['reason'] = '<script>bad()</script>'
    row['worker']['eidos_version'] = '\"><svg onload=alert(2)>'
    markup = dashboard.worker_strip({'projects': [row], 'registration_errors': []})
    assert '<img' not in markup and '<script>' not in markup and '<svg' not in markup
    assert '&lt;img' in markup and '&lt;script&gt;' in markup


def test_no_enrollment_is_explicit_and_does_not_claim_scientific_success():
    from tools import dashboard
    markup = dashboard.worker_strip(None)
    assert 'No project workers enrolled' in markup
    assert 'Science: PASS' not in markup


def test_observer_failure_withdraws_previous_effective_science(tmp_path, monkeypatch):
    from tools import serve_site
    row = worker_row(tmp_path)
    monkeypatch.setitem(serve_site.STATE, 'worker_observations', {'projects': [row], 'registration_errors': []})

    class BrokenObserver:
        def poll(self):
            raise OSError('private filesystem failure text')

    serve_site.refresh_worker_observations(BrokenObserver())
    value = serve_site.worker_view()
    assert value['projects'][0]['scientific_status'] != 'PASS'
    assert 'private filesystem failure text' not in json.dumps(value)


def test_stale_central_sample_cannot_keep_worker_science_green(tmp_path, monkeypatch):
    from tools import serve_site
    row = worker_row(tmp_path)
    monkeypatch.setitem(serve_site.STATE, 'worker_observations', {'projects': [row], 'registration_errors': []})
    monkeypatch.setitem(serve_site.STATE, 'worker_sampled', time.time() - 600)
    monkeypatch.setitem(serve_site.STATE, 'interval', 15)
    value = serve_site.worker_view()
    assert value['projects'][0]['monitor_status'] == 'STALE'
    assert value['projects'][0]['scientific_status'] == 'STALE'
    assert row['scientific_status'] == 'PASS'  # Historical object was not mutated.


def test_stopped_sampler_closes_its_owned_observer(monkeypatch):
    from tools import serve_site, worker_monitor
    stop = threading.Event()
    stop.set()
    closed = []

    class Observer:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

    monkeypatch.setattr(worker_monitor, 'WorkerMonitor', Observer)
    serve_site.sampler(15, 60, stop_event=stop)
    assert closed == [True]


def test_port_bind_failure_cannot_start_a_second_sampler(monkeypatch):
    from tools import serve_site

    def absent(*args, **kwargs):
        raise OSError('No preexisting listener')

    def bind_failed(*args, **kwargs):
        raise OSError('Port was claimed after the advisory probe')

    def forbidden(*args, **kwargs):
        raise AssertionError('A sampler must not start without owning its HTTP port')

    monkeypatch.setattr(serve_site.socket, 'create_connection', absent)
    monkeypatch.setattr(serve_site, 'ThreadingHTTPServer', bind_failed)
    monkeypatch.setattr(serve_site.threading, 'Thread', forbidden)
    assert serve_site.main(['--port', '18765']) == 2


def test_cached_page_cannot_restore_pass_after_observer_failure(tmp_path, monkeypatch):
    from tools import serve_site, dashboard
    value = {'projects': [worker_row(tmp_path)], 'registration_errors': []}
    page = '<html><!-- worker-observations:start -->' + dashboard.worker_strip(value) + '<!-- worker-observations:end --></html>'
    assert 'Science: PASS' in page
    monkeypatch.setitem(serve_site.STATE, 'worker_observations', value)

    class BrokenObserver:
        def poll(self):
            raise ValueError('failed aggregation')

    serve_site.refresh_worker_observations(BrokenObserver())
    rendered = serve_site.current_page_html(page)
    assert 'Science: STALE' in rendered and 'Science: PASS' not in rendered
