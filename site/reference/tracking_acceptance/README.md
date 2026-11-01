# Installed tracking qualification

This driver checks a non-editable Eidos wheel from outside its source checkout.
Use an isolated environment containing the lock-resolved `dev` and `tracking`
dependencies and the candidate wheel. Pass that environment's Python explicitly:

```sh
/path/to/venv/bin/python -I /path/to/Eidos/reference/tracking_acceptance/check.py \
  --source /path/to/Eidos \
  --wheel /path/to/Eidos/reference/sdk_process_acceptance/eidos-0.4.10-py3-none-any.whl \
  --out /path/to/results/tracking.json
```

The pinned protocol executes 49 actual cases using private SQLite stores,
local DVC data/cache/remote and trusted small sklearn models. Two source-only
optional-dependency checks are explicitly deselected. Source and installed
framework Python inventories must agree; the wheel's complete raw payload,
METADATA, WHEEL and RECORD must match the installed distribution. When the
installer records an archive SHA-256 it must also match. Wheel, driver and
both original/copied protocol fingerprints are checked before and after.

Pytest's base temporary directory, DVC global/system configuration and site
cache stay under the owned workspace. Ambient MLflow run/experiment settings
cannot select a target. Owned subprocesses exit before strict workspace cleanup.
Models and project code are trusted fixtures, not a hostile-code sandbox.

`--fault-child` deliberately exits the protocol child with status 17 and must
produce a FAIL receipt and nonzero exit. Ordinary failures replace an older
receipt atomically. `-O` and `-OO` are rejected before writing a receipt; a prior
receipt therefore remains historical and must never override the exit status.
Machine-local paths in a raw receipt identify the actual execution environment.

This protocol does not qualify a distributed tracking server, remote durability,
unseen model families, legacy service migration or a new machine. Final measured
results belong in `docs/TRACKING-ACCEPTANCE.json`; running the driver alone does
not publish a release or alter monitoring/recovery services.
