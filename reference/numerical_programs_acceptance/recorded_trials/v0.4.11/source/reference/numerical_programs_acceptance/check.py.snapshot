"""Installed, isolated CPU qualification; no model, checkout import or network."""
from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from email.parser import BytesParser
import hashlib
from importlib.metadata import distribution, distributions
import io
import json
from pathlib import Path
import sys
import time
import zipfile

import numpy as np
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

import framework.numerical_programs as api


LOSS = 'where(x <= log(2), log(-expm1(-x)), log1p(-exp(-x)))'
GRADIENT = 'exp(-x)/(-expm1(-x))'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def identity(wheel, expected_version):
    """Bind actual installed bytes, metadata, RECORD and all framework modules."""
    dist = distribution('eidos')
    prefix = Path(sys.prefix).resolve()
    module = Path(api.__file__).resolve()
    require(sys.flags.isolated == 1 and sys.flags.no_site == 0,
            'Run with -I and ordinary site initialization')
    require(sys.prefix != sys.base_prefix and module.is_relative_to(prefix),
            'A non-editable virtual environment is required')
    require(dist.version == expected_version, 'Installed version differs')
    body = wheel.read_bytes()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate wheel members')
        info = 'eidos-' + expected_version + '.dist-info/'
        metadata = BytesParser().parsebytes(archive.read(info + 'METADATA'))
        require(metadata['Name'] == 'eidos' and metadata['Version'] == expected_version,
                'Wheel METADATA identity differs')
        rows = list(csv.reader(io.StringIO(archive.read(info + 'RECORD').decode())))
        require(len(rows) == len(names) and set(names) == {row[0] for row in rows},
                'RECORD inventory differs')
        for name, encoded, size in rows:
            require(not Path(name).is_absolute() and '..' not in Path(name).parts
                    and '\\' not in name and '.data/' not in name, 'Unsupported wheel path')
            content = archive.read(name)
            if name == info + 'RECORD':
                require(encoded == size == '', 'RECORD self-entry differs')
                continue
            expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip('=')
            require(encoded == expected and size == str(len(content)), 'Wheel RECORD hash differs')
            installed = Path(dist.locate_file(name)).resolve()
            require(installed.is_relative_to(prefix) and installed.read_bytes() == content,
                    'Installed wheel member differs: ' + name)
        expected = {name: digest(archive.read(name)) for name in names
                    if name.startswith('framework/') and name.endswith('.py')}
        expected_lf = {name: digest(archive.read(name).decode('utf-8-sig').replace('\r\n', '\n').encode())
                       for name in expected}
    framework = module.parents[1]
    actual = {'framework/' + path.relative_to(framework).as_posix(): digest(path.read_bytes())
              for path in framework.rglob('*.py')}
    require(actual == expected and 'framework/numerical_programs/__init__.py' in actual,
            'Full framework inventory differs')
    installed_record = {p.as_posix(): p for p in dist.files or []}
    for name, sha in expected.items():
        entry = installed_record[name]
        require(entry.hash is not None and entry.hash.mode == 'sha256'
                and base64.urlsafe_b64encode(bytes.fromhex(sha)).decode().rstrip('=') == entry.hash.value,
                'Installed RECORD differs: ' + name)
    installed_distributions = list(distributions())
    packages = {canonicalize_name(d.metadata['Name']): d for d in installed_distributions}
    require(len(packages) == len(installed_distributions), 'Duplicate installed distributions')
    require(all(Path(d.locate_file('')).resolve().is_relative_to(prefix) for d in packages.values()),
            'Host distributions leaked into the virtual environment')
    require(Path(np.__file__).resolve().is_relative_to(prefix), 'NumPy imported outside the virtual environment')
    for package in packages.values():
        for raw in package.requires or []:
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate({'extra': ''}):
                target = packages.get(canonicalize_name(req.name))
                require(target is not None and req.specifier.contains(target.version, prereleases=True),
                        'Unmet installed dependency: ' + raw)
    dependency_metadata = {}
    for name, package in packages.items():
        files = {}
        for filename in ('METADATA', 'RECORD'):
            text = package.read_text(filename)
            require(text is not None, 'Installed distribution lacks ' + filename + ': ' + name)
            files[filename] = digest(text.replace('\r\n', '\n').encode())
        dependency_metadata[name] = files
    return {'sdk_version': dist.version, 'wheel_sha256': digest(body),
            'wheel_name': wheel.name, 'installed_module': str(module), 'prefix': str(prefix),
            'source_sha256_raw': actual, 'source_sha256_canonical_lf': expected_lf,
            'module_count': len(actual),
            'dependencies': sorted((name, d.version) for name, d in packages.items()),
            'dependency_metadata_sha256_lf': dependency_metadata,
            'all_installed_metadata_requirements_met': True}


