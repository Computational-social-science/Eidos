# Deterministic numerical-method compilation and explicit repair

Declared 2026-11-02 before implementation. Governing baseline: main 7a72bb2.
The previous six-proposal study exposed accurate forward copying but wrong
derivative expressions. This work translates explicitly sourced formulas into
the existing bounded scalar expression language, without model generation.

## Capability and boundaries

1. A public `compile_formulas(loss, gradient)` lowers a small arithmetic syntax
   to the existing typed interpreter. Parse, never eval/exec/import candidate
   text. Permit x, finite numeric literals, negation, add/subtract/multiply/divide,
   unary exp/expm1/log/log1p, <= comparisons and lazy where/conditional branches.
   Reject attributes, unknown names/functions, keywords, indexing, powers,
   comprehensions, assignments, booleans, nonfinite literals and unsupported AST.
2. Restrict source bytes and use the existing combined node/depth/JSON/type
   limits. Validate all branches before execution; preserve scalar float32/64.
   Syntactic acceptance does not mean mathematical correctness or safety over
   every input. This is not a Python/OS sandbox or general symbolic system.
   JSON decoding has a 64-level lexical nesting guard, respecting quoted and
   escaped text, in addition to duplicate/nonfinite/overflow number rejection.
3. Supply one explicit externally authored known-method catalog entry for
   log1mexp, with source URLs, formula strings, derivative attribution, task/domain
   and version. Use a deterministic tool request; no model guess selects a tool
   silently. No API keys, network calls, new dependencies or schedulers.
4. A source-checkout CLI accepts an explicitly pinned saved model response and
   a method ID. Retain input response bytes. Compile a new tool artifact rather
   than altering the original response. Malformed input receives no numeric
   score. Reject output collisions/overwrites and changed inputs.
5. Grade both recorded proposal and compiled method against the unchanged
   public 23-point Decimal oracle, exact dtype and no absolute-gradient floor.
   Independent sign checks require loss<0 and derivative>0 at each finite point.
   Method acceptance requires all joint numeric and sign checks, not only finite
   forward values. Parent/reader must recheck source/input/program/output hashes.
6. Explicit before/after attribution: this is external known-method tooling,
   not a repaired model response, model competence gain, autonomous tool choice,
   novel research, sealed evaluation, transfer, C1/C2 or RSI. Replaying a previous
   response is not new model inference. Existing runtime/records remain unchanged.

## Required controls before acceptance

- Small positive arithmetic/conditional examples agree with direct typed NumPy;
  branches must be lazy and fully validated, including an invalid unused branch.
- Parser/type/node/depth/byte failure controls refuse safely. Confirm forbidden
  candidate text cannot create a sentinel file or invoke Python evaluation.
- The compiled externally authored log1mexp method passes all 23 public points
  with Decimal420/520 convergence; no float diagnostic decides acceptance.
- Loss-only repair and wrong-sign derivative controls remain rejected. A finite
  wrong loss and a near-zero/zero derivative must not gain acceptance.
- Preserve and distinguish malformed response from numerically evaluated failure.
- Actual CLI execution on the previously archived T1 response retains original
  failure and produces a separately attributed compiled result. Bind raw input,
  catalog, source, runtime, lock, program and measurement identities.
- Output/source alias, existing destination, changed source and altered result
  cannot publish a successful record. Synthetic controls and posthoc recorded
  response replay are labeled; no model weights or binaries are downloaded.

Run the compiler controls and all existing RSI controls. Extend case-specific CI
to include this source-checkout work package. Keep the immutable v0.4.10 release
and prior run archives intact. A later framework/wheel promotion needs its own
versioned package and installed-runtime acceptance; this checkpoint is not that
promotion. Include the result/limits in the English roadmap and technical framework.
