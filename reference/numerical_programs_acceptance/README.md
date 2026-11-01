# Installed numerical program acceptance

The standalone checker imports `framework.numerical_programs` from a non-editable
virtual environment. It does not import the source checkout, a catalog, a model
or an API provider. NumPy and the normal complete Eidos core dependency closure
must be installed. No GPU, paid service or credentials are required.

From a checkout, create a new environment and install the candidate wheel. On
Windows:

```powershell
python -m venv .venv-numerical
.venv-numerical/Scripts/python.exe -m pip install reference/sdk_process_acceptance/eidos-0.4.11-py3-none-any.whl
.venv-numerical/Scripts/python.exe -m pip check
.venv-numerical/Scripts/python.exe -I reference/numerical_programs_acceptance/check.py --wheel reference/sdk_process_acceptance/eidos-0.4.11-py3-none-any.whl --expected-version 0.4.11
```

On Linux/macOS, use `.venv-numerical/bin/python` for the three interpreter
commands after environment creation. The shipped measurement covers native
Windows and same-host offline Linux; macOS remains unqualified until actually run.
Public installation may download packages. This is separate from the recorded
network-disabled Linux execution.

The normal installation above may resolve newer compatible dependencies. To
recreate the measured core closure, download the platform wheels with
`pip download --require-hashes -r recorded_trials/v0.4.11/bootstrap/core-requirements.txt`.
Install that complete closure with `pip install --no-index --find-links WHEELHOUSE
--require-hashes -r REQUIREMENTS`, then install the Eidos wheel normally with
`--no-index --find-links WHEELHOUSE`, and require `pip check`. Do not qualify a
`--no-deps` installation with unmet package metadata. Record the actual environment.

The checker validates full wheel/installed bytes and RECORD, dependency origins
and metadata, driver stability, exact typed outputs, 23 log1mexp points and 16
softplus points against converged Decimal references. It also rejects a finite
wrong gradient and exercises 12 parser/execution refusals, independent buffers,
signed zero and explicitly uncertified finite underflow. `-O`/`-OO` is refused.
It emits a PASS JSON document only after every check; an error emits no PASS.

[Raw trials](recorded_trials/v0.4.11/README.md), their manifest and the
[assembled receipt](../../docs/NUMERICAL-PROGRAMS-ACCEPTANCE.json) preserve actual
outcomes and failed controller attempts. The Linux primary API run uses the
public Python image by digest; a separate cached-image run adds controlled Quarto
delivery requiring Poppler. Windows additionally qualifies actual Quarto/TeX.
These operating-system controls do not establish independent-machine acceptance,
novel scientific tasks, whole-domain accuracy, automatic differentiation or RSI.
