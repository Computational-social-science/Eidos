# barron2026-softmax-fix MCP server

Four existing tools implement the v3 numerical contract of *A Fix for Softmax and Cross-Entropy*
(arXiv:2610.31642v3). This NumPy float32/float64 adapter qualifies bounded numerical kernels;
it does not reproduce all paper training outcomes. The upstream listing uses JAX.

## Environment and launch

Use the project interpreter selected in AGENTS.md. Add `--extra agent` to the project's existing
locked `uv sync` command; preserve its other selected extras and uv.lock. The historical
`.venv-repro` remains separate and is not required by this NumPy implementation.

```bash
uv run --no-sync python reference/reproduction/barron2026/mcp/server.py
```

The server speaks MCP over stdio. The lock records FastMCP 4.0.3.

## Tools and numerical scope

| Tool | Arguments | Result |
|---|---|---|
| `log_softmax` | `z`, optional `dtype` | Fixed logs, conventional comparison and difference |
| `softmax` | `z`, optional `dtype` | Probabilities and normalization check |
| `hard_cross_entropy` | `z`, `target`, optional `dtype` | Loss, fixed/standard gradients, relative zero-sum checks |
| `soft_target_cross_entropy` | `student`, `teacher`, optional `teacher_kind`, `dtype` | Loss, gradient and cancellation contract |

`dtype` is float32 or float64 (default float64). For the cancellation repair, explicitly pass
`teacher_kind="logits"`. The default `probabilities` mode preserves legacy callers and cannot
recover information already lost in rounded teacher probabilities. Inputs must be finite vectors
with matching shapes where applicable. The zero-sum diagnostic uses a dtype-relative bound,
with no absolute floor; it alone does not qualify a gradient.

For hard targets `[9, -9, -9]`, target 0, float64 loss is approximately 3.04599590255207e-8.
At `[40, 0, 0]`, the conventional target derivative collapses to zero while the fixed derivative
remains negative. Exact represented student/teacher logit equality produces a fixed zero gradient.

## Verification from the repository or source bundle root

```bash
uv run --no-sync python tools/verify_barron_mcp.py \
  --server reference/reproduction/barron2026/mcp/server.py \
  --expected reference/reproduction/barron2026/mcp/expected.json \
  --cases reference/reproduction/barron2026/mcp/cases.json \
  --require-all-tools --report reference/reproduction/barron2026/mcp/verify.json \
  --cwd reference/reproduction/barron2026/mcp
uv run --no-sync python reference/barron2026_agent/agent.py
```

The first command runs the unmodified vendored Paper2Agent verifier through a documented
numeric assertion adapter: nonzero float64 outputs use relative tolerance 1e-14 and absolute
tolerance 0; zero and discrete fields remain exact. This avoids rejecting a one-ULP Windows/Linux
libm difference. The policy is recorded in the output. All seven filed calls must pass and all four
tools must be covered. The second command independently qualifies numerical outputs against
Decimal references, checks broken controls and runs Gate S. Scientific gradient tolerances are
not replaced by the smoke comparison policy.
