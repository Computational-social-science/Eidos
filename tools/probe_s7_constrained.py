"""S7 with the category decided by the artefact, not by the model.

The open-ended probe scored 0.750: every defective case was noticed, but two were filed under the
wrong category and one clean study was failed. Category matters because it selects the artefact a
pointer must land in, so a mislabelled objection cannot be adjudicated.

This asks the narrower question the architecture allows: given an artefact of a known type and one
claim, does the evidence support the claim? The model never names a category, so it cannot mislabel
one. If accuracy rises above 0.90 that is evidence for the architecture; if it does not, the problem
was never the taxonomy.

Usage: python tools/probe_s7_constrained.py --url http://127.0.0.1:18434 --model ScienceRSI-8b.i1-Q4_K_M
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
import probe_s7  # noqa: E402

ARTEFACT = {
    "statistics": "a statistical results table",
    "support": "the cited source, in full",
    "identification": "the citation record for the reference",
    "design": "the study design record",
    None: "the full package: verified citations, a pre-registered design, and the analysis",
}

SYSTEM = (
    "You are checking one claim against one artefact. Answer a single question: does this artefact "
    "support the claim as stated? Do not judge anything else. "
    'Answer only with JSON: {"supports": true|false, "reason": "one sentence"}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18434")
    ap.add_argument("--model", default="ScienceRSI-8b.i1-Q4_K_M")
    args = ap.parse_args()

    client = LlamaCppClient(base_url=args.url, model=args.model)
    rows, hits = [], 0
    for cid, planted, text in probe_s7.CASES:
        kind = ARTEFACT[planted]
        question = f"Claim and evidence: {text}\n\nThe artefact is {kind}. Does it support the claim?"
        try:
            out = client.ask(SYSTEM, question)
        except JudgementUnavailable as exc:
            print(f"{cid}: {exc}")
            return 1
        supports = bool((out["answer"] or {}).get("supports"))
        expected = planted is None            # clean cases should be supported
        ok = supports == expected
        hits += ok
        rows.append({"id": cid, "planted": planted, "supports": supports, "expected": expected,
                     "ok": ok, "reason": (out["answer"] or {}).get("reason")})
        print(f"{cid}  {'ok  ' if ok else 'MISS'}  supports={str(supports):5s} "
              f"expected={str(expected):5s}  {(out['answer'] or {}).get('reason', '')[:70]}")

    record = {"ts": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
              "model": args.model, "mode": "category fixed by artefact; model answers support only",
              "n": len(rows), "hits": hits, "accuracy": round(hits / len(rows), 3),
              "open_ended_accuracy": 0.750, "rows": rows}
    out_path = ROOT / "artifacts" / "evaluation" / "s7_constrained.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\naccuracy {hits}/{len(rows)} = {hits/len(rows):.3f}  (open-ended was 0.750)")
    print(f"written: {out_path.relative_to(ROOT)}")
    return 0 if hits / len(rows) >= 0.90 else 2


if __name__ == "__main__":
    sys.exit(main())
