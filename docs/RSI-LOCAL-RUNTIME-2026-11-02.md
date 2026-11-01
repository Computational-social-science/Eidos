# First configured, keyless local CPU C0 execution

The public source-checkout CLI completed one actual ScienceRSI-8B trial without
a paid model API or a GPU requirement. **Runtime acceptance passed; the proposed
program failed all 23 joint numerical development points. No candidate was
retained or promoted. Scientific RSI remains unproved.**

The [machine record](RSI-LOCAL-RUNTIME-2026-11-02.json) and
[archived executed inputs](../reference/rsi_bootstrap/recorded_trials/c0-local-cpu-v1/)
retain the exact response, independent evaluator result, protocol, configuration,
runtime-source snapshot, logs and hashes. Use the
[CLI guide](../reference/rsi_bootstrap/LOCAL-RUNTIME.md) for a new local run.

## What changed

Earlier real trials used host-specific, single-use controllers. The new
`reference.rsi_bootstrap.local_runtime` CLI resolves engine/model paths from a
configuration, owns a fresh model lifetime through the existing SDK and delegates
numerical grading to a separate bounded worker. It does not read ignored scratch
scripts or require the current user's drive layout, GPU or StartLux installation.
This host explicitly configured StartLux preservation; other users declare their
own protected observations.

This is the CPU profile `local-cpu-c0-v1`, not the original GPU-assisted profile
or a matched comparison against its timings. The first prepared source snapshot
was superseded before inference; the executed protocol matches preparation v2
except for its newly allocated run nonce. There was one target proposal and one
subsequent backend control. No retry selected a better response.

## Actual outcome

| Measurement | Observed result |
|---|---|
| Runtime | COMPLETE; runtime_accepted=true; controller exit 0 |
| Model | ScienceRSI-8b.i1-Q4_K_M, SHA-256 `a7e1cdab380e52ef55dfe249f634262052c171bdd4b606b7530637398852b7ad` |
| Backend | Pinned llama.cpp b10964 binary; explicit CPU device, no GPU/KV/operator offload |
| Model readiness | 3.422 s, including model identity lookup within the load deadline |
| Target request | 37.578 s; 301 generated tokens; normal stop; zero cached prompt tokens |
| Whole controller | 53.140 s, including checks, control, cleanup and post-run hashes |
| Public numerical task | DEVELOPMENT_NONCONFORMING; 0/23 joint loss/first-derivative points |
| Existing service checks | 25 recorded observation groups of the declared StartLux front/engine endpoints and listener identities |
| RAM observations | 90 samples; no recorded resource/service/HTTP errors |
| Cleanup | Owned server terminated; PID/creation identity independently confirmed absent; watchers stopped |
| Input identity | Bound source/config/model/executable hashes unchanged; controller/evaluator runtime identities agree |
| Scientific authority | No retention, promotion, sealed evaluation, transfer result or RSI result |

The proposal uses `log(x-1)` for its small-input branch and a unit-valued
derivative expression there. Its other branch also fails the declared function
and derivative contract. These diagnoses concern this actual response on one
known public task. They do not estimate general model accuracy or prove that
local models cannot perform scientific work.

The command was launched through the tool's PowerShell wrapper, which reported
exit 1. Its direct native Python CLI exit was not separately captured. The
structured parent outcome reports runtime acceptance and mathematical failure;
the source CLI contract returns 2 for that combination. No observed shell success
is claimed, and neither exit code is treated as scientific conformance.

## Qualification and rejected controls

Before inference, the case suite passed **124 tests**: 60 existing numerical/core
tests and 64 synthetic runtime controls. No synthetic transport was counted as
model inference. Nine real subprocess fixture modes exercise successful runtime,
malformed candidate, dripping target response, oversized response, failed literal
control, changed model input, dripping health, dripping model identity and a slow
protected endpoint. Rejected runs must stop the owned process; a protected
endpoint remains alive. The slow protected read also checks continued RAM sampling.

Parent mutations cover stale run/response bindings, incomplete cleanup,
contradictory literal-control evidence, duplicated/substituted numerical points,
nonboolean verdicts, false counts, altered outputs, incorrect retention/promotion
and mismatched evaluator environments. The parent recomputes the preserved
response through the same oracle; this is receipt consistency, not a new
independent scientific method or proof against a hostile local maintainer.

Run the scoped tests with the project's interpreter:

```text
python -m pytest reference/rsi_bootstrap -q
```

## Reproducibility and limits

Run nonce: `76b9685dfda944ac9fea0685c74fd3b6`.
Protocol SHA-256:
`4b28c9e7f045d3e9385af036c0fd6651c5158fb7685d41e29ce96d8b18d3849d`.
Configuration SHA-256:
`50b9e5524d4d36b35b8aeb8c4b15b06e8aa4e5efe0d387150f4c72adfaa90e88`.

Archived source files use a `.snapshot` suffix so pytest does not automatically
collect historical test copies as current tests. This changes their archive names,
not their measured bytes or hashes.

The protocol binds 20 source/contract/lock files and actual Python, platform,
NumPy and psutil identities. Archive hashes bind raw bytes; a fresh checkout can
have different line endings and must freeze its own identities. Weights and the
backend executable are identified but not redistributed. This trial was run
from new source files before their publication commit, so the previous `main`
commit alone is not their execution identity; use the archived source hashes.

This proves a bounded same-host Windows source-checkout path. It does not prove
an installed-wheel runtime, independent new-machine installation, Linux model
execution, hard OS memory/disk quotas, network isolation or remote attestation.
CPU/GPU throughput comparison is not justified by different generated programs.
The original v0.4.10 wheel, source identity and release assets are unchanged.

The next scientific intervention remains the
[free local component plan](RSI-COMPONENT-ASSEMBLY-2026-11-02.md): curated method
retrieval plus bounded numerical feedback under a new matched-budget protocol.
The runner is now a concrete prerequisite for that experiment; no retrieval,
feedback-search or recursive-improvement gain is claimed here.
