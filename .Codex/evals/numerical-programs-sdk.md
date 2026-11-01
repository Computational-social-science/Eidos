# Installable bounded numerical-program API (candidate v0.4.11)

Declared 2026-11-02 before implementation. Source baseline a2aba94.
This work promotes the previously qualified source-checkout formula/interpreter
mechanism into a self-contained installable framework API. Historical reference
implementations, model responses and scientific receipts remain immutable.

## Public contract

`framework.numerical_programs` exposes `compile_formulas(loss, gradient)`,
`parse_program(str_or_utf8_bytes)`, `execute(program, value)` and `ScalarProgram`.
Factories produce an immutable validated value; direct construction is refused.
Its `to_dict()` returns fresh data, `to_json()` serializes the existing closed
loss/gradient-node schema, and `evaluate(value)` delegates to typed execution.
No import from reference/tools, checkout file access, catalog/network/model,
provider key, extra dependency or background work is allowed in the SDK.

The generic API accepts native NumPy float32/float64 scalars or exact 0D ndarray
values of those dtypes, finite and including negative/zero inputs. Reject masked/
other ndarray subclasses, Python bool/int/float, vectors and other dtypes without
implicit promotion. Outputs are separate scalar arrays that alias neither the
input nor each other, preserving the input dtype. This deliberately differs
from the historical positive-input-only log1mexp evaluator, which is not changed.

Keep the existing unary neg/exp/expm1/log/log1p, binary add/sub/mul/div/le and
lazy where language. Fully validate all branches and boolean/numeric operand
types. Source<=2048 UTF-8 bytes per formula, JSON<=32768 bytes, JSON nesting<=64,
combined nodes<=256 and depth<=16. Reject unknown syntax/names/attributes/calls,
duplicate/nonfinite JSON, booleans and unsupported types. Integer constants must
be exactly representable as binary64 before input-dtype rounding; floating
literals are binary64 values. Never eval/exec/import candidate text.

Every evaluated numeric intermediate, including constants and predicate operands,
must be finite. Reject undefined/overflow/nonfinite selected operations with
FloatingPointError; an invalid intermediate cannot select a finite fallback.
Unselected branches are not executed. Finite underflow to zero is not detected
as mathematical error by this API. Successful execution does not validate a
supplied gradient, numerical accuracy, method domain or scientific claim. There
is no automatic differentiation, higher-order/GPU/vector guarantee or RSI claim.
Frozen/private Python objects provide a value contract, not a hostile-Python/OS
security boundary. Model data still cannot invoke arbitrary Python operations.

## Required verification

1. Write controls before implementation. Cover parser/type/budget refusal, immutable
   values, independent output buffers, source/JSON roundtrip, exact integer policy,
   scalar dtype/domain and nonfinite intermediate/predicate failures.
2. Match the frozen legacy numerical program on the original23 normal-result
   positive points. Keep Decimal420/520 independent references and tolerances,
   with no absolute gradient floor. A finite wrong derivative must still be
   rejected by the external oracle, not accepted because compilation succeeded.
3. Independently check stable softplus and its supplied derivative at represented
   inputs -80,-20,-0.1,0,0.1,20,80,100 in both dtypes using converged Decimal
   references. Float32+100 must exercise a stable lazy branch despite overflow in
   the unused naive exp branch. These are controls, not novel tasks or transfer.
4. Build a new0.4.11 wheel through the documented version/release workflow. Freeze
   its README/metadata and complete source inventory. In fresh non-editable
   Windows and offline Linux environments, install its normal declared core
   dependency closure from locked, hash-required public wheels; require pip check.
   Execute actual API from outside checkout with -I, verify installed module paths,
   distribution/version/wheel/RECORD/full framework inventory and actual outcomes.
   A source test or --no-deps install with unmet metadata is insufficient.
5. Requalify SDK lifetimes, Quarto delivery, reproduction, tracking and recovery
   using the new wheel/source context where required; keep historical records.
   Re-render numerics publication after the version/lock changes, refresh matrix
   bundles/attestations, inspect changed publication pages and update fingerprints.
6. Complete source audit/health/technical framework/README/public copies, exact
   release labels/metadata, normal hooks and exact-final-commit CI before tagging
   or publishing v0.4.11. Preserve old tags/assets and distinguish qualified
   source/package from unmigrated legacy resident processes. No legacy restart.

The overall functional-completeness and RSI goals remain open until their own
requirements are proven. An installable formula tool is not research reasoning
or autonomous improvement of an improvement procedure.
