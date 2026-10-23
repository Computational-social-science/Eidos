"""The gate must reject a false claim, end to end.

Unit tests check the comparison logic; this fixture checks the whole path — span found,
pointer resolved, control resolved, referee document clean — and still fails, because the
number the register asserts is not the number in the evidence file.
"""
from pathlib import Path

from framework.validity import ScientificValidityGate

ROOT = Path(__file__).resolve().parents[1]
FALSE = ROOT / "reference" / "null_study"
TRUE = ROOT / "reference" / "operator_calibration"


def test_gate_rejects_a_false_claim():
    gate = ScientificValidityGate(FALSE,
                                  register=FALSE / "analysis" / "CLAIMS.yaml",
                                  document=FALSE / "docs" / "REPORT.md")
    result = gate.run()
    assert result.status == "FAIL"
    assert any(f.startswith("[S3]") for f in result.details["findings"]), \
        result.details["findings"]


def test_both_consumers_cite_the_same_evidence_file():
    """The false fixture differs from the true one only in the asserted value, so a pass
    cannot be explained by the two pointing at different artefacts."""
    false_text = (FALSE / "analysis" / "CLAIMS.yaml").read_text(encoding="utf-8")
    true_text = (TRUE / "analysis" / "CLAIMS.yaml").read_text(encoding="utf-8")
    assert "../operator_calibration/docs/evidence.json" in false_text
    assert "docs/evidence.json" in true_text
    assert "value: 0" in false_text          # asserts the operator never abstains
    assert "value: 1.0" in true_text         # the measured abstention rate
