# RSI bootstrap: development evaluator foundation

Latest checkpoint: the [decoder study](../../docs/RSI-C0-DECODER-STUDY-2026-11-02.md)
obtained admissible programs from two real local models; both failed all 23 joint
numerical points. The prior v1 responses were rejected before numerical grading.
Exact runtime sources and backend controls are archived under `recorded_trials/`.
The frozen C0 specification and early foundation records retain their historical
scope; a portable configured model runtime and RSI acceptance remain open.

This work package calibrates an executable evaluator before attempting a
model-generated numerical repair. It implements part of P0/P1 of the
[RSI roadmap](../../docs/RSI-OPTIMIZATION-PLAN.md).

The task is the known cancellation problem in `log(1 - exp(-x))`, with first
derivative `exp(-x)/(1-exp(-x))`, over a declared positive float32/float64
normal-range domain. The idea is attributed to
[Maechler/Rmpfr](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html).
The exact domain and tolerances were specified in the
[evaluation contract](../../.Codex/evals/rsi-bootstrap-foundation.md) before implementation.

Use the project's interpreter and existing NumPy/pytest dependencies:

```text
python -m pytest reference/rsi_bootstrap/test_grader.py -q
python -m pytest reference/rsi_bootstrap/test_expressions.py -q
python reference/rsi_bootstrap/grader.py --output .scratch/quality/rsi-bootstrap.json
```

The receipt compares nine externally authored implementations at 23 public
development points. The positive repair must pass all points. Eight incorrect
controls must each fail at least one point. Ordinary clean textbook inputs must
also pass, preventing an always-rejecting oracle. Loss and derivative have
separate relative checks without an absolute floor. Decimal errors are compared
before conversion to diagnostic floats. Decimal references use the actual
represented binary inputs and converge at precisions 420 and 520.

The tool binds protocol/grader/test hashes before execution and checks them again
after execution. It refuses an output path that aliases a bound input. Receipt
replacement is atomic for that file; no multi-file or power-loss transaction is
claimed. A failed command must not be treated as a new successful receipt; an
older receipt remains historical and its hashes must be checked before reuse.

The explicit test command above is required: these case-specific tests are not
in the framework's default `tests/` collection. The v0.4.10 core self-audit and
wheel qualification do not qualify this newly added research work package.

This is **public development calibration**, not a sealed test. No model is
loaded, no arbitrary candidate code is executed, no production service changes,
and no candidate is promoted. The case does not demonstrate scientific novelty,
model competence, transfer or RSI. The source and positive repair are external
development, not outputs of EIDOS self-improvement.

The historical [C0 contract](C0-SPEC.md) precedes the implemented proposal core
and same-host trials. A portable local runtime and independent sealed-task access
remain pending before a recursive campaign.

The closed expression interpreter in `expressions.py` enforces the proposed
scalar operator/type/size/depth/node limits. Its adversarial tests include
duplicate/nonfinite JSON, unsupported operations, incorrect types, invalid
unselected branches and budget overflows. This is a development prerequisite
for model programs; the recorded model runners are host-specific and the sealed
boundary remains unimplemented.
