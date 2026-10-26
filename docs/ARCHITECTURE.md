# Eidos architecture

This document states what each layer is responsible for, and — more usefully —
what it deliberately does not do.

## 1. Design constraints

1. **One source of truth per fact.** Global defaults live in
   `configs/global/framework.yaml`; a project states only its overrides in
   `configs/project.yaml`. Duplicating the global file into a project is
   forbidden because the two copies then drift. The file is loaded by
   `framework/config.py` — until 2026-10 nothing read it, and it had drifted to
   naming the framework `global_research_framework`, version 4.0, with a
   vector-store memory block that no longer existed. `tests/test_framework_config.py`
   now holds it to the code: model names, mutex pairs, probe size, VRAM budget,
   no absolute paths, no deleted layer. The version lives only in `pyproject.toml`.
2. **A gate that cannot fail is not a gate.** Every gate is tested in both
   directions (`tests/test_gates.py`). The acceptance gate originally treated
   every threshold as ">=" and silently passed an error rate of 0.12 against a
   0.05 ceiling; direction is now explicit.
3. **Optional dependencies stay optional.** The core (gates, diagnosis) imports
   with stdlib + pyyaml. numpy and matplotlib are core (the package imports them); mlflow/dvc are
   the `tracking` extra, playwright/pillow the `browser` extra. There is no langgraph, hydra or
   chromadb dependency — see §12.
4. **Failures are reported, never swallowed.** A missing tool makes its gate
   fail with an explanation; it does not become a pass.

## 2. Layers

| Layer | Module | Responsibility | Explicit non-goal |
|---|---|---|---|
| Decision | `framework/decision.py` | Typed choices with calibrated probabilities (StartLux) | Does not generate text; does not decide validity |
| Gates | `framework/gates` | Quantitative + semantic checks | Does not fix the work it rejects |
| Diagnosis | `framework/diagnosis` | Turns a failure into severity, cause, actions | Does not auto-apply fixes |
| Tracking | `framework/tracking` | MLflow runs + DVC data versions | Does not choose metrics |
| Publishing | `framework/quarto_bridge` | Quarto render + Docker/Binder package | Does not write prose |
| Inference | `framework/inference` | VRAM-aware, stage-aware model scheduling | Does not train models |

## 3. The research loop

```
hypothesis → [human gate] → literature → design → [human gate]
   → execution → quantitative gates → semantic gates
   → diagnosis (on failure) → manuscript → prose/ref gates
   → [human gate] → render + package → lessons recorded (project file)
```

Human gates are mandatory at hypothesis confirmation, critical experiment
design, and final submission. The pipeline records the requirement; it does not
pretend to satisfy it.

## 4. Gate semantics

A gate returns `GateResult(passed, score, details, human_review_required)`.

- `passed` is the only field a pipeline may branch on.
- `score` exists for dashboards, not for thresholds; do not average it into a
  pass decision.
- `details` must let a reader reproduce the verdict (values, thresholds,
  directions, missing inputs).

## 5. Hardware model

`framework/inference` assumes a 12 GB card and a hard VRAM budget (10.5 GB by
default). It loads one large model at a time, unloads between stages, and maps
stages to models. The mapping is data, not code: override
`inference.stages` in a project config.

## 6. What the framework cannot do

- It cannot make an under-powered experiment significant.
- It cannot verify a claim whose reference does not exist in the data; it can
  only report the absence (as the keystroke project does with `AVG_KEYPRESS`).
- It cannot replace a human gate. A green dashboard is not a peer review.

## 7. The closed loop: self-check and self-heal

The pipeline above is a forward path. What keeps it honest is the return path, and it has
operators with names, files and failure modes of their own.

**Self-check** (`tools/watch_pipeline.py`, every 15 s)

1. *sample* — probe every chain's boundary and every service's endpoints
   (`framework/services.py` is the one table that says which endpoints count).
2. *derive* — `tools/status_view.py::derive()` is the only verdict function; the payload, the
   page and the poller all consume its output, so they cannot disagree.
3. *decay* — `tools/chain_states.py` holds the transitions. `FAIL → PASS` must pass through
   `RUNNING`; an unrefreshed chain decays to `STALE`; `STALE` is not terminal, because fresh
   evidence after a void verdict is new evidence.

