# Reuse EIDOS in an independent research project

## Current compatibility delivery, 2026-11-04

The current qualified worker is **EIDOS Agent 0.5.0**, distribution `eidos`,
import namespace `framework`, consoles `eidos-agent` and `eidos`. The
[actual public release](https://github.com/Computational-social-science/Eidos/releases/tag/v0.5.0)
and both required exact-head CI workflows are verified. The public wheel and
dependency-lock downloads below have also been replayed and hash-checked.
The exact 51-module wheel passes native Windows and same-host offline Linux
numerical, lifecycle and recovery-shell acceptance. This supersedes the older
candidate selection below. The existing resident monitor remains separately on
0.4.12; installing a worker does not start or migrate it.

On a managed host, use a registered qualified worker for a new project, or create
a dedicated runtime below. A project's existing runtime pin takes precedence.
This workstation's distinct resident/worker/source paths are recorded in
[local deployment status](LOCAL-DEPLOYMENT-STATUS-2026-11-04.md).

Ordinary projects need neither a source fork nor a full checkout at execution
time. Use Python 3.12 and uv in a new, dedicated runtime directory. Preserve an
existing study's CUDA/PyTorch environment. Download the published wheel and the
frozen core requirements from its immutable tag, and verify both hashes before
installation. PowerShell, substituting actual absolute paths:

```powershell
$runtime = '<new dedicated runtime directory>'
$project = '<existing research project root>'
New-Item -ItemType Directory -Path $runtime -ErrorAction Stop | Out-Null
$wheel = Join-Path $runtime 'eidos-0.5.0-py3-none-any.whl'
$requirements = Join-Path $runtime 'core-requirements.txt'
Invoke-WebRequest 'https://github.com/Computational-social-science/Eidos/releases/download/v0.5.0/eidos-0.5.0-py3-none-any.whl' -OutFile $wheel
Invoke-WebRequest 'https://raw.githubusercontent.com/Computational-social-science/Eidos/v0.5.0/reference/numerical_programs_acceptance/recorded_trials/v0.5.0/input-linux/core-requirements.txt' -OutFile $requirements
if ((Get-FileHash $wheel -Algorithm SHA256).Hash -ne '56d2fe35b1e5ab552fe001ae675e3af4f095e78522fa8fae682f5ea41cfa301c') { throw 'Wheel identity mismatch' }
if ((Get-FileHash $requirements -Algorithm SHA256).Hash -ne 'ca27b7da8739f5e3f1d14e54a6172b1bc9bb9da9e4344b1103d9216b2378e5de') { throw 'Dependency lock identity mismatch' }
uv venv --python 3.12 (Join-Path $runtime 'venv')
$workerPy = Join-Path $runtime 'venv/Scripts/python.exe'
uv pip install --link-mode copy --python $workerPy --require-hashes -r $requirements
uv pip install --link-mode copy --python $workerPy --no-deps $wheel
& $workerPy -I -m framework.cli --help
& $workerPy -I -m framework.cli init --project $project --json
```

On Linux use `venv/bin/python`; retain that venv entry rather than resolving its
base-interpreter symlink. These downloads require public network access; runtime
qualification itself can be offline. No model service, paid API or credential is
required for the core path. Initial scientific acceptance is deliberately REFUSED;
configure the project's own validator and declared inputs before running `check`.
Use the selected interpreter for `check/status/report/feedback`, as shown below.
Scientific validators and Quarto/TeX/Poppler prerequisites remain project-owned.

The software repair campaign is documented in [feedback lifecycle](FEEDBACK-LIFECYCLE.md).
Use actual journal receipts to distinguish VALIDATED, RELEASED, ADOPTED, REPLAYED
and CLOSED. An installed package or Agent adapter alone cannot close a defect or
qualify scientific RSI. Public PyPI `eidos` belongs to an unrelated project.

## Historical development checkpoints

Status: 2026-11-03. Stable release: **0.4.12**. The installed project CLI and
shared-worker protocol below are **unreleased 0.5.0 development**. Installing a
worker wheel does not install or migrate the complete monitor service.

## Choose an entry point

| Need | Use | Do not assume |
|---|---|---|
| Existing stable SDK | A pinned, verified GitHub release wheel and the explicit project registry | A stable `init` or `enroll` command |
| Trial the simplified project workflow | The qualified development wheel below in a dedicated environment | A published 0.5.0 release or current production adoption |
| Agent assistance | [The thin project skill](https://github.com/Computational-social-science/Eidos/blob/feature/shared-monitor/adapters/agents/eidos-project/SKILL.md) calling the selected installation | Autonomous scientific acceptance or a qualified general research reasoner |
| Repair the framework | A separate EIDOS branch/fork and disposable downstream trial environment | Automatic upgrades of existing studies |

Do not run `pip install eidos` from the public index: that name belongs to an
[unrelated astronomy package](https://pypi.org/project/eidos/). The development
artifact below retains its existing distribution name for exact evidence replay.
Public-index publication is blocked until distribution/import/console naming and
compatibility have been qualified. This guide does not reserve a new package name.

## Trial the installed CLI

The newer **EIDOS Agent** naming/feedback candidate is retained separately at
`reference/agent_naming_acceptance/recorded_trials/windows-compat-v1/`, with wheel
SHA256 `56d2fe35b1e5ab552fe001ae675e3af4f095e78522fa8fae682f5ea41cfa301c`
and its own `requirements.txt`. Its 51-module normal Windows installation
qualifies both `eidos-agent` and legacy `eidos` console entries; its installed
old/new private inference caller comparison also passes. The local incident API
is documented in [feedback lifecycle](FEEDBACK-LIFECYCLE.md). The prior Linux
qualification below belongs to its earlier wheel, so the newer artifact is not
automatically Linux-qualified. Neither artifact is a published 0.5.0 release.

Prerequisites: Python 3.11/3.12 and uv. Use a dedicated trial environment unless
the dependency closure has been checked against the study's lock. Do not replace
a study's CUDA/PyTorch environment as a side effect of onboarding.

From the matching EIDOS checkout, select the immutable artifact at:

```text
reference/inference_probe_acceptance/recorded_trials/probe-fix-v3/input/eidos-0.5.0-py3-none-any.whl
SHA256 57f7e6481aa7f706420e3a45ba3052a10c43da58050435167dadfce99cc94b2c
```

Its core dependency hash lock is `core-requirements.txt` in the same directory.
The artifact is an acceptance candidate, not the final source checkout's wheel.
The controller tools and documentation may have advanced independently. Verify
the artifact hash and keep the wheel/lock with the trial record.

PowerShell example, substituting actual absolute paths:

```powershell
$trial = '<new trial environment>'
$profile = '<matching checkout>/reference/inference_probe_acceptance/recorded_trials/probe-fix-v3/input'
$project = '<research project>'
uv venv --python 3.12 $trial
$workerPy = "$trial/Scripts/python.exe"
Get-FileHash "$profile/eidos-0.5.0-py3-none-any.whl" -Algorithm SHA256
uv pip install --link-mode copy --python $workerPy --require-hashes -r "$profile/core-requirements.txt"
uv pip install --link-mode copy --python $workerPy --no-deps "$profile/eidos-0.5.0-py3-none-any.whl"
& $workerPy -I -m framework.cli --help
& $workerPy -I -m framework.cli init --project $project --json
```

Compare the printed SHA256 with the value above before installation. Public
dependency bootstrap can use the network; offline replay requires a prepared
hash-matching wheel cache. A full source checkout is needed to obtain this
development profile, but is not needed by installed workers at execution time.

Initialization preserves existing research files and creates `.eidos/`. An
existing `.eidos/` is refused; never delete it just to make initialization pass.
The starter validator deliberately returns REFUSED. Configure:

- `gate_command`: the real bounded validator, as an argument list;
- `expects`: the required evidence artifacts, whose content the validator checks;
- `validity_register` and `validity_document`: project-local claims and report;
- `validity_inputs`: validator helpers/module source, data manifests and configs;
- `delivery`: the manuscript and explicitly declared rendering inputs, if needed.

Then use the same selected interpreter:

```powershell
& $workerPy -I -m framework.cli check --project $project --timeout 900 --json
& $workerPy -I -m framework.cli status --project $project --json
& $workerPy -I -m framework.cli report --project $project --format html --json
& $workerPy -I -m framework.cli feedback --project $project --message '<observed defect>' --out '<new incident.zip>' --json
```

Rendering needs Quarto; PDF additionally needs TeX and Poppler `pdfinfo`.
`--execution-only` does not establish scientific acceptance. A successful status
query can return exit zero while its JSON describes scientific FAIL/STALE/UNRUN;
consume the structured fields rather than the query exit code. A result is bound
to declared inputs, not every possible undeclared dependency.

## Optional shared monitor

The development `enroll` command registers a worker with the selected central
workspace; it does not start an HTTP server or rerun research:

```powershell
& $workerPy -I -m framework.cli enroll --project $project --python $workerPy --monitor-root '<central EIDOS workspace>' --json
```

Use this only with a matching candidate controller. The existing 0.4.12 process
on 8765 has not adopted the new protocol. Do not start a second service on that
port or silently restart the existing one. See [the actual shared-worker
acceptance](https://github.com/Computational-social-science/Eidos/blob/feature/shared-monitor/reference/shared_monitor_acceptance/README.md) and its retained
Windows/Linux raw records for qualified scope.

Each study keeps its own identity, interpreter, pinned version, evidence and run
history. The central worker cards separate transport, execution, science and
evidence freshness. Runtime replacement requires an explicit re-enrollment
decision; source/configuration changes withdraw cached acceptance. Read-only
observation never invokes a gate or changes a historical run timestamp.

The dashboard is optional: CLI use remains possible without it. Loopback means
this machine only; remote workers need a separately qualified transport and
authentication design. Automatic remote exposure is not provided.

## Feedback and updates

The feedback ZIP contains local metadata and the supplied description. It does
not automatically collect private data/logs, upload an issue, propose a patch or
close an incident. Supply a sanitized reproducer deliberately when appropriate.
Existing studies retain release pins until their own replay accepts an upgrade.

The next delivery is the [closed-loop acceptance campaign](REUSE-DELIVERY-PLAN.md),
including a failed candidate and rollback. A source audit or successful export
does not close that campaign and does not demonstrate scientific RSI.

Mutable failure-injection environments need copied files, not just distinct
venv directories: uv hardlinks can alias package files and metadata. The repaired
probe profile preserves the detected aliasing mistake, restoration and isolated
atomic negative control. Windows current-wheel qualification is separate from
the older Linux protocol profile; current repair Linux qualification is open.


### Subsequent Linux caller qualification

The missing Linux entry witnesses were traced to a noexec scratch mount. With
explicit executable private scratch, a fresh network-disabled/read-only-root
container passed the actual installed old/new probe campaign with unchanged
input/wheelhouse/SDK/metadata identities and verified owned-container cleanup.
The final `reference/inference_probe_acceptance/recorded_trials/probe-fix-v3`
profile supersedes v2 as this caller acceptance; failed attempts and withdrawn
controls remain preserved. This closes only the availability-probe Linux gap,
not current-wheel shared UI, new-machine, release/rollback or scientific RSI.
