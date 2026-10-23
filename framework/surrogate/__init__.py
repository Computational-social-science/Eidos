"""Local-in-time neural operators, used the way the equation-free literature uses them.

The scientific content of Fabiani et al. (Nature Machine Intelligence, 2026) is not "a
better surrogate": it is that a *short-time* operator, learned from data, can be embedded
in system-level numerics -- fixed points, stability, continuation -- so that the
quantities a scientist wants (does this steady state exist, is it stable, where does the
branch end) are computed without ever writing down the PDE.

This module implements that layer, deliberately small:

* :class:`RandomFeatureOperator` -- a local-in-time stepper trained on short pairs
  ``(u_t, u_{t+dt})``. Random features + ridge is the RandONets idea in its cheapest
  form; it trains in milliseconds and is deterministic.
* :func:`fixed_point` -- Newton on ``psi(u) = S(u) - u`` with a finite-difference
  Jacobian and a backtracking line search.
* :func:`spectral_radius` -- eigenvalues of ``dS/du`` at a fixed point; the discrete map
  is stable when every ``|lambda| < 1``.
* :func:`continue_branch` -- warm-started continuation in a parameter, recording where
  the fixed point stops existing.

What this module is NOT: a PDE solver, a DeepONet, or a claim that token sequences are
C1 function spaces. The acceptance test (``tools/audit_surrogate.py``) is a planted-truth
system whose fixed point is known analytically, because an operator that cannot recover a
known answer must not be trusted on an unknown one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import numpy as np

Stepper = Callable[[np.ndarray, float], np.ndarray]


class RandomFeatureOperator:
    """A local-in-time stepper: ``u_{t+dt} = u_t + Phi(u_t, lam) @ w``.

    Features are ``tanh(W u + b lam + c)`` with ``W`` drawn once from a fixed seed, so
    fitting is a linear least-squares problem. Predicting the *increment* rather than the
    next state keeps the regression conditioned on the short-time dynamics, which is the
    whole point of training locally in time.
    """

    def __init__(self, n_features: int = 256, seed: int = 0, ridge: float = 1e-8,
                 scale: float = 1.0):
        self.n_features = int(n_features)
        self.seed = int(seed)
        self.ridge = float(ridge)
        self.scale = float(scale)
        self._w: Optional[np.ndarray] = None
        self._b: Optional[np.ndarray] = None
        self._c: Optional[np.ndarray] = None
        self._beta: Optional[np.ndarray] = None
        self.dim: Optional[int] = None

    def _design(self, u: np.ndarray, lam: np.ndarray) -> np.ndarray:
        # u: (n, d), lam: (n,) -> (n, m)
        return np.tanh(self.scale * (u @ self._w + np.outer(lam, self._b) + self._c))

    def fit(self, u: np.ndarray, u_next: np.ndarray,
            lam: np.ndarray) -> "RandomFeatureOperator":
        u = np.atleast_2d(np.asarray(u, dtype=float))
        u_next = np.atleast_2d(np.asarray(u_next, dtype=float))
        lam = np.asarray(lam, dtype=float).reshape(-1)
        if len(u) != len(u_next) or len(u) != len(lam):
            raise ValueError("u, u_next and lam must have the same number of rows")
        self.dim = int(u.shape[1])
        rng = np.random.default_rng(self.seed)
        dim = self.dim
        self._w = rng.normal(0.0, 1.0 / np.sqrt(dim), size=(dim, self.n_features))
        self._b = rng.uniform(-1.0, 1.0, size=self.n_features)
        self._c = rng.uniform(-np.pi, np.pi, size=self.n_features)
        design = self._design(u, lam)
        target = u_next - u
        gram = design.T @ design + self.ridge * np.eye(self.n_features)
        self._beta = np.linalg.solve(gram, design.T @ target)
        return self

    def step(self, u: np.ndarray, lam: float) -> np.ndarray:
        if self._beta is None:
            raise RuntimeError("call fit() before step()")
        u = np.asarray(u, dtype=float).reshape(1, -1)
        design = self._design(u, np.array([float(lam)]))
        return (u + design @ self._beta).reshape(-1)


def fixed_point(stepper: Stepper, lam: float, u0: np.ndarray, tol: float = 1e-8,
                max_iter: int = 60, fd_step: float = 1e-6) -> Tuple[np.ndarray, dict]:
    """Newton on ``psi(u) = S(u, lam) - u``.

    The Jacobian is built by finite differences (one stepper call per dimension), which is
    the matrix-free recipe of the equation-free literature at the size this module targets.
    Returns the iterate and a record; ``info["converged"]`` is the only field callers
    should branch on.
    """
    u = np.asarray(u0, dtype=float).copy()
    n = u.size
    for k in range(max_iter):
        residual = stepper(u, lam) - u
        norm = float(np.linalg.norm(residual))
        if norm < tol:
            return u, {"converged": True, "iterations": k, "residual": norm}
        jac = np.empty((n, n))
        for j in range(n):
            e = np.zeros(n)
            e[j] = fd_step
            jac[:, j] = ((stepper(u + e, lam) - (u + e)) - residual) / fd_step
        try:
            delta = np.linalg.solve(jac, -residual)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(jac, -residual, rcond=None)[0]
        # Backtracking: a full Newton step can leave the basin of a learned map.
        step_scale = 1.0
        for _ in range(12):
            candidate = u + step_scale * delta
            if np.linalg.norm(stepper(candidate, lam) - candidate) < norm:
                u = candidate
                break
            step_scale *= 0.5
        else:
            return u, {"converged": False, "iterations": k, "residual": norm,
                       "reason": "line search failed"}
    return u, {"converged": False, "iterations": max_iter,
               "residual": float(np.linalg.norm(stepper(u, lam) - u)),
               "reason": "max_iter"}


def spectral_radius(stepper: Stepper, u: np.ndarray, lam: float,
                    fd_step: float = 1e-6) -> float:
    """Largest ``|eigenvalue|`` of ``dS/du``; < 1 means the fixed point is attracting."""
    u = np.asarray(u, dtype=float)
    n = u.size
    jac = np.empty((n, n))
    base = stepper(u, lam)
    for j in range(n):
        e = np.zeros(n)
        e[j] = fd_step
        jac[:, j] = (stepper(u + e, lam) - base) / fd_step
    return float(np.max(np.abs(np.linalg.eigvals(jac))))


@dataclass
class BranchPoint:
    lam: float
    u: np.ndarray
    converged: bool
    rho: float = float("nan")


def continue_branch(stepper: Stepper, lams: Sequence[float], u0: np.ndarray,
                    tol: float = 1e-8) -> List[BranchPoint]:
    """Track a fixed point along ``lams``, warm-starting each solve from the last one."""
    out: List[BranchPoint] = []
    u = np.asarray(u0, dtype=float)
    for lam in lams:
        u, info = fixed_point(stepper, float(lam), u, tol=tol)
        rho = spectral_radius(stepper, u, float(lam)) if info["converged"] else float("nan")
        out.append(BranchPoint(float(lam), u.copy(), bool(info["converged"]), rho))
    return out


def rk4_step(rhs: Callable[[np.ndarray, float], np.ndarray], u: np.ndarray, lam: float,
             dt: float) -> np.ndarray:
    """One classical RK4 step -- used to *generate* short-time training data."""
    k1 = rhs(u, lam)
    k2 = rhs(u + 0.5 * dt * k1, lam)
    k3 = rhs(u + 0.5 * dt * k2, lam)
    k4 = rhs(u + dt * k3, lam)
    return u + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
