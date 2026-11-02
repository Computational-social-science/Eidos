"""P0 verifiers: a misstated p-value and a retracted citation must fail without a model.

The fixtures carry real proofpath responses in `cache.json`, so the citation tests run offline and
still assert against what the service actually returned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.verifiers import citations, stats

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "verifiers"


def _spec(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_a_correctly_reported_result_passes():
    result = stats.recompute(_spec("stats_good"))
    assert result["verdict"] == "PASS"
    assert {c["id"] for c in result["checks"]} >= {"p", "d"}
    # the recomputed values are the kernel's, not the document's
    assert abs(result["recomputed"]["p"] - 0.09) < 0.01


def test_a_misstated_p_fails():
    result = stats.recompute(_spec("stats_bad_p"))
    assert result["verdict"] == "FAIL"
    assert [c["id"] for c in result["checks"] if c["status"] == "FAIL"] == ["p"]


def test_an_inflated_effect_size_fails():
    result = stats.recompute(_spec("stats_bad_d"))
    assert result["verdict"] == "FAIL"
    assert [c["id"] for c in result["checks"] if c["status"] == "FAIL"] == ["d"]


def test_rounding_is_not_a_mismatch():
    # d = 0.44 against a recomputed 0.4417 is a rounded report, not an error. The plan's literal
    # 1e-3 relative tolerance would reject it; the comparison is made at the reported precision.
    spec = _spec("stats_good")
    spec["reported"] = {"d": 0.44}
    assert stats.recompute(spec)["verdict"] == "PASS"


def test_a_ci_that_excludes_its_own_estimate_fails():
    spec = _spec("stats_good")
    spec["reported"] = {"ci": [0.40, 0.60], "p": 0.09}
    result = stats.recompute(spec)
    assert result["verdict"] == "FAIL"
    assert any(c["id"] == "ci" and c["status"] == "FAIL" for c in result["checks"])


def test_the_citation_fixture_separates_retracted_from_unresolved(tmp_path):
    refs = [line.strip() for line in (FIXTURES / "refs.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    result = citations.check(refs, network=False, cache_path=FIXTURES / "cache.json",
                             out=tmp_path / "proofpath.json")
    statuses = [r["status"] for r in result["records"]]
    assert statuses == ["VERIFIED", "BLOCKED", "BLOCKED"]
    reasons = [r["reason"] for r in result["records"]]
    assert reasons[1] == "retracted" and reasons[2] == "unresolved"
    assert result["verdict"] == "BLOCKED"


def test_offline_uncached_reference_is_unavailable_not_verified(tmp_path):
    result = citations.check(["10.0000/never-seen"], network=False,
                             cache_path=FIXTURES / "cache.json", out=tmp_path / "p.json")
    assert result["records"][0]["status"] == citations.UNAVAILABLE
    assert result["verdict"] == "BLOCKED"


def test_a_retracted_source_blocks_even_when_the_doi_resolves():
    payload = {"result": {"state": "RESOLVED (high confidence)", "best": {"doi": "10.1/x"}},
               "retraction": {"source": "retraction-watch", "label": "Retraction"}}
    record = citations.classify(payload)
    assert record["status"] == citations.BLOCKED and record["reason"] == "retracted"


def test_a_provider_outage_is_not_a_bad_citation():
    record = citations.classify({"result": {"state": "UNVERIFIED (provider unavailable)"}})
    assert record["status"] == citations.UNAVAILABLE
