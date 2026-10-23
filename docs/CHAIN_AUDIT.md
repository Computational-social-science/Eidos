# Chain audit

**Method:** `python tools/audit_chains.py` (the table below was produced with
`--project-checker ../keystroke-observatory/scripts/check_references.py`; that project is
no longer used; the registered consumers are sealed fixtures).
runs one real operation per chain and reports PASS / FAIL / SKIP / ERROR. The table
below is its output on this host, not a design description. Run it after any change
to a chain; it takes about 15 s.

| Chain | Operation performed | Verdict |
|---|---|---|
| registry | load `projects/*/project.yaml`, resolve roots | **PASS** — 1 project, checkout present |
| gates | acceptance gate must PASS above and FAIL below a threshold; missing tool must SKIP | **PASS** — all three |
| gates + project checker | the project's own `check_references.py` invoked through `ref-check` | **PASS** — 19/19 entries agree |
| diagnosis | a failed `GateResult` must produce a diagnosis that names the metric | **PASS** — names `acc` from the gate's details |
| tracking | start an MLflow run, log a metric, end it | **PASS** — run recorded, `dvc_available=True` |
| quarto | render the project's actual manuscript through the bridge | **PASS** — 18-file manuscript, HTML render ok |
| inference | the configured budget must reject what does not fit and admit what does | **PASS** — 4 GB refuses the 5 GB entry, 12 GB admits it |
| validity (Gate S) | a valid register must PASS; the same register with an overstated objection count must FAIL | **PASS** — fixture PASS, mutated copy FAIL |
| surrogate (local NO) | a learned short-time stepper must recover a planted fixed point; shuffled labels must break it | **PASS** — 19/19 within 5%, 19 stable; control caught |
| decision | a known-answer probe through the operator, timed | **PASS** — p(17 prime)=0.963, 0.9 > 0.11; **median 182 ms** for 2 questions (n=3) |

**11 chains: 10 PASS, 1 SKIP, 0 FAIL/ERROR** on this host (the project checker SKIPs
unless `--project-checker` is given).

The Quarto row was run twice: once on a minimal probe, and once with
`--manuscript ../keystroke-observatory/manuscript`, which copies the real 18-file
manuscript into a temporary project and renders it. The second run is the one in
the table.

---

## Defects found by running it

Each was invisible to import checks and to the test suite, because no chain had
been invoked end to end.

### 1. Two gates aborted the suite when their tool was absent

`ref-check` and `prose-lint` called `subprocess.run(["ref-check", ...])`, which
raised `FileNotFoundError` straight through `run_gate` and `run_suite`. One absent
tool took down every later gate and printed a traceback instead of a verdict.

**Fixed:** a single `_run_cmd` raises `ToolMissing`; each external-tool gate turns
it into **SKIP** with `missing_tool` and `install` in the details; `run_suite`
converts any other exception into **ERROR** and continues. `GateResult.status` is
now PASS / FAIL / SKIP / ERROR, and `passed=False` with no status defaults to FAIL.

### 2. `ExperimentTracker` could not be constructed

`_init_dvc` ran `subprocess.run(["dvc", ...], check=True)` and caught only
`CalledProcessError`. On this host `dvc` is installed but its scripts directory is
not on PATH, so the call raised `FileNotFoundError` out of the constructor — the
whole tracking chain was unusable even though MLflow worked.

**Fixed:** `dvc_cmd()` resolves PATH first, then `[sys.executable, "-m", "dvc"]`;
a DVC failure sets `dvc_available=False` and leaves the run log working.

### 3. The Quarto bridge reported Quarto absent while it was present

`_check_quarto` probed a bare `quarto`. The binary ships inside a desktop
toolchain and is not on PATH, so `quarto_available` was `False` and every render
returned "Quarto not installed".

**Fixed:** candidates are tried in order — `$QUARTO_BIN`, PATH, three
home-relative locations, `%PROGRAMFILES%` — and the executable that answered is
stored as `quarto_cmd`, so the render call cannot disagree with the probe.

---

### 4. The VRAM budget was stored and then ignored

`ModelManager.__init__` recorded `vram_budget_gb` in `self.vram_budget`, but
`can_load` compared against the class constant `VRAM_BUDGET_GB` (10.5). A manager
built for a 4 GB card would admit a 5 GB model; the configured value had no effect
on the only decision it was meant to govern.

**Fixed:** `can_load` uses `self.vram_budget`; tests assert both directions
(refuse at 4 GB, admit at 6 GB) and the audit checks the same pair.

---

## The decision chain (v4.1)

`framework/decision.py` is a stdlib-only client for the shared operator
(`POST /v1/systemone`). It returns typed answers — `choice` with per-option
probabilities, `noul` with a yes probability, `score` — and raises
`DecisionUnavailable` when the service is down; it has no silent fallback.

`framework/inference` registers `StartLux-Decision-4B-Q8_0` and routes the four
judgement stages (`routing`, `hypothesis_screening`, `gate_triage`,
`failure_classification`) plus `evaluation_gates` to it. Generative stages keep
their generators; the audit fails if the operator leaks into a generative stage.

