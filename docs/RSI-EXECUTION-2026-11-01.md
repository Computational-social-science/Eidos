---
document_id: EIDOS-RSI-EXECUTION-001
updated: 2026-11-01
work_package: public_development_oracle_foundation
roadmap_phase: P0_and_partial_P1
model_evaluation: not_run
sealed_evaluation: not_run
scientific_rsi: not_demonstrated
---

# RSI optimization: first executed work package

The [optimization roadmap](RSI-OPTIMIZATION-PLAN.md) has entered execution.
The first deliverable is a calibrated public numerical evaluator and a concrete
seed-procedure specification. This does not complete P1, implement C0 or
demonstrate recursive improvement.

## What was executed

The [protocol](../.Codex/evals/rsi-bootstrap-foundation.md) was written before
the grader. An initial test failed because the grader did not exist; the red
result is retained in `.scratch/quality/rsi-bootstrap-red.log`. The implemented
[grader and controls](../reference/rsi_bootstrap/README.md) then passed 15 scoped
tests. Review identified source-attribution and input-overwrite weaknesses;
six new controls failed before their fixes. A further tolerance-boundary check
prevents Decimal errors being rounded into acceptance. The final scoped suite
passed **22 tests**, with no failures or skips, in 3.46 seconds.

The executable calibration receipt is
[RSI-BOOTSTRAP-DEVELOPMENT-2026-11-01.json](RSI-BOOTSTRAP-DEVELOPMENT-2026-11-01.json).
It records actual protocol/grader/test hashes, starting/ending source stability,
interpreter/NumPy identity, represented inputs and all control-point results.
Its hashes were independently reread against the current files after publication.
The calibration itself took 0.50 seconds on the recorded CPU environment.

## Numerical result and interpretation

The known log1mexp cancellation mechanism is a development transfer target for
the Softmax lesson: mathematically equivalent expressions can discard the small
quantity needed for the loss or derivative. Source attribution is to
[Maechler/Rmpfr](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html).
The reference computes the defining function using Decimal, separately from the
piecewise production repair. Its first derivative is checked analytically.

| Externally authored implementation | Conforming public points | Whole-domain result |
|---|---:|---|
| Textbook formula | 8/23 | Rejected |
| Piecewise repair and stable derivative | 23/23 | Accepted as a development positive control |
| Loss-only repair, textbook derivative | 15/23 | Rejected |
| Gradient floor | 18/23 | Rejected |
| log1p-only repair | 15/23 | Rejected |
| expm1-only repair | 16/23 | Rejected |
| Wrong derivative sign | 0/23 | Rejected |
| Always zero | 0/23 | Rejected |
| Output dtype substitution | 0/23 | Rejected |

The positive control's maximum relative errors were:

| Dtype | Loss | First derivative |
|---|---:|---:|
| float32 | 9.15e-8 | 6.35e-8 |
| float64 | 2.28e-16 | 1.37e-16 |

These conservatively rounded values are bounded by the declared development
tolerances of 2e-5 and 2e-12. The 23 points span two dtypes and specified input
regimes. They are related development cases, not 23 independent scientific
tasks; the table is not a model score or a reliability confidence interval.

Ordinary textbook inputs also pass at x=1 in both dtypes. This checks that the
oracle does not win by rejecting everything. Tail controls show why a large
absolute tolerance would admit a zero result even when its relative error is 1.

## Closed expression execution boundary

The bounded expression interpreter is also implemented: 23 additional controls
test grammar, operand types, duplicate/nonfinite JSON, input dtype, disallowed
operations, full validation of unused branches, and size/depth/node limits.
The combined grader/interpreter suite passed 45 scoped tests in 1.97 seconds;
the [source-bound execution receipt](RSI-EXPRESSION-ACCEPTANCE-2026-11-01.json)
retains all test outcomes and checks source stability across the run. Model outputs
can eventually use this closed language; arbitrary generated Python is not
executed. This development restriction is not a general operating-system
sandbox and does not implement the C0 runner or sealed evaluation.

## Seed and trust boundaries

The [C0 specification](../reference/rsi_bootstrap/C0-SPEC.md) fixes the first
candidate scope, model identity, resource envelope, expression-grammar proposal
and recording requirements. It distinguishes an improved numerical target A1
from an improved improver C1. The local ScienceRSI artifact was separately
hashed; no model was loaded, swapped or inferred in this work package.

The grader and positive repair are externally authored. Review and independent
mathematical reference calculations improve confidence in this public tool;
they are not independent sealed scientific acceptance. Sealed candidate/evaluator
access separation, the C0 model runner and the matched recursive campaign
remain unimplemented or unrun. No candidate,
scientific authority or deployment was promoted.

Framework self-check, bounded recovery and monitoring are preserved. The core
v0.4.10 wheel, immutable release assets and previous scientific outcomes were
not rewritten. Its default framework suite does not discover these new
case-specific tests; use the explicit command in the work-package README.

## Next executable queue

1. Implement and adversarially test the single-attempt C0 development runner
   using the closed interpreter, preserving all resource/error outcomes.
2. Freeze the exact prompt and fresh model/runtime admission profile, then run
   the declared local-model development comparison. Distinguish numerical
   conformance, task completion and cost. Keep model weights fixed thereafter.
3. Establish separate sealed-task stewardship and validate candidate/evaluator
   access separation. G1 cannot pass from the public calibration result.
4. Only after those gates, run paired improvers from identical A/H/B states and
   fresh outcomes; evaluate procedure improvement separately from kernel repair.
