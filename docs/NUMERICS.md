# Numerical guards: softmax collapse and cancellation

Two failures, one check. `framework/verifiers/numerics.py` carries both halves and
`tools/audit_numerics.py` applies them to the framework and to every consumer.

## What is caught

| shape | example | what it costs |
|---|---|---|
| log-of-sum | `log(sum(exp(z)))` | cancellation: `log_softmax([9,-9,-9])` returns 0 instead of -3.05e-8 at float32 |
| log-of-probability | `log(softmax(z))` | underflow to `-inf` for small probabilities |
| overflow | `exp(z)/sum(exp(z))` with `\|z\| > 709` | `inf/inf` → `nan` |

The static half reads the AST, not the names. `log(sum(exp(x - max(x))))` is **not** reported: the max
shift is the fix, and the detector checks for it rather than pattern-matching the text.

## What is measured

`probe(fn, z)` compares a callable against a 50-digit `Decimal` reference and returns a verdict:

```
PASS          relative error <= 1e-6      (six digits; float64 cannot do better on this input)
LOSSY         <= 1e-2
WRONG         otherwise
CANCELLATION  returned exactly 0 where the reference is not 0
COLLAPSE      non-finite, or OverflowError
```

The reference is `decimal`, not numpy: a numpy reference would inherit the cancellation it is meant to
detect.

## How a consumer opts in

```yaml
# projects/<name>/project.yaml
numerics: required
```

`tools/audit_numerics.py --projects` then scans that project's tree, and both pre-commit and CI fail on a
finding. Projects that do no probability arithmetic are not forced to declare anything.

## Intentional textbook code

A file that computes the textbook form on purpose — the converted paper returns it so a caller can see
the gap — marks the line:

```python
naive = z - np.log(np.sum(np.exp(z)))  # numerics: intentional — comparison only
```

The marker is on the code line and is reviewable in the diff. It suppresses that line only.
