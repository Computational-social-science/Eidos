set -eu
mkdir /tmp/trial
trap 'if [ -d /tmp/trial/results ]; then cp -r /tmp/trial/results /out/results; fi' EXIT
for arm in old new; do
 python -m venv /tmp/trial/env-$arm
 /tmp/trial/env-$arm/bin/python -m pip install --no-index --find-links /wheels --require-hashes -r /input/core-requirements.txt
 done
/tmp/trial/env-old/bin/python -m pip install --no-index --no-deps /input/eidos-0.4.12-py3-none-any.whl
/tmp/trial/env-new/bin/python -m pip install --no-index --no-deps /input/eidos-0.5.0-py3-none-any.whl
/tmp/trial/env-new/bin/python /input/check.py --workspace /tmp/trial --fixture /input/fixture.py.snapshot --old-wheel /input/eidos-0.4.12-py3-none-any.whl --new-wheel /input/eidos-0.5.0-py3-none-any.whl
