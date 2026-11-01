# Local method retrieval and public-feedback experiment

Declared 2026-11-02 before implementation or live execution of this campaign.
This supplements, rather than rewrites, the earlier C0/CPU execution contracts.

## Question and claim boundary

Can a fixed local ScienceRSI model apply an externally supplied, documented
numerical method more successfully when given retrieved method summaries and
public development counterexamples than when repeatedly proposing independently?

The corpus deliberately contains the known log1mexp repair. This is method
reuse, not discovery. The combined intervention changes knowledge and feedback
history. It cannot isolate retrieval from feedback or estimate the roadmap's
matched-A/H/B improvement-of-the-improver effect. No EIDOS-generated C1/C2,
sealed result, scientific promotion or RSI claim is possible.

## Frozen task and comparison

- Keep the existing log1mexp loss/first-derivative task, interpreter, 23 public
  points, Decimal references and tolerances. Do not patch a response or oracle.
- One hashed local GGUF/backend; CPU, 12 threads, context 8192, thinking off,
  temperature 0, top_p 0.9, seed 19, maximum 768 target output tokens. Use a fresh
  owned server for every candidate. Metadata calls do not generate candidates.
- Two arms, three candidates each, in fixed interleaved order: baseline-1,
  retrieval-feedback-1, baseline-2, retrieval-feedback-2, baseline-3,
  retrieval-feedback-3. Execute all three even after an early success.
- Baseline: original task prompt only; no previous response or numerical feedback.
- Treatment: original task plus deterministic top-two local method retrieval.
  Later candidates also receive the best prior admissible candidate from that
  arm (highest joint conformance count, earliest tie), and at most four failed
  public observations (first/last failure per dtype). If all prior responses are
  malformed, report the latest malformed status rather than inventing a score.
- Retrieval query: `log1mexp log(1-exp(-x)) cancellation accurate expm1 log1p loss derivative`.
  Method summaries and analytic derivation are maintainer-authored external help,
  with primary-source URLs and input hashes. No network retrieval runs in the
  experiment. Do not count this as full OpenScholar or ERA reproduction.

## Equal ceilings and accounting

Each arm has at most 3 target candidates, 10,000 total model tokens and 3,000
seconds of charged wall time. Token totals include target and post-target literal
control prompt/completion tokens, including cached prompt tokens. Actual spent
cost can differ under the same ceilings and must be reported, not hidden.

Before generation, render/tokenize the actual target and control templates on
the owned backend. Reserve both prompt counts, output maxima and a conservative
template margin before admitting a request. Refuse context overflow or missing/
incoherent usage. Recheck actual token use and context fit after responses.
The literal control remains after the target and is never scored as a candidate.

Charge retrieval/feedback construction and every complete attempt's load, model,
evaluation, control, identity and cleanup time to its arm. Preserve actual total
campaign wall time and one-time setup separately. All aborts remain records. A
runtime, source, context or budget error stops the campaign and prevents a valid
comparison; partial results cannot be relabelled a completed experiment.

Measurement detail fixed before the first live campaign: cost timing uses
`perf_counter` with its implementation/resolution recorded. Total API time runs
from `run()` entry through final receipt preparation, excluding interpreter/CLI
startup and the final atomic write. Setup, owned-worker dispatch and parent
verification are reported separately. Internal controller deadlines use
`monotonic`; a cross-check between these clocks allows one recorded deadline-clock
tick for quantization. Arm ceilings themselves use the outer cost clock without
that tolerance. This clarification followed synthetic testing, before model calls.

## Required controls before inference

1. Deterministic retrieval actually selects the sourced log1mexp method; altered,
   duplicate or unbound cards cannot silently enter a prompt.
2. Baseline requests contain no treatment text/history. Feedback is reconstructed
   from prior accepted records of its own arm; stale/foreign/nonconforming receipt
   bindings or omitted earlier failures cannot yield campaign acceptance.
3. Extra context and all dependencies are frozen inputs; existing no-context CPU
   behavior still works. No provider keys, hosted fallback or new scheduler.
4. Oversized context, token/context oversubscription, malformed usage and budget
   overflow are rejected. Non-generative tokenization is distinguished from
   inference. Protected-service and model lifetime controls remain required.
5. Parent receipt verification recomputes retrieval/feedback and outcome accounting;
   inconsistent inventories, fabricated counts or altered raw responses refuse.
6. Synthetic controls are not model evidence. Freeze source/config/bank/protocol
   before the six actual calls and keep every unfavorable response and cost.

## Report

Report every attempt's actual prompt/context, citations, response, numerical
status and points, runtime acceptance, token/wall cost and retention. Report
first success, best score and complete conformance counts descriptively. These
are repeated proposals on one public function, not independent scientific task
units; do not compute a scientific-reliability confidence interval from 23 points
or three proposals. The parent reuses the same oracle for receipt coherence,
not a second independent scientific authority. Novelty/transfer/RSI remain unproved.
