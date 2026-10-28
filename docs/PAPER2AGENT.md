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
