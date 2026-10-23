"""Demo data for the front page: fixed points of a learned short-time operator.

This module is the single source for the numbers the demo shows. The page renders them;
nothing else computes them. It previously lived in `tools/surrogate_lab.py`, which also
built a second standalone page -- two implementations of the same figure, which the
framework's own single-source rule forbids.

The system is ``du/dt = lam - u^2``; the operator is fitted on one-step pairs and the
fixed point is solved by Newton on the learned map. Every quantity here is measured, not
assumed: ``max_rel_error`` compares against the closed form ``sqrt(lam)``.
"""

from __future__ import annotations

import numpy as np

from ..surrogate import RandomFeatureOperator, fixed_point, spectral_radius

# The training pairs are generated with RK4 in the audit tool; import lazily so this
# module does not depend on a tool at import time.
GRID = 91
CHECK = (0.20, 0.40, 0.60, 0.80, 1.00)
DT = 0.05


def _rhs(u: np.ndarray, lam: float) -> np.ndarray:
    return lam - u * u


def _rk4(u: np.ndarray, lam: float, dt: float = DT) -> np.ndarray:
    k1 = _rhs(u, lam)
    k2 = _rhs(u + 0.5 * dt * k1, lam)
    k3 = _rhs(u + 0.5 * dt * k2, lam)
    k4 = _rhs(u + dt * k3, lam)
    return u + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)


def _pairs(n: int = 1200, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    lam = rng.uniform(0.1, 1.0, size=n)
    u = (np.sqrt(lam) + rng.normal(0.0, 0.25, size=n)).reshape(-1, 1)
    u_next = np.array([_rk4(row, float(l)) for row, l in zip(u, lam)])
    return u, u_next, lam


def _trace(op, lam: float, u0: float = 1.0, steps: int = 6) -> list[float]:
    u = np.array([u0], dtype=float)
    trace = [float(u[0])]
    for _ in range(steps):
        u, info = fixed_point(op.step, lam, u, tol=1e-10, max_iter=1)
        trace.append(float(u[0]))
        if info["converged"]:
            break
    u, _ = fixed_point(op.step, lam, np.array([u0], dtype=float), tol=1e-10, max_iter=80)
    trace.append(float(u[0]))
    return trace


def build_demo() -> dict:
    u, u_next, lam = _pairs()
    op = RandomFeatureOperator(n_features=256, seed=0).fit(u, u_next, lam)

    rows = []
    for value in np.linspace(0.1, 1.0, GRID):
        u_star, info = fixed_point(op.step, float(value), np.array([1.0]), tol=1e-9)
        truth = float(np.sqrt(value))
        rho = spectral_radius(op.step, u_star, float(value)) if info["converged"] else None
        rows.append({"lam": round(float(value), 4),
                     "learned": round(float(u_star[0]), 6) if info["converged"] else None,
                     "truth": round(truth, 6),
                     "rho": round(float(rho), 5) if rho is not None else None,
                     "rel_error": round(abs(float(u_star[0]) - truth) / truth, 6)
                     if info["converged"] else None})

    checkpoints = [r for r in rows if any(abs(r["lam"] - c) < 0.006 for c in CHECK)]
    errors = [r["rel_error"] for r in rows if r["rel_error"] is not None]
    return {"dt": DT, "features": 256, "train_rows": int(len(u)), "seed": 0,
            "grid": GRID, "rows": rows, "checkpoints": checkpoints,
            "traces": {f"{lam0:.2f}": _trace(op, lam0) for lam0 in (0.2, 0.5, 0.9)},
            "max_rel_error": max(errors) if errors else None,
            "median_rel_error": float(np.median(errors)) if errors else None}
