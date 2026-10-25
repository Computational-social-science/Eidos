# Health record

Every number here is produced by `tools/record_self_audit.py` into `docs/SELF_AUDIT.json`
and re-checked by `--check` in CI; none is typed by hand.

## Current state

| dimension | measurement | verdict |
|---|---|---|
| unit tests | **157 collected**, all passing | ✅ |
| coverage of `framework/` | **73%**, no-regression by >1 point | ✅ |
| chain audit | **11 chains: 10 PASS, 1 SKIP, 0 FAIL/ERROR** | ✅ |
| Gate S on the reference fixture | PASS (valid register) and FAIL (mutated copy) | ✅ |
| Gate S on Eidos itself | **PASS — 8 objections, 0 open** (consumers are sealed fixtures) | ✅ |
| CI (GitHub Actions) | test job 3.11 + 3.12 green; audit job green | ✅ |
| consumers | `demo_onboarding` (template, must pass), `operator_calibration` (LLM, must pass), `null_study` and `prose_lie` (must be rejected) | 4 |
| render chain | html 19 KB, pdf 13 KB, docx 11 KB from one Quarto source (`docs/RENDER_CHECK.json`) | ✅ |
| external contracts | Quarto 1.10.19 (`tools/quarto`, via `QUARTO_BIN`), DVC, MLflow, decision service, BootLoops | ✅ |
| coupling | 0 import cycles, 0 absolute-path literals | ✅ |

Additional instruments, each with its own evidence file:

| instrument | what it proves | record |
|---|---|---|
| fixture audit | every Gate S check trips on a case built for it, and one clean case passes | `docs/FIXTURES.json` |
| mutation fuzz | wrong registers and wrong evidence are rejected; equivalent rewrites are accepted | `docs/FUZZ.json`, `docs/fuzz_history.jsonl` |
| chain consumers | a gate that exits 0 without its artefact is not a pass; a missing binary is SKIP | `docs/CHAIN.json` |
| service probe | a service counts as up only if every endpoint answers | `tools/audit_services.py` |
| state ledger | capabilities with the artefact that would refute each | `docs/EVOLUTION.json` |
| scheduler heartbeat | a scheduler that stops ticking raises a fault within three intervals | `docs/status/scheduler.json` |

The SKIP is the project checker: it needs a project path to run. The two adopters are
deliberately unlike each other — one Python repository with a manuscript, one Lean library
with neither — which is what closed O8.

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
4. **Quarto is installed outside the repository** (`E:/2026-AI4S/tools/quarto`), reached
   through `QUARTO_BIN`; a fresh clone without that variable will report SKIP.
