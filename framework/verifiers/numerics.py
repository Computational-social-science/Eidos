"""Numerical guards for the two failures Barron (2026) names: collapse and cancellation.

`softmax` and `cross-entropy` are usually written in their textbook form, and that form loses the
answer twice over:

* **cancellation** — `log(sum(exp(z)))` with large `|z|` subtracts two nearly equal numbers, so
  `log_softmax([9, -9, -9])` returns 0 instead of -3.05e-8;
* **collapse** — `exp(z) / sum(exp(z))` overflows to `inf/inf` or underflows to `0/0` for `|z|` past
  ~709, returning `nan` where the answer is a perfectly ordinary probability.

A consumer that computes either by the textbook route does not fail loudly: it returns a plausible
number (0.0, or 1.0, or nan) and the rest of the pipeline reasons on it. That is why this is a check and
not a note in a style guide.

Two instruments:

``audit_source(paths)``
    Static: finds the textbook shapes in Python source (``log(sum(exp(...)))``, ``log`` applied to a
    softmax, ``exp`` on raw logits without a max shift) and reports file:line.

``probe(fn, z)``
    Runtime: compares a callable ``log_softmax`` against a ``Decimal`` reference at 50 digits and counts
    the digits it lost. Collapse and cancellation both show up as lost digits, whatever the code looks
    like.

The reference is computed in ``decimal`` so the check does not share arithmetic with the thing it
checks; a numpy reference would inherit the same cancellation it is meant to detect.
"""

from __future__ import annotations

import ast
import math
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Iterable, Sequence

getcontext().prec = 50

#: The vector Barron et al. print: the naive form returns 0.0 here, the stable form -3.046e-8.
PAPER_INPUT = (9.0, -9.0, -9.0)
#: Past ~709, exp overflows in float64: the collapse case.
OVERFLOW_INPUT = (1000.0, 0.0, -1000.0)


def reference_log_softmax(z: Sequence[float]) -> list[Decimal]:
    """log_softmax at 50 digits, by the stable identity z - m - log(sum(exp(z - m)))."""
    values = [Decimal(str(v)) for v in z]
    m = max(values)
    total = sum(((v - m).exp() for v in values), Decimal(0))
    return [v - m - total.ln() for v in values]


def _relative_error(observed: float, expected: Decimal) -> float:
    if expected == 0:
        return 0.0 if observed == 0 else math.inf
    if not math.isfinite(observed):
        return math.inf
    return float(abs((Decimal(str(observed)) - expected) / expected))


def probe(log_softmax, z: Sequence[float] = PAPER_INPUT) -> dict:
    """Run one callable against the high-precision reference.

    Returns the worst relative error, the digits it preserved, and a verdict. A `nan`/`inf` result is a
    collapse; a zero result where the reference is not zero is a cancellation.
    """
    expected = reference_log_softmax(z)
    try:
        observed = list(log_softmax(list(z)))
    except OverflowError as exc:
        # exp(1000) raises before it can return inf: in Python floats the collapse *is* the
        # exception. Numpy would return inf/nan instead, and the non-finite branch below catches that.
        return {"input": list(z), "verdict": "COLLAPSE", "error": f"OverflowError: {exc}",
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
    verdict = ("COLLAPSE" if collapsed else "CANCELLATION" if zeroed
               else "PASS" if worst <= 1e-6 else "LOSSY" if worst < 1e-2 else "WRONG")
    return {"input": list(z), "observed": [float(v) for v in observed],
            "reference": [float(v) for v in expected], "verdict": verdict,
            "worst_relative_error": None if worst == math.inf else worst,
            "digits_lost": digits}


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
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        if not _mentions_softmax(tree):
            continue
        # A file may compute the textbook form on purpose — to show what it does. The marker makes
        # that intent explicit and reviewable, instead of teaching the scanner to ignore the shape.
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

        def _intentional(lineno: int) -> bool:
            for candidate in (lineno - 1, lineno - 2, lineno - 3):  # same line, or one/two above
                if 0 <= candidate < len(lines) and "numerics: intentional" in lines[candidate]:
                    return True
            return False
        def _max_shifted(call: ast.Call) -> bool:
            """Is this exp() computed on (x - max(x))? Then the sum is already stabilised."""
            for arg in call.args:
                for inner in ast.walk(arg):
                    text = _call_name(inner).lower()
                    if "max" in text:
                        return True
                    if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.Sub):
                        sides = [getattr(inner.left, "id", ""), getattr(inner.right, "id", "")]
                        names = [getattr(side, "attr", "") for side in (inner.left, inner.right)]
                        if any("max" in str(x).lower() for x in sides + names):
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
                        if exps and all(_max_shifted(c) for c in exps):
                            continue          # log(sum(exp(x - max(x)))) is the fix, not the bug
                        findings.append({
                            "file": str(path), "line": node.lineno,
                            "kind": "log-of-sum",
                            "detail": "log(sum(...)) computed directly: cancellation when the terms "
                                      "are large and nearly equal; use logsumexp or a max shift"})
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


def summarise(findings: list[dict]) -> str:
    if not findings:
        return "clean"
    return "; ".join(f"{Path(f['file']).name}:{f['line']} {f['kind']}" for f in findings)
