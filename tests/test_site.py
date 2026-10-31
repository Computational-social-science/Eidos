"""The delivery page must be structurally complete and free of substitution tokens.

The page is generated, so the failure mode is not a typo but a missing substitution: a
token left in the HTML, a nav anchor pointing at a section that was renamed, or a table
that lost its caption. These are cheap to check and embarrassing to ship.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import build_site  # noqa: E402

DATA = {
    "meta": {"version": "0.0.0-test", "license": "MIT"},
    "decision": {"latency_ms": 182, "accuracy": 1.0, "abstain_answerable": 0.0,
                 "abstain_unanswerable": 1.0, "fisher_p": 2e-29,
                 "tau_identified": False, "min_conf": 0.54},
    "audit": {"tests_collected": 1, "coverage_total": 2},
    "chains": [{"chain": "gates", "status": "PASS", "detail": "ok"},
               {"chain": "decision", "status": "SKIP", "detail": "no service"}],
    "registry": [{"name": "proj", "root": "../proj", "gate": "['true']", "available": True}],
    "referee": {"total": 2, "open": 0},
    "lean": [{"target": "lean-nhb", "theorem": "t", "verdict": "PASS", "time": "2.7 s"}],
    "extra": {"rows": [{"lam": 0.1, "learned": 0.3, "truth": 0.316, "err": 0.05,
                        "inside": True}],
              "inside_max": 0.05, "outside_max": 0.9},
    "commit": "deadbee",
    "today": "2026-01-01",
}


def test_render_has_no_unsubstituted_tokens():
    page = build_site.render(DATA)
    assert not re.findall(r"__[A-Z_]+__", page), "a token survived substitution"


def test_every_section_has_a_nav_entry_and_the_nav_resolves():
    import site_page
    page = build_site.render(DATA)
    # The count is pinned to the navigation list, not to a number typed once: adding a section
    # without adding a rail entry (or the reverse) is a broken page.
    assert page.count("<section") == len(site_page.RAIL)
    ids = set(re.findall(r'<section[^>]*id="([^"]+)"', page))
    nav = re.findall(r'<nav class="rail"[^>]*>(.*?)</nav>', page, re.S)[0]
    hrefs = set(re.findall(r'href="#([^"]+)"', nav))
    assert hrefs == ids, f"nav/href mismatch: {hrefs ^ ids}"


def test_render_carries_captions_math_and_the_demo_data():
    page = build_site.render(DATA)
    assert page.count("<caption") == page.count("<table") >= 4
    assert page.count("<math") >= 3
    assert '<script id="demo-data" type="application/json">{' in page
    assert "demo" in page.lower()


def test_demo_is_self_contained():
    """The page must not depend on another file for its core content."""
    page = build_site.render(DATA)
    assert "lab/lab.html" not in page
    assert "iframe" not in page.lower()
    assert 'id="numerics-gradients"' in page
    assert 'id="numerics-regime"' in page
    assert "reports/numerics/evidence.json" in page


def test_page_states_the_whole_framework_not_only_gate_s():
    page = build_site.render(DATA).lower()
    for term in ("bootloops", "inspect", "deepeval", "promptfoo", "ragas", "startlux",
                 "mlflow", "dvc", "quarto", "bootstrap_project.sh", "cc by-nc"):
        assert term in page, f"missing positioning term: {term}"
