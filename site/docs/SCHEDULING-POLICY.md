# Scheduling and duplicate-work policy

2026-11-01, updated after the user's decision: remove Eidos external CRON,
run research on demand, retain observational monitoring and core self-check /
self-healing. This supersedes the v0.4.8 policy retaining two Hermes jobs.

| Work | Owner and trigger |
|---|---|
| Live sampling and dashboard | One resident monitor, existing Startup entry; require fresh samples and advancing sequence. |
| Health detection and recovery | Resident monitor and supervisor; sustained faults, declared actions, ownership, cooldown, bounded attempts and measured verification. No external CRON is required. |
| Contract drift | Explicit checks after environment/toolchain changes; the previous daily Hermes schedule is removed. |
| Small subsystem smoke checks | Keep internal chain checking available. New-start source enforces ownership; two legacy loops remain pending consolidation. Bounded fixture checks are distinct from full report builds or training. |
| Claim verification | Changed declared inputs or explicit refresh; reuse a matching input-bound verdict for at most 24 hours. |
| Experiments, full suites and report builds | Explicit project commands, source/data workflows or CI; age alone must not execute a consumer gate. |

## Applied configuration

Removed `af4ae1129d9c` (`eidos-watchdog`) and `d61994a076b9`
(`Eidos contract drift`) using the managed Hermes CLI. Both definitions and
selected job outputs/notepads/execution records were backed up first; no run was
active. The live execution database still contains their 993 historical rows.
One unrelated Hermes job is unchanged. No Startup entry or resident process was
removed. See [the retirement record](CRON-RETIREMENT-2026-11-01.json).

The web page primarily observes state; the retained internal control loop can
perform known, bounded repairs. Explicit refresh and recovery controls remain
available. This policy does not turn off `maybe_auto_recover`, diagnosis, the
sampler stall watchdog or supervisor restart. External schedule deletion also
does not stop already running chain loops. Script shims and the isolation parser
remain compatibility resources; no new schedule is installed by this change.

## Source changes and runtime limits

The retained optional cron wrapper separates `execution_ok` from `ok` (health). A completed negative
watchdog check retains `execution_ok=true`, `ok=false`, its negative child exit and
causes. A scheduler-completed check therefore does not mean a healthy system.
Unchanged incident ages are quiet; new causes and recovery notify. Invalid JSON,
contradictory fields/exits and actual checker failures remain execution errors.
The external scheduler's own failure notices are not suppressed.

Manual refresh and background reconciliation share one lock through the gate
and snapshot build. Reuse requires a matching current input digest, PASS/FAIL
status and an aware check time less than 24 hours old; reuse never renews that
time. Explicit refresh forces its selected consumer's recheck, while other valid
rows can be reused. `build_pipeline.py --force` deliberately rechecks all.
Age-only automatic execution of arbitrary consumer gates has been removed.

These source changes require a monitor running the new source. Two legacy chain
loops and the legacy monitor were observed on global Python. Stopping/restarting
them was rejected by automatic approval (`blocked by policy`); they have not been
killed, restarted or migrated. New-start ownership guards do not consolidate old
instances retroactively. Runtime migration, reboot/logon and a clean 24-hour
observation remain pending.

## Core function preservation: development qualification

The current source repair preserves three consecutive fault samples, a base
ten-minute retry interval, the launcher's exponential failure cooldown and at most
three automatic launch attempts per unresolved incident. A refused/healthy
preflight is not a launch and does not consume its budget. Only a measured healthy
observation resets that incident budget. Unknown actions remain unavailable.

Automatic/manual paths share state ownership. Launch intent is atomically saved
before starting a process; a later publication failure retains that reservation.
Corrupt or invalid state is preserved and reported rather than reset. The runtime
startup observation window is 300 seconds (90 seconds for other service checks),
with in-flight launch protection at least as long. Successful process creation is
an attempt, never sufficient proof of repair. Terminal records require observed
health or an explicit failed outcome; log write failures are visible.
An attempt token prevents concurrent observers from settling a launch twice.
Journal records have stable event IDs and atomic publication; after a state-commit
failure, retry reuses the first recorded terminal outcome. State and log are still
separate files, not one atomic reader snapshot or a power-loss guarantee.

These are controlled source-level tests, not a live-service fault-injection,
installed-wheel, reboot or clean-soak certificate. The immutable v0.4.8 assets do
not contain later development changes. See [the focused receipt](CORE-RECOVERY-ACCEPTANCE.json).

The 0.4.9 adds a separate real disposable-service before/after comparison
on Windows and offline Linux, including observed console visibility and actual
process cleanup. It preserves the same bounded control loop; it does not migrate
legacy services or qualify model restarts. See [recovery acceptance](RECOVERY-ACCEPTANCE.md).

## Other chain findings

| Finding | Correction or remaining work |
|---|---|
| Reproduction labels outlived inputs or omitted failing bundle items | Source-bound schema-2 receipts, complete inventories, recomputation and declared dependency invalidation. Controlled verification is separate from paper reproduction. |
| Refreshing one consumer rechecked every consumer | Reuse recent unchanged rows; explicitly force the selected row or all rows. |
| Manual and background work had different locks | One reconciliation lock covers both monitor paths. It does not lock arbitrary external research programs. |
| Evidence age triggered arbitrary gates | Removed; stale evidence remains visible and explicit project execution remains available. |
| Handwritten MATCH test fixtures no longer met S12 | Execute controlled stubs in disposable copies, preserving original templates. Research receipts get no legacy exemption. |
| Other subprocess callers retain incomplete lifetimes | Pipeline verification, tracking, contract probes, formal/citation and update probes still need caller-specific qualification. |
| Multiple CLI audit writers can touch aggregate files | Current source uses per-target cross-process locks, process-local serialization, owner-specific marker cleanup and atomic JSON writes; controlled overlapping-CLI tests preserve earlier FAIL rows and reject a busy second run without work. Legacy writers that do not use this protocol remain pending migration. |

See [orchestration](ORCHESTRATION.md), [runtime isolation](CRON-ISOLATION.md) and
[functional acceptance](FUNCTIONAL_COMPLETENESS.md). This is not a clean runtime
acceptance certificate.


## Observed interruption and subsequent check, 2026-11-01

At 20:56:04 UTC+8, legacy scheduler tick 1013 recorded `demo (NO)` exiting
with 3221225786 (0xC000013A), and the instrument correctly raised ALARM.
Microsoft identifies that status as STATUS_CONTROL_C_EXIT; the code alone does
not identify the actor or mechanism that interrupted this child. See the
[NTSTATUS reference](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55).

The per-chain record subsequently contains an actual PASS at 21:05:43 with
91 points and maximum relative error 0.0002%. The heartbeat observed at 21:06:04
(tick 1015) is idle: `due=[]`, `ran=[]`, `failed=[]`. It is not itself execution
evidence. Later advancing instrument samples returned OK; `failures_total=9`
and the alarm history were retained. Producer identity is not present in this
legacy per-chain record, so the passing run is not attributed to a particular
resident scheduler. No alarm reset or service restart was performed.

A separate owned, read-only project-environment replay also produced 91/91 valid
points (seed 0, NumPy 2.5.4, maximum relative error 2e-6). A fresh isolated `-I`
process using the legacy executable lacked NumPy; that controlled profile does
not reproduce the resident processes' import environment and does not establish
the cause of their interruption. Neither result is a new scientific experiment.

Both previously identified global-Python 3.14 loops remain alive. Source locks
and hidden child containment do not retroactively apply to them. Runtime
migration remains PENDING under the previously documented automatic approval
rejection; this observation is not a clean-24-hour or deployment certificate.
