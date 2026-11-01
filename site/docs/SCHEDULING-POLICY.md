# Scheduling and duplicate-work policy

2026-11-01: the user requested immediate consolidation. Automatic health checks
remain useful; research execution is not a periodic heartbeat.

| Work | Owner and trigger |
|---|---|
| Live sampling and dashboard | One resident monitor, existing Startup entry; require fresh samples and advancing sequence. |
| Independent watchdog | Existing Hermes script job, nominally every five minutes; no LLM, incident/recovery notices. |
| Contract drift | Existing Hermes script job, daily 07:15; also run explicitly after environment changes. |
| Small subsystem smoke checks | One owned chain loop; bounded fixture checks, not full report builds or training. |
| Claim verification | Changed declared inputs or explicit refresh; reuse a matching input-bound verdict for at most 24 hours. |
| Experiments, full suites and report builds | Explicit project commands, source/data workflows or CI; age alone must not execute a consumer gate. |

## Applied configuration

Both existing Eidos Hermes jobs retain their IDs, schedules, scripts and history.
They already used `no_agent=true`; both now pin the project interpreter and working
directory, with catch-up disabled. Missed checks do not replay as a burst after
downtime. Managed CLI updates followed a local configuration backup. Unrelated
Hermes, Windows and Startup tasks remain intact. No duplicate Codex automation
was found or created. Failure history was not reset.

## Source changes and runtime limits

The cron wrapper separates `execution_ok` from `ok` (health). A completed negative
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

## Other chain findings

| Finding | Correction or remaining work |
|---|---|
| Reproduction labels outlived inputs or omitted failing bundle items | Source-bound schema-2 receipts, complete inventories, recomputation and declared dependency invalidation. Controlled verification is separate from paper reproduction. |
| Refreshing one consumer rechecked every consumer | Reuse recent unchanged rows; explicitly force the selected row or all rows. |
| Manual and background work had different locks | One reconciliation lock covers both monitor paths. It does not lock arbitrary external research programs. |
| Evidence age triggered arbitrary gates | Removed; stale evidence remains visible and explicit project execution remains available. |
| Handwritten MATCH test fixtures no longer met S12 | Execute controlled stubs in disposable copies, preserving original templates. Research receipts get no legacy exemption. |
| Other subprocess callers retain incomplete lifetimes | Pipeline verification, tracking, contract probes, formal/citation and update probes still need caller-specific qualification. |
| Multiple CLI audit writers can touch aggregate files | Scheduled tick ownership is qualified; complete cross-CLI writer ownership still needs a concurrency test. |

See [orchestration](ORCHESTRATION.md), [runtime isolation](CRON-ISOLATION.md) and
[functional acceptance](FUNCTIONAL_COMPLETENESS.md). This is not a clean runtime
acceptance certificate.
