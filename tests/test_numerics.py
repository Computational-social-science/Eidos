"""The numerical guard must fail on the code it was written for, and pass the fix.

Two negative controls and one positive, because a scanner that reports "clean" on everything is
indistinguishable from one that does not run:

* the textbook form collapses at |z| > 709 and loses digits at the paper's own input;
* the stabilised form keeps the answer in both places.

The static half is checked on a file written for the purpose, not on the repository.
"""

import math
from pathlib import Path

import pytest

from framework.verifiers import numerics


def _naive_log_softmax(z):
    return [v - math.log(sum(math.exp(w) for w in z)) for v in z]


def _stable_log_softmax(z):
    m = max(z)
    total = math.log(sum(math.exp(v - m) for v in z))
    return [v - m - total for v in z]


def test_exponent_overflow_is_separate_from_gradient_collapse():
    result = numerics.probe(_naive_log_softmax, numerics.OVERFLOW_INPUT)
    assert result["verdict"] == "OVERFLOW"


def test_forward_log_probability_rounds_to_zero_in_float32():
    """The paper's own observation: at float32 the naive form returns exactly 0.0 for [9, -9, -9]."""
    import numpy as np

    def naive_float32(z):
        values = np.asarray(z, dtype=np.float32)
        return [float(v) for v in values - np.log(np.sum(np.exp(values)))]

    result = numerics.probe(naive_float32, numerics.PAPER_INPUT)
    assert result["verdict"] == "FORWARD_ROUNDING", result


def test_max_shift_is_sufficient_only_for_the_mild_float64_case():
    assert numerics.probe(_stable_log_softmax, numerics.PAPER_INPUT)["verdict"] == "PASS"
    assert numerics.probe(_stable_log_softmax, numerics.OVERFLOW_INPUT)["verdict"] == "FORWARD_ROUNDING"


def test_a_zero_forward_result_is_not_mislabeled_gradient_cancellation():
    result = numerics.probe(lambda z: [0.0 for _ in z], numerics.PAPER_INPUT)
    assert result["verdict"] == "FORWARD_ROUNDING"


def test_the_static_scan_finds_the_textbook_shape(tmp_path: Path):
    naive = tmp_path / "naive.py"
    naive.write_text(
        "import math\n"
        "def log_softmax(z):\n"
        "    return [v - math.log(sum(math.exp(w) for w in z)) for v in z]\n",
        encoding="utf-8")
    findings = numerics.audit_source([naive])
    assert [f["kind"] for f in findings] == ["log-of-sum"]


def test_the_static_scan_finds_log_of_a_softmax(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import numpy as np\n"
        "def loss(z):\n"
        "    p = np.exp(z) / np.exp(z).sum()\n"
        "    return -np.log(softmax(z))[0]\n",
        encoding="utf-8")
    kinds = {f["kind"] for f in numerics.audit_source([bad])}
    assert "log-of-probability" in kinds


def test_the_converted_server_is_clean():
    server = (Path(__file__).resolve().parents[1] / "reference" / "reproduction" /
              "barron2026" / "mcp" / "server.py")
    assert numerics.audit_source([server]) == []


def test_max_shift_alone_is_not_certified_as_the_paper_fix(tmp_path):
    path = tmp_path / "max_shift.py"
    path.write_text('import numpy as np\ndef log_softmax(z):\n'
                    '    return z - z.max() - np.log(np.sum(np.exp(z - z.max())))\n',
                    encoding="utf-8")
    assert numerics.audit_source([path])


def test_the_decimal_oracle_preserves_small_dominant_log_probability():
    assert numerics.reference_log_softmax([1000.0, 0.0, -1000.0])[0] < 0


def test_numerical_oracle_does_not_mutate_decimal_context():
    import importlib
    from decimal import localcontext, getcontext
    with localcontext() as context:
        context.prec = 23
        importlib.reload(numerics)
        numerics.reference_log_softmax([9.0, -9.0, -9.0])
        assert getcontext().prec == 23


def test_unparseable_source_is_not_reported_clean(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def softmax(:\n", encoding="utf-8")
    assert numerics.audit_source([path])[0]["kind"] == "unscannable-source"
    path.write_bytes(b"#\xff\n")
    assert numerics.audit_source([path])[0]["kind"] == "unscannable-source"
