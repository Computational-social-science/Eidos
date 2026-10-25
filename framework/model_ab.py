"""A/B for the decision model: the same fixed questions to two endpoints.

A model upgrade is not proved by a file hash. It is proved by asking both builds the same
questions and comparing what they answer. The questions are fixed here so that a comparison
between two runs is a comparison of models, not of prompts.

The thresholds are pre-registered in `configs/updates.yaml` and applied by `decide()`; a run that
falls short is a FAIL, not a warning.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "status" / "model_ab.json"

#: Fixed questions with closed option sets. They cover the kinds of decision the framework asks
#: (choose a branch, accept or hold, classify a failure), so a drift in any of them shows up.
PROMPTS: list[tuple[str, dict[str, str]]] = [
    ("A gate failed on an artefact whose checksum does not match the lock. Classify the cause.",
     {"environment": "the code is fine, the environment or cache changed",
      "methodology": "the check itself is wrong or mis-specified",
      "data": "the input data changed"}),
    ("A hypothesis survived screening but its effect size is inside the noise band. What now?",
     {"hold": "do not report it yet", "report": "report it with the interval",
      "replicate": "collect more data before deciding"}),
    ("Two chains disagree about the same project's verdict. Which one is authoritative?",
     {"gate": "the gate that checks the claim", "chain": "the chain that ran last",
      "none": "neither until the disagreement is explained"}),
    ("A dependency published a patch release. What should happen before the pin moves?",
     {"try": "try it in isolation and compare", "pin": "move the pin and watch CI",
      "ignore": "wait for the next minor"}),
    ("A manuscript claim cites a number that appears nowhere in the evidence file. Classify.",
     {"prose": "the prose and the evidence disagree",
      "evidence": "the evidence file is incomplete",
      "claim": "the claim itself is unsupported"}),
    ("A monitor reports PASS while its underlying sample is two days old. What is the verdict?",
     {"stale": "stale evidence is not a pass", "pass": "the last known state was fine",
      "fail": "the monitor is broken"}),
    ("A negative control passes. What does that say about the instrument?",
     {"blind": "the instrument cannot fail, so it proves nothing",
      "fine": "the control was mislabelled", "unknown": "not enough information"}),
    ("An upgrade passes its own probe but the chain audit fails afterwards. What is the cause?",
     {"coherence": "the candidate works alone but not with the rest",
      "flaky": "the audit is flaky", "probe": "the probe was too weak"}),
    ("A reviewer asks for the p-value of a comparison that was never pre-registered. Response?",
     {"exploratory": "label it exploratory and say so",
      "report": "compute it and report it as confirmatory",
      "refuse": "decline to compute it"}),
    ("Two runs of the same chain give different durations but identical verdicts. Is that a fault?",
     {"no": "duration is not a verdict", "yes": "determinism is broken",
      "maybe": "only if the difference exceeds the noise band"}),
    ("A fixture that should fail starts passing. What must be checked first?",
     {"fixture": "whether the fixture still contains the defect",
      "gate": "whether the gate stopped checking", "both": "both, in that order"}),
    ("An artifact's hash changed but its version string did not. What is the right response?",
     {"refuse": "refuse to use it until the difference is explained",
      "accept": "accept it, the version is what matters",
      "rehash": "update the lock to the new hash"}),
]


CONTEXT = "fixed A/B prompt; answer from the question alone"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def collect(url: str, prompts=None, timeout: float = 60.0) -> list[dict]:
    """Ask one endpoint every question. Unreachable is recorded, never invented."""
    import sys
    sys.path.insert(0, str(ROOT))
    from framework.decision import DecisionClient, DecisionUnavailable

    client = DecisionClient(url, timeout=timeout)
    rows = []
    for question, options in (prompts or PROMPTS):
        try:
            answer = client.choose(question, options, {"context": CONTEXT})
            rows.append({"question": question, "choice": answer.choice,
                         "probability": answer.probability})
        except DecisionUnavailable as exc:
            rows.append({"question": question, "choice": None, "probability": None,
                         "error": str(exc)})
    return rows


def compare(base: list[dict], candidate: list[dict]) -> dict:
    """Agreement and score drift over the questions both endpoints actually answered."""
    pairs = [(a, b) for a, b in zip(base, candidate)
             if a.get("choice") and b.get("choice")]
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a["choice"] == b["choice"])
    deltas = [abs((a.get("probability") or 0.0) - (b.get("probability") or 0.0)) for a, b in pairs]
    return {"n": n,
            "agreement": (agree / n) if n else 0.0,
            "mean_abs_delta": (sum(deltas) / len(deltas)) if deltas else None,
            "disagreements": [{"question": a["question"][:60], "base": a["choice"],
                               "candidate": b["choice"]}
                              for a, b in pairs if a["choice"] != b["choice"]]}


def decide(result: dict, min_agreement: float = 0.9, max_delta: float = 0.05,
           min_n: int = 10) -> dict:
    """The pre-registered rule. Every clause must hold; a short run is not a pass."""
    reasons = []
    if result["n"] < min_n:
        reasons.append(f"only {result['n']} of the questions were answered by both endpoints")
    if result["agreement"] < min_agreement:
        reasons.append(f"agreement {result['agreement']:.3f} < {min_agreement}")
    if result["mean_abs_delta"] is None or result["mean_abs_delta"] > max_delta:
        reasons.append(f"mean |Δp| {result['mean_abs_delta']} > {max_delta}")
    return {"ok": not reasons, "reasons": reasons,
            "thresholds": {"min_agreement": min_agreement, "max_delta": max_delta,
                           "min_n": min_n}}


def run(base_url: str, candidate_url: str | None = None, out: Path | None = None) -> dict:
    """Compare two endpoints (or one endpoint with itself, as a harness control)."""
    base = collect(base_url)
    candidate = collect(candidate_url or base_url)
    result = compare(base, candidate)
    verdict = decide(result)
    payload = {"ts": _now(), "base_url": base_url, "candidate_url": candidate_url or base_url,
               "control": not candidate_url, "n_prompts": len(PROMPTS),
               "result": result, "verdict": verdict}
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=os.environ.get("DECISION_SERVICE_URL", "http://127.0.0.1:8090"))
    ap.add_argument("--candidate", help="second endpoint; omit to run the harness control")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    payload = run(args.base, args.candidate, args.out)
    result, verdict = payload["result"], payload["verdict"]
    print(f"{'PASS' if verdict['ok'] else 'FAIL'}  model A/B"
          f"{' (control: same endpoint twice)' if payload['control'] else ''}")
    print(f"  answered by both: {result['n']}/{payload['n_prompts']}")
    print(f"  agreement: {result['agreement']:.3f}   mean |Δp|: {result['mean_abs_delta']}")
    for reason in verdict["reasons"]:
        print(f"  - {reason}")
    for row in result["disagreements"][:5]:
        print(f"  ≠ {row['base']} -> {row['candidate']}: {row['question']}")
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
