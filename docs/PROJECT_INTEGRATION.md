# Project integration

A working repository is registered in EIDOS rather than moved into it. The project
owns its source, data, scientific acceptance, tests and manuscript; EIDOS owns
command discovery, invocation, declared-output checks and bound observations.
Isolated copies may be used for failure injection without changing the original.

## Register an existing project

Create `projects/my_study/project.yaml`:

```yaml
name: my_study
root: ../../../my_study
gate_command: ["{python}", "validate.py"]
test_command: ["{python}", "-m", "pytest", "-q"]
render_command: ["{python}", "render.py"]
expects: [docs/evidence.json]
reports: [docs/report.html, docs/report.pdf, docs/report.docx]
validity_register: analysis/CLAIMS.yaml
validity_document: docs/REPORT.md
expected_gate_s: PASS
validity_inputs: [validate_helpers.py, configs/study.json, data/manifest.json]
```

`root` is relative to the registration file or absolute. Commands are argument
lists, never shell strings. `{python}` and generic Python executable names use the
interpreter running EIDOS; select the project's environment before invoking it.
Optional commands raise a configuration error when absent. Missing checkouts are
shown as MISSING by `list` and cannot be executed.

```sh
python -m framework.project list
python -m framework.project exec my_study test
python -m framework.project check my_study
python -m framework.project exec my_study render
python tools/audit_validity.py --project my_study
```

The project defines what its gate actually checks. Exit 0 maps to PASS, exit 1 to
FAIL and other exits to ERROR, except missing tools (SKIP) and explicitly declared
nonzero research states. `exit_statuses` cannot convert a nonzero exit into PASS.
`expected_gate_s: FAIL` declares a deliberate negative control; a matching failure
means that control behaved as expected, not that its scientific claim succeeded.

`expects` lists files that a successful **gate** must leave behind. Exit 0 with a
missing required file is FAIL. This does not by itself prove that an existing file
is fresh or scientifically correct: the project validator must check its content
and provenance. Test and render commands do not inherit the gate's output
requirements. `reports` is a list of reader-facing paths, not an implicit proof
that every format was rendered successfully.

## Bind cached scientific verdicts

Snapshots bind the registration, framework Python sources, Gate S file handles,
the directly executed Python gate script and explicit `validity_inputs`.
Recognized Python interpreter options are accounted for; unknown options make the
snapshot unobservable instead of guessing a script. Python module mode (`-m`)
requires explicit input files. Code passed with `-c` is bound by the command
itself; any modules it imports still need explicit inputs.

Declare imported validator helpers, configuration, data manifests and any other
files needed to invalidate an old verdict in `validity_inputs`. This is an exact
file list, not a recursive import/dependency resolver. Large declared inputs are
hashed by streaming. Declaring only a manifest binds that manifest, not every
underlying dataset or model: the project validator must verify those identities.

Outside-project inputs additionally require exact permission:

```yaml
validity_inputs: [../shared/data-manifest.json]
validity_external_inputs: [../shared/data-manifest.json]
```

Permission alone does not declare an input. Referencing a permitted file through
`validity_inputs` or a Gate S handle binds its contents. Changes withdraw the old
cached verdict and queue a Gate S recheck; that recheck does not rerun experiments,
regenerate missing research data or establish scientific truth. Formal toolchain
snapshot binding remains unqualified. See [the completeness ledger](FUNCTIONAL_COMPLETENESS.md).

## Scaffold and rehearse

```sh
python tools/bootstrap_project.py --name my_study --dest ../my_study
```

The bootstrap refuses a nonempty destination or existing registration. Its LLM
measurement template requires the configured local decision service; a fresh
clone without that service has not passed this measurement. A non-LLM project
should register its own producer and validator; `reference/demo_quantitative`
provides a separate bounded quantitative example.

`tools/release_gate.py` rehearses the template before a release is recorded.
Each invocation owns a unique workspace. The missing-output negative control uses
its own local spec without global registration. Existing projects and status
directories are never deleted to make room for a rehearsal. Cleanup checks the
owned directory's device/file identity and resolved path; a replacement is retained
and reported as an error. `--keep` prints the unique workspace it preserves.
Subprocess timeouts own the entire worker tree and use hidden Windows execution.
A failed scaffold is not executed, and a failed coverage producer cannot reuse a
cached passing count. A successful rehearsal remains a template test.

## Independent local intake evidence

On 2026-11-01, the existing HPAF Unicode forensic engine was exercised with its two
local corpora in an isolated QA workspace: 513 and 520 records, 1,033 total.
Normal inputs generated all three expected HTML files. Invalid JSON made the
original engine exit 0 without reports; the EIDOS output contract correctly
returned FAIL. An exploratory count claim passed Gate S, an incorrect count was
rejected by S3, and validator-source or explicitly declared corpus changes withdrew
the old bound verdict. An initial overstatement of exploratory work as supported
was rejected by S4; the claim strength was corrected without inventing preregistration.

[The intake record](INDEPENDENT-INTAKE-ACCEPTANCE.json) preserves identities and
negative outcomes. Original code/data were unchanged. Raw corpora and the original
HTML reports remain private to the host and are not distributed by EIDOS.
This is independent intake and invalidation evidence, **not** complete scientific
lifecycle acceptance, scientific novelty, new-machine installation or publication
qualification. Reproducible generic delivery and journal-format review for this
independent project remain open. The public regression suite uses its own isolated
fixtures and does not depend on those private corpora.

## Historical adopters and remaining acceptance

The earlier keystroke-observatory gate/render measurements and migration decision
are historical adopter evidence. Current registrations are discovered from
`projects/*/project.yaml`; neither a historical single-member count nor a template
rehearsal describes the current consumer set. A second project's complete lifecycle
must still execute its research, reject bad evidence, deliver independently usable
results and demonstrate change detection. See [functional completeness](FUNCTIONAL_COMPLETENESS.md).

## Applying this host's runtime update

The source fixes do not replace already running interpreter instances. On this
host, the monitor and two old chain loops still use the earlier global Python;
the configured launcher already selects project Python 3.12. Their controlled
restart was rejected by automatic approval and was not retried through another
termination path. [The migration record](MONITOR-RUNTIME-MIGRATION-2026-11-01.json)
therefore remains PENDING. New starts enforce loop/tick ownership, but old
processes are not retroactively covered. A live web response is not proof that
the current source is running. Historical soak failures and restart events remain
part of the acceptance record.
