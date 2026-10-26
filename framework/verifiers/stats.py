"""Recompute reported statistics instead of believing them.

The plan's rule: a number in the evaluation either matches a deterministic recomputation inside
tolerance or the quantitative gate fails. The model never supplies these numbers, and no model is
loaded to check them.

The arithmetic comes from `academic_research_kernel` (deterministic functions over scipy), not
from Eidos: p from t/F/chi2, Cohen's d, achieved power, CI consistency, odds/risk ratios. This
module is the binding layer — it reads a declarative spec, calls those functions, compares against
what the document reported, and writes an artefact a gate can point at.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTEFACT = ROOT / "artifacts" / "evaluation" / "stat_recompute.json"

#: The plan asks for a relative tolerance of 1e-3 on p and on the effect size. Applied literally
#: that rejects any rounded report: d = 0.44 against a recomputed 0.4417 is a 0.4 % difference and
#: would fail, as would p = 0.09 against 0.0925. The comparison here is therefore made at the
#: precision the document claims — half a unit in the last reported place — with REL_TOL as a floor
#: for values reported with many digits. A misstated number still fails; a rounded one does not.
REL_TOL = 1e-3


def _decimals(value: float) -> int:
    text = repr(float(value))
    if "e" in text or "E" in text:
        return 6
    return len(text.split(".")[1]) if "." in text else 0


def _matches(reported: float, recomputed: float) -> tuple[bool, float]:
    """Agreement at the reported precision. Returns (agrees, allowed difference)."""
    half_ulp = 0.5 * 10 ** (-_decimals(reported))
    allowed = half_ulp + REL_TOL * abs(recomputed)
    return abs(float(reported) - float(recomputed)) <= allowed, allowed


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _kernel():
    try:
        import academic_research_kernel.recompute as recompute
    except ModuleNotFoundError as exc:                       # pragma: no cover - environment
        raise RuntimeError(
            "academic-research-kernel is not installed: `pip install academic-research-kernel` "
            "(extra: verifiers)") from exc
    return recompute


def _relative_delta(reported: float, recomputed: float) -> float:
    if reported == recomputed:
        return 0.0
    scale = max(abs(reported), abs(recomputed), 1e-12)
    return abs(reported - recomputed) / scale


def recompute(spec: dict) -> dict:
    """Run every statistic the spec reports, and say which ones disagree.

    Spec (all keys optional except `groups` for a t test):

        {"test": "t",
         "groups": {"m1": 1.2, "sd1": 0.4, "n1": 30, "m2": 1.0, "sd2": 0.5, "n2": 30},
         "reported": {"p": 0.031, "d": 0.44, "ci": [0.02, 0.38], "power": 0.62},
         "ci_level": 0.95}
    """
    rk = _kernel()
    spec = dict(spec or {})
    test = spec.get("test", "t")
    groups = spec.get("groups") or {}
    reported = spec.get("reported") or {}
    checks: list[dict] = []

    if test != "t":
        raise ValueError(f"unsupported test {test!r}; this binding implements the two-sample t test")

    need = ("m1", "sd1", "n1", "m2", "sd2", "n2")
    missing = [key for key in need if key not in groups]
    if missing:
        raise ValueError(f"groups is missing {missing}")

    m1, sd1, n1 = float(groups["m1"]), float(groups["sd1"]), int(groups["n1"])
    m2, sd2, n2 = float(groups["m2"]), float(groups["sd2"]), int(groups["n2"])

    # Pooled-variance t and df: the conventional two-sample test a paper reports.
    sp2 = ((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2)
    se = math.sqrt(sp2 * (1 / n1 + 1 / n2))
    t_value = (m1 - m2) / se if se else float("inf")
    df = n1 + n2 - 2

    recomputed = {"t": t_value, "df": df}
    p_result = rk.p_from_t(t_value, df)
    recomputed["p"] = float(p_result["recomputed"])

    if "p" in reported:
        rp = float(reported["p"])
        # The kernel compares at the reported precision, which is the question a reader asks:
        # does the printed p follow from the printed test statistic?
        match = rk.check_p_match(rp, recomputed["p"])
        agrees = bool(match.get("match", match.get("consistent", False)))
        checks.append({"id": "p", "reported": rp, "recomputed": recomputed["p"],
                       "relative_delta": _relative_delta(rp, recomputed["p"]),
                       "status": "PASS" if agrees else "FAIL", "detail": match})

    d_result = rk.cohens_d(m1, sd1, n1, m2, sd2, n2)
    recomputed["d"] = float(d_result["recomputed"]["cohens_d"])
    recomputed["g"] = float(d_result["recomputed"]["hedges_g"])
    if "d" in reported:
        rd = float(reported["d"])
        agrees, allowed = _matches(rd, recomputed["d"])
        checks.append({"id": "d", "reported": rd, "recomputed": recomputed["d"],
                       "relative_delta": _relative_delta(rd, recomputed["d"]),
                       "allowed": allowed, "status": "PASS" if agrees else "FAIL"})

    if "power" in reported:
        power = rk.achieved_power_ttest(recomputed["d"], n1, n2)
        recomputed["power"] = float(power["recomputed"])
        rpw = float(reported["power"])
        agrees, allowed = _matches(rpw, recomputed["power"])
        checks.append({"id": "power", "reported": rpw, "recomputed": recomputed["power"],
                       "relative_delta": _relative_delta(rpw, recomputed["power"]),
                       "allowed": allowed, "status": "PASS" if agrees else "FAIL"})

    if "ci" in reported:
        level = float(spec.get("ci_level", 0.95))
        ci = [float(x) for x in reported["ci"]]
        ci_result = rk.check_ci_consistency(m1 - m2, ci[0], ci[1], level=level)
        recomputed["ci"] = ci
        # Two conditions, as the plan states: the CI must contain the reported estimate, and its
        # midpoint must be consistent with it.
        contains = ci[0] <= (m1 - m2) <= ci[1]
        consistent = bool(ci_result.get("consistent", ci_result.get("ok", False)))
        checks.append({"id": "ci", "reported": ci, "estimate": m1 - m2,
                       "contains_estimate": contains, "midpoint_consistent": consistent,
                       "status": "PASS" if (contains and consistent) else "FAIL",
                       "detail": ci_result})

    verdict = "PASS" if checks and all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {"ts": _now(), "test": test, "inputs": groups, "recomputed": recomputed,
            "checks": checks, "verdict": verdict,
            "tolerance": {"relative": REL_TOL},
            "library": "academic-research-kernel"}


def check(spec: dict, out: Path | None = None) -> dict:
    """Recompute and persist. The artefact is what a gate points at, not the conversation."""
    result = recompute(spec)
    target = out or ARTEFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["artefact"] = str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target)
    return result
