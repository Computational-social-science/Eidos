# Compile a sourced numerical method beside a saved proposal

This source-checkout tool translates short formulas into EIDOS's existing typed
scalar expression language. It never evaluates candidate text as Python and
never starts a model, downloads weights, calls an API or schedules background
work. NumPy and the repository sources are required. Use the current project
environment (Python 3.11/3.12); this prototype is not in the v0.4.10 wheel.

The motivating [recorded comparison](../../docs/NUMERICAL-METHOD-COMPILER-2026-11-02.md)
retains the original local-model failure at 0/23 joint points. A separately
compiled, externally supplied known method passes 23/23. This is method reuse,
not proof that the model repaired itself or EIDOS gained RSI.

## Execute without a model service

From the repository root:

```text
python -m reference.numerical_method_tools --response reference/rsi_bootstrap/recorded_trials/rsi-retrieval-feedback-v1/retrieval-feedback-1/response.json --sha256 173cbf478e059a16fb9fe8ed2b5f4ba5213b4f034240c47b6c9154e10999e13a --method log1mexp-v1 --output .scratch/my-method-replay
python -m reference.numerical_method_tools --verify .scratch/my-method-replay
```

The destination must be new; existing files or directories are refused.
`--response` is a saved single-choice chat-completion JSON response and the hash
pins its exact bytes. Malformed message content is preserved and has no invented
numerical zero. An invalid transport envelope is refused before publication.
The original proposal and tool-generated program remain separate artifacts.

The catalog contains one versioned positive-input log1mexp method. Its forward
formula is attributed to the [Rmpfr documentation](https://search.r-project.org/CRAN/refmans/Rmpfr/html/log1mexp.html).
Its first derivative is an explicit external maintainer derivation, not automatic
differentiation or a model result. The entry links the existing method card by
canonical JSON content hash, independent of whitespace/key order/newlines.
Each execution separately binds raw source/catalog/card bytes. No upstream
article or implementation is bundled and no new dependency is introduced.

## Translation API

```python
from reference.numerical_method_tools.compiler import compile_formulas
from reference.rsi_bootstrap.expressions import parse_program, execute
import json
import numpy as np

tree = compile_formulas(
    'where(x <= log(2), log(-expm1(-x)), log1p(-exp(-x)))',
    'exp(-x)/(-expm1(-x))',
)
loss, derivative = execute(parse_program(json.dumps(tree)), np.asarray(1e-12))
```

Allowed syntax: x, finite numeric constants, unary minus, + - * /, exp/expm1/log/
log1p, one <= comparison, and lazy `where(condition,a,b)` or `a if condition else b`.
All branches are validated before execution. Source is limited to 2,048 UTF-8
bytes per formula; combined program limits remain 256 nodes and depth 16.
Strict UTF-8 JSON decoding also rejects duplicate fields, nonfinite/overflow
numbers and nesting over 64 levels while respecting quoted/escaped text.
Unknown names, attributes, subscripts, imports, keyword arguments and all other
operations are refused. There is no algebraic simplifier or symbolic derivation.

**Successful translation is not scientific acceptance.** The CLI separately
checks actual loss and derivative at the existing 23 public represented float32/
float64 inputs against Decimal420 references with Decimal520 convergence checks.
Relative tolerances remain 2e-5/2e-12, with no absolute-gradient floor. Loss<0
and derivative>0 are additional necessary checks, not substitutes for error
checks. Outside that public normal-result scope, outputs can underflow/overflow;
the API does not certify the entire positive real line, vectors, GPU, AMP or
higher-order derivatives. No arbitrary generated code is executed.

## Evidence and reader

The output preserves the exact response, compiled program, both assessments and
raw source/contract/lock/catalog snapshots (`.snapshot` suffix). `record.json`
is the terminal marker. A partial directory without that marker is incomplete.
The producer rechecks input/source/runtime and actual published payloads before
writing it. This is not a multi-file power-loss transaction or hostile-OS sandbox.

The reader checks file inventory/hashes, reconstitutes the selected method and
replays both programs from captured verified bytes. It compares all assessment
and core fields except the replay's varying timestamp/duration. Canonical JSON
comparison preserves boolean/integer/float differences. An ending stability
bracket rechecks receipt, source, environment, inventory and payload hashes.
It uses the same oracle; another process does not create independent scientific
authority. A malicious maintainer able to replace all code/records is outside
this integrity check's trust boundary.

Historical verification requires matching raw source bytes and runtime identity;
different checkouts, line endings or library versions can require a new recorded
replay, using the unchanged archived response and its explicit hash. The source
snapshots preserve what originally ran; pytest does not collect their test copies.
Neither replay nor a locally fabricated response proves original model provenance.
Trace that separately through the prior campaign's complete recorded evidence.

Run controls with no weights or credentials:

```text
python -m pytest reference/rsi_bootstrap reference/numerical_method_tools -q
```

CLI exit zero means the selected tool method passed its bounded execution checks.
The original proposal can still fail. Exit two means tool nonconformance; exit one
means refused/invalid execution or verification. Inspect the separate summaries.