**Self-heal** (`framework/recovery.py`)

4. *plan* — a service with a known repair gets an ordered plan; anything else is refused, and
   the refusal is recorded.
5. *execute* — the launcher is idempotent and starts only the half that is missing. A start in
   flight blocks a second one; a process that exists is not by itself a reason to skip.
6. *verify* — the same endpoint table decides whether the repair worked. A `502` behind a
   healthy front door is still a failure.
7. *record* — `docs/status/recoveries.jsonl` carries phase, outcome and reason. An unlogged
   repair is indistinguishable from no repair.

**Feedback → evolution** (`tools/evolution.py`, `tools/fuzz_register.py`, `tools/audit_*.py`)

8. An instrument that finds a defect (a mutation the gate accepts, a component with no style
   rule, a page that renders without running, a vacuous pass) becomes a *guard* before the next
   commit: a fixture, a check, or a transition rule. `docs/EVOLUTION.json` holds the ledger —
   capabilities with their witnesses, and the counter that matters: blind spots found, and how
   many are still open.

The assembly view draws this as a fourth column (instruments) and an arc back to the chains;
the operator band beneath it draws steps 1–7 as the loop they form. If the arc is missing, the
picture is a pipeline pretending to be a system.

## 8. Releases re-earn the onboarding claim

A release is a claim that this framework can take a new project from nothing to a checked verdict.
`build_site.py --release` therefore runs `tools/release_gate.py` first and refuses to write
`site/versions.json` if it fails:

1. scaffold a project from `reference/demo_onboarding` into `docs/status/_release_rehearsal`
2. run its measurement (48 operator calls, ~27 s)
3. run Gate S on the scaffold and require PASS
4. run the template's `show_rejection.py` and require a rejection by S3 **and** S9

The rehearsal runs inside the repository because a directory on another drive cannot be described
relative to the registry, and leaves no registration behind — a registry entry pointing at a
deleted directory makes every later `load_projects()` fail.

Consumers are their own signal: the sampler reads each project's `docs/evidence.json`, not the
page's cached copy, and a project nobody has re-measured in 24 hours raises the fault line. The
same applies to the scheduler: `docs/status/scheduler.json` is checked every tick, and the server
restarts the loop when the heartbeat is older than two intervals.

## 9. Two demos, and a measured answer to "is one enough?"

One demo proves what it touches. `tools/demo_coverage.py` maps each capability to the artefact
that would demonstrate it and separates two different claims:

* **self-test** — the framework's own chains exercise the machinery (11/11)
* **in a demo** — a consumer project produced the artefact (6/11)

That second number is the one that speaks to the mission, and it is printed on the monitor band
rather than in a footnote. The gap is deliberate and named: service pairing, tracking, three-format
rendering, mutation equivalence and the SKIP rule are demonstrated by the framework's tests, not by
a consumer, and the next demo is chosen to close the largest gap rather than the easiest one.

The two demos are structurally unlike each other on purpose:

| | `demo_onboarding` | `demo_quantitative` |
|---|---|---|
| input | a language model, three wordings | a linear model, a planted effect |
| claim | agreement across wordings, Wilson interval | coverage and bias of an estimator |
| gate | Gate S only | Gate S **and** a quantitative acceptance gate |
| failure shown | a register that lies (S3 + S9) | a gate that exits 0 with no artefact |
| output | markdown report | rendered HTML through Quarto |

`release_gate.py` now refuses a release when either the onboarding rehearsal fails or the demo
coverage falls below six capabilities.

## 10. The monitor is audited like the code

A dashboard that lies is worse than no dashboard, so the pages are checked the way a result is:

| check | what it refuses |
|---|---|
| layout | two text boxes that intersect; content wider than its box |
| paint order | a label whose centre sits under an opaque rect drawn after it |
| clipping | svg text that falls outside its own viewBox |
| hit-test | html text whose centre is covered by a painted, positioned element |
| contrast | text below AA, drawn lines below 3:1 |
| visual language | type sizes off the declared scale, more colours or weights than the scale allows |
| runtime | a page error, a console error, a canvas that was never drawn |

