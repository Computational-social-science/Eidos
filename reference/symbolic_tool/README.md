# Free symbolic-gradient reference tool

This isolated study derives a first derivative from a **validated forward
program**, using SymPy 1.14.0 and the installed Eidos 0.4.11 numerical-program SDK.
It does not read a supplied gradient to construct the replacement. It preserves
the original forward JSON and stable `expm1`/`log1p` execution forms. No inference,
API key, subscription or hosted fallback is used. SymPy and mpmath license files
and dependency metadata are bound in each environment receipt.

Actual native Windows and network-disabled public-image Linux measurements
passed the same 23 log1mexp, 16 softplus and 8 square controls. The saved model
proposal remains a separate 0/23 joint result; its forward passed 23/23. The
derived treatment passes 23/23 joint controls. This is an external tool result on
known cases, not model learning, novel discovery, sealed transfer or RSI.

See the [English report](../../docs/SYMBOLIC-GRADIENT-TOOL-2026-11-02.md),
[summary receipt](../../docs/SYMBOLIC-GRADIENT-TOOL-2026-11-02.json),
[preregistered contract and admission tightening](../../.Codex/evals/symbolic-gradient-tool.md)
and [raw archive](recorded_trials/v1/).

## Reproduce locally

Use CPython 3.12 and a new environment outside this checkout. From the repository
root, set `UV_PROJECT_ENVIRONMENT` to that environment's absolute path, then run:

```text
uv sync --frozen --project reference/symbolic_tool --extra dev
uv pip check --python <environment-python>
<environment-python> -I -B <repo>/reference/symbolic_tool/qualification.py prepare --root <repo> --bundle <new-external-input-directory>
```

Keep the printed manifest SHA. Change working directory outside the checkout:

```text
<environment-python> -I -B <input>/qualification.py run --bundle <input> --output <new-output-directory> --manifest-sha <printed-sha>
<environment-python> -I -B <input>/qualification.py verify --bundle <input> --output <output>/measurement --manifest-sha <printed-sha>
```

The normal core wheel is already versioned in `reference/sdk_process_acceptance`.
This adapter remains a reference source tool; it is not added to the released
wheel. Install/bootstrap downloads are separate from scientific execution.

For actual offline Linux, prepare a wheel directory containing **only** Linux
CPython 3.12 compatible/universal artifacts whose hashes occur in this study's
`uv.lock`, including pytest dependencies. The public digest-pinned Python image
must already be available. Run `offline.py --bundle <input> --wheels <wheel-dir>
--output <new-output-dir> --manifest-sha <sha>`. The controller verifies its owned
container, disabled network, read-only root/input/wheels, private executable tmpfs,
locked bootstrap and removal. It never stops existing services or uses CRON.
Public CI reruns native Linux/Windows tests; it does not claim offline networking.

## Admission and limits

Only the SDK's closed scalar schema is translated with trusted constructors;
candidate strings never reach `sympify`, `parse_expr`, `eval` or `lambdify`.
Both numeric dtypes retain independent acceptance requirements. Literal
`x <= constant` thresholds are admitted conservatively after finite real value
and derivative boundary checks using both represented dtypes. Original selected
intermediates are checked before CAS cancellation. Nonliteral thresholds,
unproved boundaries, unsupported symbolic output and SDK budget overflows are
explicit refusals. CAS checks do not prove whole-domain or finite-precision
correctness. General constant-expression predicates, arrays/GPU and higher-order
AD remain unqualified.

The SDK owns worker/pytest process trees with 120-second worker and 180-second
campaign deadlines. Receipt readers rebuild programs, rerun all represented
inputs against independently converged Decimal definitions, check full installed
SDK/lock identities and recheck inputs/payloads at the end. Hashes are local
integrity evidence; this is not remote attestation, a hostile-code security
sandbox or a hard memory bound. Known tests are not independent sealed tasks.

The raw archive retains every measured prototype/failure, not only the successful
pair. Input Python files are archived as `.py.snapshot` to avoid test collection;
restore their original names when reconstructing a bundle and verify its manifest.
The already-versioned wheel is referenced by SHA rather than duplicated.
