# EIDOS Agent naming compatibility

The immutable `recorded_trials/windows-compat-v1` profile measures a fresh normal
Windows core installation in copy mode. All 51 SDK modules match the candidate
wheel. Six real console invocations cover both help entries, initialization by
`eidos-agent`, status by `eidos`, deliberate scientific refusal and a local-only
feedback export. Existing project data is preserved. No model is invoked.

The product brand is EIDOS Agent. This trial still installs distribution `eidos`
and imports `framework`; the new console alias does not constitute a package or
namespace migration. It is an unreleased compatibility candidate, not a PyPI
publication, production deployment, Linux trial or scientific evaluation.

To repeat the exact retained driver, prepare a **new** owned directory with the
candidate wheel at `wheels/eidos-0.5.0-py3-none-any.whl`, install that wheel and
the frozen requirements into its `env` virtual environment using copy mode,
then execute outside the checkout:

```text
<trial>/env/Scripts/python.exe -I -X utf8 <profile>/driver.py.snapshot <trial>
```

The driver refuses existing synthetic project/export targets by exclusive
creation; use a new directory for each measurement. Read `result.json` even on
failure. The profile manifest seals exact measured bytes and sizes, including
the wheel, original driver, raw command receipts and dependency requirements.
