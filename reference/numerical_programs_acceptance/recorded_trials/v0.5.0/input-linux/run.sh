set -eu
mkdir /tmp/trial
trap 'if [ -d /tmp/trial/results ]; then cp -r /tmp/trial/results /out/probe-results; fi' EXIT
for arm in old new; do
 python -m venv /tmp/trial/env-$arm
 /tmp/trial/env-$arm/bin/python -m pip install --no-index --find-links /wheels --require-hashes -r /input/core-requirements.txt
 done
/tmp/trial/env-old/bin/python -m pip install --no-index --no-deps /input/eidos-0.4.12-py3-none-any.whl
/tmp/trial/env-new/bin/python -m pip install --no-index --no-deps /input/eidos-0.5.0-py3-none-any.whl
cd /tmp
/tmp/trial/env-new/bin/python -I /input/numerical.py --wheel /input/eidos-0.5.0-py3-none-any.whl --expected-version 0.5.0 > /out/numerical.json 2> /out/numerical.stderr
/tmp/trial/env-new/bin/python -I /input/shell.py --wheel /input/eidos-0.5.0-py3-none-any.whl --expected-version 0.5.0 --identity-driver /input/numerical.py --identity-sha256 11e515a4d17259f56d8effd0aca0c933965b01f683cd73ba9a6920f4a53297db > /out/shell.json 2> /out/shell.stderr
/tmp/trial/env-new/bin/python -I /input/lifecycle.py > /out/lifecycle.json 2> /out/lifecycle.stderr
/tmp/trial/env-new/bin/eidos-agent --help > /out/agent-help.txt
/tmp/trial/env-new/bin/eidos --help > /out/legacy-help.txt
/tmp/trial/env-new/bin/python -I /input/probe.py --workspace /tmp/trial --fixture /input/fixture.py.snapshot --old-wheel /input/eidos-0.4.12-py3-none-any.whl --new-wheel /input/eidos-0.5.0-py3-none-any.whl > /out/probe.stdout 2> /out/probe.stderr
