# Recovery acceptance and its limits

Version 0.4.9 preserves resident diagnosis, self-check, bounded automatic
recovery and explicit recovery controls after the two external Eidos CRON jobs
were retired. Removing schedules did not remove these functions. The existing
Startup entry remains. The [retirement record](CRON-RETIREMENT-2026-11-01.json)
retains the scope and 993 preserved execution-history rows.

## Actual before/after comparison

[The receipt](RECOVERY-LIVE-ACCEPTANCE.json) contains real disposable HTTP-service
observations on native Windows and a network-disabled Linux container. The same
final checker is copied into a detached checkout of `c12acdd617f1bac1d2449d2cb98dc7b085a5e404`
for the before measurement. Imported module locations and source hashes are
checked, so the old checkout cannot silently use the repaired package.

| Control | Before: c12acdd | After: 0.4.9 |
|---|---|---|
| Crash, sustained detection, actual process launch and endpoint verification | Works in the bounded fixture | Preserved |
| Missing/throttled route reported healthy | 404, 405, 410 and 429 incorrectly accepted | Rejected |
| Redirect substitutes another endpoint | Incorrectly accepted | Original endpoint must answer; redirect rejected |
| Windows recovered process console | Nonzero handle; `IsWindowVisible=True` | Handle zero; invisible |
| Linux listener with unavailable PID attribution | Duplicate-start request not refused | Existing listener refuses another launch |
| Preflight result and reported samples | Could contradict after a second probe | Derived from the same response map |

Each platform executes thirteen named controls. A private service starts on an
OS-selected loopback port, deliberately exits with code 17, remains down for two
samples and is restarted on the third. Real responses confirm recovery. A degraded
endpoint and a still-held port must not start another instance. The runner owns
the process tree; its completion is followed by bounded port and fixture-PID exit
checks before its uniquely owned workspace is removed.

The Windows experiment also established that a closed-loopback TCP probe can time
out on this host. A timeout is therefore not evidence of a free port. A completed,
validated Windows TCP table can establish absence; malformed, failed or unknown
observations remain unknown. Unattributed listeners use a conservative socket
probe, and unobservable occupancy refuses an unaccounted launch. The table format
and switches follow [Microsoft's netstat documentation](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netstat).

## Preserved safeguards and semantics

Three consecutive faults, cooldown, per-incident automatic attempt limits,
persisted launch reservations and measured terminal outcomes remain in place.
Manual/automatic observers share state ownership and attempt identities. Refused
or already-healthy requests do not spend a launch attempt. First terminal events
survive a failed state commit without duplicate accounting. Corrupt state and
unwriteable logs are reported, not silently reset. Public preflight reports retain
attribution without returning raw command lines that can contain credentials.

HTTP 2xx and authentication responses 401/403 qualify endpoint **presence**. This
does not establish valid credentials, loaded model identity, successful inference
or scientific task quality. Missing routes, throttling, redirects and server errors
are not accepted presence. The sampler and recovery path share this rule.

The checker refuses `-O` and `-OO`. Nonzero workers and malformed zero-exit JSON
must replace a deliberately copied prior PASS with FAIL. An empty/duplicate check
inventory, invalid booleans or invalid fixture process identities cannot pass.
The [focused source tests](CORE-RECOVERY-ACCEPTANCE.json) and installed SDK records
qualify separate boundaries; the installed lifecycle checker does not by itself
qualify a model-service restart.

## Reproduce safely

From a configured source checkout:

```sh
python reference/recovery_acceptance/check.py --out .scratch/recovery-live.json
```

The checker creates its own temporary service and private state. It does not
install CRON, change Startup, or target existing research-service processes.
To replay the before case, create a separate detached c12acdd worktree and copy
only `reference/recovery_acceptance/check.py` and `service.py` from version 0.4.9
into the same directory there. Invoke that copy; its three expected defects make
the before run fail. Preserve both receipts rather than treating the deliberate
negative as a broken after qualification.

This is source-checkout qualification of a disposable service on the same host,
with accelerated sampling intervals and unchanged cooldown constants. It is not a
real model-service restart, installed-recovery-path qualification, reboot/logon,
full-duration retry-timing or clean 24-hour certificate. Existing legacy monitor
and chain-loop migration remains pending after automatic approval rejected the
stop/restart operation (`blocked by policy`). Failure history remains intact.
