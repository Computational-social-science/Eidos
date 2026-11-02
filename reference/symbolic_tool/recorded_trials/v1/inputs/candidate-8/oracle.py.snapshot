"""Independent Decimal definitions, convergence and explicit relative errors."""
from decimal import Decimal, localcontext

import numpy as np


def inputs():
    rows = []
    for dtype, small, tail in (
        (np.float32, [1e-30, 1e-12, 1e-8, 1e-5, .1], [1, 20, 50, 80]),
        (np.float64, [1e-100, 1e-16, 1e-12, 1e-8, .1], [1, 20, 50, 80, 600]),
    ):
        cutoff = np.log(np.asarray(2, dtype=dtype))
        values = [*small, np.nextafter(cutoff, dtype(-np.inf)),
                  np.nextafter(cutoff, dtype(np.inf)), *tail]
        rows.extend(np.asarray(x, dtype=dtype) for x in values)
    return rows


def reference(value, method, precision):
    with localcontext() as context:
        context.prec = precision
        x = Decimal.from_float(float(value))
        if method == 'log1mexp':
            e = (-x).exp()
            return (1-e).ln(), e/(1-e)
        if method == 'softplus':
            e = x.exp()
            return (1+e).ln(), e/(1+e)
        if method == 'square':
            return x*x, 2*x
        raise ValueError('Unknown independent reference')


def assess(program, value, method):
    precisions = (420, 520) if method == 'log1mexp' else (160, 220)
    low, high = [reference(value, method, precision) for precision in precisions]
    with localcontext() as context:
        context.prec = 120
        convergence = [abs(a/b-1) if b else abs(a) for a, b in zip(low, high)]
        if not all(e < Decimal('1e-90') for e in convergence):
            raise ArithmeticError('Independent reference failed convergence')
    row = {'method': method, 'dtype': value.dtype.name,
           'input_hex': float(value).hex(), 'precisions': precisions,
           'reference': [str(v) for v in high],
           'convergence_errors': [str(v) for v in convergence]}
    try:
        outputs = program.evaluate(value)
        if (type(outputs) is not tuple or len(outputs) != 2
                or any(type(v) is not np.ndarray or v.shape != ()
                       or v.dtype != value.dtype or not np.isfinite(v) for v in outputs)):
            raise ValueError('Output type/shape/dtype/finite mismatch')
        tolerance = Decimal('2e-5' if value.dtype == np.dtype('float32') else '2e-12')
        with localcontext() as context:
            context.prec = 120
            errors = [abs(Decimal.from_float(float(a))/b-1) if b
                      else abs(Decimal.from_float(float(a))) for a, b in zip(outputs, high)]
        accepted = [e <= tolerance if b else e == 0 for e, b in zip(errors, high)]
        row.update(output_hex=[float(a).hex() for a in outputs],
                   relative_errors=[str(e) if b else None for e, b in zip(errors, high)],
                   zero_errors=[str(e) if not b else None for e, b in zip(errors, high)],
                   loss_passed=accepted[0], gradient_passed=accepted[1], passed=all(accepted))
    except (FloatingPointError, ValueError, TypeError) as error:
        row.update(loss_passed=False, gradient_passed=False, passed=False,
                   execution_error=type(error).__name__ + ': ' + str(error))
    return row
