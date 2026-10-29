"""MCP tools for Barron (2026), "A fix for softmax and cross-entropy".

Runs on fastmcp 4.0.3, the baseline the Paper2Agent skill names in its runtime reference.

The four functions reproduce the paper's Equations 13, 19, 42 and 43 with float64 numpy, the same
arithmetic the paper's JAX listing performs. Each tool returns the value *and* the property the paper
claims for it, so a caller can assert a boolean rather than compare float reprs.

Run over stdio:  python server.py
"""

from __future__ import annotations

import numpy as np
from fastmcp import FastMCP

mcp = FastMCP("barron2026-softmax-fix")

EPS = float(np.finfo(np.float64).eps)


def _sum_is_zero(values: np.ndarray) -> bool:
    """A sum of a few float64 terms is zero to within their own rounding error.

    The bound is 8 eps times the larger of 1 and the largest entry — the error a three-term sum can
    accumulate — not a tolerance fitted to the observed residual.
    """
    scale = max(1.0, float(np.abs(values).max()))
    return bool(abs(float(values.sum())) <= 8 * EPS * scale)


def _as_array(values: list[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def _logsumexp(z: np.ndarray) -> float:
    return float(z.max() + np.log(np.sum(np.exp(z - z.max()))))


@mcp.tool()
def log_softmax(z: list[float]) -> dict:
    """Equation 13: log_softmax(z) = z - log(sum(exp(z))), stabilised by the max shift.

    Both evaluations are returned. The paper reports the naive form collapsing to exactly 0.0 on
    z = [9, -9, -9]; in float64 numpy it returns -3.046e-8 instead, so the collapse is a property of the
    precision and the backend, not of the formula alone. `stable_minus_naive` shows the gap directly.
    """
    z_arr = _as_array(z)
    stable = z_arr - _logsumexp(z_arr)
    # The textbook form the paper compares against: returned so a caller can see the gap, never
    # used to answer.
    naive = z_arr - np.log(np.sum(np.exp(z_arr)))  # numerics: intentional — comparison only
    return {
        "log_softmax": [float(v) for v in stable],
        "first": float(stable[0]),
        "naive_first": float(naive[0]),
        "stable_minus_naive": float(stable[0] - naive[0]),
    }


@mcp.tool()
def softmax(z: list[float]) -> dict:
    """Equation 19: softmax(z) = exp(z - log_softmax(z)), which stays finite and normalised."""
    z_arr = _as_array(z)
    out = np.exp(z_arr - _logsumexp(z_arr))
    return {
        "softmax": [float(v) for v in out],
        "sum": float(out.sum()),
        "is_normalised": bool(abs(out.sum() - 1.0) < 1e-12),
        "max": float(out.max()),
    }


@mcp.tool()
def hard_cross_entropy(z: list[float], target: int) -> dict:
    """Equation 42: cross-entropy of a one-hot target, and the gradient it produces.

    The paper's claim: the gradient is softmax(z) - onehot(t), which sums to zero. `grad_sum_is_zero`
    reports that property directly, so a caller never has to eyeball a float.
    """
    z_arr = _as_array(z)
    log_p = z_arr - _logsumexp(z_arr)
    onehot = np.zeros_like(z_arr)
    onehot[target] = 1.0
    grad = np.exp(log_p) - onehot
    return {
        "loss": float(-log_p[target]),
        "grad": [float(v) for v in grad],
        "grad_sum": float(grad.sum()),
        "grad_sum_is_zero": _sum_is_zero(grad),
        "smallest_gradient": float(np.min(np.abs(grad))),
    }


@mcp.tool()
def soft_target_cross_entropy(student: list[float], teacher: list[float]) -> dict:
    """Equation 43: cross-entropy against a soft target, whose gradient is softmax(student) - teacher."""
    s = _as_array(student)
    t = _as_array(teacher)
    log_p = s - _logsumexp(s)
    grad = np.exp(log_p) - t
    return {
        "loss": float(-np.sum(t * log_p)),
        "grad": [float(v) for v in grad],
        "grad_sum": float(grad.sum()),
        "grad_sum_is_zero": _sum_is_zero(grad),
    }


if __name__ == "__main__":
    mcp.run()
