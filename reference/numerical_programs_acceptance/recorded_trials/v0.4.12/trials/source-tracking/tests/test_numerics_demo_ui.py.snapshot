"""The scientific showcase selects filed evidence; it does not calculate kernels."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import site_page


def payload():
    return {
        "paper": "https://arxiv.org/html/2610.31642v3",
        "paper_version": "2610.31642v3",
        "scope": "Numerical kernels only; no training reproduction.",
        "qualification": {"verdict": "PASS", "cases": [], "negative_controls": []},
        "collapse": [{
            "dtype": "float32", "margin": 18, "standard_loss": 0,
            "fixed_loss": 3.046e-8, "standard_gradient": [0, 1.523e-8, 1.523e-8],
            "fixed_gradient": [-3.046e-8, 1.523e-8, 1.523e-8],
            "reference_gradient": ["-3.046e-8", "1.523e-8", "1.523e-8"],
            "standard_error": 0.8165, "fixed_error": 1e-8,
            "standard_residual": 3.046e-8, "fixed_residual": 0,
        }],
        "cancellation": [],
        "downloads": {
            "report": "reports/numerics/report.html", "json": "reports/numerics/evidence.json",
            "csv": "reports/numerics/cases.csv", "bundle": "reports/numerics/reproduce.zip",
            "pdf": "reports/numerics/report.pdf", "docx": "reports/numerics/report.docx",
        },
    }


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_demo_uses_numerics_and_removes_learned_operator_controls():
    section = site_page.sec_demo({"demo": json.dumps(payload())})
    for required in ("Softmax Collapse", "Softmax Cancellation", "Independent Decimal",
                     "Paper2Agent", "float32", "float64", "precomputed", "training"):
        assert required in section
    for obsolete in ("learned operator", "Newton", 'id="lam"', 'id="replay"', 'id="rho_plot"'):
        assert obsolete not in section
    assert 'id="demo"' in section
    assert "-3.046" in section, "the default case must be visible without JavaScript"


def test_native_controls_have_labels_and_results_have_table_captions():
    doc = Document(site_page.sec_demo({"demo": json.dumps(payload())}))
    labels = {attrs.get("for") for tag, attrs in doc.elements if tag == "label"}
    selects = {attrs["id"] for tag, attrs in doc.elements if tag == "select"}
    assert selects == {"numerics-mode", "numerics-dtype", "numerics-case"}
    assert selects <= labels
    assert sum(tag == "table" for tag, _ in doc.elements) == sum(tag == "caption" for tag, _ in doc.elements)
    assert any(attrs.get("aria-live") == "polite" for _, attrs in doc.elements)


def test_evidence_links_are_real_contract_paths():
    data = payload()
    doc = Document(site_page.sec_demo({"demo": data}))
    hrefs = {attrs.get("href") for tag, attrs in doc.elements if tag == "a"}
    assert set(data["downloads"].values()) <= hrefs
    assert data["paper"] in hrefs
    assert "reports/numerics/paper2agent.md" in hrefs


def test_scientific_figure_has_accessible_vector_exports():
    section = site_page.sec_demo({"demo": payload()})
    doc = Document(section)
    charts = [attrs for tag, attrs in doc.elements if tag == "svg"]
    assert len(charts) == 2
    assert all(attrs.get("role") == "img" and attrs.get("aria-label") for attrs in charts)
    assert not any(tag == "img" for tag, _ in doc.elements), "print masters must not become static web charts"
    hrefs = {attrs.get("href") for tag, attrs in doc.elements if tag == "a"}
    assert "reports/numerics/figure-float32.svg" in hrefs
    assert "reports/numerics/figure-float32.pdf" in hrefs


def test_demo_explains_the_repair_and_compares_measured_before_and_after():
    section = site_page.sec_demo({"demo": payload()})
    for phrase in ("Before repair", "After repair", "log1p", "negative sum", "expm1", "logit_distillation", "Repair strategy"):
        assert phrase in section


def test_script_selects_evidence_without_browser_numerical_kernels():
    script = site_page.DEMO_JS
    assert 'getElementById("demo-data")' in script
    assert "standard_gradient" in script and "reference_gradient" in script
    for forbidden in ("Math.exp(", "Math.expm1(", "Math.log1p(", "fetch(", "innerHTML"):
        assert forbidden not in script


def test_inline_json_cannot_close_the_script_and_preserves_evidence():
    data = payload()
    data["scope"] = "Literal </script><script> must stay evidence text"
    encoded = site_page._demo_json({"demo": data})
    assert "</script>" not in encoded
    assert json.loads(encoded) == data


def test_browser_selects_filed_cases_without_errors_or_mobile_overflow():
    playwright = pytest.importorskip("playwright.sync_api", reason="optional browser interaction check")
    from browser import launch
    from numerics_case import build_case

    data = build_case()
    ctx = {"demo": data}
    source = ('<!doctype html><html lang="en"><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width, initial-scale=1">'
              f'<style>{site_page.CSS}</style><body><main>{site_page.sec_demo(ctx)}</main>'
              f'<script id="demo-data" type="application/json">{site_page._demo_json(ctx)}</script>'
              f'<script>{site_page.DEMO_JS}</script></body></html>')
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(source)
        initial = page.locator('#numerics-sweep-chart path[data-series="standard"]').get_attribute("d")
        assert page.locator("#training-chart path").count() == 6
        page.select_option("#training-seed", "1")
        assert page.locator("#training-chart path").count() == 2
        assert "seed 1 standard: 1.502e-1" in page.locator("#training-readout").inner_text()
        page.locator("#training-step").fill("0")
        assert "seed 1 standard: 0" in page.locator("#training-readout").inner_text()
        page.select_option("#training-metric", "heldout_kl_float64")
        page.select_option("#training-scale", "symlog")
        page.locator("#training-standard").uncheck()
        assert page.locator("#training-chart path").count() == 1
        page.locator("#training-fixed").uncheck()
        assert "Select a repair variant" in page.locator("#training-readout").inner_text()
        assert "logit gap 18" in page.locator("#numerics-status").inner_text()
        assert "-3.04600e-8" in page.locator("#numerics-gradients").inner_text()
        page.select_option("#numerics-mode", "cancellation")
        assert initial != page.locator('#numerics-sweep-chart path[data-series="standard"]').get_attribute("d")
        assert "Absolute L2" in page.locator("#numerics-sweep-title").inner_text()
        assert "1.00000e-7" in page.locator("#numerics-status").inner_text()
        assert "Represented Δ" in page.locator("#numerics-inputs").inner_text()
        page.select_option("#numerics-case", "0")
        assert "Δ=0 has no logarithmic x" in page.locator("#numerics-chart-readout").inner_text()
        assert "undefined at zero reference" in page.locator("#numerics-standard-error").inner_text()
        assert "undefined at zero reference" in page.locator("#numerics-fixed-error").inner_text()
        page.select_option("#numerics-dtype", "float64")
        assert "float64" in page.locator("#numerics-status").inner_text()
        page.select_option("#numerics-mode", "collapse")
        page.select_option("#numerics-case", label="40")
        assert "logit gap 40" in page.locator("#numerics-status").inner_text()
        page.locator("#numerics-scrub").fill("10")
        assert "logit gap 20" in page.locator("#numerics-status").inner_text()
        for width in (375, 900, 1100, 1280, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert page.locator("#numerics-mode").is_visible()
            assert page.locator("#numerics-gradient-chart").evaluate(
                "n => getComputedStyle(n.parentElement).backgroundColor !== 'rgb(255, 255, 255)'")
            assert page.locator(".numerics-method > p").evaluate(
                "node => node.getBoundingClientRect().height === 0")
        page.locator(".numerics-method summary").click()
        assert page.evaluate("""() => document.querySelector('.numerics-scope').getBoundingClientRect().top
            >= document.querySelector('.numerics-method').getBoundingClientRect().bottom""")
        assert errors == []
        browser.close()
