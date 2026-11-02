# Project integration

A working repository is registered in EIDOS rather than moved into it. The project
owns its source, data, scientific acceptance, tests and manuscript; EIDOS owns
command discovery, invocation, declared-output checks and bound observations.
Isolated copies may be used for failure injection without changing the original.

## Register an existing project

Create `projects/my_study/project.yaml`:

```yaml
name: my_study
root: ../../../my_study
gate_command: ["{python}", "validate.py"]
test_command: ["{python}", "-m", "pytest", "-q"]
render_command: ["{python}", "render.py"]
expects: [docs/evidence.json]
reports: [docs/report.html, docs/report.pdf, docs/report.docx]
validity_register: analysis/CLAIMS.yaml
validity_document: docs/REPORT.md
expected_gate_s: PASS
validity_inputs: [validate_helpers.py, configs/study.json, data/manifest.json]
```

`root` is relative to the registration file or absolute. Commands are argument
lists, never shell strings. `{python}` and generic Python executable names use the
interpreter running EIDOS; select the project's environment before invoking it.
Optional commands raise a configuration error when absent. Missing checkouts are
shown as MISSING by `list` and cannot be executed.

```sh
python -m framework.project list
python -m framework.project exec my_study test
python -m framework.project check my_study
python -m framework.project exec my_study render
python tools/audit_validity.py --project my_study
```

The project defines what its gate actually checks. Exit 0 maps to PASS, exit 1 to
FAIL and other exits to ERROR, except missing tools (SKIP) and explicitly declared
nonzero research states. `exit_statuses` cannot convert a nonzero exit into PASS.
`expected_gate_s: FAIL` declares a deliberate negative control; a matching failure
means that control behaved as expected, not that its scientific claim succeeded.

`expects` lists files that a successful **gate** must leave behind. Exit 0 with a
missing required file is FAIL. This does not by itself prove that an existing file
is fresh or scientifically correct: the project validator must check its content
and provenance. Test and render commands do not inherit the gate's output
requirements. `reports` is a list of reader-facing paths, not an implicit proof
that every format was rendered successfully.

## Bind cached scientific verdicts

Snapshots bind the registration, framework Python sources, Gate S file handles,
the directly executed Python gate script and explicit `validity_inputs`.
Recognized Python interpreter options are accounted for; unknown options make the
snapshot unobservable instead of guessing a script. Python module mode (`-m`)
requires explicit input files. Code passed with `-c` is bound by the command
itself; any modules it imports still need explicit inputs.

Declare imported validator helpers, configuration, data manifests and any other
files needed to invalidate an old verdict in `validity_inputs`. This is an exact
file list, not a recursive import/dependency resolver. Large declared inputs are
hashed by streaming. Declaring only a manifest binds that manifest, not every
underlying dataset or model: the project validator must verify those identities.

Outside-project inputs additionally require exact permission:

```yaml
validity_inputs: [../shared/data-manifest.json]
validity_external_inputs: [../shared/data-manifest.json]
```

Permission alone does not declare an input. Referencing a permitted file through
`validity_inputs` or a Gate S handle binds its contents. Changes withdraw the old
cached verdict and queue a Gate S recheck; that recheck does not rerun experiments,
regenerate missing research data or establish scientific truth. Formal toolchain
snapshot binding remains unqualified. See [the completeness ledger](FUNCTIONAL_COMPLETENESS.md).

## Scaffold and rehearse

```sh
python tools/bootstrap_project.py --name my_study --dest ../my_study
```

The bootstrap refuses a nonempty destination or existing registration. Its LLM
measurement template requires the configured local decision service; a fresh
clone without that service has not passed this measurement. A non-LLM project
should register its own producer and validator; `reference/demo_quantitative`
provides a separate bounded quantitative example.

`tools/release_gate.py` rehearses the template before a release is recorded.
Each invocation owns a unique workspace. The missing-output negative control uses
its own local spec without global registration. Existing projects and status
directories are never deleted to make room for a rehearsal. Cleanup checks the
owned directory's device/file identity and resolved path; a replacement is retained
and reported as an error. `--keep` prints the unique workspace it preserves.
Subprocess timeouts own the entire worker tree and use hidden Windows execution.
A failed scaffold is not executed, and a failed coverage producer cannot reuse a
cached passing count. A successful rehearsal remains a template test.

## Independent local intake evidence

