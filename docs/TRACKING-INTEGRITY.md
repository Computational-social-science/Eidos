# Experiment identity and data provenance

Status: v0.4.10 candidate; controlled source and installed Windows/Linux checks pass.
Final release tagging still requires exact-commit CI and asset verification.
The published lifecycle, manuscript and reproduction receipts cover their listed
operations. They do not qualify the optional tracking adapter's general
correctness. Historical receipts and wheels remain intact.

## Confirmed defects

The v0.4.9 adapter accepts an `ExperimentRun` but uses MLflow's ambient fluent
state for parameter, metric, artifact, tag and termination writes. Constructing
another tracker changes the global tracking URI and experiment. Disposable
SQLite tests reproduce wrong-run writes/termination, broken interleaving,
default-store creation by convenience helpers and inconsistent reloaded status.
Existing project databases were not modified by these probes.

The data wrapper returns no checksum for an unchanged uploaded file and calls
`dvc remote get-url`, which the installed DVC rejects. URL concatenation also
misses DVC's content-addressed layout. A controlled directory mutation preserving
file size and timestamp leaves normal cached DVC status empty despite changed
contents. These are separate defects.

## Repaired contract

- Each tracker captures its store, registry and experiment. Relative local and
  SQLite locators resolve against the project root. SQLite driver aliases share
  the database lock identity. In-memory SQLite is refused before store creation
  because isolated workers require a shareable store.
- Writes use explicit run IDs with `MlflowClient`. Foreign stores/experiments
  and terminal runs are refused. Terminating one run preserves another fluent
  run. Convenience functions use the originating tracker. Deserialized records
  require explicit `get_run` rebinding.
- Same-user, same-host wrapper instances/processes share bounded run locks.
  Lock files persist to avoid inode races. Unrelated raw clients and multiple
  hosts are outside this coordination boundary.
- Model logging/download use owned interpreters with captured tracking/registry
  context. This avoids the observed MLflow 3.17.2 `models:/` ambient-store lookup.
  Project code, `code_paths`, names and registry options remain available.
  Download refuses occupied destinations and overlap with local model sources.
- DVC commands are bounded and quiet. Paths stay inside the declared project.
  Removing a `.dvc` record preserves data. Missing optional dependencies remain
  SKIP in the chain audit.
- `get_file_hash` returns the registered DVC MD5. Default workspace validation
  independently hashes files and disables DVC checksum state caches for native
  directory/ignore verification. `require_clean=False` explicitly requests the
  recorded version despite workspace changes.
- Dataset uploads stage data and metadata, check MD5/path/size together and
  record both SHA-256 digests in a final run-bound provenance artifact. Replaced
  metadata is refused before upload. Remote uploads are not one atomic
  transaction; failed calls may retain partial artifacts.
- Tracking self-check interleaves two actual runs, reads metrics/terminal states
  back and checks DVC content and private-cache placement. User/system DVC
  configuration is isolated before imports. The worker closes database/cache handles before
  strict temporary-workspace cleanup.

The declared minimum is MLflow 3.17.2 and DVC 3.67.1; frozen third-party versions
remain unchanged. Directory verification uses the pinned DVC `StateNoop`/cache
interface and needs requalification on dependency upgrades.

## Usage

For an existing project directory:

```python
from pathlib import Path
from framework.tracking import ExperimentTracker

tracker = ExperimentTracker({
    'project_root': str(Path('my-project').resolve()),
    'experiment_name': 'repair-study',
    'enable_dvc': False,
})
first, second = tracker.start_run('baseline'), tracker.start_run('repair')
tracker.log_params(first, {'seed': 19})
tracker.log_params(second, {'seed': 19})
tracker.log_metrics(first, {'error': 0.2}, step=0)
tracker.log_metrics(second, {'error': 0.1}, step=0)
tracker.end_run(first)
tracker.end_run(second)
```

These illustrative numbers are recorded inputs, not research measurements.
Callers must record failed termination when experiments fail. Creating a run
does not execute or validate an experiment. Missing Git provenance stays missing;
required code/data/config/seed/checkpoint records and scientific gates remain
project responsibilities.

`log_model` returns its model ID, URI and originating store. Use
`tracker.download_model(run, model_id, empty_destination)` before loading the
local model through MLflow. Completed runs remain readable. Model/project code is
trusted caller code; process ownership is not a hostile-code sandbox. MLflow's
serialization/trust checks remain enforced: the owned tree fixture uses a
reviewed `sklearn.tree._tree.Tree` allowlist; the project-code fixture explicitly
selects cloudpickle. No blanket trust list is installed.

The [DVC storage-locator API](https://dvc.org/doc/api-reference/get_url) does not
prove remote existence. Explicit run writes and termination follow the
[MLflow client API](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.client.html).

## Qualification boundary

The [measured receipt](TRACKING-ACCEPTANCE.json) includes the same ten initial
controls failing on immutable v0.4.9 and passing after repair; 49 installed-wheel
cases pass on both Windows and network-disabled Linux. Source self-audit reports
1086 passed, five skipped, no failures/errors and 75% framework coverage, with
unchanged source/dependency snapshots. Coverage of separately executed workers
is not inferred from parent-process coverage. Controls include
metadata replacement, preserved-stat mutation, SQLite aliases, separate-process
ownership and unchanged ambient context. Twenty-two additional harness controls
reject altered metadata, changed inputs/dependencies, empty/duplicate/skipped
tests and inherited external DVC caches. Four installed Windows negative
controls retain runtime-failure, optimization-mode and metadata rejection.

Linux uses private tmpfs for temporary workspaces and lock/cache files. A separate
ordinary-overlay run waits in SQLite commits; an independent diagnostic captured
SQLAlchemy/Alembic commit stacks and the kernel journal wait. The original run
timed out at 900 seconds; its FAIL receipt is retained separately and is not
counted as passed. Tmpfs qualification
does not establish disk performance or persistence. No SQLite durability settings
were weakened. The frozen environment was prepared with network access; the
qualified container execution had network disabled.

Release assets and exact-commit CI remain pending. No distributed-store,
power-loss, new-machine or unseen-model acceptance is claimed. Existing
model/monitor services were not stopped or restarted.
