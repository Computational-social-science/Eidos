# Local known-method reuse: correct forward values, rejected derivatives

Status: completed public development comparison, 2 November 2026 (Asia/Shanghai;
raw UTC observations are dated 1 November). All six executions met runtime
acceptance. Neither procedure produced a jointly conforming loss/derivative
program. No scientific promotion or RSI was demonstrated.

The [machine record](RSI-RETRIEVAL-FEEDBACK-2026-11-02.json) preserves all six
responses, contexts, component errors, runtime identities and costs. The
[immutable raw archive](../reference/rsi_bootstrap/recorded_trials/rsi-retrieval-feedback-v1/)
also contains requests, receipts, controls, logs and executed source snapshots.
No failed proposal was replaced, repaired after generation or excluded.

## Question and preregistration

Can the same local ScienceRSI model apply a documented numerical method more
successfully with a small method corpus and public numerical feedback than with
repeated independent requests? The [contract](../.Codex/evals/rsi-retrieval-feedback.md)
was written before implementation; source/configuration/clock identities were
frozen before inference. Both arms used the existing positive-finite-scalar
`log(1-exp(-x))` task, closed expression interpreter, 23 represented float32/64
points and independent Decimal references at 420/520 digits. Relative tolerances
remain 2e-5/2e-12, with no absolute-gradient floor. No oracle was relaxed.

This is a combined **externally supplied knowledge plus feedback-history**
intervention. It is not the roadmap's matched-A/H/B improvement-of-the-improver
test. The bank deliberately includes the known repair, prepared by the external
maintainer workflow. It is neither discovery by EIDOS nor a reproduction of the
full OpenScholar/ERA systems. There are no sealed-task answers in the feedback.

