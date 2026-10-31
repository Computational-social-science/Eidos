"""Immutable controls age independently of their current verification."""
import json
from datetime import datetime, timezone, timedelta


def test_negative_control_uses_a_real_recent_check_not_fixture_mtime(tmp_path):
    from tools.dashboard import consumer_strip
    (tmp_path/'docs').mkdir()
    old=(datetime.now(timezone.utc)-timedelta(hours=40)).isoformat()
    (tmp_path/'docs/evidence.json').write_text(json.dumps({'generated':old}),encoding='utf-8')
    html=consumer_strip({'consumers':[{'name':'prose_lie','root':str(tmp_path),'gate_s':'FAIL',
        'expected':'FAIL','checked_at':datetime.now(timezone.utc).isoformat(),'role':'negative control'}]})
    assert 'data-stale' not in html
    assert 'Expected rejection' in html


def test_oldest_consumer_cannot_be_hidden_by_a_fresh_one():
    from framework.project import aggregate_consumer_freshness
    result=aggregate_consumer_freshness([('fresh',1.0),('stale',30.0)])
    assert result['age_h']==30 and result['stale']==['stale']


def test_missing_negative_control_check_is_not_a_pass(tmp_path):
    from framework.project import consumer_freshness
    assert consumer_freshness(tmp_path,'FAIL',None)['stale'] is True


def test_consumer_cards_do_not_scale_seven_labels_into_one_svg():
    from tools.dashboard import consumer_strip
    html=consumer_strip({'consumers':[{'name':f'consumer_{n}','gate_s':'PASS','expected':'PASS','root':'missing'} for n in range(7)]})
    assert 'consumer-grid' in html and '<svg' not in html
    assert html.count('class="node consumer consumer-card"')==7


def test_refresh_does_not_claim_success_when_registry_rebuild_failed(monkeypatch):
    import types
    import subprocess
    from tools import serve_site
    import framework.project as project
    spec=types.SimpleNamespace(available=True,gate_command=['python','gate.py'],root='missing',expected_gate_s='FAIL')
    monkeypatch.setattr(project,'load_projects',lambda:{'negative':spec})
    monkeypatch.setattr(project,'run_command',lambda *a,**k:types.SimpleNamespace(status='FAIL',stdout_tail='expected rejection'))
    monkeypatch.setattr(serve_site.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,2,'','rebuild failed'))
    assert serve_site.refresh_project('negative')['ok'] is False


def test_responsive_consumer_grid_keeps_text_readable():
    import pytest
    playwright=pytest.importorskip('playwright.sync_api')
    from tools import dashboard
    from tools.browser import launch
    cards=dashboard.consumer_strip({'consumers':[{'name':f'consumer_with_a_long_name_{n}','gate_s':'PASS','expected':'PASS','root':'missing'} for n in range(7)]})
    with playwright.sync_playwright() as p:
        browser=launch(p);page=browser.new_page()
        page.set_content(f'<style>{dashboard.CSS}</style>{cards}')
        for width,columns in ((1440,3),(900,2),(375,1)):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            tops=page.locator('.consumer-card').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().top)')
            assert len(set(tops[:columns]))==1 and tops[columns]>tops[0]
            assert page.locator('.consumer-head strong').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')>=12
        browser.close()
