# Decoder constraints exposed the next C0 bottleneck

Two actual local-model trials now generated structurally admissible programs.
**Both programs failed all 23 joint loss/gradient development points. Neither
candidate was retained or promoted. Scientific RSI remains unproved.**

The [study record](RSI-C0-DECODER-STUDY-2026-11-02.json) retains exact responses,
actual numerical outputs, protocol/source bindings, resource observations and
archive hashes. The [backend-control record](RSI-C0-DECODER-CONTROLS-2026-11-02.json)
retains both the failed initial probe and the successful bounded probe.

## Outcomes

| Artifact | Target request | Generated tokens | Stop | Syntax | Joint numerical conformance |
|---|---:|---:|---|---|---:|
| Qwen3.8-27B-UD-Q4_K_M | 172.953 s | 363 | stop | Admissible | 0/23 |
| ScienceRSI-8b.i1-Q4_K_M | 42.469 s | 313 | stop | Admissible | 0/23 |

Qwen's small-input loss takes `log(expm1(-x))`, whose argument is negative.
Its corresponding derivative uses `exp(x)/expm1(x)`, and the large-input
derivative has the wrong sign. ScienceRSI's program never uses the input `x`:
both outputs are constant expressions. These are diagnoses of the recorded
programs, not general claims about either model's scientific ability.

The score is a joint check: loss and first derivative must both conform at a
represented float32/float64 input. Some forward values can conform while the
point fails its derivative check. Twenty-three points in one known public task
are not 23 independent research problems or a model-accuracy estimate.

The [previous v1 trials](RSI-C0-MODEL-TRIALS-2026-11-01.md) were rejected before
numerical grading. They have no numerical 0/23 score. This follow-up removes an
observed formatting obstacle in these two responses and reveals mathematical
defects; it does not establish a general format-reliability rate.

## Intervention and controls

The model artifacts, original prompt, seed 19, temperature 0, top_p 0.9,
thinking disabled, 768 target output-token budget and resource policy match v1.
A direct GBNF decoder replaced generic JSON-object formatting. It fixes field
order, arity and types, bounds external whitespace and explanation length, and
admits a conservative balanced subset with at most 22 nodes per numeric
expression and depth 16. It does not encode the known repair. The accepted
external positive repair fits this subset.

This is a changed decoding procedure and search space, not a clean causal test
of one syntax feature. The 128-character explanation limit can end a sentence
midway even with a normal stop. Admissible explanatory text was not graded for
scientific faithfulness.

An initial recursive grammar passed two of three backend controls; one response
nested until its 256-token limit. It remains NOT_ACCEPTED. A revised bounded
grammar passed three of three controls with a 768-token limit. These probes also
had different time budgets, so their difference cannot be attributed solely to
the grammar. They test backend enforcement, not mathematics.

Each actual target was the first inference on its fresh owned server; recorded
prompt-cache tokens were zero. A separate literal-output control ran afterward
on that model/template. Both controls passed. This order avoids using the
control to prime the target. Auxiliary calls and server load remain additional
development cost; the table reports target-request time only.

## Runtime acceptance is not candidate acceptance

Both outer launchers exited zero, the existing service identity/health checks
were preserved, and recorded resource/sampling error lists were empty. Owned
server processes were terminated after their trials. Runtime acceptance means
the bounded trial executed and its evidence met the runtime contract; it does
not mean the candidate passed the numerical task. Shared-host sampling does
not prove uninterrupted uptime or isolate model memory consumption.

The proposal core remains commit
`639a90367f9bc9db9b3022a691402b9a8f7da04c`.
[Archived executed sources](../reference/rsi_bootstrap/recorded_trials/README.md)
identify the separate controllers, workers, decoder validator and launchers.
Their host-specific paths are not a portable runtime package. Protocol source
digests use canonical LF; archive digests bind exact stored bytes.

| Profile | Frozen protocol SHA-256 |
|---|---|
| Qwen v2 | `b4abc5b5c182149ac6705a81ce1de128c34654ea6dfd91d8850e80b8556ced4f` |
| ScienceRSI v2 | `af56c10ccfd755a6b69859dd6d5e616fc1ff7bf7994e1b8705aa1d0dbeedf4e4` |

The export validation requires the exact baseline profile inventory and binds
the archived grammar to both the frozen protocol and actual target request.
Its adversarial checks reject truncated baselines, altered executed sources,
inconsistent responses and changed request fields before publication.

## Replay and next decision

Run from the repository root in the existing project environment, without
weights, provider keys or network:

```python
import json
from pathlib import Path
from reference.rsi_bootstrap.c0 import run_once

record = json.loads(Path("docs/RSI-C0-DECODER-STUDY-2026-11-02.json").read_text())
for row in record["rows"]:
    replay = run_once(lambda prompt: row["raw_response"])
    assert replay["status"] == row["candidate_status"]
    assert len(replay["points"]) == 23
    assert replay["candidate_conforming_points"] == 0
    assert not replay["retained_for_development"]
    assert not replay["scientific_promotion"]
    print(row["profile"], replay["status"], "0/23")
```

This replays the preserved mathematical decisions, not model inference or its
timing. Keep these failures as development evidence. Next, preregister a finite,
local-only method-retrieval and counterexample-feedback experiment with matched
budgets. The [component assembly plan](RSI-COMPONENT-ASSEMBLY-2026-11-02.md)
selects reusable resources under the no-paid-service requirement. No sealed
evaluation, transfer result or recursive improvement was measured here.
