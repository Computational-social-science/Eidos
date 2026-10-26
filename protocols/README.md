# Protocols — resolved from the shared BootLoops install, not vendored

This directory deliberately contains **no copy of BootLoops**.

BootLoops is a shared toolbox on this machine (`E:/2026-AI4S/bootloops`, activated
with `~/.bootloops/activate.sh`). Vendoring it as a submodule here would create a
second copy with its own version, which is exactly the drift the owner's
"toolbox is shared, not owned" rule forbids. The same logic already applies to the
decision service: deployed once, called by every project.

## Resolution order

`framework/gates` resolves the BootLoops root in this order:

1. `$BOOTLOOPS_ROOT`
2. `quality_gates.quantitative.root` in `configs/global/framework.yaml` (null by default)
3. `~/.bootloops/config.json`
4. **fail loudly** — a project that declares quantitative gates but has no
   BootLoops install is a configuration error, not a silent pass.

The framework itself never writes a drive letter for this; a project may pin one in its own
override if it must.

## What is used from it

The gate wrappers shell out to the real protocols rather than reimplementing
them:

| Gate | BootLoops entry point |
|---|---|
| `acceptance-gate` | `bootloops` acceptance protocol |
| `planted-truth` | planted-control protocol |
| `independence-bookkeeping` | independence audit |
| `timing-discipline` | compute-budget protocol |
| `tool-stewardship` | tool provenance protocol |
| `prose-lint` | prose lint protocol |
| `ref-check` | bibliography verification |

If an entry point is absent, the gate reports a failure with the missing path.
It never substitutes a local approximation.
