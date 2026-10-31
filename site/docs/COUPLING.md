# Coupling audit — current scope

Measured 2026-11-01 by `python tools/audit_coupling.py --symbols --json docs/_coupling.json`.
The previous ten-module baseline is preserved in [the archive](archive/coupling-baseline-2026-10-20.md).
Its statements about no framework imports and no repository commits describe an earlier state.

| Measure | Current value |
|---|---|
| scanned modules (`framework/**`, `tools/*.py`) | 109 |
| module-scope internal edges | 34 |
| function-scope internal edges | 72 |
| import cycles | 0 |
| public names / names imported elsewhere in the scanned sources | 272 / 40 |
| path-pattern matches | 5 |

Source: [_coupling.json](_coupling.json). Imports found by AST are structural evidence,
not proof that every runtime path was executed. Bare imports, dynamic loading and
external commands can introduce dependencies outside this graph. Public-name usage
excludes test consumers and is not a dead-code verdict.

All five path-pattern matches were inspected: `framework/recovery.py` and
`tools/audit_stray.py`/`tools/watchdog.py` contain explanatory Windows path examples;
`tools/audit_coupling.py` contains its own detector pattern; `tools/dashboard.py`
contains a timestamp regex whose escaped d/colon sequence matches the path heuristic.
The count is therefore five heuristic matches, not five verified machine-specific
runtime dependencies. Do not label the unclassified heuristic count as a portability
certificate. Other platform assumptions still require clean-environment execution.

The monitor's chain/module matrix is a different projection: it shows imports used
by registered chain functions, not all 109 scanned modules. Generic executable-package
portability remains open in [functional completeness](FUNCTIONAL_COMPLETENESS.md).
