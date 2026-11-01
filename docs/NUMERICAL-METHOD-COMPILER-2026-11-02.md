# A compiled known method repairs the tool result, not the model's response

Status: actual deterministic CLI execution and a fresh-process reader both
completed successfully on 2 November 2026 (Asia/Shanghai). **The saved local-model
proposal remains rejected at 0/23 joint points. A separately compiled known
method passes 23/23. No new model inference, autonomous tool selection or RSI
is demonstrated.**

The [machine record](NUMERICAL-METHOD-COMPILER-2026-11-02.json) and
[raw archive](../reference/numerical_method_tools/recorded_trials/compiler-v1/)
preserve source snapshots, the original response, both programs' assessments,
preparation, actual command/exit observations and fresh-reader output. The
[usage guide](../reference/numerical_method_tools/README.md) provides a concrete
keyless reproduction command using the public archived response.

## Why this change

In the preceding [six-proposal study](RSI-RETRIEVAL-FEEDBACK-2026-11-02.md),
retrieval supplied both a correct forward method and a correct derivative.
ScienceRSI copied the forward branches but encoded `-exp(x)` as the derivative.
T1, T2 and T3 each passed 23/23 forward points while failing every derivative.
More retrieved prose did not remove the translation error.

The new layer deterministically translates a small formula syntax into the
existing typed interpreter. It does not duplicate the numerical backend or
invent another scientific grader. The [contract](../.Codex/evals/numerical-method-compiler.md)
preceded implementation and the frozen source/configuration preceded the actual
recorded-response comparison.

The catalog explicitly selects `log1mexp-v1`:

```text
loss     = where(x <= log(2), log(-expm1(-x)), log1p(-exp(-x)))
gradient = exp(-x)/(-expm1(-x))
```

The forward method is attributed to
[Mächler/Rmpfr](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html).
The derivative is an external maintainer analytic derivation. This is not an
automatic differentiation result, an upstream derivative implementation or an
EIDOS-generated discovery. The catalog's canonical content pin links the existing
`log1mexp-piecewise` card; raw byte hashes separately bind each execution.

## Actual before/after

The prior T1 response was selected explicitly and its exact bytes checked against
the prior committed study/archive. None of its code or explanatory text was
edited. The compiler produced a different, attributed tool artifact.

| Artifact | Joint points | Required derivative signs | Acceptance |
|---|---:|---:|---|
| Preserved T1 model proposal | 0/23 | 0/23 positive | Rejected |
| Compiled external known method | 23/23 | 23/23 positive | Development conforming |

All 23 compiled loss outputs were negative. The existing numerical oracle checks
loss and derivative together, input dtype and represented inputs, with relative
tolerances 2e-5 for float32 and 2e-12 for float64. There is no absolute-gradient
floor. Decimal420/520 reference convergence was checked at every public point.
Sign checks are necessary constraints; passing them alone cannot accept a method.

The actual owned CLI process exited zero in **1.839 seconds**. A separate fresh
reader process exited zero in **0.788 seconds**. These are single wall-time
observations, not throughput estimates or comparisons against the earlier model's
generation costs. Both stages use the same public oracle; process separation is
an implementation check, not independent scientific adjudication.

## Logic and evidence defects corrected during implementation

The code reviews and failure controls closed three concrete inconsistencies
before the actual comparison:

1. A receipt projection originally omitted inner core status, count, prompt and
   source fields. Updating a file hash could leave false inner acceptance beside
   rejected points/summary. The reader now compares the complete assessment/core
   excluding only replay timestamps/durations, using typed canonical JSON equality.
2. Producer/reader checks originally lacked complete end-of-publication/verification
   stability brackets. Mutations during those phases could escape an earlier
   check. The producer now checks actual published inventory/bytes before the
   terminal marker; the reader uses captured hash-verified bytes and checks all
   bindings again after replay. Regression controls inject real file mutations.
3. Depending on the interpreter's recursion limit did not deterministically bound
   JSON nesting. A lexical 64-level guard now rejects excessive nesting before
   decoding and preserves brackets inside quoted/escaped strings.

The combined compiler and existing RSI suite passed **248 tests** before the
actual comparison: 68 new compiler/receipt controls and 180 existing controls.
Controls cover syntax/type/size/depth refusal, lazy-but-fully-validated branches,
forbidden execution, Decimal convergence, wrong derivative/sign/zero controls,
malformed-response semantics, canonical card identity, aliases/overwrites,
coherent verdict forgery and files changed during publication or verification.
These tests do not themselves count as local-model evidence.

## Provenance and remaining work

Execution run: `df41f59c98f54576ad6ea5fdd971b58d`.
Terminal receipt SHA-256:
`8e074604defe789842d127f0b31ac986a6f9aa7cdc4a04c40721c054bfa486d9`.
Pre-execution preparation SHA-256:
`882538b5f77debccb8e817752ecae9f4918989e3bf2d06a73f657cfd1ff079fd`.
Original chat response SHA-256:
`173cbf478e059a16fb9fe8ed2b5f4ba5213b4f034240c47b6c9154e10999e13a`.

The execution binds 25 source/contract/catalog/card/lock/CI files. It ran on
CPython 3.12.4, NumPy 2.5.4 and this Windows CPU environment. No seed applies to
deterministic compilation/replay. No API keys, hosted provider, model weights,
new dependency, CRON or resident-service restart was needed. Raw snapshots retain
the bytes actually exercised; different environments must freeze a new replay.

This work adds a source-checkout tool, not a new wheel or qualified research
reasoner. The original v0.4.10 release and prior archives remain unchanged.
There is one known method and one public related-point domain. General symbolic
derivation, full-domain numerical correctness, autonomous catalog/tool selection,
live-model use of this interface, independently installed/new-machine acceptance,
network-denied execution, GPU/vector/AMP/higher-order support, scientific novelty,
sealed transfer and EIDOS-generated C1/C2 remain unproved.

Next connect explicit method calls to a bounded local proposal procedure and
qualify selection separately from execution. Preserve unsuccessful raw proposals
and tool assistance as different artifacts. Then compare a feedback policy that
avoids equivalent failures under preregistered matching ceilings. Framework/wheel
promotion needs versioned package and installed-runtime acceptance; a positive
known-method control cannot establish RSI or general research competence.
