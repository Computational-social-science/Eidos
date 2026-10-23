# Health record

Every number here is produced by `tools/record_self_audit.py` into `docs/SELF_AUDIT.json`
and re-checked by `--check` in CI; none is typed by hand.

## Current state

| dimension | measurement | verdict |
|---|---|---|
| unit tests | **101 collected**, all passing | ✅ |
| coverage of `framework/` | **73%**, no-regression by >1 point | ✅ |
| chain audit | **11 chains: 10 PASS, 1 SKIP, 0 FAIL/ERROR** | ✅ |
| Gate S on the reference fixture | PASS (valid register) and FAIL (mutated copy) | ✅ |
| Gate S on Eidos itself | **FAIL — 1 open objection** (single adopter) | ⚠️ honest |
| CI (GitHub Actions) | test job 3.11 + 3.12 green; audit job green | ✅ |
| external contracts | Quarto missing; DVC, MLflow, decision service, BootLoops present | ⚠️ |
| coupling | 0 import cycles, 0 absolute-path literals | ✅ |

The SKIP is the project checker: it needs a project path to run. The one open objection is
O8 in `docs/REFEREE_SIM.md` — one adopter is not evidence of generality.

## What is measured, and what is only asserted

Measured: test count, coverage, chain verdicts, contract reachability, coupling, the Gate S
fixture pair, and the local-operator recovery error.

Asserted, with the artefact named: that the gates improve a project's science (one project,
no control group), that the interfaces generalise (one adopter), and that the surrogate
layer is useful (no production consumer; the one exploration failed and is in
`experiments/`).

## Known gaps

1. **Single adopter.** Every claim about the framework's effect is a claim about
   keystroke-observatory.
2. **Coverage is uneven.** `inference` (32%) and `project` (55%) are exercised mainly by
   chains, not by unit tests.
3. **The Lean chain is verified on two projects** (lean-nhb, atlas-lean), not on a project
   this framework gates.
4. **Quarto is absent on this host**, so the PDF/DOCX path of any project cannot be
   exercised end to end.