On 2026-11-01, the existing HPAF Unicode forensic engine was exercised with its two
local corpora in an isolated QA workspace: 513 and 520 records, 1,033 total.
Normal inputs generated all three expected HTML files. Invalid JSON made the
original engine exit 0 without reports; the EIDOS output contract correctly
returned FAIL. An exploratory count claim passed Gate S, an incorrect count was
rejected by S3, and validator-source or explicitly declared corpus changes withdrew
the old bound verdict. An initial overstatement of exploratory work as supported
was rejected by S4; the claim strength was corrected without inventing preregistration.

[The intake record](INDEPENDENT-INTAKE-ACCEPTANCE.json) preserves identities and
negative outcomes. Original code/data were unchanged. Raw corpora and the original
HTML reports remain private to the host and are not distributed by EIDOS.
That initial record proves intake and invalidation only. A subsequent
[metric-repair lifecycle](INDEPENDENT-LIFECYCLE-ACCEPTANCE.json) uses the actual
original engine to expose a README/implementation mismatch: opcode-script cost is
not guaranteed to equal the promised minimum Levenshtein distance. Two of 1,033
pairs differ, with maximum excess 112 edits. The repaired dynamic program matches
an independent C++ implementation; exhaustive edit graphs and broken controls
qualify the bounded execution paths. Wrong evidence and missing outputs fail,
while declared source/data changes withdraw cached verdicts.

Both the private complete-file package and a separate 235-pair benign package
have replayed in fresh same-host Windows environments. Only the benign package
and aggregate private-file counts are public. See the [technical report](../site/reports/hpaf-metric/report.html).
This closes the recorded same-host lifecycle example; it does not establish
novel discovery, new-machine installation, Linux/Binder acceptance for this case,
or independent outside adoption.

## Historical adopters and remaining acceptance

The earlier keystroke-observatory gate/render measurements and migration decision
are historical adopter evidence. Current registrations are discovered from
`projects/*/project.yaml`; neither a historical single-member count nor a template
rehearsal describes the current consumer set. A second project's complete lifecycle
must still execute its research, reject bad evidence, deliver independently usable
results and demonstrate change detection. See [functional completeness](FUNCTIONAL_COMPLETENESS.md).

## Applying this host's runtime update

Historical migration observation from 2026-11-01: the paragraph below preserves
the earlier pending state. The monitor was subsequently restored during the
[2026-11-02 shell incident](RECOVERY-SHELL-2026-11-02.md); that restoration does
not retrospectively qualify all earlier loop migrations or a clean 24-hour soak.

The source fixes do not replace already running interpreter instances. On this
host, the monitor and two old chain loops still use the earlier global Python;
the corrected launcher now selects project Python 3.12 in an actual diagnostic.
The previous CMD `CALL monitor.env` silently ignored its settings on this host;
both CMD launchers now delegate to the stdlib configuration reader. Their controlled
restart was rejected by automatic approval and was not retried through another
termination path. [The migration record](MONITOR-RUNTIME-MIGRATION-2026-11-01.json)
therefore remains PENDING. New starts enforce loop/tick ownership, but old
processes are not retroactively covered. A live web response is not proof that
the current source is running. Historical soak failures and restart events remain
part of the acceptance record.

## Downstream reuse architecture and implementation plan (2026-11-02)

