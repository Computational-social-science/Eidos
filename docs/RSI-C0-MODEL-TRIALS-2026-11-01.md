# First real local-model C0 development trials

Two first-attempt model trials completed on the same public log1mexp task.
**Neither produced an admissible candidate. Numerical correctness was not
assessed for either response. No model or procedure was promoted.**

The [machine-readable record](RSI-C0-MODEL-TRIALS-2026-11-01.json) retains actual
responses, proposal-core results, model identities, prompt/config bindings, GPU
observations and runtime digests. The proposal core is commit
`639a90367f9bc9db9b3022a691402b9a8f7da04c`; exact trial controllers are archived
separately rather than attributed to that core commit.

## Observed outcomes

| Local artifact | Request time | Output tokens | Stop reason | Candidate result | Numerical points evaluated |
|---|---:|---:|---|---|---:|
| Qwen3.8-27B-UD-Q4_K_M | 327.03 s | 768 | length | INVALID_RESPONSE | 0 |
| ScienceRSI-8b.i1-Q4_K_M | 29.97 s | 222 | stop | INVALID_RESPONSE | 0 |

Qwen's response ended within its explanation when the output budget was
exhausted. A nonaccepting diagnostic extracted its complete program prefix;
that prefix also had invalid operator arity, so it was neither executed nor
accepted. Truncation is not the only defect. ScienceRSI stopped normally but
emitted duplicate fields and an incomplete program/envelope. Strict parsing
rejected it. Neither failure is a numerical score of zero out of 23.

Both used the same prompt string, seed 19, temperature 0, top_p 0.9, thinking
disabled, maximum 768 output tokens, context 4096, one GPU layer, CPU KV and
twelve threads. Their tokenizers produced different prompt token counts. This
is one public task, not an estimate of overall scientific competence or reliability.
The earlier fifteen-item S4 rule-following result does not transfer automatically
to structured program generation. Malformed output likewise does not prove
general scientific reasoning incapability.

## Runtime evidence and limits

Each model used a new private loopback server and SDK-owned process lifetime.
Existing StartLux endpoint, process and model identity were checked before,
during and after the run: 62 recorded continuity checks for Qwen and seven for
ScienceRSI, with no resource/sampling errors. Owned model processes were
terminated and verified absent before starting the next model. Their termination
exit codes are recorded; normal server exits are not claimed. Outer launchers
exited zero. Shared-system sampling does not prove uninterrupted uptime or
isolate model memory.

The profile required 3584 MiB GPU free before loading, at least 1792 MiB free
during execution and a maximum system-wide increase of 1536 MiB. An independent
request watchdog supplemented socket timeouts and could terminate only the owned
server. Evaluation used a separate owned subprocess with a 30-second timeout;
controller/outer limits were 900/960 seconds. Fast/late controls exercised the
watchdog; real requests did not reach the 480-second boundary.

Workers bound run nonce, frozen protocol and actual response bytes, and checked
loaded numerical-module paths and the exact prompt. Model and declared source
hashes were checked before/after. The real responses were replayed through the
proposal core; test doubles are not counted as model invocations.

[Recorded runtime sources](../reference/rsi_bootstrap/recorded_trials/README.md)
contain executed controller/evaluator/launcher copies and protocols. These are
same-host records with host-specific paths, not a portable installer. Weights
and llama.cpp binaries are not redistributed. A generic configured runtime still
needs extraction and acceptance.

The rejection decisions can be replayed without model weights or inference,
from the repository root with its project interpreter:

```python
import json
from pathlib import Path
from reference.rsi_bootstrap.c0 import run_once

record = json.loads(Path("docs/RSI-C0-MODEL-TRIALS-2026-11-01.json").read_text())
for row in record["rows"]:
    replay = run_once(lambda prompt: row["raw_response"])
    if replay["status"] != row["candidate_status"] or replay["retained_for_development"]:
        raise RuntimeError("Recorded rejection did not reproduce")
    print(row["profile"], replay["status"])
```

This checks the recorded responses against the proposal core. It does not repeat
model generation, timing, GPU sampling or service-continuity observations.

Core CI at commit 639a903 completed all six jobs successfully, including research
checks on Python 3.11/3.12: [CI evidence](https://github.com/Computational-social-science/Eidos/actions/runs/41320604944).
That CI does not execute local models or establish sealed evaluation.

## Next controlled change

1. Qualify a stricter structured decoder against the actual backend. Validate
   required fields, operators and arities; requesting a JSON object did not
   ensure this task contract.
2. Add a short unrelated expression example and bound explanation length in a
   new frozen protocol. Preserve the current invalid attempts and all costs;
   do not repair them into accepted outcomes.
3. Compare revised procedures under matched prompts/budgets. Assess numerical
   correctness only for admissible programs, using the independent loss/gradient
   oracle. Use fresh independent tasks before claiming transfer.
4. Attribute externally designed protocol changes to ordinary development. RSI
   requires the roadmap's separate matched improver experiment.

Scientific RSI, sealed generalization, unknown-gap discovery, production-service
migration and a clean 24-hour deployment observation remain unproven.
