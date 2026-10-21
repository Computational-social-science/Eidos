#!/usr/bin/env python
"""Measure and calibrate the decision operator on this project's question shapes.

WHY THIS EXISTS
    The 0.2 `none_probability` threshold and the 0.6 confidence floor in
    `Decision.accepted()` are not ours. Before either is used as a success criterion,
    the operator has to be measured on questions shaped like ours.

WHY ABSTENTION IS ASKED AS A THREE-WAY CHOICE
    A `noul` (yes/no) answer carries no `none_probability`: the engine reports it only
    for choice questions. An earlier version coerced that missing field to 0.0 and
    printed "mean none 0.000" for both classes -- a missing value dressed as a measured
    zero. Questions are asked as a choice among `yes`, `no`, `not_stated`, so abstention
    is the rate of `not_stated`, which is observable.

WHAT IT REPORTS
    * accuracy on answerable items, abstention rates per class, Fisher exact p;
    * a confidence-floor sweep on a tuning half: coverage (fraction of items acted on)
      and precision (share of acted-on items that were right), then the chosen floor
      evaluated once on a held-out half with a Wilson interval.

WHAT IT DOES NOT DO
    There is no human rater here, so no Cohen's kappa is reported: ground truth is
    constructed by the item generator, and kappa against a constructed truth would only
    restate accuracy in a different unit. Inter-rater agreement needs human labels.

Exit codes: 0 = measured, 3 = operator unavailable (SKIP).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.decision import DecisionClient, DecisionUnavailable  # noqa: E402

OPTIONS = {"yes": "the state establishes this as true",
           "no": "the state establishes this as false",
           "not_stated": "the state does not say"}

# (id, state, question, truth) -- truth None means "not answerable from the state".
HAND_ITEMS = [
    ("a1", "Trial 7 recorded 412 crates in the east wing.", "Did trial 7 record more than 400 crates?", True),
    ("a2", "Trial 9 recorded 388 crates in the east wing.", "Did trial 9 record more than 400 crates?", False),
    ("a3", "The pipeline processed 1,204 files in 38 seconds.", "Did the pipeline process more than 1,000 files?", True),
    ("a4", "The sample contains 96 participants, 61 of them women.", "Were more than half of the participants women?", True),
    ("a5", "Mean latency was 182 ms and the median was 169 ms.", "Was the mean below the median?", False),
    ("a6", "Arm B scored 0.71 and arm A scored 0.68.", "Did arm A score higher than arm B?", False),
    ("a7", "The memory budget was 12 GB and peak use was 8.0 GB.", "Did peak use exceed the budget?", False),
    ("a8", "The archive holds 157,314 sessions.", "Does the archive hold more than 150,000 sessions?", True),
    ("a9", "The first run took 4.4 s and the second took 0.18 s.", "Was the second run faster than the first?", True),
    ("a10", "Of 200 items, 145 passed.", "Did fewer than half of the items fail?", True),
    ("u1", "Trial 7 recorded 412 crates in the east wing.", "Was trial 7 run in March?", None),
    ("u2", "Trial 9 recorded 388 crates in the east wing.", "Did trial 9 use a different operator?", None),
    ("u3", "The pipeline processed 1,204 files in 38 seconds.", "Was the pipeline written in Rust?", None),
    ("u4", "The sample contains 96 participants, 61 of them women.", "Were the participants recruited in Germany?", None),
    ("u5", "Mean latency was 182 ms and the median was 169 ms.", "Was the latency measured on a laptop?", None),
    ("u6", "Arm B scored 0.71 and arm A scored 0.68.", "Did arm A use the larger model?", None),
    ("u7", "The memory budget was 12 GB and peak use was 8.0 GB.", "Was the GPU an RTX 4090?", None),
    ("u8", "The archive holds 157,314 sessions.", "Was the archive collected in 2019?", None),
    ("u9", "The first run took 4.4 s and the second took 0.18 s.", "Was the first run on a different machine?", None),
    ("u10", "Of 200 items, 145 passed.", "Did the reviewer expect 160 to pass?", None),
]

_ABSENT = ["on a GPU", "with seed 42", "by a second operator", "during the night shift",
           "from a remote host", "on a Tuesday"]


def generate_items(n_answerable: int, n_unanswerable: int, seed: int) -> list[tuple]:
    """Items whose truth is computable from the state, plus questions it cannot answer.

    Numbers are random but the arithmetic is exact, so ground truth never depends on
    the operator. The unanswerable half asks about attributes the state never carries,
    which is the shape of the question a gate must be able to decline.
    """
    rng = random.Random(seed)
    items = []
    for i in range(n_answerable):
        a, b = rng.randint(100, 999), rng.randint(100, 999)
        items.append((f"ga{i}", f"Run {i + 1} logged {a} events and {b} warnings.",
                      f"Did run {i + 1} log more events than warnings?", a > b))
    for i in range(n_unanswerable):
        a, b = rng.randint(100, 999), rng.randint(100, 999)
        items.append((f"gu{i}", f"Run {i + 1} logged {a} events and {b} warnings.",
                      f"Was run {i + 1} executed {rng.choice(_ABSENT)}?", None))
    return items


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    n = a + b + c + d
    row1, col1 = a + b, a + c
    observed = math.comb(row1, a) * math.comb(n - row1, col1 - a)
    total = math.comb(n, col1)
    extreme = 0
    for k in range(max(0, col1 - (n - row1)), min(row1, col1) + 1):
        p = math.comb(row1, k) * math.comb(n - row1, col1 - k)
        if p <= observed + 1e-9:
            extreme += p
    return extreme / total


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def sweep(rows: list[dict], taus: list[float]) -> list[dict]:
    """Coverage and precision of 'act only when confidence >= tau' on these rows."""
    out = []
    for tau in taus:
        acted = [r for r in rows if r["choice"] != "not_stated" and (r["confidence"] or 0) >= tau]
        correct = sum(1 for r in acted if r["choice"] == r["expected"])
        out.append({
            "tau": tau,
            "coverage": len(acted) / len(rows),
            "precision": (correct / len(acted)) if acted else float("nan"),
            "n_acted": len(acted),
            "correct": correct,
        })
    return out


def pick_tau(table: list[dict], min_precision: float, min_coverage: float) -> dict:
    """Smallest tau meeting the precision floor with acceptable coverage."""
    qualifying = [r for r in table
                  if r["n_acted"] and r["precision"] >= min_precision and r["coverage"] >= min_coverage]
    if qualifying:
        return qualifying[0]
    usable = [r for r in table if r["n_acted"]]
    return max(usable, key=lambda r: (r["precision"], r["coverage"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="decision service URL")
    parser.add_argument("--n", type=int, default=100, help="total items (default 100)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--min-precision", type=float, default=0.95)
    parser.add_argument("--min-coverage", type=float, default=0.40)
    parser.add_argument("--json", metavar="PATH", help="write the full record here")
    args = parser.parse_args()

    items = list(HAND_ITEMS)
    if args.n > len(items):
        extra = args.n - len(items)
        items += generate_items(extra // 2, extra - extra // 2, args.seed)
    items = items[:args.n] if args.n < len(items) else items

    client = DecisionClient(args.url) if args.url else DecisionClient()
    if not client.health().get("up"):
        print(f"SKIP  decision service not running at {client.url}")
        return 3

    rows = []
    for item_id, state, question, truth in items:
        expected = "not_stated" if truth is None else ("yes" if truth else "no")
        started = time.perf_counter()
        try:
            decision = client.choose(question, OPTIONS, state)
        except DecisionUnavailable as exc:
            print(f"SKIP  operator became unavailable mid-run: {exc}")
            return 3
        rows.append({
            "id": item_id,
            "class": "answerable" if truth is not None else "unanswerable",
            "expected": expected,
            "choice": decision.choice,
            "confidence": decision.confidence,
            "none": decision.none_probability,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        })

    answered = [r for r in rows if r["class"] == "answerable"]
    unknown = [r for r in rows if r["class"] == "unanswerable"]
    hits = sum(1 for r in answered if r["choice"] == r["expected"])
    abstain_a = sum(1 for r in answered if r["choice"] == "not_stated")
    abstain_u = sum(1 for r in unknown if r["choice"] == "not_stated")
    fisher_p = fisher_two_sided(abstain_u, len(unknown) - abstain_u,
                                abstain_a, len(answered) - abstain_a)
    latencies = [r["latency_ms"] for r in rows]
    none_reported = [r["none"] for r in rows if r["none"] is not None]

    print(f"n = {len(rows)}  ({len(answered)} answerable, {len(unknown)} unanswerable)")
    print(f"accuracy on answerable items : {hits}/{len(answered)} = {hits / len(answered):.3f}")
    print(f"abstention ('not_stated')    : answerable {abstain_a}/{len(answered)}, "
          f"unanswerable {abstain_u}/{len(unknown)}   Fisher p = {fisher_p:.2e}")
    print(f"none_probability             : {len(none_reported)}/{len(rows)} returned"
          + (f", max {max(none_reported):.3f}" if none_reported else ""))
    print(f"latency                      : median {statistics.median(latencies):.0f} ms, "
          f"max {max(latencies):.0f} ms")

    # Split by id so the two halves are fixed by the seed, not by request order.
    order = list(range(len(rows)))
    random.Random(args.seed + 1).shuffle(order)
    cut = len(order) // 2
    tune = [rows[i] for i in order[:cut]]
    held = [rows[i] for i in order[cut:]]

    taus = [round(0.50 + 0.01 * i, 2) for i in range(50)]
    table = sweep(tune, taus)
    chosen = pick_tau(table, args.min_precision, args.min_coverage)
    tau = chosen["tau"]

    acted_held = [r for r in held if r["choice"] != "not_stated" and (r["confidence"] or 0) >= tau]
    correct_held = sum(1 for r in acted_held if r["choice"] == r["expected"])
    precision = correct_held / len(acted_held) if acted_held else float("nan")
    lo, hi = wilson(correct_held, len(acted_held))

    print(f"\nconfidence floor, tuned on half the items (n={len(tune)}):")
    for r in [x for x in table if abs((x['tau'] * 100) % 10) < 1e-9][::5]:
        print(f"  tau={r['tau']:.2f}  acted={r['n_acted']:3d}  "
              f"precision={r['precision']:.3f}  coverage={r['coverage']:.2f}")
    print(f"  -> chosen tau = {tau:.2f}  (tune precision {chosen['precision']:.3f}, "
          f"coverage {chosen['coverage']:.2f})")

    # A floor can only be *located* where the operator sometimes errs. With zero errors,
    # precision is 1.0 at every tau and "the smallest tau that clears the precision
    # floor" is an artefact of the grid, not a finding.
    correct_answered = [r for r in answered if r["choice"] == r["expected"]]
    floor_observed = min((r["confidence"] or 0.0) for r in correct_answered) if correct_answered else None
    identified = any(r["precision"] < 1.0 for r in table if r["n_acted"])
    if not identified and floor_observed is not None:
        print(f"  [!] tau is NOT identified: no answer was wrong at any floor, so precision "
              f"stayed 1.000 across the grid.\n"
              f"      Lowest confidence on a correct answer: {floor_observed:.3f}. A floor at "
              f"or below that loses nothing measurable;\n"
              f"      placing it higher needs items the operator sometimes gets wrong.")

    print(f"held-out (n={len(held)}): acted on {len(acted_held)} "
          f"({len(acted_held) / len(held):.2f}), precision {precision:.3f} "
          f"[95% CI {lo:.2f}-{hi:.2f}]")
    print(f"abstentions among held-out answerable: "
          f"{sum(1 for r in held if r['class'] == 'answerable' and r['choice'] == 'not_stated')}"
          f"/{sum(1 for r in held if r['class'] == 'answerable')}")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "items": rows, "accuracy": hits / len(answered),
            "abstain_answerable": abstain_a / len(answered),
            "abstain_unanswerable": abstain_u / len(unknown),
            "fisher_p": fisher_p, "tau": tau,
            "tau_identified": identified,
            "min_confidence_correct": floor_observed,
            "held_out": {"n": len(held), "acted": len(acted_held),
                         "precision": precision, "ci": [lo, hi]},
            "sweep": table,
        }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
