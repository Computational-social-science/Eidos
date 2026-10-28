"""Numbers that appear in prose must come from somewhere a machine can check.

`docs/MODEL_VERDICTS.md` and the README both quote 0.867 and 0.850. Those were typed by hand into
three documents at different times, which is how two of them came to disagree about the deployed
context. The policy file is the committed source (artefacts are gitignored), so the test reads it and
requires the documents to agree.
"""

from __future__ import annotations

from pathlib import Path

from framework import config

ROOT = Path(__file__).resolve().parents[1]
VERDICTS = (ROOT / "docs" / "MODEL_VERDICTS.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _policy():
    return config.global_config()


def test_the_s4_number_in_the_documents_is_the_policy_number():
    declared = _policy()["gates"]["s4_probe"]["model_accuracy_structured"]
    text = f"{declared:.3f}"
    assert text in VERDICTS, f"S4 structured accuracy {text} missing from MODEL_VERDICTS.md"
    assert text in README, f"S4 structured accuracy {text} missing from README"


def test_the_s7_numbers_in_the_documents_are_the_policy_numbers():
    s7 = _policy()["gates"]["s7"]
    assert s7["status"] == "not gateable"
    held = f"{s7['held_out_accuracy']:.3f}"
    assert held in VERDICTS and held in README, f"S7 held-out accuracy {held} missing"
    lo, hi = s7["wilson95"]
    assert f"[{lo:.3f}, {hi:.3f}]" in VERDICTS or f"[{lo:.2f}, {hi:.2f}]" in VERDICTS


def test_the_deployed_context_appears_in_the_verdict_document():
    ctx = _policy()["inference"]["models"][0]["context"]
    assert str(ctx) in VERDICTS


def test_the_documents_do_not_quote_the_superseded_s7_figure_as_current():
    """0.950 was the tuned figure; it may appear only alongside the held-out correction."""
    if "0.950" in VERDICTS:
        assert "0.850" in VERDICTS
        assert "optimistic" in VERDICTS.lower()


def test_health_table_matches_the_self_audit_record():
    """The table's two headline numbers come from docs/SELF_AUDIT.json; drift must fail here."""
    import json as _json
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]
    record = _json.loads((root / "docs" / "SELF_AUDIT.json").read_text(encoding="utf-8"))
    health = (root / "docs" / "HEALTH.md").read_text(encoding="utf-8")
    assert f"**{record['tests_collected']} collected**" in health
    assert f"**{record['coverage_total']}%**" in health
