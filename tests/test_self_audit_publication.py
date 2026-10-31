"""The measured record and its headline documents must move together."""
from contextlib import contextmanager
import json

import pytest

from tools import record_self_audit


@pytest.fixture
def publication(tmp_path,monkeypatch):
    docs=tmp_path/'docs';docs.mkdir()
    out=docs/'SELF_AUDIT.json';out.write_text('{"old":true}')
    health=docs/'HEALTH.md'
    health.write_text('| unit tests | **5 collected**, 5 passed; old skips | ✅ |\n'
                      '| coverage of `framework/` | **60%** |\n'
                      '| chain audit | **11 chains: 10 PASS, 1 SKIP, 0 FAIL/ERROR** | ✅ |\n',encoding='utf-8')
    technical=tmp_path/'Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'
    technical.write_text('Historical v0.4.2: 642 passed.\n<!-- self-audit:start -->\n'
                         '本轮验收：5 passed、框架源码覆盖率 60%\n<!-- self-audit:end -->\n',encoding='utf-8')
    monkeypatch.setattr(record_self_audit,'ROOT',tmp_path)
    monkeypatch.setattr(record_self_audit,'OUT',out)
    return out,health,technical,{'tests_collected':7,'tests':{'passed':6,'skipped':2},'coverage_total':81,
                               'stability':{'execution':{'collection_level_skips':1}},
                               'chains':{'total':3,'pass':1,'skip':2,'fail':0}}


def test_record_updates_current_headlines_and_preserves_historical_results(publication):
    out,health,technical,record=publication
    record_self_audit.publish_record(record)
    assert json.loads(out.read_text())==record
    assert '**7 collected**, 6 passed;' in health.read_text(encoding='utf-8')
    assert '**81%**' in health.read_text(encoding='utf-8')
    assert '1 item skips, 1 collection-level' in health.read_text(encoding='utf-8')
    assert '**3 chains: 1 PASS, 2 SKIP, 0 FAIL/ERROR**' in health.read_text(encoding='utf-8')
    assert '本轮验收：6 passed、1 个用例 skipped、1 个可选模块收集 skipped，框架源码覆盖率 81%' in technical.read_text(encoding='utf-8')
    assert 'Historical v0.4.2: 642 passed.' in technical.read_text(encoding='utf-8')


def test_partial_publication_failure_restores_all_prior_documents(publication,monkeypatch):
    from framework import artifacts
    out,health,technical,record=publication
    before={p:p.read_bytes() for p in (out,health,technical)}
    original=artifacts.atomic_output;failed=False
    @contextmanager
    def failing(path):
        nonlocal failed
        if path==health and not failed:
            failed=True
            raise OSError('simulated document write failure')
        with original(path) as temporary:yield temporary
    monkeypatch.setattr(artifacts,'atomic_output',failing)
    with pytest.raises(OSError,match='simulated document write failure'):
        record_self_audit.publish_record(record)
    assert {p:p.read_bytes() for p in before}==before


def test_missing_headline_marker_cannot_publish_an_unsynchronized_record(publication):
    out,health,_,record=publication
    health.write_text('An unexpected document layout')
    old=out.read_bytes()
    with pytest.raises(ValueError,match='headline marker'):
        record_self_audit.publish_record(record)
    assert out.read_bytes()==old


def test_unmeasured_coverage_cannot_poison_existing_publication_markers(publication):
    out,health,technical,record=publication
    before={p:p.read_bytes() for p in (out,health,technical)}
    with pytest.raises(ValueError,match='coverage was not measured'):
        record_self_audit.publish_record({**record,'coverage_total':None})
    assert {p:p.read_bytes() for p in before}==before
