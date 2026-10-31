"""Existing Paper2Agent tools upgraded to the arXiv:2610.31642v3 kernel contract.

Four tool names are preserved. Teacher probabilities remain a named legacy mode;
the v3 cancellation fix requires teacher_kind="logits". This validates numerical
kernels, not the paper's training/grokking claims. NumPy float32/float64 only.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import numpy as np
from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from framework import stable_numerics as kernels

mcp = FastMCP("barron2026-softmax-fix")
EPS = float(np.finfo(np.float64).eps)


def _sum_is_zero(values: np.ndarray) -> bool:
    """Residual relative to gradient magnitude, with no absolute tolerance floor."""
    values = np.asarray(values)
    if not np.isfinite(values).all():
        return False
    scale = float(np.abs(values).sum())
    residual = abs(float(values.sum()))
    return bool(residual == 0 if scale == 0 else residual <= 8 * np.finfo(values.dtype).eps * scale)


def _as_array(values: list[float], dtype: str = "float64") -> np.ndarray:
    if dtype not in ("float32", "float64"):
        raise ValueError("dtype must be float32 or float64")
    array = np.asarray(values, dtype=dtype)
    if array.ndim != 1 or not array.size or not np.isfinite(array).all():
        raise ValueError("tools require a nonempty finite vector")
    return array


@mcp.tool()
def log_softmax(z: list[float], dtype: Literal["float32", "float64"] = "float64") -> dict:
    """v3 Eq. 5: excluded-maximum log1p; max shifting alone is the comparison."""
    values = _as_array(z, dtype)
    fixed = kernels.log_softmax(values)
    shifted = values - values.max()
    standard = shifted - np.log(np.sum(np.exp(shifted)))  # numerics: intentional comparison
    return {"log_softmax": fixed.tolist(), "first": float(fixed[0]),
            "naive_first": float(standard[0]),
            "stable_minus_naive": float(fixed[0] - standard[0]),
            "dtype": dtype, "paper_version": "2610.31642v3"}


@mcp.tool()
def softmax(z: list[float], dtype: Literal["float32", "float64"] = "float64") -> dict:
    """Exponentiated fixed log-softmax; gradients require the differentiable adapter."""
    out = kernels.softmax(_as_array(z, dtype))
    return {"softmax": out.tolist(), "sum": float(out.sum()),
            "is_normalised": bool(abs(float(out.sum()) - 1) <= 8 * np.finfo(out.dtype).eps),
            "max": float(out.max()), "dtype": dtype}


@mcp.tool()
def hard_cross_entropy(z: list[float], target: int,
                       dtype: Literal["float32", "float64"] = "float64") -> dict:
    """v3 Eqs. 6–7: retain the target derivative past the precision cliff."""
    values = _as_array(z, dtype)
    loss, gradient = kernels.hard_cross_entropy(values, target)
    # Deliberately retain the conventional computation as a negative control.
    shifted = values - values.max()
    log_p = shifted - np.log(np.sum(np.exp(shifted)))  # numerics: intentional comparison
    standard = np.exp(log_p)
    standard[target] -= 1
    return {"loss": float(loss), "grad": gradient.tolist(),
            "grad_sum": float(gradient.sum()), "grad_sum_is_zero": _sum_is_zero(gradient),
            "smallest_gradient": float(np.min(np.abs(gradient))),
            "standard_grad": standard.tolist(),
            "standard_grad_sum_is_zero": _sum_is_zero(standard), "dtype": dtype}


@mcp.tool()
def soft_target_cross_entropy(student: list[float], teacher: list[float],
                              teacher_kind: Literal["probabilities", "logits"] = "probabilities",
                              dtype: Literal["float32", "float64"] = "float64") -> dict:
    """v3 Eq. 9 for teacher logits; probability targets are explicit legacy compatibility.

    The legacy default preserves prior callers. It cannot recover precision lost
    before the probabilities reached the tool and is not certified against v3 cancellation.
    """
    s, t = _as_array(student, dtype), _as_array(teacher, dtype)
    if s.shape != t.shape:
        raise ValueError("student and teacher must have matching shapes")
    if teacher_kind == "logits":
        loss, gradient = kernels.logit_distillation(s, t)
    elif teacher_kind == "probabilities":
        if np.any(t < 0) or abs(float(t.sum()) - 1) > 8 * np.finfo(t.dtype).eps:
            raise ValueError("probability targets must be nonnegative and sum to one")
        loss = -np.sum(t * kernels.log_softmax(s))
        gradient = kernels.softmax(s) - t
    else:
        raise ValueError("teacher_kind must be probabilities or logits")
    return {"loss": float(loss), "grad": gradient.tolist(),
            "grad_sum": float(gradient.sum()), "grad_sum_is_zero": _sum_is_zero(gradient),
            "teacher_kind": teacher_kind, "dtype": dtype,
            "cancellation_fix": teacher_kind == "logits"}


if __name__ == "__main__":
    mcp.run()
