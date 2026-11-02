# Free symbolic gradient tool qualification v1

Declared before implementation on 2026-11-02. Source baseline d51362c.
This is an isolated reference experiment using the immutable Eidos0.4.11 wheel,
not a modification of its numerical-program SDK or a new RSI result.

## Question and treatment

Can a structurally translated SymPy1.14.0 first derivative repair the recorded
local model's supplied-gradient failure, while keeping its forward program
unchanged and preserving expm1/log1p execution forms? Original T1 remains a
separate model result. The tool is external assistance, not another model call,
automatic scientific discovery, higher-order AD or an improved improver.

Input: a validated SDK ScalarProgram. Build SymPy objects only from its public
closed loss-node schema, with exact represented binary64 constants and one real
symbol x. Never sympify/parse/eval/lambdify candidate strings. Never consult the
supplied gradient to construct the new derivative. SymPy performs differentiation;
the adapter lowers only its explicit allowed scalar nodes back into the SDK's
bounded JSON language. Preserve the original loss JSON exactly. Retain stable
expm1/log1p primitives; do not simplify the derivative into textbook unstable
forms or add case-specific rewrites to fit the public answers.

For where, support x<=finite real constant expressions. Before differentiating,
require CAS checks of finite real one-sided value and first-derivative limits,
their exact equality and the selected boundary value. Refuse unproved,
discontinuous, nondifferentiable and nonrepresentable conditions; this is a
conservative admission check, not a whole-domain mathematical certificate.
All runtime domain/precision checks remain independent. Existing SDK input,
JSON/depth/node/finite-intermediate and output-buffer contracts remain in force.
Generated powers must be finite integer powers lowered through bounded products
and division. Exact binary64 constants are retained; other rational coefficients
use exact representable numerator/denominator nodes or are refused. Unsupported
symbolic outputs or output-budget overflows must not emit a qualifying program.

## Fixed controls and decisions

1. Hash and retain the original T1 chat response
   reference/rsi_bootstrap/recorded_trials/rsi-retrieval-feedback-v1/retrieval-feedback-1/response.json
   at SHA256173cbf478e059a16fb9fe8ed2b5f4ba5213b4f034240c47b6c9154e10999e13a.
   Its original gradient must remain0/23 joint acceptance; its forward remains23/23.
2. Derive from that forward alone, without hand-supplying a repaired gradient.
   Compare both original and derived programs on the unchanged23 positive
   float32/float64 development inputs, including cutoff neighbors and the
   float64 tail600. Use independently converged Decimal420/520 direct definitions,
   relative tolerances2e-5/2e-12, no absolute gradient floor. Required joint
   derivative-tool result:23/23 or explicit FAIL/UNQUALIFIED.
3. General operator controls: x*x at -2,-0,0,2 and stable piecewise softplus at
   -80,-20,-0.1,0,0.1,20,80,100 in both dtypes. Use independent Decimal references
   (160/220 for softplus), represented inputs, exact zero checks where appropriate,
   and the same relative tolerances. These known controls are not held-out tasks.
4. Refuse a jump, a cusp, a branch-boundary pole, unsupported variable thresholds,
   malformed/untrusted candidate syntax, wrong input types and generated programs
   outside the SDK bounds. A finite wrong gradient must still fail the independent
   oracle. Include input/driver/receipt mutation and actual timeout/refusal controls.
5. Run from outside the checkout with -I in a dedicated non-editable environment.
   Bind Eidos wheel/METADATA/RECORD/full45-module inventory, SymPy/mpmath/normal core
   pins and license metadata, tool/oracle/protocol/candidate hashes before/after,
   actual dtype/output/error values, elapsed time and terminal status. Require
   complete declared dependencies and pip/uv dependency check. No paid API,
   service key, model inference, GPU, CRON or legacy-process changes.
6. Native Windows and network-disabled Linux must execute the actual tool under
   owned120-second worker deadlines; parent limit180seconds. Public dependency
   bootstrap is separate from offline execution. Retain all measured failures,
   exact environment identities and owned cleanup. This is not a hostile-code/OS
   or hard-memory sandbox. Source-level tests alone are insufficient.
7. Review code and Python changes, execute scoped regression controls, and update
   the completeness ledger, English RSI plan and technical framework. Preserve
   all v0.4.11 release bytes/tags, original model/scientific records and unrelated
   pipeline changes. No source SDK capability is promoted by this reference case.

## Sources and scope

SymPyBSD3-Clause release and artifact provenance:
https://pypi.org/project/sympy/1.14.0/
Stable code-generation functions and their derivative rules:
https://docs.sympy.org/latest/modules/codegen.html
Known log1mexp method attribution:
https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html

SymPy's algebra and boundary checks are not the numerical oracle. Success would
establish one bounded free tool-integration path on known cases. Live local-model
tool selection, fresh sealed transfer, independent scientific novelty, portable
GPU/vector/higher-order behavior and recursive improvement remain open.
