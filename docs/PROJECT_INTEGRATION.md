# Project integration

**Decision:** a working repository is **registered**, never copied into this tree.
Registered consumers are lightweight and sealed: `operator_calibration` (100 forward passes
against the local operator, must pass) and `null_study` (a false claim on the same evidence,
must be rejected). An external project is
registered only once it is validated enough to serve as evidence.

Why the move was rejected is documented where it was decided —
`keystroke-observatory/MIGRATION.md` §7.3 (bare-module imports, a gate that
hard-codes `docs/`, artefacts that double as the manuscript's data source). It is
not repeated here; this file owns only the integration contract.

---

## The contract

One YAML file per project, `projects/<name>/project.yaml`:

```yaml
name: keystroke_observatory
root: ../../../keystroke-observatory        # relative to this file, or absolute
gate_command:   ["{python}", "scripts/check_handoff.py"]
test_command:   ["{python}", "-m", "pytest", "tests/", "-q"]
render_command: ["{python}", "main.py", "render"]
reports: [docs/MANUSCRIPT.html, outputs/rendered/index.pdf]
```

* `{python}` is replaced with the interpreter running the framework — a bare
  `python` can be a different install without the project's dependencies.
* `gate_command` is required. `test_command` and `render_command` are optional and
  raise when invoked while absent.
* Exit codes are mapped coarsely: **0 PASS, 1 FAIL, anything else ERROR**. The
  framework does not re-read the project's findings; that would be a second
  implementation of its gate contract.
* A missing `root` raises on `check` / `exec`. `list` marks it `[MISSING]`
  instead, so a fresh clone can enumerate what it lacks without failing.
* **No state is written into the YAML.** A recorded verdict goes stale and then
  contradicts the project; the status lives in the project's own artefacts.

```bash
python -m framework.project list
python -m framework.project check operator_calibration
python -m framework.project exec  operator_calibration gate
```

---

## Ownership

| Concern | Owner |
|---|---|
| Gate vocabulary, findings, gate implementations | **project** |
| Tests, manuscript pipeline, artefact-to-sentence binding | **project** |
| Discovery, invocation, exit-code mapping | **framework** |
| Generic gates, diagnosis, tracking, Quarto bridge, inference | **framework**, unused by this project and not required by it |

The two gate layers coexist deliberately. The project's contract (five statuses,
structured findings, validation rules) is stricter than the framework's boolean
skeleton, but upstreaming it on the evidence of **one** project would be extracting
a general core from a single case. A second project that needs the same vocabulary
is the condition for upstreaming, with a conformance test against this one.

---

## Verified

| Check | Result |
|---|---|
| `check keystroke_observatory` | PASS, exit 0, 15.2 s — `PASS 15  FAIL 0  UNVERIFIED 0`, `GATE: OPEN` |
| `exec keystroke_observatory render` | PASS, exit 0, 37.6 s — HTML, DOCX, Typst PDF |
| Project source untouched | `docs/*` mtimes predate the run; only `outputs/rendered/` was written |
| Framework suite | all tests pass, including missing-root, shell-string, undeclared-command, crash→ERROR, and a guard that the registry imports no heavy dependency |

---

## Limits

1. A fresh clone of Eidos does not carry the projects; `list` shows them
   `[MISSING]` until the sibling checkouts exist.
2. Framework tests and project tests are separate suites; use `exec ... test`.
3. The registry has one member, so generalisation is unproven until a second
   project registers without a code change.