**Verified live, 2026-10-20.** The operator was served from the local GGUF
(4B AutoThink Q8_0, llama.cpp on :8081) behind `startlux-decide` on :8090. A
known-answer probe returned p(17 prime)=0.963, p(15 prime)=0.0076, and chose
0.9 over 0.11 with p=0.995. **Median wall-clock was 182 ms for 2 questions**
(n=3) and 253 ms for 3 questions in a separate 5-run probe — the published
"~26 ms" is the engine's read-out, not the HTTP round trip, so it is not the
number a caller experiences.

**The diagnosis seam, exercised against the live operator.** `refine_with_operator()`
sends only diagnoses the rules could not name (root cause "specific cause needs
investigation") and records the operator's answer in `context_snapshot["operator"]`
whether or not it is accepted. Three real calls:

| Gate | Operator choice | p | none | Outcome |
|---|---|---|---|---|
| `missing-csv` | `data` | 0.867 | 0.024 | accepted — category corrected from `methodology` to `data` |
| `gpu-oom` | `model` | 0.205 | 0.188 | declined — below the 0.6 confidence floor |
| `mystery-gate` | `gate_logic` | 0.783 | **0.464** | declined — `none_probability` says no option fully fits |

The refusal is the design working: a forced category for a failure nobody
understands is worse than an honest "needs investigation" plus a recorded attempt.

**Latency is bimodal.** Easy confident questions answered in ~180–250 ms; the
ambiguous `mystery-gate` call took **4.4 s**, because AutoThink deliberates when its
gate is not cleared. A framework quoting one number for the operator would be wrong
for half its traffic.

### Calibration: abstention is carried by the option set, not by `none_probability`

`tools/decision_probe.py` asks 100 items over short states — 50 answerable from the
state, 50 asking about a dimension the state never mentions (10 of each hand-written,
the rest generated with exact arithmetic) — as a three-way choice
(`yes` / `no` / `not_stated`).

| Measure | Result |
|---|---|
| accuracy, answerable items | **50/50** |
| abstention, answerable | **0/50** |
| abstention, unanswerable | **50/50** |
| Fisher exact, two-sided | **p = 2.0e-29** |
| `none_probability` returned | 100/100 items, **max 0.033** |
| latency | median 122 ms, max 191 ms |

The separation holds at n=100. The useful finding is still the negative one:
**`none_probability` never approached 0.2** even on items the operator declined. The
engine reports `none_probability` only for choice questions, and abstention is expressed
by *choosing the `not_stated` option*, not by raising that field. Two consequences:

1. A gate written as `none_probability >= 0.2` will essentially never fire. The
   effective criterion in `Decision.accepted()` is the confidence floor.
2. Abstention must be *offered*: the caller has to put a "not stated" option in the
   option set. With a bare yes/no (`noul`), the operator answers anyway — in the first
   version of this probe, unanswerable items came back at p(yes)=0.21–0.64 with no
   none field at all.

**The confidence floor is not identified by this data, and the probe says so.** No
answer was wrong at any floor from 0.50 to 0.99, so precision stayed 1.000 across the
whole grid and "the smallest τ that clears 0.95" is an artefact of the grid, not a
measured optimum. What the data does support: the lowest confidence on a correct answer
was **0.540**, so any floor at or below that costs nothing measurable here; where it
should sit above it needs items the operator sometimes gets wrong. Held-out at the
grid's lowest floor: acted on 23/50, precision 1.00 (95 % CI 0.86–1.00).

That first version also printed "mean none 0.000" for both classes because it coerced
a missing field to zero. The probe now treats an absent `none` as absent, and prints the
non-identification warning instead of crowning a threshold.

### The service is now startable, not a hand-started pair of processes

`decision-service/scripts/serve.sh` starts llama.cpp, waits for health, then points the
engine at it; `stop.sh` reverses it. Four defects surfaced while making it work: MSYS
paths are unusable by native binaries (`cygpath -w`), `curl -o /dev/null` returns exit
23 in this shell (every health probe read "down"), the package has no `__main__.py`,
and a cold 4.5 GB load exceeds 90 s. `serve.ps1` is now a wrapper over the tested
script instead of a second, drifted copy.

**Deployment defects found (upstream, worked around).** The engine's
`pyproject.toml` does not declare `jinja2`, so `serve` died at
`apply_chat_template` until it was installed; the GGUF repository ships no
`decision_config.json` or tokenizer, so the metadata had to be pulled from the
non-GGUF repo into the same folder; and `decision-service/scripts/serve.ps1`
passes `--launch-llamacpp`, a flag this CLI version does not have (the working
invocation is `--backend llamacpp --llamacpp-url http://127.0.0.1:8081`).
The exact commands are in `decision-service/docs/DEPLOYMENT_VERIFIED.md`.

---

## Remaining gaps (measured, not guessed)

1. **Inference is exercised at the budget level, not at the model level.** No model
   was loaded: that needs a running Ollama/llama.cpp endpoint and is a GPU-host
   action, not a CI action.
2. **CI is defined, emulated locally, and has never run on a runner.**
   `.github/workflows/ci.yml` exists. Its exact commands were reproduced in a
   throwaway venv (Python 3.14, not the matrix's 3.11/3.12): `pytest` → 69 passed;
   `audit_chains --ci` → 7 PASS / 1 SKIP (the SKIP is the project checker, absent by
   design); `audit_coupling` → no cycles. A green GitHub run still needs a commit, a
   remote and `gh auth`, and this checkout has none of the three (no commits yet, no
   remote, `gh` unauthenticated). Until then the badge would be decoration, so there
   is none.
3. **The Quarto render is a temporary copy, not the project's output path.**
   Rendering in place would rewrite the project's `outputs/rendered`; the bridge
   therefore proves it can render the manuscript, not that it can replace the
   project's own renderer.

### Removed: the memory layer

`framework/memory` was built, exercised (JSON roundtrip, Chroma backend), and then
deleted. No project wrote to it, so it was weight without evidence. The intent it
served is covered twice already: **procedural knowledge → agent skills**, and
**project-local history → the project's own `LESSONS` file** (keystroke keeps
`docs/LESSONS.jsonl`). A framework-owned vector store would have been a third,
unused place for the same knowledge, and on this host `chromadb` +
`sentence-transformers` segfault in one process (`KNOWN_ISSUES.md` §1).

---

## Reproducibility

**Clean-room run:** `uv venv .venv-repro && uv pip install -e '.[dev]'` in a fresh
environment, then `pytest tests/` → **57 passed, 1 skipped** (58 collected). The skip
is the MLflow-dependent tracking test (`importorskip`), which is correct: the clean
room carries only the declared core (`pyyaml`) plus `pytest`. This proves the
declared dependency metadata is sufficient for the core suite, including the
decision client and its socket tests; it does not prove the optional extras work,
because they are not installed there.

**Not covered:** the extras (`tracking`, `semantic`) are installed only on this host; a
clean-room run of each extra is a separate check. `framework/agents` was retired on
2026-10-20: it had no consumer outside itself, and the typed decision layer replaced what
it was for (`archive/retired-20261020/README.md`).

---

## What "advanced" means here, chain by chain

| Chain | State | Basis |
|---|---|---|
| registry | **used** | one real project, invoked repeatedly |
| gates | **used + hardened** | four verdicts, tool-missing semantics, per-gate isolation |
| diagnosis | **used** | consumes a `GateResult` and names the failed metric |
| tracking | **used** | real MLflow run; DVC initialised in the audit's temp root |
| quarto | **used** | rendered the project's 18-file manuscript |
| inference | **logic-tested** | configured budget enforced in both directions |
| decision | **used, live** | known-answer probe passed; 182 ms median for 2 questions |
| bootstrap | **smoke-tested earlier** | one project generated, then removed |

The distinction matters: "works" means a run happened; "used" means a real project
depends on it. Only the registry, the gates and tracking (in this audit) are used.

## Gate S and the Lean audit — measured runs

The chain is only credible if it has been pointed at real proofs. Two runs, both on
2026-10-21, on this host:

| target | module / theorem | verdict | wall |
|---|---|---|---|
| `lean-nhb` (core-only, no mathlib) | `NHB.PhaseI.Core` / `PhaseI.Selective.silent_iff_acceptedAndWrong` | **PASS** | 2.7 s |
| `atlas-lean` (mathlib-backed, 1 000+ theorems) | `Atlas.AlgebraicCombinatorics.code.BooleanSperner` / `SpernerProperty.boolean_sperner` | **PASS** | 112.9 s |

Each PASS means all four steps held: the module built (scoped to the audited module, not
the whole library), `#print axioms` resolved the constant, the axiom list stayed inside
`{propext, Classical.choice, Quot.sound}` with no `sorryAx`, and the control file
asserting `(1 : Nat) = 2` **failed** to compile.

The first attempt at the `lean-nhb` theorem used the unqualified name and was rejected in
24.3 s with `error(lean.unknownIdentifier)`. That failure is the evidence that the chain
bites: it does not report an empty axiom list for a name it could not resolve.

---

## CI incident, 2026-10-21

The first three GitHub Actions runs went red in the `audit` job while both `test` jobs
(3.11, 3.12) passed. The log named the cause:

```
ERROR registry  FileNotFoundError: projects/keystroke_observatory/project.yaml:
root does not exist: /home/runner/work/Eidos/keystroke-observatory
```

A project is registered as a **pointer**; on a CI runner the pointer resolves to nothing,
which is expected, and `--ci` already asked for leniency — but `load_projects()` was
called without `allow_missing`, so the error escaped before the SKIP branch could run.

**Fixed:** `load_projects(allow_missing=not STRICT_REGISTRY)`. Locally a detached
checkout is still an error (a project that is not there must not look audited); on CI it
is a SKIP. The behaviour is pinned by
`test_missing_project_root_raises_locally_but_is_skippable_in_ci`.
