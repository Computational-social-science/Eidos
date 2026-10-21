# Tools — local helpers, not a vendored toolbox

This directory is for **project-local** helper scripts that are genuinely part of
the framework (for example, a small adapter for a specific instrument).

It is deliberately **not** a place to copy third-party toolboxes:

- BootLoops → resolved from the shared install (`$BOOTLOOPS_ROOT`).
- The StartLux decision service → deployed once, called over HTTP.
- Quarto, MLflow, DVC, Inspect, DeepEval, Promptfoo, Ragas → installed as
  packages/CLIs, never committed.

A tool copied here is a tool that will drift. If something must be adapted,
write a thin wrapper that names the upstream version it targets.
