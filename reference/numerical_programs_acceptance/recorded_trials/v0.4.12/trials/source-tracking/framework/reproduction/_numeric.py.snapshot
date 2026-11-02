"""Exact comparison of represented JSON int/binary-float statistics."""

from __future__ import annotations

from fractions import Fraction
import json
import math


def number(value, name: str) -> Fraction:
    if type(value) not in (int, float) or (
        type(value) is float and not math.isfinite(value)
    ):
        raise ValueError(
            name + " must be a finite JSON integer or float (not a boolean)"
        )
    return Fraction(value)


def settings(expected, tolerance, relative):
    expected_exact = number(expected, "expected")
    tolerance_exact = number(tolerance, "tolerance")
    if tolerance_exact < 0 or type(relative) is not bool:
        raise ValueError("tolerance must be nonnegative and relative must be a boolean")
    return expected_exact, tolerance_exact


def comparison(expected, observed, tolerance=1e-3, relative=False) -> dict:
    expected_exact, tolerance_exact = settings(expected, tolerance, relative)
    delta = abs(number(observed, "observed") - expected_exact)
    limit = tolerance_exact * (abs(expected_exact) if relative else 1)
    if delta.denominator == 1:
        diagnostic = delta.numerator
        try:
            str(diagnostic)
        except ValueError:
            diagnostic = None
    else:
        try:
            diagnostic = float(delta)
        except OverflowError:
            diagnostic = None
        if diagnostic is not None and not math.isfinite(diagnostic):
            diagnostic = None
    return {
        "verdict": "MATCH" if delta <= limit else "MISMATCH",
        "delta": diagnostic,
        "delta_exact": {
            "numerator": hex(delta.numerator),
            "denominator": hex(delta.denominator),
            "radix": 16,
        },
        "limit_exact": {
            "numerator": hex(limit.numerator),
            "denominator": hex(limit.denominator),
            "radix": 16,
        },
    }


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonstandard JSON constant: " + value)


def _float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON float outside finite binary64 range: " + value)
    return parsed


def loads(text: str):
    return json.loads(
        text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float
    )


def output_value(text: str, selector: str):
    text = text.strip()
    try:
        payload = loads(text)
    except ValueError:
        lines = text.splitlines()
        if not lines:
            raise ValueError("output is not JSON")
        payload = loads(lines[-1])
        # Logging before one compact JSON result is supported. A second JSON
        # object/array is ambiguous; do not silently select the favorable one.
        prefix = "\n".join(lines[:-1])
        for line in prefix.splitlines():
            candidate = line.lstrip()
            if candidate.startswith(("{", "[")):
                raise ValueError(
                    "ambiguous JSON-like output before final result; send logs to stderr"
                )
    node = payload
    for part in selector.split("."):
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise ValueError("output has no " + selector)
    number(node, "observed")
    return node
