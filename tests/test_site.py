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
    "meta": {"version": "0.0.0-test"},
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


def test_render_has_eight_sections_and_resolving_nav():
    page = build_site.render(DATA)
    assert page.count("<section") == 8
    ids = set(re.findall(r'<section id="([^"]+)"', page))
    hrefs = set(re.findall(r'<nav class="toc"[^>]*>(.*?)</nav>', page, re.S)[0]
                and re.findall(r'href="#([^"]+)"', re.findall(
                    r'<nav class="toc"[^>]*>(.*?)</nav>', page, re.S)[0]))
    assert hrefs == ids, f"nav/href mismatch: {hrefs ^ ids}"


def test_render_carries_captions_math_and_the_demo_data():
    page = build_site.render(DATA)
    assert page.count("<caption") == page.count("<table") >= 4
    assert page.count("<math") >= 3
    assert "const ROWS = [" in page
    assert "demo" in page.lower()
