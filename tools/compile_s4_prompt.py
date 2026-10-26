"""Compile a better S4 prompt on train cases, then judge it on cases it never saw.

The plan's P4 says DSPy `BootstrapFewShot`: pick demonstrations by measured accuracy, hold out at
least five cases, refuse below fifteen fixtures. DSPy itself is not installed here, and this file
does not claim to be DSPy — it is the same idea without the dependency: a greedy search over
demonstrations scored on train, one fixed holdout, and a refusal to report a gain that is not
measured on the holdout.

Baseline: the zero-shot instruction used by tools/probe_s4.py (0.733 overall, 2/6 on qualifications).
Candidate: the same instruction plus the three rule clauses the model ignored, and up to three
worked examples chosen greedily from train.

Usage: python tools/compile_s4_prompt.py --url http://127.0.0.1:8081
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from framework.inference.llama_cpp import JudgementUnavailable, LlamaCppClient  # noqa: E402
import probe_s4  # noqa: E402

# Stratified so the holdout contains the rule types the model missed, not five easy cases.
HOLDOUT = {"s4-03", "s4-06", "s4-09", "s4-13", "s4-14"}
MAX_DEMOS = 3

RULES = (
    " Apply these clauses exactly, in this order: "
    "(1) if no power analysis is reported, fail; "
    "(2) if fewer confounders are adjusted than named, fail; "
    "(3) if power is below 0.75, fail even when a shortfall was declared; "
    "(4) between 0.75 and 0.80, pass weakly only when the shortfall was declared before data "
    "collection, otherwise fail; "
    "(5) at or above 0.80, pass only when pre-registration is present, otherwise pass weakly.")


def answer(client: LlamaCppClient, system: str, case: dict):
    try:
        out = client.ask(system, probe_s4.prompt(case))
    except JudgementUnavailable:
        return None
    return (out["answer"] or {}).get("verdict")


def score(client: LlamaCppClient, system: str, cases: list[dict]) -> tuple[int, list[dict]]:
    rows = []
    for case in cases:
        got = answer(client, system, case)
        rows.append({"id": case["id"], "expected": probe_s4.label(case), "got": got,
                     "ok": got == probe_s4.label(case)})
    return sum(r["ok"] for r in rows), rows


def demo_text(case: dict) -> str:
    return f"{probe_s4.prompt(case)} -> {{\"verdict\":\"{probe_s4.label(case)}\"}}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--model", default="ScienceRSI-8b.i1-Q4_K_M.gguf")
    args = ap.parse_args()

    train = [c for c in probe_s4.CASES if c["id"] not in HOLDOUT]
    holdout = [c for c in probe_s4.CASES if c["id"] in HOLDOUT]
    assert len(train) + len(holdout) == len(probe_s4.CASES) and len(holdout) >= 5

    client = LlamaCppClient(base_url=args.url, model=args.model)
    base_system = probe_s4.SYSTEM

    base_train, base_rows = score(client, base_system, train)
    base_hold, base_hold_rows = score(client, base_system, holdout)
    print(f"baseline      train {base_train}/{len(train)}   holdout {base_hold}/{len(holdout)}")

    chosen: list[dict] = []
    system = base_system + RULES
    best = score(client, system, train)[0]
    for _ in range(MAX_DEMOS):
        gains = []
        for case in train:
            if case in chosen:
                continue
            trial = system + "\n" + "\n".join(demo_text(c) for c in chosen + [case])
            gains.append((score(client, trial, train)[0], case))
        if not gains:
            break
        gains.sort(key=lambda pair: pair[0], reverse=True)
        top_score, top_case = gains[0]
        if top_score <= best:
            break
        chosen.append(top_case)
        best = top_score
        system = base_system + RULES + "\n" + "\n".join(demo_text(c) for c in chosen)
        print(f"  + demo {top_case['id']}  train {best}/{len(train)}")

    cand_train, _ = score(client, system, train)
    cand_hold, cand_hold_rows = score(client, system, holdout)
    print(f"candidate     train {cand_train}/{len(train)}   holdout {cand_hold}/{len(holdout)}")
    for row in cand_hold_rows:
        print(f"   {row['id']} expected {row['expected']:9s} got {str(row['got']):9s} "
              f"{'ok' if row['ok'] else 'MISS'}")

    record = {
        "ts": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "optimizer": "greedy demonstration selection (BootstrapFewShot without rationales); not DSPy",
        "model": args.model, "train": [c["id"] for c in train], "holdout": sorted(HOLDOUT),
        "baseline": {"train": base_train, "holdout": base_hold,
                     "holdout_rows": base_hold_rows},
        "candidate": {"train": cand_train, "holdout": cand_hold,
                      "holdout_rows": cand_hold_rows, "demos": [c["id"] for c in chosen],
                      "system": system},
        "promoted": cand_hold > base_hold and cand_hold / len(holdout) >= 0.90,
    }
    out = ROOT / "artifacts" / "evaluation" / "s4_prompt_compile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    verdict = "PROMOTE" if record["promoted"] else "DO NOT PROMOTE"
    print(f"\n{verdict}: holdout {base_hold} -> {cand_hold} of {len(holdout)} "
          f"(bar: strictly better and >= 0.90)")
    print(f"written: {out.relative_to(ROOT)}")
    return 0 if record["promoted"] else 3


if __name__ == "__main__":
    sys.exit(main())
