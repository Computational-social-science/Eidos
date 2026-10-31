# Health record

Every number here is produced by `tools/record_self_audit.py` into `docs/SELF_AUDIT.json`
and re-checked by `--check` in CI; none is typed by hand.

## Current state

| dimension | measurement | verdict |
|---|---|---|
| unit tests | **626 collected**, 626 passed; 4 optional Torch modules skipped in project env (16 tests separately passed on CUDA Python) | ✅ |
| coverage of `framework/` | **68%**, source-only scope including unexecuted modules; future no-regression by >1 point | measured |
| chain audit | **11 chains: 10 PASS, 1 SKIP, 0 FAIL/ERROR** | ✅ |
| Gate S on the reference fixture | PASS (valid register) and FAIL (mutated copy) | ✅ |
| Gate S on Eidos itself | **PASS — 8 objections, 0 open** (consumers are sealed fixtures) | ✅ |
| CI (GitHub Actions) | locked installs; local checks and remote CI are separate. See the [workflow runs](https://github.com/Computational-social-science/Eidos/actions/workflows/ci.yml) for the commit being assessed | live result |
| consumers | `demo_onboarding`, `demo_quantitative`, `operator_calibration`, `null_study`, `prose_lie`, `barron2026_agent`, plus measured `softmax_training` and `softmax_matrix` (saved models and final gradient endpoints independently validated) | 8 |
| render chain | html 19 KB, pdf 13 KB, docx 11 KB from one Quarto source (`docs/RENDER_CHECK.json`) | ✅ |
| external contracts | Quarto 1.10.19 (`tools/quarto`, via `QUARTO_BIN`), DVC, MLflow, decision service, BootLoops | ✅ |
| coupling | 0 import cycles across 107 scanned modules; 5 path-pattern matches in documentation/regex, manually reviewed | measured heuristic |

Additional instruments, each with its own evidence file:

| instrument | what it proves | record |
|---|---|---|
| fixture audit | every Gate S check trips on a case built for it, and one clean case passes | `docs/FIXTURES.json` |
| mutation fuzz | wrong registers and wrong evidence are rejected; equivalent rewrites are accepted | `docs/FUZZ.json`, `docs/fuzz_history.jsonl` |
| chain consumers | a gate that exits 0 without its artefact is not a pass; a missing binary is SKIP | `docs/CHAIN.json` |
| service probe | a service counts as up only if every endpoint answers | `tools/audit_services.py` |
| state ledger | capabilities with the artefact that would refute each | `docs/EVOLUTION.json` |
| scheduler heartbeat | a scheduler that stops ticking raises a fault within three intervals | `docs/status/scheduler.json` |
| demo coverage | 6 of 11 capabilities are demonstrated by a consumer, not only by a self-test | `docs/DEMO_COVERAGE.json` |
| model A/B | twelve fixed questions to two endpoints; agreement and score drift against a pre-registered rule, with a self-comparison control | `framework/model_ab.py`, `docs/status/model_ab.json` |
| dependency updates | sense on a timer, try in a throwaway env, promote only on a passing try inside the TTL, roll back from lock history | `lock/versions.lock.json`, `tools/update_operator.py` |
| README screenshots | captured from the built pages; page hashes recorded, commit refused when a page changed after its picture | `tools/screens.py`, `docs/SCREENS.json` |
| page guards | paint order, clipping, html hit-test, contrast, visual language, runtime — each with a test that builds the defect | `tools/audit_layout.py`, `tools/audit_contrast.py`, `tools/audit_visual.py`, `tests/test_layout_guards.py` |

The SKIP is the project checker: it needs a project path to run. The two adopters are
deliberately unlike each other — one Python repository with a manuscript, one Lean library
with neither — which is what closed O8.

## What is measured, and what is only asserted

2026-10-31: the former coverage command included tests and tools while this table called it
framework coverage. It now uses `coverage run --source=framework`, including unexecuted
framework modules. This changes the denominator; compare future records only within this scope.
Scientific case scope and corrected failure paths: [quality review](QUALITY-2026-10-31.md).
The Collapse/Cancellation case has 96 recorded cases, 12 qualification cases, two rejected
negative controls, and the existing four-tool MCP/agent. Full paper training outcomes remain unreproduced; the separately archived paired reconstruction and precision/epsilon matrix do not establish a paper MATCH.

Measured: test count, coverage, chain verdicts, contract reachability, coupling, the Gate S
fixture pair, and the local-operator recovery error.

Asserted, with the artefact named: that the gates improve a project's science (one project,
no control group), that the interfaces generalise (one adopter), and that the surrogate
layer is useful (no production consumer; the one exploration failed and is in
`experiments/`).

## Known gaps

1. **Single adopter.** Every claim about the framework's effect is a claim about
   keystroke-observatory.
2. **Coverage is uneven.** `inference/__init__.py` (38%), `inference/gguf.py` (0%) and
   `project.py` (61%) still leave substantial paths untested.
3. **The Lean chain is verified on two projects** (lean-nhb, atlas-lean), not on a project
   this framework gates.
4. **Quarto is installed outside the repository** (`E:/2026-AI4S/tools/quarto`), reached
   through `QUARTO_BIN`; a fresh clone without that variable will report SKIP.

## Checking it, without reading a label

```bash
python tools/health.py            # OK    seq=41 age=4.2s faults=-
python tools/serve_model.py status
python tools/serve_model.py swap --model ScienceRSI-8b.i1-Q4_K_M --dry-run
```

`health.py` prints the verdict **and** the sample sequence and age that produced it, and exits
non-zero on STALE/ALARM/unreachable. It exists because `overall: OK` was read as health for ten hours
on 2026-10-27 while the sampler was dead — the `stale` flag was in the payload and nobody looked.

`serve_model.py swap` decides before it acts: registry footprint against measured free VRAM, refuses
when the target would not fit beside what is resident, unloads through the router's API instead of
killing a process, and confirms identity from `/v1/models` afterwards. Two hand swaps had already
sent StartLux prompts into ScienceRSI and killed the desktop runtime; the procedure belongs in code.

The watchdog now also compares the sample `seq` with the last one it saw, so a sampler that keeps
rewriting the same payload is reported instead of looking alive.


Matrix acceptance: 36 complete trajectories, 1,836 points, 36 independent final gradient reloads; CPU/Gate S acceptance PASS. Mixed outcomes are reported in [the matrix report](../site/reports/softmax-matrix/report.html). Strict 24h soak remains RUNNING with 18 observed failures as of 2026-10-31 22:03 Asia/Shanghai; deployment transitions and the deliberate invalidation probe count as strict failures. Current monitor recovered to OK. Snapshot: [observation record](SOAK-OBSERVATION-2026-10-31.json).

Consumer snapshot acceptance: changed declarations revoke cached verdicts, background checks preserve sampling, and timeout cleanup owns descendants. See [functional completeness](FUNCTIONAL_COMPLETENESS.md). Generic Docker/Binder packaging remains incomplete.

Release observation on 2026-11-01: strict soak remains RUNNING after 547 observations, with 43 failures retained. This is not a clean 24-hour acceptance. See [dated snapshot](SOAK-OBSERVATION-2026-11-01.json).
