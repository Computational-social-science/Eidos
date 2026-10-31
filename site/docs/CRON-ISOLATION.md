# Scheduler runtime isolation

The EIDOS Hermes watchdog failed in the real scheduler while direct project-Python
checks succeeded. The scheduler overlays its workspace and dependency environment
on `PYTHONPATH`; its regular `tools` package shadows EIDOS's tools namespace.
The failure occurred before the wrapper could launch its configured project checker.

The existing managed shims now read only the stdlib runtime configuration from
`tools/cron_entry.py` under a non-main module name. They then invoke the configured
project Python in a fresh `-I -X utf8` process. `PYTHONPATH` and `PYTHONHOME` are
removed from the forwarded environment so plain Python descendants cannot regain
the scheduler's import paths or foreign compiled extensions. UTF-8 is explicit,
stdin is closed, output streams and exit codes are preserved, and Windows children
use `CREATE_NO_WINDOW`. The scheduler continues to own its existing process tree.

Update the two existing EIDOS shims with:

```sh
python tools/install_hermes_cron.py
```

Use the project interpreter and configure `scripts/monitor.env` or `EIDOS_PYTHON`
first. The installer preflights both known script files, backs up originals by
hash, publishes atomically and rolls back a partial installation. It changes no
job schedule, model or notification configuration. No SDK source patch is required.

## Acceptance and limits

[The scheduler acceptance record](CRON-SCHEDULER-ACCEPTANCE-2026-11-01.json)
preserves the reproduced bootstrap failure, the pre-repair streak of 32 errors,
successful scheduler execution rows, actual interpreter/flags/console state and
installed-shim hashes. The execution database was opened read-only. Job status
was not rewritten: successful real dispatches reset the streak naturally.

Tests cover an already-imported foreign `tools` package, a plain Python grandchild,
the real non-main configuration reader, paths containing spaces, Unicode output,
normal/nonzero exits and a zero console-window handle on Windows. Manual checks
also use the actual Hermes managed-store bootstrap and injected import paths.

The watchdog has completed multiple real scheduled dispatches. The daily contract
check passed the same bootstrap manually; its next scheduled daily dispatch has
not yet been qualified. Its existing MLflow version-change finding is retained.
Nominal interval configuration and actual dispatch timestamps are recorded
separately; this is not a real-time deadline guarantee, reboot/logon replay or a
clean 24-hour stability test. A cached manual `ok` file alone does not prove the
scheduler ran. The EIDOS monitor's overall verdict covers its named instruments;
it currently does not substitute for inspecting external Hermes job state.
