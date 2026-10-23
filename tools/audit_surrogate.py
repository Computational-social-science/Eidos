"""Acceptance gate for the local-NO layer: recover a planted truth, or fail.

The system is ``du/dt = lam - u^2``, chosen because every quantity the module claims to
compute is known in closed form:

    fixed point   u*(lam) = sqrt(lam)        for lam > 0, none for lam < 0
    stability     dS/du = 1 - 2 u* dt       (|.| < 1 near the fixed point)

The operator sees only short-time pairs from ``lam in [0.1, 1.0]``. It must then

1. recover ``u*(lam)`` for held-out ``lam`` within 5% relative error at >= 90% of points,
2. produce a spectral radius below 1 at those fixed points, and
3. fail the same test when the training labels are shuffled -- a gate that cannot fail is
   not a gate.

No extrapolation is claimed: the continuation runs inside the training interval, because
a learned stepper has no business asserting behaviour outside its data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.surrogate import (RandomFeatureOperator, continue_branch,  # noqa: E402
                                 fixed_point, rk4_step, spectral_radius)

DT = 0.05
RHS = lambda u, lam: lam - u * u  # noqa: E731


def training_pairs(n: int = 1200, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    lam = rng.uniform(0.1, 1.0, size=n)
    # Sample around the true branch so the local pairs are informative, plus some spread.
    u = np.sqrt(lam) + rng.normal(0.0, 0.25, size=n)
    u = u.reshape(-1, 1)
    u_next = np.array([rk4_step(RHS, row, float(l), DT) for row, l in zip(u, lam)])
    return u, u_next, lam


def evaluate(shuffle: bool = False) -> dict:
    u, u_next, lam = training_pairs()
    if shuffle:
        rng = np.random.default_rng(123)
        perm = rng.permutation(len(u))
        u_next = u_next[perm]
    op = RandomFeatureOperator(n_features=256, seed=0).fit(u, u_next, lam)

    lams = np.linspace(0.1, 1.0, 19)
    branch = continue_branch(op.step, lams, u0=np.array([1.0]))
    rows = []
    for point in branch:
        truth = float(np.sqrt(point.lam))
        rel = abs(float(point.u[0]) - truth) / truth if point.converged else float("inf")
        rows.append({"lam": point.lam, "u": float(point.u[0]) if point.converged else None,
                     "truth": truth, "rel_error": rel, "rho": point.rho,
                     "converged": point.converged})
    good = [r for r in rows if r["converged"] and r["rel_error"] < 0.05]
    stable = [r for r in good if r["rho"] < 1.0]
    return {
        "points": len(rows),
        "converged": sum(1 for r in rows if r["converged"]),
        "within_5pct": len(good),
        "fraction_within": len(good) / len(rows),
        "stable": len(stable),
        "worst_rel_error": max((r["rel_error"] for r in rows if r["converged"]), default=None),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--negative-test", action="store_true",
                    help="shuffle the training labels; the gate must catch it")
    args = ap.parse_args(argv)

    forward = evaluate(shuffle=False)
    ok = forward["fraction_within"] >= 0.90 and forward["stable"] >= forward["within_5pct"]

    if args.negative_test:
        control = evaluate(shuffle=True)
        caught = control["fraction_within"] < 0.90
        if args.json:
            print(json.dumps({"forward": forward, "control": control, "caught": caught},
                             indent=2))
        else:
            print(f"control (shuffled labels): {control['fraction_within']:.0%} within 5% "
                  f"-> {'CAUGHT' if caught else 'NOT CAUGHT'}")
        return 0 if caught else 1

    if args.json:
        print(json.dumps(forward, indent=2))
    else:
        print(f"local-NO audit: {forward['within_5pct']}/{forward['points']} fixed points "
              f"within 5% ({forward['fraction_within']:.0%}), "
              f"{forward['stable']} stable, worst relative error "
              f"{forward['worst_rel_error']:.4f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
