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


def test_the_textbook_form_collapses_when_exp_overflows():
    result = numerics.probe(_naive_log_softmax, numerics.OVERFLOW_INPUT)
    assert result["verdict"] == "COLLAPSE"


def test_the_textbook_form_cancels_to_zero_in_float32():
    """The paper's own observation: at float32 the naive form returns exactly 0.0 for [9, -9, -9]."""
    import numpy as np

    def naive_float32(z):
        values = np.asarray(z, dtype=np.float32)
        return [float(v) for v in values - np.log(np.sum(np.exp(values)))]

    result = numerics.probe(naive_float32, numerics.PAPER_INPUT)
    assert result["verdict"] == "CANCELLATION", result


def test_the_stabilised_form_passes_both_inputs():
    for z in (numerics.PAPER_INPUT, numerics.OVERFLOW_INPUT):
        result = numerics.probe(_stable_log_softmax, z)
        assert result["verdict"] == "PASS", (z, result)


def test_a_function_that_returns_zero_is_named_a_cancellation():
    result = numerics.probe(lambda z: [0.0 for _ in z], numerics.PAPER_INPUT)
    assert result["verdict"] == "CANCELLATION"


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
