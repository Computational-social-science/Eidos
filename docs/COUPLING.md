# Coupling audit — measured, not asserted

"Loosely coupled" is a claim. This is the measurement behind it: `tools/audit_coupling.py`
parses the real import graph with `ast` (not grep), separates module-scope imports
(**hard**: the target must import for the source to import) from imports inside a
function (**soft**: paid only on that code path), finds strongly connected components,
and counts process/network boundaries and absolute-path literals.

Run: `make coupling` (exit 1 on any cycle).

## Result

| Measure | Value |
|---|---|
| modules scanned (`framework/**`, `tools/*.py`) | **10** |
| hard internal edges | **1** |
| soft internal edges | **8** |
| cycles (SCC > 1) | **0** |
| absolute-path literals in framework code | **0** |
| `os.environ` reads | **6**, across 4 modules (2 of them at import time) |

The single hard edge is `tools.decision_probe → framework.decision`: a tool may import
a library eagerly. **No framework module imports another at module scope.** The only
intra-framework edge at all is `framework.diagnosis → framework.decision`, inside
`refine_with_operator()`, and its direction is policy → infrastructure, which is the
direction that is allowed.

`tools/audit_chains` imports seven framework modules, all at function scope. It is the
**composition root**: it is the only place that knows every chain, which is why it is
also the place a new chain must be registered.

## Public surface, per module (`--symbols`)

| Module | Public names | Imported elsewhere |
|---|---|---|
| `framework.gates` | 18 | 1 (`GateRegistry`) |
| `framework.inference` | 11 | 2 (`ModelManager`, `StageAwareScheduler`) |
| `framework.tracking` | 11 | 1 (`ExperimentTracker`) |
| `framework.diagnosis` | 8 | 1 (`FailureDiagnosisEngine`) |
| `framework.project` | 8 | 1 (`load_projects`) |
| `framework.decision` | 6 | 2 (`DecisionClient`, `DecisionUnavailable`) |
| `framework.quarto_bridge` | 2 | 1 (`QuartoBridge`) |

**9 of 64 public names (14 %) are imported by anything outside their own module.** Each
chain is therefore reached through one or two entry points, which is what keeps the
in-process graph loose.

The third module previously listed here, `framework/agents` (11 public names, **0**
consumers anywhere in `tools/` or `tests/`), was retired on 2026-10-20 and moved to
`archive/retired-20261020/`. It is kept out of the package, with a README explaining why
and what would be required to restore it. Deleting rather than archiving would have been
irreversible: this repository still has no commits.

## What is actually coupled

Not the Python. The boundaries are contractual:

| Boundary | Contract | Enforced by |
|---|---|---|
| `gates` → BootLoops | CLI flags and exit codes of `~/.bootloops/activate.sh` | `audit_chains` (invokes the real protocol) |
| `quarto_bridge` → Quarto | `quarto render` arguments, output paths | `audit_chains` (renders the project manuscript) |
| `tracking` → MLflow / DVC | `mlflow` API in-process; `dvc` CLI via `python -m dvc` | `audit_chains` (records a run) |
| `project` → a project's own commands | `gate_command` / `test_command` / `render_command` from `project.yaml` | `audit_chains --project-checker` |
| `decision` → StartLux service | HTTP `POST /v1/systemone`, JSON answer shape | `audit_chains` (known-answer probe) |
| `inference` → llama.cpp / Ollama | HTTP `/v1/models`, `/api/*` | budget-level only; no model is loaded in the audit |

So the honest statement is: **loose in-process, contract-coupled at the edges.** A
refactor inside `framework/` cannot break another module's imports, because there are
none to break; a change in BootLoops' or Quarto's CLI can break a chain silently until
`make audit` runs.

## Known weaknesses

1. **Shotgun surgery at the composition root.** Adding a chain means editing
   `tools/audit_chains.py`. That is the price of having one place that knows the whole
   system; the alternative (chains importing each other) is worse.
2. **Policy depends on infrastructure in one place.** `diagnosis.refine_with_operator()`
   constructs a `DecisionClient` when no client is injected. The seam is already
   injectable (`client=` parameter) and the import is function-scope, but a `Protocol`
   would make the substitution explicit rather than conventional.
3. **Soft imports fail late.** A missing optional dependency surfaces when the code
   path runs, not at import. This is deliberate (a project pays only for what it uses)
   and is why `ToolMissing → SKIP` exists.
4. **Two processes can hold the same port.** During deployment, two `llama-server`
   instances listened on :8081 at once. No module detects this; `serve.sh`'s health
   probe only asks whether *a* server answers.
5. **Two environment reads happen at import time.** `framework/decision.py` binds
   `DEFAULT_URL` and `DEFAULT_TIMEOUT` when the module is imported, so changing
   `DECISION_SERVICE_URL` afterwards has no effect on the default client. The other
   four reads (`BOOTLOOPS_ROOT`, `QUARTO_BIN`, the inference endpoint, the Quarto path)
   are resolved at call time. This is global state, just small enough to be easy to
   miss.

## What not to do

Do not add a service layer, an event bus, or a dependency-injection container for 11
modules. The measured problem is not internal coupling; it is that external contracts
are checked by one script that is run by hand. The fix is more executable contracts,
not more indirection.
