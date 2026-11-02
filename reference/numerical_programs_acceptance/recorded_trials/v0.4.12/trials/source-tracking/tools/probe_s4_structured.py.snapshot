"""Give the model the fields, not the prose, and see whether the verdicts change.

The prose probe scored 11/15, and every miss was a field it ignored rather than a rule it could not
apply. This asks the same fifteen cases with the fields already extracted — same model, same rule,
same temperature — so the difference isolates reading from judging.

If agreement rises to 15/15, the failure was extraction and the fix is an artefact, not a prompt.
If it stays at 11/15, the model cannot apply the rule even to structured input, and P2 closes as a
negative result.

Usage: python tools/probe_s4_structured.py --url http://127.0.0.1:8081
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from framework.inference.llama_cpp import JudgementUnavailable, LlamaCppClient  # noqa: E402
import probe_s4  # noqa: E402

SYSTEM = (
    "You judge design validity from a structured record. Apply the rule exactly: required power is "
    "0.80; below 0.75 fails; between 0.75 and 0.80 is WEAK_PASS only if shortfall_declared is true, "
    "otherwise FAIL; at or above 0.80 is PASS when pre_registered is true, otherwise WEAK_PASS; "
    "if confounders_adjusted < confounders_named, FAIL; if power is null, FAIL. "
    'Answer only with JSON: {"verdict":"PASS|WEAK_PASS|FAIL"}')


def record_of(case: dict) -> dict:
    return {"power": case["power"], "required_power": probe_s4.REQUIRED,
            "confounders_named": case["named"], "confounders_adjusted": case["adjusted"],
            "pre_registered": case["prereg"], "shortfall_declared": case["declared"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--model", default="ScienceRSI-8b.i1-Q4_K_M.gguf")
    args = ap.parse_args()

    client = LlamaCppClient(base_url=args.url, model=args.model)
    rows, agree = [], 0
    for case in probe_s4.CASES:
        payload = json.dumps(record_of(case), ensure_ascii=False)
        try:
            out = client.ask(SYSTEM, payload)
        except JudgementUnavailable as exc:
            print(f"{case['id']}: {exc}")
            return 1
        got = (out["answer"] or {}).get("verdict")
        want = probe_s4.label(case)
        agree += got == want
        rows.append({"id": case["id"], "expected": want, "got": got, "ok": got == want})
        print(f"{case['id']}  expected {want:9s} got {str(got):9s} {'ok' if got == want else 'MISS'}")

    n = len(rows)
    record = {"ts": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
              "model": args.model, "input": "structured fields (no prose)", "n": n, "agree": agree,
              "agreement": round(agree / n, 3), "rows": rows}
    out_path = ROOT / "artifacts" / "evaluation" / "s4_probe_structured.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nstructured agreement {agree}/{n} = {agree/n:.3f}  (prose was 11/15 = 0.733)")
    print(f"written: {out_path.relative_to(ROOT)}")
    return 0 if agree == n else 2


if __name__ == "__main__":
    sys.exit(main())
