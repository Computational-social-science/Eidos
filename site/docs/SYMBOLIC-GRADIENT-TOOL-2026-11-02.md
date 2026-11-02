# A free symbolic derivative closes one measured gradient failure

The recorded local model's log1mexp forward program already passed all 23 public
development points, while its supplied derivative failed every point. An isolated
SymPy 1.14.0 adapter now derives the first derivative from that forward alone.
Actual Windows and network-disabled Linux runs each pass 23/23 joint controls
without changing the forward JSON. No model was called and no corrected analytic
gradient was supplied to the adapter.

This establishes a bounded external-tool treatment. It does not establish that
the model learned the repair, that EIDOS selects tools successfully during live
inference, or that an improvement procedure improved itself. Scientific RSI
remains **NOT_DEMONSTRATED**. These are known log1mexp development controls, not
new Softmax training experiments or independent sealed scientific tasks.

## Fixed comparison and actual results

The [contract](https://github.com/Computational-social-science/Eidos/blob/main/.Codex/evals/symbolic-gradient-tool.md)
was declared before implementation. Its initial broader constant-expression
threshold proposal was conservatively narrowed before final platform runs after
review found a floating-threshold counterexample. The target, point set,
reference definitions and success thresholds were unchanged.

| Measurement, on each platform | Forward | First derivative | Joint |
|---|---:|---:|---:|
| Original saved model T1, 23 points | 23/23 | 0/23 | 0/23 |
| Same forward + tool-derived gradient | 23/23 | 23/23 | 23/23 |
| Stable softplus control, 16 points | 16/16 | 16/16 | 16/16 |
| Square control, 8 points | 8/8 | 8/8 | 8/8 |

Each platform also passed 20 scoped tests and nine actual integrity/timeout
controls: changed candidate, changed driver, changed payload, rehashed duplicate
points, rehashed zero-gradient program, integer substituted for a Boolean,
rehashed environment, resealed refusal records and a started worker timeout.
Eight boundary/predicate refusals are rederived during receipt verification.
These deterministic controls do not provide a statistical effect-size estimate.

Windows used CPython 3.12.4; Linux used CPython 3.12.16. Both used NumPy 2.5.4,
SymPy 1.14.0, mpmath 1.3.0 and the study's complete frozen dependency closure.
The campaign took 8.62 s on Windows and 14.21 s on Linux, excluding environment
bootstrap; these are single observed durations, not a performance benchmark.
The Linux bootstrap took 17.07 s with networking already disabled. Initial public
wheel/image acquisition occurred separately and is not included in the offline
execution claim.

## Tool, numerical oracle and attribution

The adapter accepts only a validated `framework.numerical_programs.ScalarProgram`.
It structurally maps the closed loss-node schema to trusted SymPy constructors,
using exact represented binary64 constants and one real symbol. It does not send
candidate strings to `sympify`, `parse_expr`, `eval` or `lambdify`. The supplied
gradient is retained as original evidence and ignored when constructing the new
derivative. The resulting explicit allowed nodes are lowered to the installed
SDK; stable `expm1`/`log1p` primitives and the original forward JSON are retained.
Unsupported outputs, integer-power expansion and combined SDK node/depth/JSON
budget excesses are refused rather than replaced by an unrelated formula.

Numerical acceptance uses separately implemented direct Decimal definitions at
the exact represented input. Log1mexp references converge at precisions 420/520;
softplus/square use 160/220. Relative tolerances are 2e-5 for float32 and 2e-12
for float64, including the nonzero float64 tail at x=600. There is no absolute
gradient floor. Exactly zero reference values require exactly zero error.
Readers reconstruct the programs and re-execute every original point against
this oracle; they do not trust recorded `passed` flags or correct-looking losses.

SymPy is a free BSD-licensed symbolic implementation; its stable code-generation
functions provide the differentiation rules used here. The package, mpmath
license files and installed metadata are bound in the receipts. SymPy is the
treatment, **not** the numerical oracle. See the
[release provenance](https://pypi.org/project/sympy/1.14.0/) and
[official function documentation](https://docs.sympy.org/latest/modules/codegen.html).
The retained forward follows the known piecewise log1mexp approach documented by
[Rmpfr](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html);
this experiment does not claim that method as a discovery.

## Logic defects found and contained

1. **CAS cancellation hides a domain hole.** At zero, `(x*x)/x` can simplify to
   `x`, even though the original selected program evaluates `0/0`. The adapter
   now checks original selected-path intermediates before CAS simplification.
2. **An exact threshold can differ from the executed threshold.** The expression
   `(10000000000000000+1)-10000000000000000` is exactly one in CAS but zero in
   binary64 execution. The tool explicitly refuses nonliteral thresholds and
   checks literal boundaries with both supported represented dtypes. General
   constant-expression predicate support is left unqualified.
3. **Internally consistent receipts can still be scientifically wrong.** A
   rehashed zero gradient or 23 duplicated successful points could evade a
   count-only reader. Readers now replay full programs, point inventories,
   typed values, reference errors, refusals and installed environment identities;
   they recheck input/output bytes after that work.
4. **A compatible dependency is not the locked dependency.** The first actual
   Linux attempt correctly refused an iniconfig 2.3.0 wheel outside the 2.3.1 lock.
   Offline installation checks artifact SHA-256 values against `uv.lock`, applies
   complete version constraints and independently verifies the installed closure.
   Bootstrap pip is explicitly recorded outside the scientific dependency lock.
5. **A declared environment is not an executed environment.** A Windows namespace
   package identity check failed and was corrected to inspect a concrete installed
   module. A Linux noexec tmpfs prevented NumPy library loading; the owned private
   tmpfs now explicitly permits execution. Failed attempts remain in the archive.

The boundary admission checks are conservative CAS checks of finite real
one-sided values/first derivatives and selected boundary values. They do not
prove whole-domain correctness, all floating-point intermediate behavior or
general mathematical validity. Every consumer still needs independent numerical
and scientific acceptance.

## Reproducibility and ownership

The SDK is the immutable installed Eidos 0.4.11 wheel at SHA-256
`752b5f30e7d225f74799b929bbd22cd28f3396aefb081d862efb1d21ba2d498a`.
All 45 framework modules, wheel members, METADATA/RECORD, dependency origins,
complete study-lock versions, actual interpreter/platform and new license files
are checked. No SDK/core dependency declaration or historical release byte was
changed. The adapter itself is an isolated reference source tool, not a newly
installed SDK feature.

The final input manifest is
`83cd8edde58ffcfd156bcef7852a7995229b97be942a3e5deb3b58e2e1ba74f7`.
Its pins include the exact original T1 response at SHA-256
`173cbf478e059a16fb9fe8ed2b5f4ba5213b4f034240c47b6c9154e10999e13a`.
The [summary receipt](https://github.com/Computational-social-science/Eidos/blob/main/docs/SYMBOLIC-GRADIENT-TOOL-2026-11-02.json)
links a raw-byte manifest covering 170 archived input/output/diagnostic files.
All measured intermediate passes and failures are retained separately from the
final paired qualification. Early unbound test diagnostics are labelled as such.

Both executions start outside the checkout with `-I` in non-editable venvs.
Workers/pytest use the installed SDK's owned Windows Job/POSIX process groups,
120-second worker and 180-second campaign deadlines. The actual Linux public
image is digest-pinned, network-disabled, read-only at root/input/wheel mounts,
with capabilities dropped and a private executable tmpfs. Container ownership,
terminal exit and removal were inspected. No resident service, model/GPU process
or CRON configuration was changed. These are execution/lifecycle controls, not
remote attestation, a hostile-code sandbox or a hard memory guarantee.

Replay instructions and the adapter are in the
[reference directory](https://github.com/Computational-social-science/Eidos/tree/main/reference/symbolic_tool).
The added CI workflow reruns native Windows/Linux qualification after public
dependency bootstrap; it makes no offline-network claim.

## Next acceptance boundary

Use this qualified local tool in one finite **live local-model tool-selection**
campaign, with a preregistered assistance policy, matched call/token/time budgets
and all failed proposals retained. Keep this case as public development data.
An independent evaluator must own sealed transfer tasks and their references.
Only after successful transfer should EIDOS attempt an improved improvement
procedure and a second generation under the existing RSI gates. Installing a
free component does not by itself satisfy any of those gates.
