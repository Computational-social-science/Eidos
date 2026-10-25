"""DEMO · can the pipeline tell a valid estimator from a biased one?

A planted-truth study: the effect is known by construction, so the estimator's bias and interval
coverage can be measured rather than argued about. Two estimators are run on the same simulated
data — the honest difference in means, and the same estimator with a deliberate +0.30 offset.

The honest one must cover the planted value at roughly its nominal rate; the biased one must not.
If both looked fine, the measurement would be blind, and no amount of prose would fix that.

    python build_evidence.py        # ~1 s, no model, no network
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def eidos_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "framework" / "gates").is_dir():
            return parent
    raise SystemExit("cannot locate Eidos: set EIDOS_ROOT")


ROOT = eidos_root(HERE)
sys.path.insert(0, str(ROOT))

from framework.gates import AcceptanceGate  # noqa: E402
OUT = HERE / "docs" / "evidence.json"

THETA = 0.5          # planted effect of x on y
SIGMA = 1.0
N_PER_SIM = 200
N_SIMS = 400
BIAS = 0.30          # the corruption the biased estimator carries
SEED = 20261025
Z = 1.959964


def run() -> dict:
    rng = np.random.default_rng(SEED)
    covered_honest = 0
    covered_biased = 0
    estimates = []
    for _ in range(N_SIMS):
        x = rng.integers(0, 2, N_PER_SIM)
        y = THETA * x + rng.normal(0.0, SIGMA, N_PER_SIM)
        n1, n0 = int(x.sum()), int((1 - x).sum())
        if n1 == 0 or n0 == 0:
            continue
        theta_hat = y[x == 1].mean() - y[x == 0].mean()
        se = math.sqrt(SIGMA ** 2 * (1 / n1 + 1 / n0))
        lo, hi = theta_hat - Z * se, theta_hat + Z * se
        estimates.append(theta_hat)
        covered_honest += int(lo <= THETA <= hi)
        # the same interval, shifted: this is what a corrupted pipeline would report
        lo_b, hi_b = lo + BIAS, hi + BIAS
        covered_biased += int(lo_b <= THETA <= hi_b)

    n = len(estimates)
    return {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "theta_true": THETA,
        "theta_hat": round(float(np.mean(estimates)), 4),
        "bias": round(float(np.mean(estimates) - THETA), 4),
        "coverage": round(covered_honest / n, 3),
        "coverage_biased": round(covered_biased / n, 3),
        "n_sims": n,
        "n_per_sim": N_PER_SIM,
        "seed": SEED,
        "bias_shift": BIAS,
    }


def gate(data: dict) -> tuple[list[dict], bool]:
    """Quantitative acceptance, with the direction of every threshold stated.

    Coverage must be at least 0.90; the corrupted estimator's coverage must be at most 0.60.
    A bare threshold would silently pass one of these the wrong way round.
    """
    criteria = {
        "coverage": {"threshold": 0.90, "direction": ">="},
        "coverage_biased": {"threshold": 0.60, "direction": "<="},
        "abs_bias": {"threshold": 0.05, "direction": "<="},
    }
    results = {"coverage": data["coverage"], "coverage_biased": data["coverage_biased"],
               "abs_bias": abs(data["bias"])}
    outcome = AcceptanceGate({"name": "quantitative acceptance"}).run(
        {"results": results, "criteria": criteria})
    rows = [{"metric": metric, **detail} for metric, detail in outcome.details.items()]
    return rows, outcome.passed


def main() -> int:
    data = run()
    rows, passed = gate(data)
    data["gates"] = rows
    data["accepted"] = passed
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"theta* {data['theta_true']} · mean estimate {data['theta_hat']} "
          f"(bias {data['bias']:+.4f}) · coverage {data['coverage']:.3f} · "
          f"biased estimator coverage {data['coverage_biased']:.3f} "
          f"over {data['n_sims']} simulations")
    print(f"wrote {OUT}")
    for row in rows:
        print(f"  {'PASS' if row.get('met') else 'FAIL'}  {row['metric']}: "
              f"{row.get('value')} {row.get('direction')} {row.get('threshold')}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
