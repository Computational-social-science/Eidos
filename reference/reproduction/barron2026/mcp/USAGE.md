# barron2026-softmax-fix — MCP server

Four tools from Barron (2026), *A fix for softmax and cross-entropy* (arXiv:2610.31642), evaluated in
float64 numpy: the paper's own listing is JAX, and the arithmetic is the same.

## Install and launch

```bash
uv pip install --python .venv-repro/Scripts/python.exe "fastmcp==4.0.3"
.venv-repro/Scripts/python.exe reference/reproduction/barron2026/mcp/server.py
```

The server speaks MCP over stdio. `fastmcp==4.0.3` is the baseline the Paper2Agent skill names in
`references/runtime.md`; `mcp` resolves to 2.3.0 with it.

## Tools

| tool | arguments | returns |
|---|---|---|
| `log_softmax` | `z: list[float]` | stabilised values, the naive evaluation, and `stable_minus_naive` |
| `softmax` | `z: list[float]` | probabilities, their sum, `is_normalised` |
| `hard_cross_entropy` | `z: list[float]`, `target: int` | loss, gradient, `grad_sum`, `grad_sum_is_zero` |
| `soft_target_cross_entropy` | `student: list[float]`, `teacher: list[float]` | loss, gradient, `grad_sum_is_zero` |

`grad_sum_is_zero` is not a fitted tolerance: it tests the sum against 8 ulp of the gradient's own
scale, which is what a three-term float64 sum can accumulate.

## Example

```json
{"tool": "hard_cross_entropy", "arguments": {"z": [9, -9, -9], "target": 0}}
```

returns `loss = 3.0459958111350716e-08` and a gradient whose sum is `8.9e-16` — zero to rounding,
where the naive evaluation of the same expression collapses.

## Verification

Paper2Agent's own verifier, unmodified, with `--require-all-tools`:

```bash
.venv-repro/Scripts/python.exe <Paper2Agent>/skills/paper2agent/paper2mcp/scripts/verify_mcp_server.py \
  --server reference/reproduction/barron2026/mcp/server.py \
  --expected reference/reproduction/barron2026/mcp/expected.json \
  --cases reference/reproduction/barron2026/mcp/cases.json \
  --require-all-tools --report reference/reproduction/barron2026/mcp/verify.json
```

Result: `{"success": true, "mode": "calls", "cases_checked": 4}` — inventory matched, every tool
answered, every asserted value matched.

## What this package does not claim

The paper's claim that the naive form returns *exactly* `0.0` on `z = [9, -9, -9]` is a property of
its precision and backend. In float64 numpy the naive form returns `-3.0459959887707555e-08`, close to
the stabilised value. The tools therefore return both numbers instead of asserting the collapse.
