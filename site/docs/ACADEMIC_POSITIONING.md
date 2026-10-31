# Academic positioning and evidence scope

EIDOS is research infrastructure for making the relationship between a scientific
claim, its execution and its evidence explicit and testable. Its present scholarly
value is methodological: a failure can produce a checked implementation, an
independent reference, negative controls and a regression contract reusable by
another project. Broad improvements in scientific productivity or discovery quality
remain hypotheses for evaluation.

## Contribution and attribution

The Softmax Collapse/Cancellation repair is due to Barron, Gnanapragasam and Tschannen,
[A Fix for Softmax and Cross-Entropy, v3](https://arxiv.org/html/2610.31642v3).
EIDOS reuses its existing Paper2Agent/MCP conversion. EIDOS's case contribution is
the executed validation/delivery path and its bounded empirical reconstruction;
the original mathematical method is not an EIDOS discovery.

| Level | Question | Accepted local evidence | Boundary |
|---|---|---|---|
| Numerical mechanism | Does the actual computation preserve the intended loss and gradient? | Filed float32/float64 cases, Decimal references, backend probes and rejected broken controls | Finite exponent range and quantized inputs remain; AMP/bfloat16 and higher-order backward are unqualified. |
| System behavior | Does numerical repair preserve an intended stationary point? | Saved teacher/student states and independently checked final outcomes | The bounded teacher–student setup does not demonstrate generalisation. |
| Scientific endpoint | Does the method improve held-out learning under the specified budget? | Three-seed, 36-trajectory precision/epsilon matrix, every pair retained | Mixed outcomes; no full-paper MATCH, universal benefit or population inference. |
| Transfer | Can another project reuse the safeguards to catch a new error? | Reusable kernels, verifier and input-bound gates are implemented | Independent-domain effectiveness and a controlled comparison remain to be demonstrated. |

Software correctness tests, operational uptime and scientific validity answer
different questions. A large test count does not establish novelty, a novel claim
does not establish reproducibility, and a healthy service does not establish either.

## Research questions for subsequent work

1. Align the cited implementation's input representation, initialization and model
   details; register ablations that distinguish architecture effects from arithmetic.
2. Qualify each precision/backend with independent loss and relative-gradient
   references and deliberately broken controls before using it in a new experiment.
3. Transfer the safeguards to an independently onboarded AI4S project. Inject a
   new numerical/evidence failure and measure detection and reproduction outcomes
   against a declared baseline.
4. Evaluate research quality and effort with independent projects and reviewers,
   reporting unsuccessful transfers and false acceptances as well as successes.

The homepage orders the scientific argument before implementation details and links
each evidence level to its artifacts. Its matrix summary is computed only after
artifact and final-gradient acceptance, and is withheld on revalidation failure.
Publication SVG/PDF masters remain separate from dark, interactive web displays.

Engineering acceptance remains in [functional completeness](FUNCTIONAL_COMPLETENESS.md).
Version `0.4.1` indicates initial development; historical `4.x` numbering is retained
as history and does not establish production maturity.
