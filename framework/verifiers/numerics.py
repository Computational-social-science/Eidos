"""Numerical risk screening and independent references for arXiv:2610.31642v3.

The paper's Softmax Collapse is a missing target gradient past the precision
cliff; Softmax Cancellation is an inaccurate student-teacher gradient near
stationarity. They are distinct from exponent overflow and forward rounding.
Static AST screening is heuristic and cannot certify a training backend.
``probe`` checks only forward log probabilities. Gradient probes qualify the
bounded NumPy kernels (or a consumer adapter) against independent Decimal
arithmetic, with positive cases and deliberately broken negative controls.
"""

from __future__ import annotations

import ast
import math
import os
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Iterable, Sequence

#: The vector Barron et al. print: the naive form returns 0.0 here, the stable form -3.046e-8.
PAPER_INPUT = (9.0, -9.0, -9.0)
#: Exponent overflow is separate from the paper's gradient-collapse mechanism.
OVERFLOW_INPUT = (1000.0, 0.0, -1000.0)


def reference_log_softmax(z: Sequence[float]) -> list[Decimal]:
    """Definition in adaptive Decimal precision, independently of float kernels.

    Precision includes the full logit span, so 1+exp(-1000) is not rounded to 1.
    The bounded reference refuses spans over 10000 rather than certifying zeros.
    """
    with localcontext() as context:
        context.prec = _reference_precision(z)
        values = [Decimal.from_float(float(v)) for v in z]
        m = max(values)
        total = sum(((v - m).exp() for v in values), Decimal(0))
        normalizer = total.ln()
        return [v - m - normalizer for v in values]


def _reference_precision(z: Sequence[float]) -> int:
    values = [float(v) for v in z]
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("reference requires nonempty finite logits")
    span = max(values) - min(values)
    if not math.isfinite(span) or span > 10000:
        raise ValueError("reference logit span exceeds supported verification range 10000")
    return 80 + math.ceil(span / math.log(10))


def reference_cross_entropy(z: Sequence[float], target: int) -> tuple[Decimal, list[Decimal]]:
    """High precision definition: CE and q-onehot, not the repaired float algorithm."""
    with localcontext() as context:
        context.prec = _reference_precision(z)
        logs = reference_log_softmax(z)
        gradient = [value.exp() for value in logs]
        gradient[target] -= 1
        return -logs[target], gradient


def reference_distillation(student: Sequence[float], teacher: Sequence[float]) -> list[Decimal]:
    """Independent high precision q-p for represented student/teacher logits."""
    if len(student) != len(teacher):
        raise ValueError("student and teacher must have matching shapes")
    with localcontext() as context:
        context.prec = max(_reference_precision(student), _reference_precision(teacher))
        return [q.exp() - p.exp() for q, p in
                zip(reference_log_softmax(student), reference_log_softmax(teacher))]


def _gradient_result(loss, gradient, expected_loss: Decimal,
                     expected_gradient: list[Decimal], input_dtype) -> dict:
    import numpy as np

    values = np.asarray(gradient)
    if values.dtype != np.dtype(input_dtype):
        return {"verdict": "ERROR", "error": "candidate gradient dtype differs from input dtype"}
    if (values.ndim != 1 or values.size != len(expected_gradient) or
            values.dtype not in (np.dtype("float32"), np.dtype("float64")) or
            not np.isfinite(values).all() or not math.isfinite(float(loss))):
        return {"verdict": "ERROR", "error": "invalid gradient shape, dtype or finite range"}
    tolerance = 5e-5 if values.dtype == np.float32 else 1e-11
    error = max(_relative_error(float(value), expected)
                for value, expected in zip(values, expected_gradient))
    loss_error = _relative_error(float(loss), expected_loss)
    # Accumulate the diagnostic in float64; its bound follows the candidate dtype.
    scale = float(np.abs(values.astype(np.float64)).sum())
    residual = abs(float(values.astype(np.float64).sum()))
    zero_sum = residual == 0 if scale == 0 else residual <= 8 * np.finfo(values.dtype).eps * scale
    passed = error <= tolerance and loss_error <= tolerance and zero_sum
    return {"verdict": "PASS" if passed else "FAIL", "dtype": str(values.dtype),
            "loss": float(loss), "gradient": values.tolist(),
            "gradient_relative_error": error if math.isfinite(error) else None,
            "loss_relative_error": loss_error if math.isfinite(loss_error) else None,
            "zero_sum_relative_residual": residual / scale if scale else 0.0,
            "tolerance": tolerance}


