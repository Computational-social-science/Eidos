"""Tests for the local-in-time operator layer and its system-level numerics.

The planted system is ``du/dt = lam - u^2`` with ``u* = sqrt(lam)``; every assertion below
compares against that closed form rather than against a previous run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.surrogate import (RandomFeatureOperator, continue_branch, fixed_point,
                                 rk4_step, spectral_radius)

DT = 0.05
RHS = lambda u, lam: lam - u * u  # noqa: E731


def fitted(n=800, seed=0, shuffle=False):
    rng = np.random.default_rng(seed)
    lam = rng.uniform(0.1, 1.0, size=n)
    u = (np.sqrt(lam) + rng.normal(0.0, 0.25, size=n)).reshape(-1, 1)
    u_next = np.array([rk4_step(RHS, row, float(l), DT) for row, l in zip(u, lam)])
    if shuffle:
        u_next = u_next[np.random.default_rng(1).permutation(n)]
    return RandomFeatureOperator(256, seed=0).fit(u, u_next, lam)


def test_fixed_point_is_recovered():
    op = fitted()
    u, info = fixed_point(op.step, 0.5, np.array([1.0]))
    assert info["converged"]
    assert abs(u[0] - np.sqrt(0.5)) / np.sqrt(0.5) < 0.05


def test_fixed_points_are_stable_on_the_branch():
    op = fitted()
    for lam in (0.2, 0.5, 0.9):
        u, info = fixed_point(op.step, lam, np.array([1.0]))
        assert info["converged"]
        assert spectral_radius(op.step, u, lam) < 1.0


def test_continuation_tracks_the_closed_form():
    op = fitted()
    branch = continue_branch(op.step, np.linspace(0.1, 1.0, 7), np.array([1.0]))
    assert all(p.converged for p in branch)
    errs = [abs(p.u[0] - np.sqrt(p.lam)) / np.sqrt(p.lam) for p in branch]
    assert max(errs) < 0.05


def test_shuffled_labels_do_not_recover_the_branch():
    """The negative control: destroy the dynamics and the recovery must collapse."""
    op = fitted(shuffle=True)
    branch = continue_branch(op.step, np.linspace(0.1, 1.0, 7), np.array([1.0]))
    errs = [abs(p.u[0] - np.sqrt(p.lam)) / np.sqrt(p.lam)
            for p in branch if p.converged]
    assert (not errs) or max(errs) > 0.05


def test_unfitted_operator_refuses_to_step():
    op = RandomFeatureOperator(64)
    try:
        op.step(np.array([1.0]), 0.5)
    except RuntimeError as exc:
        assert "fit()" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unfitted operator stepped silently")
