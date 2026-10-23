"""The gate must reject a false claim, end to end.

Unit tests check the comparison logic; this fixture checks the whole path — span found,
pointer resolved, control resolved, referee document clean — and still fails, because the
number the register asserts is not the number in the evidence file.
"""
from pathlib import Path

from framework.validity import ScientificValidityGate

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "reference" / "null_study"


def test_gate_rejects_a_false_claim():
    gate = ScientificValidityGate(STUDY,
                                  register=STUDY / "analysis" / "CLAIMS.yaml",
                                  document=STUDY / "docs" / "REPORT.md")
    result = gate.run()
    assert result.status == "FAIL"
    assert any(f.startswith("[S3]") for f in result.details["findings"]), \
        result.details["findings"]


def test_the_false_fixture_differs_from_the_true_one_only_in_the_number():
    """Both studies cite the same evidence file; only the asserted value differs."""
    true_claims = (ROOT / "reference" / "surrogate_study" / "analysis" / "CLAIMS.yaml")
    false_claims = (STUDY / "analysis" / "CLAIMS.yaml")
    assert "value: 1" in true_claims.read_text(encoding="utf-8")
    assert "value: 19" in false_claims.read_text(encoding="utf-8")
