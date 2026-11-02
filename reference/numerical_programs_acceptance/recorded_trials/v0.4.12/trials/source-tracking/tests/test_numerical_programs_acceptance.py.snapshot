"""Broken-result and provenance controls for the installed qualification driver."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import numpy as np
import pytest


DRIVER = Path(__file__).resolve().parents[1] / 'reference/numerical_programs_acceptance/check.py'


@pytest.mark.parametrize('outputs', [(), (np.asarray(1.),),
    (np.asarray(1.), np.asarray(1.), np.asarray(1.)),
    (np.float64(1), np.asarray(1.)), (np.asarray(1.), np.float64(1)),
    [np.asarray(1.), np.asarray(1.)]])
def test_incomplete_extra_or_scalar_results_cannot_be_qualified(outputs):
    ns = runpy.run_path(str(DRIVER))
    with pytest.raises(RuntimeError):
        ns['comparison'](SimpleNamespace(evaluate=lambda x: outputs),
                         np.asarray(1.), 'log1mexp', (420, 520))


@pytest.mark.parametrize('mutation', ['driver', 'dependency-metadata'])
def test_execution_cannot_be_attributed_to_changed_inputs(tmp_path, monkeypatch, mutation):
    driver = tmp_path / 'check.py'
    driver.write_bytes(DRIVER.read_bytes())
    ns = runpy.run_path(str(driver))
    scope = ns['main'].__globals__
    state = {'dependency_metadata_sha256_lf': 'original'}

    def controls():
        if mutation == 'driver':
            driver.write_bytes(driver.read_bytes() + b'\n# replaced during qualification\n')
        else:
            state['dependency_metadata_sha256_lf'] = 'replacement'
        return {}

    monkeypatch.setitem(scope, 'identity', lambda *args: dict(state))
    monkeypatch.setitem(scope, 'controls', controls)
    monkeypatch.setattr(sys, 'argv', ['check.py', '--wheel', str(tmp_path/'candidate.whl'),
                                     '--expected-version', '0.4.11'])
    with pytest.raises(RuntimeError, match='changed'):
        ns['main']()
