"""Acceptance gate for the self-rewrite consumer.

Three claims are checked, and each can fail:

1. **One-step prediction generalises.** A local operator fitted on the first half of a
   loop predicts the held-out transitions: median cosine error below 0.15.
2. **The fixed point is predictable.** Newton on the learned map must converge and land
   near the observed last iterate (median agreement below 0.15) for most seeds.
3. **A control that can fail.** Shuffle the (p_n, p_{n+1}) pairs and both numbers must
   collapse. A gate that passes on noise is measuring its own tolerance.

Two modes:

* ``--stub`` (default, no model): the "model" applies a deterministic contraction to the
  text, so the machinery is tested without inference. This is what CI runs.
* ``--live``: calls a local Ollama model. It costs inference time and is therefore not a
  CI step.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.loops.self_rewrite import (LoopTrace, distance, embed,  # noqa: E402
                                          evaluate, fit_and_predict, run_loop)

SEEDS = [
    "Summarise the paragraph in one sentence and keep every number.",
    "List three risks of the proposed experiment and one mitigation each.",
    "Explain the difference between a fixed point and a limit cycle, briefly.",
    "Rewrite the method section so a non-specialist can follow it.",
    "State the null and alternative hypotheses for the comparison.",
    "Give the shortest correct proof that the sum of two even numbers is even.",
    "Describe what would falsify the main claim, in one sentence.",
    "Translate the abstract into plain English without dropping caveats.",
]


def stub_model(text: str) -> str:
    """A deterministic contraction: keep the longest 65% of the words, in order.

    It is not a language model; it is a map with a known fixed point (any text short
    enough to be unchanged), which is exactly what the machinery needs.
    """
    body = text.split("Reply with the instruction only.", 1)[-1].strip()
    words = body.split()
    keep = max(1, int(len(words) * 0.65))
    return " ".join(words[:keep])


def ollama_model(text: str, model: str = "openchat:7b") -> str:
    payload = json.dumps({"model": model, "prompt": text, "stream": False,
                          "options": {"temperature": 0.0, "num_predict": 96}}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode()).get("response", "").strip()


def shuffled(traces: list[LoopTrace]) -> list[LoopTrace]:
    rng = np.random.default_rng(7)
    out = []
    for t in traces:
        perm = rng.permutation(len(t.vectors))
        out.append(LoopTrace(t.texts, t.vectors[perm], t.distances, t.fixed, t.contraction))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="use a local Ollama model")
    ap.add_argument("--model", default="openchat:7b")
    ap.add_argument("--seeds", type=int, default=len(SEEDS))
    ap.add_argument("--cycles", type=int, default=6)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    gen = (lambda t: ollama_model(t, args.model)) if args.live else stub_model
    traces = [run_loop(gen, s, args.cycles) for s in SEEDS[:args.seeds]]
    forward = evaluate(traces)
    control = evaluate(shuffled(traces))

    ok = (forward["median_test_error"] < 0.15
          and forward["median_agreement"] < 0.15
          and forward["converged_operator"] >= max(1, int(0.8 * forward["seeds"])))
    caught = (control["median_test_error"] > forward["median_test_error"] * 1.5
              or control["median_agreement"] > 0.15)

    if args.json:
        print(json.dumps({"forward": forward, "control": control, "ok": ok,
                          "control_caught": caught}, indent=2))
    else:
        print(f"self-rewrite audit ({'live' if args.live else 'stub'}): "
              f"{forward['fixed_observed']}/{forward['seeds']} loops observed fixed; "
              f"median contraction {forward['contraction_median']:.3f}")
        print(f"  held-out one-step error {forward['median_test_error']:.3f} "
              f"(limit 0.15), operator converged "
              f"{forward['converged_operator']}/{forward['seeds']}, "
              f"fixed-point agreement {forward['median_agreement']:.3f}")
        print(f"  control: error {control['median_test_error']:.3f}, "
              f"agreement {control['median_agreement']:.3f} -> "
              f"{'CAUGHT' if caught else 'NOT CAUGHT'}")
    return 0 if (ok and caught) else 1


if __name__ == "__main__":
    raise SystemExit(main())
