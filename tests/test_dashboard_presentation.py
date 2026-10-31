"""State transitions must remain truthful on a page that stays open."""
import datetime
import json
import shutil
import subprocess

import pytest

from tools import dashboard as dash


def sample(**changes):
    return {
        'ts': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'seq': 1, 'chains': {'gates': 'PASS'},
        'signals': {'quarto': {'state': 'OK'}}, **changes,
    }


@pytest.mark.parametrize('changes, expected', [
    ({'ts': '2000-01-01T00:00:00+00:00'}, 'STALE'),
    ({'stale': True}, 'STALE'),
    ({'chains': {'gates': 'ERROR'}}, 'ALARM'),
    ({'chains': {'gates': 'unrecognised'}}, 'ALARM'),
    ({'signals': {'quarto': {}}}, 'ALARM'),
    ({'server_error': 'sampler unavailable'}, 'ALARM'),
    ({'overall': 'ALARM'}, 'ALARM'),
    ({'consistency': {'ok': False}}, 'ALARM'),
    ({'derived': {'overall': 'OK'}, 'chains': {'gates': 'FAIL'}}, 'ALARM'),
    ({'chains': {'gates': 'SKIP'}}, 'OK'),
])
def test_display_guard_rejects_false_green(changes, expected):
    assert dash.observation_status(sample(**changes))['overall'] == expected


def test_empty_observation_is_not_a_healthy_pipeline():
    assert dash.observation_status({})['overall'] == 'UNKNOWN'


def test_future_dated_sample_cannot_make_sampler_box_green():
    stamp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()
    page = dash.operator_strip(sample(ts=stamp), [])
    assert 'self-check · sample · STALE' in page
    assert 'record · PASS' not in page


def test_missing_required_service_remains_visible_as_unobserved():
    svg, _, _ = dash.topology(
        {'chain_modules': {'q': ['framework.quarto_bridge']}}, {'q': 'PASS'}, {}, {}, 0)
    assert "data-service='quarto'" in svg
    assert "data-service-state='quarto'" in svg
    assert 'UNOBSERVABLE' in svg
    assert f"fill='{dash.PALETTE['STALE']}'" in svg


def test_control_success_and_stale_verdict_are_not_promoted(monkeypatch):
    import framework.project
    fresh = {'age_h': 0.1, 'stale': False, 'source': 'verification'}
    monkeypatch.setattr(framework.project, 'consumer_freshness', lambda *args: fresh)
    row = {'name': 'negative', 'root': '.', 'gate_s': 'FAIL', 'expected': 'FAIL', 'role': 'control'}
    page = dash.consumer_strip({'consumers': [row]})
    assert 'CONTROL OK' in page and 'Gate S FAIL' in page
    fresh['stale'] = True
    page = dash.consumer_strip({'consumers': [row]})
    assert 'Reverification required' in page and 'Cached Gate S FAIL' in page
    assert 'CONTROL OK' not in page


def test_failed_recovery_does_not_count_as_healed(monkeypatch, tmp_path):
    monkeypatch.setattr(dash, 'STATUS', tmp_path)
    (tmp_path / 'recoveries.jsonl').touch()
    rows = [{'phase': 'verified', 'outcome': 'gave_up', 'ok': False,
             'ts': datetime.datetime.now(datetime.timezone.utc).isoformat()}]
    page = dash.operator_strip({'derived': {'faults': []}}, rows)
    assert '0 healed' in page and '1 healed' not in page


@pytest.mark.parametrize('rows', [
    [{'phase': 'verified', 'outcome': 'recovered'}, {'phase': 'attempt', 'ok': True}],
    [{'phase': 'attempt', 'service': 'a', 'ok': True},
     {'phase': 'verified', 'service': 'b', 'outcome': 'recovered'}],
])
def test_older_or_unrelated_terminal_event_cannot_verify_new_attempt(rows):
    page = dash.operator_strip({'derived': {'faults': ['a = DOWN']}}, rows)
    assert 'verify · RUNNING' in page and 'verify · PASS' not in page


