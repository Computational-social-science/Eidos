# RSI bootstrap foundation: public development calibration

Defined 2026-11-01 before implementation of the executable grader. This is the
first executable work package of `docs/RSI-OPTIMIZATION-PLAN.md`.

## Claim and boundary

The development evaluator must distinguish a cancellation-prone implementation
of `f(x) = log(1 - exp(-x))`, for finite positive x, from a valid repair. It
must check both f and df/dx against an independently computed high-precision
reference at the exact input represented in float32 or float64.

This is a known numerical method, not scientific novelty, a sealed test, a model
qualification or an RSI demonstration. The implementation and positive repair
control are externally authored development tools; no EIDOS-generated repair
is claimed. Public case points are development coverage, not independent task
units for a confidence interval on scientific reliability.

Primary source: Martin Maechler's
[Rmpfr documentation](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html).
The numerical idea is a piecewise use of expm1 and log1p. The reference uses
Decimal exponentiation, subtraction and logarithm, without those production
formulas. The derivative reference is obtained analytically as
`exp(-x) / (1 - exp(-x))` in high precision.

## Frozen public development domain

- Float32: 1e-30, 1e-12, 1e-8, 1e-5, 0.1, the two neighboring represented
  values around log(2), 1, 20, 50 and 80.
- Float64: 1e-100, 1e-16, 1e-12, 1e-8, 0.1, the two neighboring represented
  values around log(2), 1, 20, 50, 80 and 600.
- Reference computation: Decimal precision 420 and 520; require agreement after
  conversion to the output dtype. Use Decimal.from_float on the represented
  input, rather than interpreting its printed decimal as an exact real.
- Finite positive values, first derivative only. This domain keeps the listed
  true values/derivatives in the dtype's normal representable range. It does
  not qualify subnormal behavior, nonpositive x, AMP, other backends or higher derivatives.

## Grading contract fixed before implementation

1. A successful result has exactly the input dtype and shape for loss and
   derivative, with all values finite.
2. Compare loss and derivative separately using relative error against the
   nonzero Decimal reference, without an absolute error floor. Float32 maximum
   relative error: 2e-5. Float64 maximum relative error: 2e-12. These are
   development conformance tolerances, not scientific reliability estimates.
3. A known valid piecewise repair must pass every point in both dtypes.
4. The textbook implementation must fail. Independent broken controls must also
   fail: loss-only repair with broken derivative, small-gradient flooring,
   single-branch log1p, single-branch expm1, sign-flipped derivative, always-zero
   output, and output dtype substitution.
5. A clean ordinary input must pass the same point grader for the textbook
   formula, so the oracle cannot reject every output and still appear correct.
6. A deliberately bad oracle that uses a large absolute gradient/loss tolerance
   would accept at least one zeroed small result; the real point grader must
   reject that same control.
7. No resource/transport/model error may be scored as scientific correctness.
   No model call is part of this calibration run.

## Capability and regression checks

- Reference consistency at both precisions, including the large-x float64 tail.
- Analytic checks at independently selected simple points.
- Positive and all required negative controls have their expected verdicts.
- Wrong shape, wrong dtype and nonfinite results are rejected by the point grader.
- Missing/nonfinite reference values cannot become PASS.
- A calibration receipt contains protocol/source hashes, actual interpreter and
  NumPy version, represented inputs, per-point errors and complete control results.
- The report explicitly retains NOT_RUN for model and sealed evaluations and
  NOT_DEMONSTRATED for scientific RSI.

## Trust and promotion

The development grader and its fixtures are public and mutable by the external
maintainer. They are not a sealed evaluator or an operating-system sandbox.
Independent implementation review plus mathematical controls test the grader;
same-author code alone does not establish independent scientific ground truth.

Before G1 can pass, freeze a separate task manifest and evaluator, implement and
verify candidate/evaluator access separation, and assign sealed evaluation
ownership. Before any recursive claim, run the roadmap's matched A/H/B branches.
No candidate promotion, deployment change or scientific gate authority is
authorized by a successful calibration receipt.

## Minimal C0 specification to freeze after calibration

Input: allowed helper code, development-only mechanism context and feedback,
declared model/runtime identity and budget. Output: a bounded proposed repair,
all attempt records and executable observations. The trusted runner executes
only in a disposable environment; the candidate receives no sealed answers.
Initial weights are fixed. External human/Codex repairs are recorded as external
development and cannot be credited to C0. C0 is not implemented by this document.