The first two of these exist because failures shipped: a header band appended after the column
labels covered them, and a footer ran past its band. Neither is visible to a bounding-box
intersection test, so both guards were added with a test that builds a page containing the defect
and requires the audit to reject it (`tests/test_layout_guards.py`).

Column headers carry their own state — a module takes the worst verdict among the chains that use
it, a service takes its own health — and the poll recomputes both. A chain that was skipped is not
a fault in the module it uses: SKIP is excluded from the worst-of calculation, and a module whose
users were all skipped reports SKIP rather than borrowing a colour it did not earn.

The operator strip reads the recovery log as a small state machine, not as a boolean: an attempt
line says whether a process started, a terminal line says whether the repair was verified.
Reading only the last line made `verified / recovered` red — that row carries `outcome`, not `ok`
— and made a bare attempt green before anything had been verified. Four tests pin the cases
(verified, attempt-only, failed, empty).

## 11. Dependency versions move only on evidence

`framework/updates.py` separates sensing from promotion. Sensing asks PyPI and GitHub what exists
and writes a report; it cannot change a pin. Promotion requires a passing try for exactly that
version, recorded within a week, and refuses to move a pin backwards. `rollback` restores the
previous pin from the lock's own history.

`apply` installs the pinned version and measures the host again; a promotion bumps the framework's
own minor version, a rollback bumps its patch. A weights pin additionally requires a passing A/B
over twelve fixed questions (agreement ≥ 0.90, mean |Δp| ≤ 0.05).

The pin is single-sourced in `lock/versions.lock.json`; `docs/UPDATES.md` explains the rules and
what the operator deliberately does not do (it does not install binaries or weights).

### The README's pictures are artefacts too

`docs/screens/*.png` are captured from the built pages by `tools/screens.py`, which records the
source page hashes in `docs/SCREENS.json`. The commit hook refuses a commit when a page changed
after its picture was taken: before this, the README kept showing the previous release's monitor
because nothing tied the image to the page it claimed to show.

## 12. What is not here, and why

Three things that earlier documents promised are not in the code, and their absence is recorded
rather than left to be discovered:

| Piece | Status | Reason |
|---|---|---|
| LangGraph / LangChain agent graph | removed | `framework/agents` had eleven symbols and no consumer. The work is done by chains plus the typed decision operator. |
| Hydra configuration | never wired | `framework/project.py` merges one YAML per project; a second configuration system would be a second source of truth. |
| Vector memory (`chromadb`) | removed | No consumer, and it segfaulted with sentence-transformers on this host (`KNOWN_ISSUES.md` §1). |
| `requirements.txt` | deliberate | `pyproject.toml` declares, `uv.lock` pins. A flat list beside them drifts; `uv export --no-hashes` generates one when a tool demands it. |

The README claimed LangGraph orchestration until 2026-10-26 while no module imported it — the
framework's own rule (a claim must resolve to an artefact) applied to the framework. See
`docs/ORCHESTRATION.md` for what actually runs.

## 13. Verifiers run before a claim

Two checks are deterministic and run before anything is written into a claim register:

* **identity** — `framework/verifiers/citations.py` asks `proofpath` whether a reference resolves
  and whether a retraction notice exists, and maps the answer onto `VERIFIED` / `BLOCKED` /
  `SOURCE_UNAVAILABLE`. The third state exists because a provider outage is not a bad citation.
* **arithmetic** — `framework/verifiers/stats.py` recomputes p, d, g, achieved power and CI
  consistency with `academic-research-kernel` and compares them with what the document reports, at
  the precision the document reports. Both write JSON artefacts under `artifacts/`.

Neither loads a model. The ScienceRSI integration plan puts them first for that reason: a check that
needs a GPU to fail is a check that will be skipped when the GPU is busy.

Gate S gained **S10**: a claim that declares `citations` or `statistics` must have the corresponding
artefact, and the verdict distinguishes "nothing has judged this yet" (`BLOCKED`) from "the verifier
said no" (`FAIL`). A claim that declares `support: required` needs a `SUPPORTED` record with a
resolvable passage; without one the gate is `BLOCKED`.

`framework/inference` now carries the VRAM mutex the plan requires: `mutex_with` on a model spec,
refusal to load when a partner is resident even if both footprints would fit, and
`validate_registry()`, which rejects an asymmetric declaration outright.