The small bank contains original short summaries with primary-source citations:
the [Rmpfr log1mexp documentation](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html),
[NumPy expm1](https://numpy.org/doc/stable/reference/generated/numpy.expm1.html)
and [NumPy log1p](https://numpy.org/doc/stable/reference/generated/numpy.log1p.html).
Deterministic lexical retrieval selected `log1mexp-piecewise` and `log1p-small`.
The first includes the small-input `log(-expm1(-x))` and large-input
`log1p(-exp(-x))` branches. The supplied derivative
`exp(-x)/(-expm1(-x))` is explicitly a maintainer analytic derivation, rather
than a quotation or claimed derivative implementation from Rmpfr.

## Frozen local execution

| Item | Configuration |
|---|---|
| Model | Existing ScienceRSI-8b i1-Q4_K_M GGUF; 5,027,784,544 bytes |
| Model SHA-256 | `a7e1cdab380e52ef55dfe249f634262052c171bdd4b606b7530637398852b7ad` |
| Backend | Existing native llama.cpp b10964; identified, not redistributed |
| Device | CPU, 12 threads; fresh owned server for each proposal |
| Decoding | Seed 19, temperature 0, top_p 0.9, thinking off, grammar constrained |
| Context/output | 8,192 context; at most 768 target completion tokens |
| Runtime | CPython 3.12.4, NumPy 2.5.4, psutil 7.2.2; Windows |
| Arm ceilings | Three targets, 10,000 logical model tokens, 3,000 charged seconds each |
| Per-attempt deadline | 900 seconds; no provider credentials or hosted fallback |

Generation was interleaved B1,T1,B2,T2,B3,T3. All three opportunities per arm ran
even after failure. Baselines received only the task and no prior feedback.
Treatment received the two selected summaries; later treatment requests also
received the best prior admissible candidate from their own arm, breaking ties
in favor of the earliest, and at most four actual failed public observations.

Metadata/template/tokenization calls were non-generative. Each target was
followed by a literal format control; those controls are not research proposals.
Token accounting includes both target and control prompts/completions, including
cached tokens. Every target reported zero cached prompt tokens and `stop`, with
301, 407 or 465 completion tokens; none reported output-limit truncation.

## Complete outcomes

Component counts below are posthoc same-oracle diagnostics under the existing
relative tolerances, computed separately from each actual typed output using
Decimal comparisons. The frozen joint grader can stop at a nonfinite loss, so
an absent derivative diagnostic is not counted as a derivative failure. Controls
cover that case and float diagnostic rounding just above a tolerance.
**Joint acceptance requires both outputs at the same point.** A
correct forward value does not compensate for a failed derivative.

| Attempt | Runtime accepted | Loss points | Derivative points | Joint points | Total model tokens | Charged seconds |
|---|---|---:|---:|---:|---:|---:|
| B1 | Yes | 0/23 | 4/23 | 0/23 | 626 | 54.945 |
| T1 | Yes | 23/23 | 0/23 | 0/23 | 1,080 | 72.632 |
| B2 | Yes | 0/23 | 4/23 | 0/23 | 626 | 55.383 |
| T2 | Yes | 23/23 | 0/23 | 0/23 | 1,826 | 93.557 |
| B3 | Yes | 0/23 | 4/23 | 0/23 | 626 | 54.944 |
| T3 | Yes | 23/23 | 0/23 | 0/23 | 1,826 | 94.274 |

Both arms had zero conforming proposals, no first success and best joint score
0/23. Baselines spent **1,878 tokens and 165.272 seconds**; treatment spent
**4,732 tokens and 260.464 seconds**. These are equal ceilings, not equal actual
spend. Higher treatment cost produced no observed gain in joint acceptance.

One-time setup was 0.123 seconds, owned-worker dispatch 426.726 seconds, parent
verification 0.484 seconds and total API duration 427.333 seconds. Worker and
parent overhead explain the difference from summed arm costs. Total API timing
runs from `run()` entry through final receipt preparation, excluding interpreter/
CLI startup and the final atomic receipt write. Cost uses QueryPerformanceCounter
with 1e-7-second reported resolution; internal deadline timing uses monotonic
with 0.015625-second resolution. A one-deadline-tick tolerance applies only to
cross-clock consistency, not to the 3,000-second arm ceiling.

## What failed and what this changes

The baseline programs are identical and are mathematically incorrect. Their
constant-one derivative happens to meet tolerance at the four log(2) neighboring
inputs, while their loss fails. These four points do not provide a joint pass. The
treatment accurately encodes the supplied piecewise loss but emits the derivative
`-exp(x)` in both branches instead of the supplied positive derivative. T1 uses
a negated denominator constant; T2/T3 use the equivalent literal -1. At tiny x,
the returned derivative is approximately -1 while the true value is approximately
1/x. At larger x the wrong derivative grows in magnitude instead of decaying.
All treatment derivative points fail, despite 23/23 passing loss points.

B1–B3 have identical raw content. T2/T3 also have identical raw content. This is
consistent with the frozen deterministic configuration and fresh prompt caches;
these are repeated opportunities, not independent random samples. Under the
preregistered joint-score/earliest-tie rule, T1 remains the selected prior program
for both T2 and T3. Consequently T3 reuses T1 feedback rather than incorporating
T2's revised syntax. This is a measured limitation of the search policy, not
evidence that all possible feedback methods fail.

The observation supports a narrow engineering conclusion: this configuration
can copy the known forward method but cannot reliably translate even a supplied
derivative into the required program. It does not isolate the effects of model
size, quantization, thinking mode, output budget, grammar or retrieval separately.
The 23 related points and three proposals per arm are not independent scientific
tasks; no reliability interval, p-value or general model ranking is justified.

The next bounded work package should:

1. Add an explicitly attributed deterministic path from sourced formulas to typed
   expressions and derivative/sign checks. Preserve the raw model proposal and
   reject incorrect output; any tool-generated repair must be a separate artifact.
   This is a known-method tool adapter, not autonomous RSI.
2. Preregister a feedback policy that tracks new counterexamples and candidate
   equivalence instead of repeatedly choosing the earliest tied failure. Compare
   it against the frozen policy with the same local model and resource ceilings.
3. Qualify an additional existing local model on the same execution contract
   before assigning research authority. Preserve all attempts; do not change
   decoding, budgets and models together and then attribute a gain to one factor.
4. After public-task competence, establish independent sealed stewardship and
   fresh-task acceptance before testing an EIDOS-generated C1/C2 procedure.

## Provenance, preservation and limits

Campaign run: `ae199bddabab40f8a937d9e57a3ce060`.
Protocol SHA-256:
`186ab5bfa7a423dc3e71a73ea796884be687d2a6833576f9438a8d588de66a2b`.
Pre-inference preparation SHA-256:
`7bf62479132783e65ca31d90c729959608dbfeabf325ee1cc2c988558d0bf927`.
Configuration SHA-256:
`ce1278dee31b9b3506b6ae0085aaa07819e0d6d0cc3ffa974d4220fb99b70750`.

The protocol binds 25 source/contract/lock/bank files. The archive stores their
exact bytes with `.snapshot` suffixes, preventing pytest from collecting old
test copies as current tests. The test-only synthetic server and export audit
are auxiliary snapshots, not inference inputs. Parent reconstruction checks the
actual request against each arm's corpus/history and recomputes receipts/costs;
it reuses the same numerical oracle and adds no second scientific authority.

The durable `progress.json` retains `INCOMPLETE` as its live default even when
all rows have reached COMPLETED. Terminal status is established by
`campaign-result.json` and the separately verified `campaign-outcome.json`.
Never interpret the live progress default as the authoritative terminal verdict.

All six owned server identities were absent at export. Recorded StartLux health,
listener PID/create-time identity and RAM observations met the existing guards.
These are sampled observations, not proof of uninterrupted uptime. Legacy
resident services were not restarted. Self-check, self-healing and monitoring
remain required; no CRON, scheduled task or paid backend was added.

The scoped synthetic/control suite passed **180 tests** before inference. It is
not model evidence. This campaign demonstrates a same-host Windows CPU source
checkout, without a mandatory GPU or service credential. It does not establish
new-machine/installed-wheel/Linux/GPU model qualification, hard OS resource
isolation, outbound-network denial or remote compute attestation. Model/backend
files are identified but not bundled; their full redistribution terms remain
unqualified. The v0.4.10 wheel, release assets and prior records remain unchanged.
