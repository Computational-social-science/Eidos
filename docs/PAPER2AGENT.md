# Paper2Agent inside Eidos

[Paper2Agent](https://github.com/jmiao24/Paper2Agent) (MIT; Miao et al., *Nature* 2026) turns a paper
and its code into a paper skill plus an MCP server. It is a good way to obtain an **independent
execution** of a published method, which is the one thing a framework cannot manufacture for itself.

Its output is a **toolbox**. It helps do work; it proves nothing. That distinction is the whole
integration, and it is why this repository does not wrap the engine.

## What Eidos takes from it

A delivery, under contract, and then a number.

```
dist/<project>-agent/
├── skill/<paper-name>/SKILL.md      # the paper, as procedure
└── mcp/<repo-name>-mcp/USAGE.md     # how to run the tools that were built from its code
```

`framework/reproduction.check_delivery()` requires both. A partial run — the skill without the MCP
component, which Paper2Agent's own contract calls partial — is refused, because a procedure with no
executable behind it cannot produce evidence.

Then one **reproduction spec** per number the project intends to rely on:

```json
{
  "paper": "tissue-2024",
  "tool": "predict_interval",
  "command": ["python", "repro/run_tissue.py", "--gene", "Acta2"],
  "expected": 0.927,
  "tolerance": 0.001
}
```

`tools/reproduction_check.py run spec.json` executes it, parses the JSON the command prints
(`json_path`, default `value`), and compares:

| verdict | meaning |
|---|---|
| `MATCH` | observed within tolerance of the paper's number |
| `MISMATCH` | the paper says one thing and the code another — a finding, not a failure to hide |
| `UNRUN` | no command, non-zero exit, or output that is not JSON: nothing was checked |

The record lands in `artifacts/reproduction/<paper>.json`. Gate S **S12** reads it: a claim that
declares `reproduction: <paper>` and has no record is `BLOCKED`; a `MISMATCH` is `FAIL`; only `MATCH`
lets the claim through.

```yaml
- id: C4
  text: "The interval covers the planted effect in 0.927 of simulations"
  reproduction: tissue-2024
```

## What it deliberately does not do

* **It does not trust "verified".** Paper2Agent runs verifier agents of its own; those reports are
  useful for deciding whether to *run* a delivery, and are listed by `check_delivery`, but they are not
  the artefact S12 reads. The number is compared or the claim is blocked.
* **It does not run the engine here.** The locally installed skill ships without its `scripts/`, and a
  conversion takes 25+ minutes of a driving agent's tokens. This module consumes deliveries; producing
  them is a separate decision, made per paper.
* **It does not turn a converted tool into a consumer.** A consumer is a sealed project whose measured
  behaviour is checked; a converted MCP server is a dependency that either reproduces a number or does
  not.

## Why this is the scientific use of it

The reproducibility problem is not "can a model read the paper" — it is "did anyone run the code".
Paper2Agent makes running it cheap enough to do routinely; S12 makes the result binding. That pairing
is what turns a conversion into evidence, and it is the only part of Paper2Agent's output that this
framework is willing to argue from.

## Limits, stated

* One number per spec. A paper whose claim is a figure or a table needs one spec per value.
* Tolerance is a policy decision, not a property of the paper: the default is absolute 1e-3, and a
  relative tolerance must be asked for explicitly.
* A `MISMATCH` does not say the paper is wrong. It says the code and the text disagree, and a human
  has to decide which one the project is going to cite.


## First real object: Barron et al., *A fix for softmax and cross-entropy*

The test object is arXiv:2610.31642 (Barron, Gnanapragasam & Tschannen, 2026). Its Sections 2 and 3
print four-significant-digit values for two numerical bugs, which makes it a good object: the claims
are exact numbers, not narrative.

**The engine could not be run here.** The installed skill ships `SKILL.md` only; the repository's
`paper2mcp/scripts/` (preprocess, verify) are absent locally and a fresh clone failed on this network
(`invalid index-pack output`). A conversion is also a 25-minute agentic build with no LLM channel of
its own. So this is the manual workflow the skill itself documents — paper to code to tool — and the
result is the same artefact S12 reads.

Eight specs, one per printed number, executed with the paper's own JAX listing under
`.venv-repro` (jax 0.4x, optax 0.2.8):

| quantity | paper | observed |
|---|---|---|
| `log_softmax([9,-9,-9])[0]` | −3.046e−8 | −3.0459972e−8 |
| target gradient through softmax | 3.046e−8 | 3.0459969e−8 |
| fixed cross-entropy | 3.046e−8 | 3.0459972e−8 |
| gradient sum | 0 | 0.0 |
| standard cross-entropy (the bug) | 0 | 0.0 |
| soft-target gradient, first entry | −4.595504e−8 | −4.5955044e−8 |
| fp32 vs fp64 maximum error | 0 | 2.54e−15 |
| standard soft-target, first entry | −5.960464e−8 | −5.9604645e−8 |

All eight `MATCH`, so the record is `MATCH` and a claim citing `reproduction: barron2026-softmax-fix`
passes S12.

What this establishes: the paper's numerical claims reproduce on this host with its own code. What it
does not establish: that JAX's autodiff and the analytic gradient agree beyond this example, or
anything about Section 4's training results (Slingshot, grokking) — those need the training runs, and
a claim about them would need its own specs.

Two failures found while building this, both in my code rather than the paper's: `run_spec` parsed
only the last line of stdout, so any pretty-printed JSON was `UNRUN`; and `json_path` could not index
a list, so `soft_grad.0` was unaddressable. Both are fixed and pinned by tests.


## Running the engine on the PDF: where it stops

The engine was fetched from the upstream tarball, and its paper-side pipeline was executed against
the PDF:

| stage | result |
|---|---|
| `prepare` | **ok** — 1 source, snapshot kept, review plan created |
| `extract` | **ok** — 10 pages classified, status `needs_agent_review`, page plans on disk |
| `build --draft` | **fails** — the builder's own validator rejects the package it just wrote: `Unexpected directory: assetsigure … Unexpected file: references\paper.md` |
| `verify` | not reached — no `build.json` exists to verify |

The build failure reproduces with a fresh output directory (`/tmp/stage1`), so it is not a path or
stale-output artefact. It is the same class as the engine defects the skill itself warns about, and
fixing it means patching third-party code — which this project does not do silently. The working tree
stays on disk (`p2a_work/`, gitignored) so a later attempt does not restart from zero.

What this changes: **the engine is not currently usable as-is on this host**, so the reproduction in
the previous section was produced by the manual workflow (the paper's own listing), not by a converted
MCP server. The artefact S12 reads is the same either way; what is missing is the third-party tool,
not the evidence.


### Correction: the clone failure was a path, not the network

An earlier version of this file said a fresh `git clone` failed on this network. That was wrong, and
the diagnosis took one command to overturn:

| destination | result |
|---|---|
| `/tmp/p2a` (MSYS path) | `fatal: fetch-pack: invalid index-pack output` — twice |
| `.scratch/clone-depth` (native path) | **cloned**, `--depth 1` |
| `.scratch/clone-filter` (native path) | **cloned**, `--filter=blob:none` |
| `.scratch/clone-full` (native path) | **cloned**, full history |

Git here is a native Windows binary and MSYS does not translate arguments for it, so `/tmp/p2a`
reached git as a drive-relative path (`E:	mp\p2a`); it created the directory and then failed inside
its pack step, reporting `invalid index-pack` rather than anything about paths. The repo, the server
and the link were fine throughout.

The build failure above is a different matter and stays: it reproduces with a native output path
(`.scratch/stage-native`), so it is the engine's validator, not the filesystem.


## The MCP server, and the third-party verifier that passes it

The paper-only branch stalls (above), so the code branch was taken instead: four tools from Equations
13, 19, 42 and 43, in `reference/reproduction/barron2026/mcp/server.py`, on `fastmcp==4.0.3` — the
baseline the skill names in `references/runtime.md` — with `mcp` resolving to 2.3.0.

Paper2Agent's verifier ran unmodified, with `--require-all-tools`:

```
{"success": true, "mode": "calls", "cases_checked": 4}
```

| case | tool | asserted |
|---|---|---|
| `log_softmax_stable_value` | `log_softmax` | `first == -3.0459958111350716e-08` |
| `softmax_normalised` | `softmax` | `is_normalised` |
| `hard_ce_gradient_sums_to_zero` | `hard_cross_entropy` | `grad_sum_is_zero`, `loss == 3.0459958111350716e-08` |
| `soft_ce_gradient_sums_to_zero` | `soft_target_cross_entropy` | `grad_sum_is_zero`, exact gradient |

`grad_sum_is_zero` is not a fitted tolerance: it tests the sum against 8 ulp of the gradient's own
scale, the error a three-term float64 sum can accumulate. On `z = [9, -9, -9]` the residual is
`8.9e-16`.

One claim is deliberately **not** reproduced: the paper says the naive form returns *exactly* `0.0` on
that input. In float64 numpy it returns `-3.0459959887707555e-08`, so the collapse depends on precision
and backend. The tool returns both evaluations and the gap between them rather than asserting a
collapse that does not happen here.

`tests/test_mcp_barron.py` keeps the report honest: it fails if `verify.json` stops describing this
package (inventory, case count, every case passing), so a stale report cannot outlive the code.


## The agent Eidos can actually call

A converted MCP server is a toolbox; an agent is a toolbox plus a caller that checks what came back.
`reference/barron2026_agent/agent.py` is that caller, and `projects/barron2026_agent/project.yaml`
registers it with the framework, so the dashboard, the chain audit and the site see it beside the other
consumers.

One run does five things:

1. starts `reference/reproduction/barron2026/mcp/server.py` over stdio (the same file Paper2Agent's
   verifier checks);
2. calls all four tools on the paper's input `z = [9, -9, -9]` and one negative control;
3. writes `docs/evidence.json` and `docs/agent_trace.json`;
4. compares the answer against `specs.json` — the tolerance is the one already registered there, not a
   new number chosen for this run;
5. runs Gate S on `analysis/CLAIMS.yaml` and exits non-zero unless it passes.

```
C1  matches_paper_value  true   (-3.0459958111350716e-08 against the printed -3.046e-08)
C2  grad_sum_is_zero     true   (8.9e-16)
control fired            true   (teacher [0.5, 0.6] leaves -0.1 in the gradient sum, as arithmetic says)
gate_s                   PASS
```

The control is the part worth keeping: the same tool, called with a teacher that does not sum to one,
must leave exactly `1 - sum(teacher)` behind. Without it, "the gradient sums to zero" would pass on a
tool that returns zeros for everything.

CI runs this in its own `agent-e2e` job — the vendored verifier first, then the agent — so the committed
report cannot outlive a change that breaks the server.
