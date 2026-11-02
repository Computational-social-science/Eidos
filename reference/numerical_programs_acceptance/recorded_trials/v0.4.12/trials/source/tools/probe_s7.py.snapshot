"""S7 probe: a different rule family from S4, on purpose.

S4 asked for an inequality and the model got the inequalities wrong even with the numbers in front of
it. S7 asks for something else — find the defect a referee would find, and name its category. If the
model fails this too, the conclusion is not "the prompt needs work" but "this model is not a gate
component".

Twelve scenarios: eight with one planted defect (two per category), four clean. A defect counts as
found only when a major or fatal objection names the right category; a clean case counts only when no
major or fatal objection is raised. Both directions are scored, because a model that objects to
everything would otherwise look good.

Usage: python tools/probe_s7.py --url http://127.0.0.1:8081
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.inference.llama_cpp import JudgementUnavailable, LlamaCppClient  # noqa: E402

SYSTEM = (
    "You are simulating a referee. Read the claim and its evidence summary, and list the objections a "
    "careful referee would raise. Categories: identification (wrong or retracted source, citation does "
    "not support the claim), statistics (test, power, multiplicity, effect size), design (confounding, "
    "selective outcome, missing control), other. Severity: minor, major, fatal. "
    'Answer only with JSON: {"verdict":"PASS|WEAK_PASS|FAIL","objections":[{"severity":"minor|major|'
    'fatal","category":"identification|statistics|design|other","evidence_pointer":"string",'
    '"resolvable":true,"suggested_revision":"string"}]}')

CASES = [
    ("S7-01", "statistics",
     "Claim: the treatment improves recall. Evidence: p = 0.04 with n = 6 per group; twelve "
     "comparisons were run and none was corrected."),
    ("S7-02", "statistics",
     "Claim: the design was adequately powered. Evidence: achieved power 0.41 for the claimed effect "
     "size, against a pre-registered requirement of 0.80."),
    ("S7-03", "support",
     "Claim: X causes Y. Evidence: the cited paper reports only a correlation, in a different "
     "population, and says causation was not tested."),
    ("S7-04", "support",
     "Claim: the effect replicates. Evidence: the cited replication is of a different intervention "
     "with a different outcome measure."),
    ("S7-05", "identification",
     "Claim: prior work established the baseline. Evidence: the DOI resolves to a different paper by "
     "different authors with a similar title."),
    ("S7-06", "identification",
     "Claim: the method follows established practice. Evidence: the cited article was retracted."),
    ("S7-07", "design",
     "Claim: the intervention improved the outcome. Evidence: treatment and control differ by 12 years "
     "in baseline age, and age was not adjusted in the model."),
    ("S7-08", "design",
     "Claim: the primary outcome improved. Evidence: the pre-registration names a different primary "
     "outcome; the reported one was chosen after inspection."),
    ("S7-09", None,
     "Claim: the intervention improves recall by 4 points. Evidence: pre-registered; power 0.93; two "
     "confounders named and both adjusted; citation verified and not retracted; independent "
     "replication reported."),
    ("S7-10", None,
     "Claim: the effect holds in the sampled population only. Evidence: power 0.88; three confounders "
     "adjusted; claims limited to the sampled population; sources verified."),
    ("S7-11", None,
     "Claim: the assay is specific. Evidence: a negative control was included and behaved as expected; "
     "power 0.81; sources verified; no selective reporting declared."),
    ("S7-12", None,
     "Claim: the result replicates. Evidence: two independent replications; pre-registered; citations "
     "verified; confounders named and adjusted."),
]

MAJOR = ("major", "fatal")


def judge(answer: dict) -> tuple[bool, str]:
    objections = answer.get("objections") or []
    hard = [o for o in objections if o.get("severity") in MAJOR]
    return bool(hard), ",".join(sorted({str(o.get("category")) for o in hard}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--model", default="ScienceRSI-8b.i1-Q4_K_M.gguf")
    args = ap.parse_args()

    client = LlamaCppClient(base_url=args.url, model=args.model)
    rows, hits = [], 0
    for cid, planted, text in CASES:
        try:
            out = client.ask(SYSTEM, text)
        except JudgementUnavailable as exc:
            print(f"{cid}: {exc}")
            return 1
        answer = out["answer"] or {}
        hard, categories = judge(answer)
        if planted is None:
            ok = not hard
            note = "clean" if ok else f"false positive: {categories}"
        else:
            ok = planted in categories.split(",")
            note = f"expected {planted}, got {categories or 'none'}"
        hits += ok
        rows.append({"id": cid, "planted": planted, "caught": hard, "categories": categories,
                     "ok": ok, "verdict": answer.get("verdict"), "note": note})
        print(f"{cid}  {'ok  ' if ok else 'MISS'}  {note:40s} verdict={answer.get('verdict')}")

    defective = [r for r in rows if r["planted"]]
    clean = [r for r in rows if not r["planted"]]
    record = {
        "ts": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": args.model, "n": len(rows), "hits": hits,
        "accuracy": round(hits / len(rows), 3),
        "sensitivity": round(sum(r["ok"] for r in defective) / len(defective), 3),
        "specificity": round(sum(r["ok"] for r in clean) / len(clean), 3),
        "rows": rows,
    }
    out_path = ROOT / "artifacts" / "evaluation" / "s7_probe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\naccuracy {hits}/{len(rows)} = {hits/len(rows):.3f} | sensitivity "
          f"{record['sensitivity']} | specificity {record['specificity']}")
    print(f"written: {out_path.relative_to(ROOT)}")
    return 0 if hits / len(rows) >= 0.90 else 2


if __name__ == "__main__":
    sys.exit(main())