def references(x, method, precisions):
    outputs = []
    for precision in precisions:
        with localcontext() as context:
            context.prec = precision
            exact = Decimal.from_float(float(x))
            if method == 'log1mexp':
                exponential = (-exact).exp()
                outputs.append(((1 - exponential).ln(), exponential / (1 - exponential)))
            else:
                exponential = exact.exp()
                outputs.append(((1 + exponential).ln(), exponential / (1 + exponential)))
    with localcontext() as context:
        context.prec = 120
        require(all(abs(a / b - 1) < Decimal('1e-90') for a, b in zip(*outputs)),
                'Independent Decimal reference did not converge')
    return outputs[1]


def comparison(program, x, method, precisions):
    actual = program.evaluate(x)
    require(type(actual) is tuple and len(actual) == 2, 'Exactly two output arrays are required')
    require(all(type(a) is np.ndarray and a.shape == () and a.dtype == x.dtype
                and np.isfinite(a) for a in actual), 'Shape/dtype/finite result differs')
    expected = references(x, method, precisions)
    with localcontext() as context:
        context.prec = 120
        errors = [abs(Decimal.from_float(float(a)) / b - 1) for a, b in zip(actual, expected)]
    tolerance = Decimal('2e-5' if x.dtype == np.dtype('float32') else '2e-12')
    return {'method': method, 'dtype': x.dtype.name, 'represented_input': float(x),
            'output_hex': [float(a).hex() for a in actual],
            'relative_errors': [str(e) for e in errors],
            'passed': all(e <= tolerance for e in errors)}


