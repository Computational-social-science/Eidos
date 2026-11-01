# Owned project-command execution

The public entry is `framework.project.run_command`. All three command kinds
(`gate`, `test`, `render`) call `framework.subprocesses.run_tree`; the implementation
and both operating-system helpers ship inside the SDK wheel. Source checkouts
retain `tools/bounded_process.py` and the former Windows helper CLI as compatibility
entries. The configuration bootstrap can load the implementation using stdlib
`runpy` without importing an unrelated global `framework`/`tools` package.

## Lifetime and outcomes

A finite positive execution timeout is required before any worker starts.
The runner captures UTF-8 stdout/stderr, closes stdin and hides Windows consoles.
OS process creation and bounded cleanup can add time to the execution wait;
this is not a hard real-time deadline or a memory/output-volume limit.
Keep large research outputs in declared files.

Windows acquires a kill-on-close Job before the target can start. A private status
channel distinguishes worker exit codes from helper failures. On the qualified
Linux path each scope has a separate guardian process group, anonymous status file
and owner-lifetime pipe. A killed caller closes that pipe; the guardian closes its
group, and nested SDK scopes receive cancellation through their own owner pipes.
On normal root completion the guardian flushes the worker result and closes its
whole group itself. It does not hand cleanup back to a caller that might already
be dying. The parent's observed guardian termination is a control event, never
the research worker's exit code. Ordinary inherited-output descendants therefore
cannot turn successful root completion into a false timeout.

Timeout is ERROR/124; containment failure is ERROR/125. A real worker exit 125
can still map to a declared research OPEN. Missing executable is SKIP/127;
permission/execution failure is ERROR/126. Programmatic `ProjectSpec` objects use
the same exit-map validation as YAML registrations. Signal codes, reserved timeout/
unavailable codes and mappings to PASS are refused. Partial timeout diagnostics are preserved.
Required gate artifacts remain a separate acceptance contract.

These are trusted short-lived project commands, not a sandbox. Processes that
deliberately escape OS ownership, service/broker launches, arbitrary hostile code,
GPU cleanup after driver faults and other operating systems are not qualified by
these tests. Persistent services belong to explicit supervisors.

## Actual acceptance

[The machine record](SDK-PROCESS-ACCEPTANCE.json) binds the wheel, driver, source,
runtime, image and outcomes. A new Windows environment installs the wheel and its
cached dependencies offline. A network-disabled Linux container installs the same
wheel over the existing qualified CPU dependency environment; it is not a fresh
Linux dependency-resolution or new-machine test. Both invoke the driver with
Python isolation from outside the checkout and verify imports resolve to installed
`site-packages`, not repository source.

Controls cover timeout, successful root exit, nested calls, business code 125 and
missing executables. Windows also checks its actual console-window handle. Linux
adds a delayed-cleanup handoff control. Two private broken candidate wheels first
reproduced nested and handoff leaks; the final wheel rejects both. Only the fixed
wheel is distributed. Download the
[fixed wheel](../reference/sdk_process_acceptance/eidos-0.4.11-py3-none-any.whl) and
[standalone checker](../reference/sdk_process_acceptance/check.py).
Reproduce with a fresh environment and the checked driver:

```sh
python -m pip install eidos-0.4.11-py3-none-any.whl
python -I -X utf8 reference/sdk_process_acceptance/check.py
```

Select a new environment before installation; do not overwrite another project's
environment. The repository's lock and this standalone wheel installation are
different installation contracts; actual resolved versions are retained in the
record. This acceptance does not migrate already running monitors, prove reboot
or clean-24-hour stability, or establish scientific truth.

The source-checkout monitor recovery path has a separate
[real disposable-service comparison](RECOVERY-ACCEPTANCE.md). Do not infer model
restart acceptance from this installed project-command lifecycle test.

## Remaining callers

This change qualifies the project-command entry and its shared primitive.
Quarto manuscript/figure calls now use this primitive and require fresh artifacts;
see the [direct delivery contract](QUARTO-DELIVERY.md). Direct subprocess paths in
update governance,
formal/citation checkers and inference still require caller-specific migration and
failure-path acceptance. A project command encloses ordinary children it launches;
that does not make a direct Python call to another SDK entry automatically bounded.
See the [functional completeness ledger](FUNCTIONAL_COMPLETENESS.md).

Local tracking DVC/model subprocess paths now use owned interpreters and explicit
run identities; their separate [installed qualification](TRACKING-INTEGRITY.md)
does not qualify distributed MLflow stores or remote API deadlines.

Sources: [Python subprocess timeout semantics](https://docs.python.org/3.12/library/subprocess.html),
[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).


Direct reproduction now uses the same owned lifetime and source-bound receipts.
The [installed reproduction controls](REPRODUCTION-ACCEPTANCE.json) exercise 18
case groups and 512 Decimal-oracle comparisons on each qualified OS; three
false-MATCH probes are retained against the preserved 0.4.7 installation.
See [reproduction scope](REPRODUCTION-INTEGRITY.md); this is not paper training.
