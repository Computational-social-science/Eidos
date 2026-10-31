# Orchestration: what actually runs

This page exists because the README used to say the framework orchestrates agents with
**LangGraph**, and it does not. No module imports `langgraph`, `langchain`, `hydra` or `chromadb`;
none of them appears in `pyproject.toml`. A reader who installed Eidos expecting an agent graph
would have found no graph, and a reader who trusted the README would have had no way to tell.

So: what runs, in order, and what was removed.

## The five pieces

```
chain registry        tools/audit_chains.py      eleven chains, decorator-registered, run in order
   │                  tools/refresh_chains.py     decides what is due (tiered intervals)
   ▼
sampler               tools/watch_pipeline.py    every 15 s: probe, classify, record, recover
   │
   ├──► verdict       tools/status_view.py       one function: signals + chains -> OK / ALARM
   ├──► recovery      framework/recovery.py      plan, execute, verify; attempt and terminal rows
   └──► page          tools/dashboard.py         renders the verdict, never computes it
   ▼
governance            tools/update_operator.py   sense, try, promote, apply, roll back
```

**Chains** are the unit of work. Each is a function registered with `@chain(...)` that declares
what it needs; the runner executes them in order, records a span, and reports PASS / SKIP / FAIL.
A missing external dependency is a SKIP — unexercised, not passed.

**The scheduler** does not run everything on every tick. Each chain has an interval; the loop asks
`due()` what has aged past it, runs those, and writes a heartbeat. `nothing due` is a state, not a
crash.

**The sampler** is the monitor's only writer. It probes services and artefacts, classifies each
signal against a reference, and derives one verdict. It also drives recovery: a fault sustained
for three samples triggers one attempt, which is logged as an attempt (a process started) and,
separately, as a terminal row (the repair held). Those are different claims and are stored as
different rows.

**The decision operator** (`framework/decision.py`) answers typed questions — choice, yes/no,
score — from a local StartLux model. If the service is unreachable it raises
`DecisionUnavailable`; it never falls back to a regex or a general model's guess under the name
"decision".

**Update governance** is new in 4.2.0 and is documented in `docs/UPDATES.md`: sensing cannot move
a pin, a pin only moves on a passing try, and `apply` is the only command that installs.

## What is deliberately absent

| Piece | Status | Why |
|---|---|---|
| LangGraph / LangChain agent graph | **removed** | `framework/agents` had eleven symbols and no consumer. The work it described — hypothesis, literature, design, execution, evaluation, diagnosis, manuscript — is done by chains plus the typed operator; a graph nobody runs is a diagram, not a system. |
| Hydra configuration | never wired | `framework/project.py` and `configs/` cover the need with one YAML merge per project. |
| Vector memory (`chromadb`) | removed | No project consumed it, and chromadb + sentence-transformers segfaulted in one process on this host (`docs/KNOWN_ISSUES.md` §1). Procedural knowledge lives in skills, history in each project's `LESSONS`. |
| `requirements.txt` | deliberate | `pyproject.toml` declares dependencies and extras; `uv.lock` pins the resolved set. A `requirements.txt` beside them is a third copy that drifts — see below. |

The original design is archived at `docs/archive/technical-framework-v4.1-2026-10-20.md`.
The current technical framework describes the implementation. Open acceptance
items are tracked in `docs/FUNCTIONAL_COMPLETENESS.md`.

Consumer snapshots bind registry configuration, framework source and declared Gate S
inputs. Changes withdraw cached verdicts and queue one background recheck while
sampling continues. Missing bindings are UNOBSERVABLE; affected cards are STALE.
This checks claim records, not a new training run. See the ledger for scope and
retry/publication rules.

## Installing, and why there is no requirements.txt

```bash
uv sync --frozen --extra dev --extra tracking --extra verifiers --extra browser
# or, without uv:
pip install -e ".[dev,tracking]"
```

`pyproject.toml` answers *what this project needs*; `uv.lock` answers *what was resolved together*.
A `requirements.txt` would answer both again, differently, and the first time one of them is edited
by hand the two disagree. If a downstream environment insists on a flat list, generate it from the
lock rather than maintaining it:

```bash
uv export --no-hashes > requirements.txt     # a derived artefact, never edited by hand
```

`make test` and the gates do not depend on either file: they run with whatever interpreter the
caller provides. CI tests 3.11 and 3.12; this host's project environment is 3.12.
The separate CUDA research interpreter is 3.14 and is not interchangeable with it.

## If you are adding orchestration

Add a chain, not a framework. A new graph library arrives with its own runtime model, its own
state and its own failure modes, and none of that is observable to `audit_chains` — the moment it
matters, the framework's claim ("these chains ran") stops being checkable. The chain registry
gives you ordering, dependency declaration, spans and a verdict for free; if a piece of work
cannot be expressed as a chain, that is a design question worth answering before it is a
dependency worth adding.