Status: architecture decision and staged implementation plan. Existing interfaces
and proposed interfaces are distinguished below. This dated plan uses the
0.4.12 source/qualification baseline; published availability is recorded by
[GitHub Releases](https://github.com/Computational-social-science/Eidos/releases).
Installing a wheel does not
install the repository's monitor, fixtures, configuration or scientific data.

### One core, several entry points

The recommended default is an independent research repository with its own
environment and pinned EIDOS dependency. A shared local control workspace manages
project registrations and a single optional dashboard. An Agent or MCP adapter
calls the same tested core operations. It must not create another implementation
of scientific gates, execution ownership, evidence binding or recovery.

| Form | Role | Current boundary |
|---|---|---|
| Versioned wheel / future PyPI distribution | Default SDK dependency per research project | Wheels exist; no PyPI publication or ownership of a PyPI name is established here. |
| Agent instructions plus CLI / future generic MCP adapter | Natural-language entry for an existing local model or coding agent | The Barron Paper2Agent adapter is case-specific. A general EIDOS research agent is not delivered by that adapter. |
| Central local dashboard | Aggregate independent project observations | Existing monitor reads this checkout's registry and status files. Installing SDKs elsewhere does not auto-register them. |
| Project template | Minimal claims, validator, report and evidence conventions | Existing bootstrap is repository-based and its default measurement needs the local decision service. A model-free installed initializer remains to be built. |
| GitHub fork | Modify EIDOS itself and contribute patches upstream | Useful for framework development; ordinary scientific projects should depend on a pinned release instead of maintaining a framework fork. |
| Container | Optional reproducible execution profile | Qualified reference profiles are not a universal production deployment image. |

A distribution name need not equal its Python import namespace. The current
distribution is named `eidos` and uses the generic `framework` namespace. Before
public-index publication, verify publisher rights/name availability and evaluate
an `eidos` import namespace with a documented compatibility transition. Do not
tell users to run unqualified `pip install eidos` and assume it is this project.
The desired user interface is `eidos init`, `eidos check`, `eidos report`,
`eidos feedback` and `eidos monitor`; these commands are a proposal, not currently
installed console entry points.

### What can be used now

Install a verified, versioned wheel in the research project's own environment,
using its dependency lock and artifact checksum. Then supply an explicit registry:

```sh
python -m pip install /verified/path/eidos-0.4.11-py3-none-any.whl
python -m framework.project list --projects-dir /path/to/local-registry
python -m framework.project check my_study --projects-dir /path/to/local-registry --json
```

For that command, place the registration at
`/path/to/local-registry/my_study/project.yaml`. The schema at the start of this
document applies. Replace placeholder paths with actual local paths. Installing
only the wheel does not reproduce the repository's complete uv lock; lock the
downstream environment separately. Some source APIs still read checkout-relative
configuration. The `config` subcommand and a complete monitor must not be assumed
portable merely because `check` works outside the checkout.

An additional disposable same-host probe used the installed 0.4.12 candidate
outside this repository with an explicit external registry. A gate producing its
required file returned PASS; a gate exiting zero without that file returned FAIL.
The temporary project was removed. This verifies that narrow integration path,
not a scientific lifecycle, PyPI delivery or release publication. The local
observation is `.scratch/quality/downstream-reuse-probe-2026-11-02.json`.

An explicit project-environment executable can be the first element of a central
registration's command. `{python}` instead resolves to the EIDOS caller's
interpreter; a central monitor must not assume it is every project's interpreter.
Cached Gate S evaluation and project command execution remain separate operations.

### Sharing the dashboard without sharing environments

On this host, multiple registered projects can share
`http://127.0.0.1:8765/`. Register each independent checkout in the existing central
workspace's `projects/<name>/project.yaml`; the current monitor discovers that
registry. An arbitrary registry passed to a standalone SDK command is not
automatically enrolled in this monitor. Do not start one competing 8765 server
for every project. The dashboard is optional: headless SDK/CI execution remains
useful while it is unavailable.

The target design separates three concerns:

1. Each project worker runs in its own locked environment and owns its scientific
   commands, datasets, outputs and validation.
2. A local control workspace stores registrations, versioned event/receipt
   references and monitor state outside installed package directories.
3. One dashboard shows project, run and component identities; execution health,
   scientific verdict, evidence currency and repair state remain separate fields.

Each observation needs project ID, run ID, event ID, sequence, schema version,
EIDOS package version and wheel hash, project/validator/data/config identities,
interpreter, timestamp and evidence references. A newer central server must not
relabel an older worker as running the new core. Gate observations must bind
inputs before/after validation. State updates must be atomic, reject out-of-order
events and remain isolated by project. Shared GPU/model use needs admission
control so one project cannot silently replace another's resident model.

These worker-ingestion and generic per-project runtime contracts are proposed;
the present dashboard is not yet a distributed event service. `127.0.0.1` means
the current machine: a remote machine has its own localhost. Remote aggregation
requires a separately qualified transport, authentication and access policy.

### A concrete downstream-to-core feedback loop

Use an explicit state machine:

```text
DETECTED -> TRIAGED -> REPRODUCED -> PATCH_CANDIDATE
         -> INDEPENDENTLY_VALIDATED -> RELEASED -> DOWNSTREAM_VERIFIED
```

Failed reproduction, rejected patches, incomplete validation and regression
rollback are retained terminal/branch outcomes, never silently called resolved.
Operational service recovery is distinct from framework source modification.

1. Capture a local incident with exact versions, failure type, expected/actual
   behavior, bounded logs and evidence references. Deduplicate by a normalized
   fingerprint including relevant component/version; retain every occurrence.
2. Classify environment/setup, downstream implementation, scientific assumption,
   core defect or unknown. An unexpected scientific null result is not by itself
   an EIDOS defect. Preserve the original failing run unchanged.
3. Reproduce using a minimal distributable fixture in isolation. Private data,
   prompts, model files and credentials remain local unless explicitly released.
   A user may opt in to submitting a sanitized GitHub issue/patch; network access
   and a GitHub account must not be required for local feedback.
4. Make the failure a rejecting regression case and retain a valid positive
   control. A proposed fix must not weaken scientific thresholds, remove negative
   controls or rewrite the failing evidence to manufacture success.
5. Apply the candidate in an isolated branch/workspace. Check targeted behavior,
   independent references where applicable, existing consumers, installed-package
   replay and delivery compatibility. The proposing model cannot be the only
   oracle accepting its own patch.
6. Release a new immutable version with the defect ID, regression witness,
   compatibility notes and rollback target. Do not mutate an existing release's
   bytes or silently upgrade all research environments.
7. Trial the new dependency in a copy of the affected project's environment.
   Replay the original failure and at least one unaffected consumer. Only then
   mark DOWNSTREAM_VERIFIED and offer other pinned projects an explicit upgrade.
8. Persist the accepted lesson as a regression test, validator rule, adapter
   contract or scoped procedure. File scientific findings in the project's wiki
   when present. Prose memory alone does not enforce a behavior change.

The standard incident bundle/export CLI, cross-project feedback queue and full
release-to-originating-project status linkage are not implemented yet. Existing
tests, snapshots, recovery logs, dependency try/promote/rollback and
`tools/evolution.py` are useful parts of this loop; the evolution ledger is an
instrument, not an autonomous source-code repair engine.

### Sustained improvement without uncontrolled self-modification

Trigger this loop on a failed run, stale binding, rejected gate, recovery failure
or an explicit research request. Keep bounded monitoring and self-healing; do
not reintroduce repetitive external CRON research runs. Apply finite budgets,
deduplication, retry ceilings and stop conditions. Exhausted/ambiguous incidents
stay visible for human review. Candidate generation may use free local models;
deterministic/independent acceptance must remain effective if the model is weak.

Separate the trusted acceptance policy and sealed evaluation set from the
candidate's write scope. Promote useful tools/procedures only after validation;
do not auto-install arbitrary generated global skills. An updated worker,
package, validator or model must revoke affected cached conclusions. Software
repair, accumulated procedures and measured research improvement are different
claims. Autonomous scientific RSI requires additional held-out transfer evidence
that the improvement procedure itself improves, with fixed comparisons and
matched compute budgets. Installing an Agent or collecting more tests does not
establish that claim.

### Delivery order and acceptance

| Priority | Deliverable | Acceptance before advertising support |
|---|---|---|
| P0 | Finish coherent 0.4.12 publication already in progress | Current evidence/version metadata, installed replay, exact-final-commit CI and immutable assets agree. |
| P1 | Installed CLI and model-free initializer; explicit workspace/config paths | Two independent noneditable environments, no source checkout dependency, missing-output and changed-input refusals. Keep compatibility for existing registrations. |
| P2 | Shared dashboard project-runtime boundary | Two projects with different dependencies run concurrently, isolated state, correct worker versions, continued sampling when one worker fails and no duplicate server. |
| P3 | Local incident bundle plus feedback state machine | Inject a real core defect, reproduce, reject before repair, validate the patch and replay at the originating project; retain a failed-patch control and rollback record. |
| P4 | Thin generic Agent/MCP adapter | Each tool calls the same core operation; malformed requests and unsupported claims are refused; unavailable local models never trigger hosted fallback. |
| P5 | Qualify sustained improvement | Measure recurrence, replay success, regressions, time to downstream verification, reproducibility, accepted-result rate and held-out research performance. |

An Agent should follow the core contracts rather than replacing P1-P3. PyPI
publication needs a verified project name and publisher, plus pinned installation
instructions. A fork remains a development route. Do not make either a prerequisite
for local reuse.

Primary distribution references:
[Python package names and import names](https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/),
[packaging flow](https://packaging.python.org/en/latest/flow/),
[GitHub fork workflow](https://docs.github.com/en/pull-requests/how-tos/work-with-forks/fork-a-repo?tool=webui).
