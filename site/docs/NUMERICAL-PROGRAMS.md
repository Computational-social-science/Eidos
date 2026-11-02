# Bounded numerical programs

`framework.numerical_programs` provides a small scalar formula/JSON API that can
be used from an installed EIDOS package. It imports only NumPy and the standard
library. It has no model, network, service credential, catalog or checkout-path
dependency. Research cases, method attribution and their oracles remain separate
from this general execution primitive.

## Use the API

```python
import numpy as np
from framework.numerical_programs import compile_formulas, parse_program

program = compile_formulas(
    'where(x <= log(2), log(-expm1(-x)), log1p(-exp(-x)))',
    'exp(-x)/(-expm1(-x))',
)
x = np.asarray(1e-12, dtype=np.float64)
value, supplied_derivative = program.evaluate(x)
saved_program = program.to_json()
reloaded = parse_program(saved_program)
```

This known log1mexp forward method is attributed to
[Mächler/Rmpfr](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html).
The displayed derivative is an external analytic derivation. The SDK compiles
the two supplied expressions; it does not differentiate one to obtain the other.
Record the original formulas, serialized program, actual input dtype/value,
code/dependency versions, source citations and independent checks in your project.

`compile_formulas(loss, gradient)` and `parse_program(text_or_utf8_bytes)` return
an immutable `ScalarProgram`. Direct construction is refused. `to_dict()` returns
fresh JSON data, and `to_json()` emits the closed loss/gradient-node schema.
`program.evaluate(x)` and `execute(program, x)` return independent 0D arrays;
changing either output cannot change the input, other output or program.

Native `np.float32`, `np.float64` scalars and exact 0D arrays of those dtypes are
accepted. Any finite input is permitted, including negative values and signed
zero; each method's mathematical domain remains the caller's responsibility.
Python numbers, vectors, masked/other ndarray subclasses, nonnative/other dtypes
and nonfinite inputs are refused without implicit promotion.

## Syntax and bounds

Formula text permits x, finite numeric constants, unary minus, + - * /,
exp/expm1/log/log1p, a single <= comparison and lazy `where(c,a,b)` or
`a if c else b`. Unknown names, attributes, imports, indexing, powers, keywords,
comprehensions, assignments and other operations are refused. Candidate text is
never evaluated as Python. All branches are fully type/grammar-validated before
execution; only the selected numeric branch executes.

The JSON form has exactly `loss` and `gradient` nodes. Nodes are `{"input":"x"}`,
`{"const":number}` or `{"op":name,"args":[nodes]}`. Only `le` produces booleans;
`where` requires a boolean condition and numeric branches. Both outputs must be
numeric. Duplicate fields and nonfinite JSON values are refused.

| Limit | Value |
|---|---:|
| UTF-8 source bytes per formula | 2,048 |
| JSON bytes | 32,768 |
| JSON nesting levels | 64 |
| Combined expression nodes | 256 |
| Expression depth | 16 |

Constants are normalized binary64 values before casting into the input dtype.
Integer literals that binary64 cannot represent exactly are refused; powers of
two above 2^53 can still be exact. Floating literals already denote binary64
values. Serialized programs make this normalization explicit. Runtime arithmetic
and each scalar result retain the input dtype.

## Errors and scientific acceptance

Wrong Python argument types raise `TypeError`; invalid grammar, budgets, types
inside the JSON schema or nonfinite input raise `ValueError`. Any selected
numeric operation/constant producing a nonfinite intermediate raises
`FloatingPointError`, including an operand used only in a predicate. Thus
`where(log(-x)<=0,1,2)` at positive x cannot hide its invalid log behind a finite
branch result. An unselected invalid mathematical branch is not evaluated.

Finite underflow to zero can still occur. Finite results, successful compilation
and a plausible forward value do not verify a gradient or guarantee numerical
accuracy. The API does not enforce loss/derivative signs, certify a method's
domain or promote research claims. Use independent references, explicit dtypes,
appropriate relative errors without a hiding absolute floor and broken controls.
The [historical compiler case](https://github.com/Computational-social-science/Eidos/blob/main/docs/NUMERICAL-METHOD-COMPILER-2026-11-02.md) illustrates
why forward-only acceptance failed. Its frozen reference interpreter retains
its positive-input diagnostic behavior; this SDK has a separate generic, finite
execution contract.

This scalar CPU API does not promise vectors, GPU, AMP, automatic/higher-order
derivatives or whole-domain mathematical correctness. Immutable Python values
and language limits restrict ordinary expression use; they are not a hostile
Python/OS sandbox or hard real-time resource guarantee. Installed-package and
source/runtime qualification remain distinct from scientific authority and RSI.

## Installed evidence and replay

The [v0.4.12 candidate receipt](NUMERICAL-PROGRAMS-ACCEPTANCE.json) binds the wheel, all
45 framework modules, metadata/RECORD, actual environments, independent numerical
controls and full current source audit. The
[standalone checker and replay instructions](https://github.com/Computational-social-science/Eidos/tree/main/reference/numerical_programs_acceptance)
explain normal installation and the frozen core closure. Windows and a public-image
offline Linux environment were actually measured; a later replay records its own
runtime and outcome. Source-checkout tests alone are insufficient installed evidence.