def probe_hard_cross_entropy(candidate, z, target: int) -> dict:
    """Check a consumer's (loss, gradient) against the independent Decimal definition."""
    expected_loss, expected_gradient = reference_cross_entropy(z, target)
    try:
        loss, gradient = candidate(z, target)
        import numpy as np
        return _gradient_result(loss, gradient, expected_loss, expected_gradient, np.asarray(z).dtype)
    except Exception as exc:  # A failed candidate must be recorded, not certified.
        return {"verdict": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def probe_logit_distillation(candidate, student, teacher) -> dict:
    """Check the logits contract, including exact stationarity, against Decimal q-p."""
    with localcontext() as context:
        context.prec = max(_reference_precision(student), _reference_precision(teacher))
        expected_loss = -sum((p.exp() * q for p, q in
                              zip(reference_log_softmax(teacher), reference_log_softmax(student))),
                             Decimal(0))
    expected_gradient = reference_distillation(student, teacher)
    try:
        loss, gradient = candidate(student, teacher)
        import numpy as np
        return _gradient_result(loss, gradient, expected_loss, expected_gradient, np.asarray(student).dtype)
    except Exception as exc:
        return {"verdict": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def kernel_regression_report(hard_candidate=None, soft_candidate=None, backend: str | None = None) -> dict:
    """Bounded kernel qualification with deliberately broken negative controls.

    A PASS covers these cases, dtypes and installed backend only. It is neither
    a training reproduction nor an attestation for untested consumer code.
    """
    import numpy as np
    from framework import stable_numerics as kernels

    hard_candidate = kernels.hard_cross_entropy if hard_candidate is None else hard_candidate
    soft_candidate = kernels.logit_distillation if soft_candidate is None else soft_candidate

    cases = []
    for dtype, margins in ((np.float32, (0, 18, 80)), (np.float64, (0, 40, 700))):
        for margin in margins:
            result = probe_hard_cross_entropy(hard_candidate,
                                              np.array([margin, 0, 0], dtype=dtype), 0)
            cases.append({"name": f"{np.dtype(dtype)} hard margin {margin}", **result})
        teacher = np.array([2, 1, 0], dtype=dtype)
        student = teacher + np.array([-1e-7, 1e-7, 0], dtype=dtype)
        for name, s, t in (("equality", teacher, teacher), ("near teacher", student, teacher),
                           ("far teacher", np.array([1000, -1000], dtype=dtype),
                            np.array([-1000, 1000], dtype=dtype))):
            result = probe_logit_distillation(soft_candidate, s, t)
            cases.append({"name": f"{np.dtype(dtype)} {name}", **result})

    def broken_hard(z, target):
        shifted = z - z.max()
        logs = shifted - np.log(np.exp(shifted).sum())  # numerics: intentional negative control
        gradient = np.exp(logs)
        gradient[target] -= 1
        return -logs[target], gradient

    def noisy_stationary(student, teacher):
        loss, _ = kernels.logit_distillation(student, teacher)
        return loss, np.array([1e-12, -1e-12, 0.0], dtype=student.dtype)

    collapsed = probe_hard_cross_entropy(broken_hard, np.array([40.0, 0.0, 0.0]), 0)
    equal = np.array([2.0, 1.0, 0.0])
    cancelled = probe_logit_distillation(noisy_stationary, equal, equal)
    controls = [{"name": "lost target gradient", "rejected": collapsed["verdict"] == "FAIL"},
                {"name": "nonzero stationary gradient", "rejected": cancelled["verdict"] == "FAIL"}]
    passed = all(row["verdict"] == "PASS" for row in cases) and all(c["rejected"] for c in controls)
    return {"paper": "arxiv:2610.31642v3", "backend": backend or f"numpy {np.__version__}",
            "verdict": "PASS" if passed else "FAIL", "cases": cases, "negative_controls": controls,
            "scope": "bounded numerical kernels; consumer backends and training outcomes are not certified"}


def _relative_error(observed: float, expected: Decimal) -> float:
    if expected == 0:
        return 0.0 if observed == 0 else math.inf
    if not math.isfinite(observed):
        return math.inf
    return float(abs((Decimal(str(observed)) - expected) / expected))


def probe(log_softmax, z: Sequence[float] = PAPER_INPUT) -> dict:
    """Run one callable against the high-precision reference.

    Returns forward relative error and a verdict. These forward diagnostics do
    not establish either of the paper's gradient failure mechanisms.
    """
    expected = reference_log_softmax(z)
    try:
        observed = list(log_softmax(list(z)))
    except OverflowError as exc:
        # Python exp may raise; NumPy may instead return non-finite values.
        return {"input": list(z), "verdict": "OVERFLOW", "error": f"OverflowError: {exc}",
                "digits_lost": None, "worst_relative_error": None}
    except Exception as exc:  # noqa: BLE001 - an exception is a datum here
        return {"input": list(z), "verdict": "ERROR", "error": f"{type(exc).__name__}: {exc}",
                "digits_lost": None, "worst_relative_error": None}
    if len(observed) != len(expected):
        return {"input": list(z), "verdict": "ERROR", "error": "wrong length",
                "digits_lost": None, "worst_relative_error": None}

    worst = max(_relative_error(float(o), e) for o, e in zip(observed, expected))
    collapsed = any(not math.isfinite(float(o)) for o in observed)
    zeroed = (not collapsed
              and any(float(o) == 0.0 and e != 0 for o, e in zip(observed, expected)))
    digits = None if worst in (0.0, math.inf) else max(0.0, -math.log10(worst))
    # The tiers are empirical, not aspirational: even the stabilised form computes 9 - 9.00000003
    # in float64, so it carries ~1e-9 relative error on this input and can never reach 1e-12.
    # PASS means "at least six digits", which is what float64 supports here.
    verdict = ("OVERFLOW" if collapsed else "FORWARD_ROUNDING" if zeroed
               else "PASS" if worst <= 1e-6 else "LOSSY" if worst < 1e-2 else "WRONG")
    return {"input": list(z), "observed": [float(v) for v in observed],
            "reference": [float(v) for v in expected], "verdict": verdict,
            "worst_relative_error": None if worst == math.inf else worst,
            "digits_preserved": digits, "reference_decimal": [str(v) for v in expected]}


# -- static scan ---------------------------------------------------------------------------------

_SOFTMAX_HINTS = ("softmax", "log_softmax", "cross_entropy", "logsumexp")


def _call_name(node: ast.AST) -> str:
    """The name a call is made under: `np.log(...)` and `log(...)` both give "log"."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _mentions_softmax(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name.lower()
        elif isinstance(node, ast.Call):
            name = _call_name(node).lower()
        else:
            continue
        if any(hint in name for hint in _SOFTMAX_HINTS) or name.endswith("_entropy"):
            return True
    return False


def audit_source(paths: Iterable[Path]) -> list[dict]:
    """Find the textbook shapes. A finding is file, line, and which shape it is."""
    findings: list[dict] = []
    for path in paths:
        path = Path(path)
        if not path.is_file() or path.suffix != ".py":
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeError, OSError) as exc:
            findings.append({"file": str(path), "line": getattr(exc, "lineno", 1) or 1,
                             "kind": "unscannable-source", "detail": f"{type(exc).__name__}: {exc}"})
            continue
        if not _mentions_softmax(tree):
            continue
        # A file may compute the textbook form on purpose — to show what it does. The marker makes
        # that intent explicit and reviewable, instead of teaching the scanner to ignore the shape.
        lines = source.splitlines()

        def _intentional(lineno: int) -> bool:
            for candidate in (lineno - 1, lineno - 2, lineno - 3):  # same line, or one/two above
                if 0 <= candidate < len(lines) and "numerics: intentional" in lines[candidate]:
                    return True
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) in ("log", "ln"):
                if _intentional(node.lineno):
                    continue
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call) and _call_name(inner) == "sum":
                        exps = [c for c in ast.walk(inner)
                                if isinstance(c, ast.Call) and _call_name(c) == "exp"]
                        findings.append({
                            "file": str(path), "line": node.lineno,
                            "kind": "log-of-sum",
                            "detail": "log(sum(...)) may round away the dominant class correction. "
                                      "A max shift prevents overflow, not Softmax Collapse; "
                                      "use the excluded-maximum/log1p kernel and test gradients."})
            if isinstance(node, ast.Call) and _call_name(node) == "log":
                if _intentional(node.lineno):
                    continue
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call) and "softmax" in _call_name(inner):
                        findings.append({
                            "file": str(path), "line": node.lineno,
                            "kind": "log-of-probability",
                            "detail": "log(softmax(z)) underflows to -inf for small probabilities; "
                                      "compute log_softmax on the logits instead"})
    return findings


def python_sources(root: Path) -> list[Path]:
    """Enumerate consumer source without virtual environments or generated caches."""
    root = Path(root)
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    paths = []
    for directory, children, names in os.walk(root):
        children[:] = [name for name in children if not name.startswith(".venv")
                       and name not in {"venv", ".scratch", ".git", "__pycache__", "node_modules"}]
        paths.extend(Path(directory) / name for name in names if name.endswith(".py"))
    return sorted(paths)


def consumer_preflight(root: Path) -> dict:
    """Fail closed on source risks; built-in kernels do not qualify a consumer backend."""
    paths = python_sources(root)
    findings = audit_source(paths)
    if not paths:
        findings.append({"file": str(root), "line": 1, "kind": "unscannable-source",
                         "detail": "required numerical consumer has no scannable Python source"})
    runtime = kernel_regression_report()
    return {"verdict": "FAIL" if findings or runtime["verdict"] != "PASS" else "PASS",
            "scanned": len(paths), "findings": findings, "kernel_regression": runtime,
            "scope": "heuristic consumer screening and built-in kernels; does not certify consumer gradients"}


def summarise(findings: list[dict]) -> str:
    if not findings:
        return "clean"
    return "; ".join(f"{Path(f['file']).name}:{f['line']} {f['kind']}" for f in findings)
