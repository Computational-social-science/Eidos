---
name: eidos-project
description: Use an installed EIDOS project CLI to initialize research workspaces, check evidence, prepare reports, inspect status and export local feedback. Select an explicit project and interpreter; scientific acceptance remains with the project's validator.
---

# EIDOS project adapter

Use the existing versioned core and return its structured receipts. This skill
does not include a model backend, independent gate implementation or running
monitor service. The simplified CLI needs an unreleased 0.5.0 candidate; stable
0.4.12 does not provide this whole interface. Do not install public-index `eidos`:
it belongs to a different project.

## Select the project and runtime

Resolve the user's target research root and read its local instructions. Select
the project's qualified interpreter or an explicitly configured worker environment.
Use that exact interpreter for every command; a generic PATH `eidos` may refer to
another installation. On Linux keep the venv entry path instead of resolving its
symlink to the base Python executable.

Before action, inspect the selected installation's version/origin and
`<worker-python> -I -m framework.cli --help`. Match it to the pinned EIDOS wheel
and its provenance. If absent or unsupported, report the missing capability;
do not silently install/upgrade dependencies, reuse a global Python or invent a
successful receipt. The development wheel's source, core lock and qualification
are described in the EIDOS repository's `docs/DOWNSTREAM-QUICKSTART.md`.

## Operations

Use argument arrays through the host's execution API, an explicit `--project`
root and finite execution timeout. Commands below show argument boundaries;
substitute actual paths without concatenating untrusted shell fragments.

```text
<worker-python> -I -m framework.cli init --project <root> --json
<worker-python> -I -m framework.cli check --project <root> --timeout 900 --json
<worker-python> -I -m framework.cli status --project <root> --json
<worker-python> -I -m framework.cli report --project <root> --format html --json
<worker-python> -I -m framework.cli feedback --project <root> --message <description> --out <new-zip> --json
```

Initialize only the selected project. Existing `.eidos/` is not an error to fix
by deleting it. The initial validator intentionally refuses acceptance. Read
`.eidos/project.yaml`, the declared scientific protocol and claims before
execution. Imported helpers/module source, configuration and data manifests need
explicit input declarations. Do not generate a permissive validator or weaken
the project's acceptance criteria merely to pass a check.

`--execution-only` means command/output-contract checking, not scientific PASS.
Report rendering needs configured manuscript inputs, Quarto and format-specific
external tools; a valid file does not establish scientific or journal acceptance.
Read-only `status` never substitutes for an authorized research run.

## Interpret receipts

Preserve status, scientific_status, execution_status, run ID, timestamp and
artifact/digest references when present. Read the JSON even when a status query
exits zero: the query can succeed while the research verdict is FAIL or STALE.
Keep REFUSED, BLOCKED, UNRUN, SKIP, ERROR and STALE visible. Missing or changed
evidence requires revalidation; a fluent explanation cannot restore PASS.
Return the actual receipt path/identifier with scope and unmet prerequisites.

## Optional observation and feedback

Only explicitly enroll with a matching candidate controller and a user-selected
central workspace. Registration does not start the monitor:

```text
<worker-python> -I -m framework.cli enroll --project <root> --python <worker-python> --monitor-root <central-root> --json
```

Ordinary observation must not rerun research. Do not start another 8765 server,
restart the existing service or replace pinned runtime identity as an onboarding
side effect. A local loopback dashboard is optional and does not provide remote
worker support by itself.

Feedback exports local metadata and the supplied description; it neither uploads
an issue nor closes an incident. Do not include secrets/private data in the
description or automatically attach logs/data. A proposed fix must retain the
original reproducer and protected acceptance rule. Keep candidate testing,
release publication, explicit downstream upgrade and originating-project replay
separate. Close an incident only when the actual release and replay evidence
justify it; otherwise report the remaining step.

Default operation uses local/free resources. If a requested model/operator is
unavailable or unqualified, report the limit or hand off; never silently call a
paid provider. Successful software repair is not a claim of scientific RSI.
