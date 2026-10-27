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
