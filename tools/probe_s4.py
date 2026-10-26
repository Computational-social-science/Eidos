"""S4 behavioural probe: fifteen labelled cases, one verdict each.

The plan's P3 gate is "behavioural probe >= 0.90 agreement before the model is promotable", and P4
refuses to compile prompts below fifteen labelled fixtures. This produces both: the cases, the
labels, the model's answers, and the agreement.

Labels are computed from the fields by the rule below, not assigned by eye — so the comparison is
"model vs rule", and the rule is the thing a reader can disagree with.

Rule (required power 0.80):
  no power reported                     -> FAIL
  confounders adjusted < named          -> FAIL
  power < 0.75                          -> FAIL
  0.75 <= power < 0.80                  -> WEAK_PASS if the shortfall was pre-declared, else FAIL
  power >= 0.80                         -> PASS if pre-registered, else WEAK_PASS

Usage: python tools/probe_s4.py [--url http://127.0.0.1:8081]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.inference.llama_cpp import JudgementUnavailable, LlamaCppClient  # noqa: E402

REQUIRED = 0.80
CASES = [
    dict(id="s4-01", power=0.41, prereg=True, named=2, adjusted=2, declared=False),
    dict(id="s4-02", power=0.93, prereg=True, named=2, adjusted=2, declared=False),
    dict(id="s4-03", power=0.78, prereg=True, named=2, adjusted=2, declared=True),
    dict(id="s4-04", power=0.78, prereg=True, named=2, adjusted=2, declared=False),
    dict(id="s4-05", power=None, prereg=True, named=0, adjusted=0, declared=False),
    dict(id="s4-06", power=0.86, prereg=True, named=3, adjusted=1, declared=False),
    dict(id="s4-07", power=0.86, prereg=False, named=1, adjusted=1, declared=False),
    dict(id="s4-08", power=0.74, prereg=True, named=1, adjusted=1, declared=True),
    dict(id="s4-09", power=0.80, prereg=True, named=0, adjusted=0, declared=False),
    dict(id="s4-10", power=0.99, prereg=True, named=4, adjusted=4, declared=False),
    dict(id="s4-11", power=0.55, prereg=False, named=0, adjusted=0, declared=False),
    dict(id="s4-12", power=0.90, prereg=True, named=2, adjusted=2, declared=False),
    dict(id="s4-13", power=0.79, prereg=False, named=1, adjusted=1, declared=True),
    dict(id="s4-14", power=0.60, prereg=True, named=3, adjusted=2, declared=False),
    dict(id="s4-15", power=0.95, prereg=True, named=1, adjusted=1, declared=False),
]

SYSTEM = (
    'You judge design validity under one rule: required power is 0.80; a study whose achieved power '
    'is between 0.75 and 0.80 is WEAK_PASS only if the shortfall was declared before data '
    'collection; unadjusted confounders or absent power analysis are FAIL. '
    'Answer only with JSON: {"verdict":"PASS|WEAK_PASS|FAIL",'
    '"checks":[{"id":"power","status":"PASS|FAIL|NOT_APPLICABLE","evidence_pointer":"string"}],'
    '"blocking":["id"]}')


def label(case: dict) -> str:
    if case["power"] is None:
        return "FAIL"
    if case["adjusted"] < case["named"]:
        return "FAIL"
    power = case["power"]
    if power < 0.75:
        return "FAIL"
    if power < REQUIRED:
        return "WEAK_PASS" if case["declared"] else "FAIL"
    return "PASS" if case["prereg"] else "WEAK_PASS"


def prompt(case: dict) -> str:
    power = ("no power analysis is reported" if case["power"] is None
             else f"achieved power is {case['power']:.2f}")
    shortfall = "the shortfall was declared before data collection" if case["declared"] \
        else "no shortfall was declared"
    return (f"A study reports: {power} against a required 0.80; "
            f"{case['named']} confounders are named and {case['adjusted']} are adjusted for; "
            f"pre-registration: {'present' if case['prereg'] else 'absent'}; {shortfall}. "
            f"Judge the design.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--model", default="ScienceRSI-8b.i1-Q4_K_M.gguf")
    args = ap.parse_args()

    client = LlamaCppClient(base_url=args.url, model=args.model)
    rows, agree = [], 0
    for case in CASES:
        expected = label(case)
        try:
            out = client.ask(SYSTEM, prompt(case))
        except JudgementUnavailable as exc:
            print(f"{case['id']}: {exc}")
            return 1
        got = (out["answer"] or {}).get("verdict")
        ok = got == expected
        agree += ok
        rows.append({"id": case["id"], "expected": expected, "got": got, "ok": ok,
                     "tokens": out["usage"].get("completion_tokens")})
        print(f"{case['id']}  expected {expected:9s} got {str(got):9s} {'ok' if ok else 'MISS'}")

    n = len(rows)
    record = {"ts": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
              "model": args.model, "url": args.url, "n": n, "agree": agree,
              "agreement": round(agree / n, 3), "rule": "required power 0.80; see tools/probe_s4.py",
              "rows": rows}
    out_path = ROOT / "artifacts" / "evaluation" / "s4_probe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nagreement {agree}/{n} = {agree/n:.3f}  (plan P3 threshold 0.90)")
    print(f"written: {out_path.relative_to(ROOT)}")
    return 0 if agree / n >= 0.90 else 2


if __name__ == "__main__":
    sys.exit(main())