def controls():
    program = api.compile_formulas(LOSS, GRADIENT)
    program = api.parse_program(program.to_json().encode())
    points = []
    for dtype, small, tail in (
        (np.float32, [1e-30, 1e-12, 1e-8, 1e-5, .1], [1, 20, 50, 80]),
        (np.float64, [1e-100, 1e-16, 1e-12, 1e-8, .1], [1, 20, 50, 80, 600]),
    ):
        cutoff = np.log(np.asarray(2, dtype=dtype))
        values = [*small, np.nextafter(cutoff, dtype(-np.inf)),
                  np.nextafter(cutoff, dtype(np.inf)), *tail]
        points.extend(comparison(program, np.asarray(x, dtype=dtype), 'log1mexp', (420, 520)) for x in values)
    require(len(points) == 23 and all(p['passed'] for p in points), 'Log1mexp control failed')
    wrong = api.compile_formulas(LOSS, '0')
    wrong_point = comparison(wrong, np.asarray(1e-12, dtype=np.float64), 'log1mexp', (420, 520))
    require(wrong_point['passed'] is False, 'Independent oracle accepted a finite wrong gradient')
    softplus = api.compile_formulas('where(x<=0,log1p(exp(x)),x+log1p(exp(-x)))',
                                    'where(x<=0,exp(x)/(1+exp(x)),1/(1+exp(-x)))')
    extra = [comparison(softplus, np.asarray(x, dtype=dtype), 'softplus', (160, 220))
             for dtype in (np.float32, np.float64) for x in (-80, -20, -.1, 0, .1, 20, 80, 100)]
    require(all(p['passed'] for p in extra), 'Softplus control failed')
    names = []

    def refused(label, function, exception):
        try:
            function()
        except exception:
            names.append({'case': label, 'accepted': True})
        else:
            raise RuntimeError('Missing expected refusal: ' + label)

    refused('candidate Python import', lambda: api.compile_formulas('__import__("os")', '1'), ValueError)
    refused('invalid unused branch syntax', lambda: api.compile_formulas('where(x<=0,x,x.real)', '1'), ValueError)
    refused('duplicate JSON', lambda: api.parse_program('{"loss":{},"loss":{},"gradient":{}}'), ValueError)
    refused('inexact binary64 integer', lambda: api.compile_formulas('9007199254740993', '1'), ValueError)
    refused('source byte budget', lambda: api.compile_formulas('x' * 2049, '1'), ValueError)
    refused('JSON nesting budget', lambda: api.parse_program('[' * 65 + '0' + ']' * 65), ValueError)
    refused('ordinary constructor', api.ScalarProgram, TypeError)
    refused('nonfinite predicate intermediate',
            lambda: api.compile_formulas('where(log(-x)<=0,1,2)', '1').evaluate(np.float64(1)), FloatingPointError)
    refused('Python float input', lambda: program.evaluate(1.), TypeError)
    refused('masked input', lambda: program.evaluate(np.ma.asarray(1.)), TypeError)
    refused('vector input', lambda: program.evaluate(np.asarray([1.])), ValueError)
    refused('nonfinite input', lambda: program.evaluate(np.float64(np.inf)), ValueError)
    x = np.asarray(-0., dtype=np.float32)
    copied = api.compile_formulas('x', 'x')
    a, b = copied.evaluate(x)
    require(np.signbit(a) and np.signbit(b) and not any(
        np.shares_memory(u, v) for u, v in ((x, a), (x, b), (a, b))), 'Buffer/signed-zero contract failed')
    a[...] = 12
    require(np.signbit(x) and np.signbit(b), 'Output mutation escaped its buffer')
    data = copied.to_dict()
    data['loss'] = {'const': 99}
    require(copied.evaluate(np.float64(-2))[0] == -2, 'Mutable JSON changed the program')
    underflow = api.compile_formulas('exp(-1000)', '0').evaluate(np.float64(1))
    require(all(v == 0 for v in underflow), 'Documented finite underflow behavior differs')
    return {'log1mexp': points, 'softplus': extra, 'wrong_gradient': wrong_point,
            'refusals': names, 'buffer_signed_zero_and_serialization': 'PASS',
            'finite_underflow_is_not_certification': 'PASS'}


def main():
    if sys.flags.optimize:
        raise SystemExit('Qualification requires active checks; omit -O/-OO.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--expected-version', required=True)
    args = parser.parse_args()
    started = time.monotonic()
    driver = Path(__file__).resolve()
    driver_before = driver.read_bytes()
    before = identity(args.wheel, args.expected_version)
    results = controls()
    require(before == identity(args.wheel, args.expected_version), 'Installed source/dependencies changed')
    require(driver.read_bytes() == driver_before, 'Qualification driver changed during execution')
    record = {'schema': 1, 'kind': 'eidos.numerical-programs-installed-acceptance',
              'status': 'PASS', 'generated': datetime.now(timezone.utc).isoformat(),
              'platform': sys.platform, 'python': sys.version, 'executable': sys.executable,
              'optimization_level': sys.flags.optimize,
              'driver_sha256_lf': digest(driver_before.decode('utf-8-sig').replace('\r\n', '\n').encode()),
              **before, 'controls': results, 'elapsed_seconds': time.monotonic() - started,
              'limits': ['Same-host CPU scalar controls; no new-machine, GPU, vector, AD or whole-domain guarantee.',
                         'Known external methods and supplied derivatives; no model, discovery or RSI qualification.',
                         'No network operation; public artifact bootstrap is separate from offline execution.']}
    print(json.dumps(record, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
