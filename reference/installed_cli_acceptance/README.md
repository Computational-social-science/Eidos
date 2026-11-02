# Installed CLI acceptance (unreleased 0.5.0)

This is a development qualification profile, not a published 0.5.0 release.
The stable release remains 0.4.12. The candidate adds model-free project-local
`init/check/status/report/feedback` operations on the existing SDK.

The [frozen prototype record](recorded_trials/prototype-3/acceptance.json) and
[raw manifest](recorded_trials/prototype-3/manifest.json) preserve 26 actual
console cases on each of native Windows and same-host offline Linux. The Linux
worker uses a pinned cached public Python image, hash-locked dependencies,
read-only inputs, no network and verified cleanup of its uniquely owned container.
This does not establish independent-machine portability.

The exact candidate wheel SHA-256 is:

```text
0d8ca60088be1366f90889ddba686e32c28b15d458a7a5033470a26d683d78cf
```

## Replay outside the source checkout

Use a dedicated normal, noneditable environment. Core dependencies are listed
with hashes in `recorded_trials/prototype-3/input/core-requirements.txt`.
Installing them may use a public package download; the recorded Linux execution
is a separate network-disabled measurement. No model, GPU, paid API or credential
is required. Do not infer that an unrelated public-index package name is EIDOS.

For example, with actual absolute paths substituted:

```sh
python -m venv /tmp/eidos-cli
/tmp/eidos-cli/bin/python -m pip install --require-hashes -r /checkout/reference/installed_cli_acceptance/recorded_trials/prototype-3/input/core-requirements.txt
/tmp/eidos-cli/bin/python -m pip install --no-deps /checkout/reference/installed_cli_acceptance/recorded_trials/prototype-3/input/eidos-0.5.0-py3-none-any.whl
/tmp/eidos-cli/bin/python -m pip check
cd /tmp
/tmp/eidos-cli/bin/python -I /checkout/reference/installed_cli_acceptance/check.py --fixture /checkout/reference/installed_cli_acceptance/fixture --out /tmp/cli-results --expected-version 0.5.0 --wheel /checkout/reference/installed_cli_acceptance/recorded_trials/prototype-3/input/eidos-0.5.0-py3-none-any.whl --identity-driver /checkout/reference/numerical_programs_acceptance/check.py
```

On Windows use the dedicated environment's `Scripts/python.exe` and real Windows
paths. The output directory must not already exist. An editable environment or
optimized (`-O`/`-OO`) driver invocation is refused. Public dependencies remain
separate prerequisites; this profile is not an installer for Quarto/TeX or models.

## What is checked

The driver invokes the installed console through the qualified SDK Job/group
boundary. It checks placeholder refusal, explicit execution-only status,
missing-output rejection, a synthetic Gate S positive/negative pair, module and
configuration invalidation, undeclared-module refusal, failed-run preservation,
metadata-only local feedback, overwrite refusal and missing-manuscript refusal.
It binds driver/fixture bytes, the candidate wheel, the independent numerical
identity driver and complete installed SDK identity before and after all cases.
Raw identity logs include the unchanged 23 log1mexp and 16 softplus controls.

The fixture contains deliberately constructed evidence and preregistration
fields to exercise Gate S. These are synthetic test inputs, not a historical
research registration or empirical scientific result. Passing them does not
establish novelty, scientific truth, complete research lifecycle, monitor
enrollment, a generic Agent or RSI.

The archive retains rejected/intermediate harnesses and their raw PASS documents.
Those documents are withdrawn qualification candidates, not current acceptance.
An editable-environment probe exposed one false acceptance. An independent
installed-source mutation after the last console case makes the v4 driver accept
outdated provenance; v5 rejects it at final whole-wheel identity. Two separately
created prefixes preserve that comparison without changing the qualified positive
environments. The v3 namespace-origin setup error is also retained.

Framework self-audit and installed profile have separate bindings. The archived
self-audit covers framework/tools/tests and measured 1,237 passes, six skips,
76% framework coverage, ten passing chains and one skip. This reference driver
and raw measurements are bound separately by the manifest, not by that source
audit's Python-file inventory. Three-format CLI delivery, central worker
enrollment, full incident-to-release-to-originating-project replay and scientific
RSI remain distinct acceptance work.