def test_browser_poll_repaints_dependencies_and_fails_closed(tmp_path):
    """Execute the shipped JS against DOM doubles; exercise transitions, not source strings."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required to execute the dashboard client contract')
    client = tmp_path / 'client.js'
    client.write_text(dash.JS.replace('__PALETTE__', json.dumps(dash.PALETTE)), encoding='utf-8')
    runner = tmp_path / 'check.cjs'
    runner.write_text(r'''
const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
const el = (dataset = {}) => ({dataset, textContent: '', innerHTML: '', className: '',
  attrs: {}, style: {}, classList: {add() {}, toggle() {}},
  setAttribute(k, v) { this.attrs[k] = v; }, addEventListener() {}, querySelector() { return null; }});
const ids = Object.fromEntries(['ov','meta','faults','chain-summary','chain-detail','boundary-summary',
  'live','livetext','observation-note'].map(k => [k, el()]));
const dot = el(), cell = el({chainState: 'gates'}), serviceCell = el({serviceState: 'quarto'});
const title = el(), age = el(), header = el(), serviceTitle = el();
const chain = el({chain: 'gates'});
chain.querySelector = q => ({circle: dot, title, '[data-chain-age]': age})[q] || null;
const service = el({service: 'quarto'});
service.querySelector = q => ({text: header, title: serviceTitle})[q] || null;
const groups = {'g.node.chain': [chain], '[data-chain-state]': [cell],
  'g.node.service': [service], '[data-service-state]': [serviceCell]};
const context = vm.createContext({Date, AbortSignal,
  document: {getElementById: k => ids[k] || null, querySelectorAll: q => groups[q] || [],
    addEventListener() {}, body: el()}, location: {protocol: 'file:'},
  fetch: async () => { throw new Error('connection refused'); }});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const d = {ts: new Date().toISOString(), seq: 1, chains: {gates: 'PASS'},
  chain_meta: {gates: {age_s: 12, detail: 'new sample'}}, signals: {quarto: {state: 'OK'}}};
context.applySample(d);
assert.equal(dot.attrs.fill, cell.attrs.fill);
assert.equal(cell.attrs.fill, '#57ab5a');
assert.equal(serviceCell.attrs.fill, '#57ab5a');
d.seq = 2; d.chains.gates = 'FAIL'; d.signals.quarto.state = 'UNOBSERVABLE';
context.applySample(d);
assert.equal(dot.attrs.fill, '#e5534b'); assert.equal(cell.attrs.fill, '#e5534b');
assert.equal(serviceCell.attrs.fill, '#d29922'); assert.equal(header.attrs.fill, '#d29922');
assert.match(title.textContent, /FAIL/); assert.equal(age.textContent, '12s');
assert.equal(ids.ov.textContent, 'ALARM'); assert.equal(ids['boundary-summary'].textContent, '0/1 observed OK');
assert.equal(context.sampleView({...d, signals: {}, chains: {} }).overall, 'UNKNOWN');
d.seq = 3; d.chains.gates = 'PASS'; d.signals.quarto.state = 'OK'; context.applySample(d);
vm.runInContext('lastAdvanceAt = Date.now() - 46000', context);
context.applySample(d);
assert.equal(ids.ov.textContent, 'STALE'); assert.equal(ids.live.className, 'off');
d.seq = 4; context.applySample(d); assert.equal(ids.ov.textContent, 'OK');
d.seq = 1; context.applySample(d); assert.equal(ids.ov.textContent, 'STALE');
(async () => {
  await context.poll();
  assert.equal(ids.ov.textContent, 'UNAVAILABLE'); assert.equal(ids.live.className, 'off');
  assert.match(ids['observation-note'].textContent, /cached/);
  process.stdout.write('state transitions and unavailable transport: PASS');
})().catch(e => { console.error(e); process.exitCode = 1; });
''', encoding='utf-8')
    result = subprocess.run([node, str(runner), str(client)], capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
