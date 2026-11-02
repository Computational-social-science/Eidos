"""Conservative structural first derivative, isolated from the released SDK.

No candidate strings are evaluated or parsed by SymPy. CAS admission is not a
domain or floating-point accuracy certificate: retain independent validation.
"""
from __future__ import annotations

import json
import math

import numpy as np
import sympy as sp
from sympy.codegen.cfunctions import expm1, log1p

from framework.numerical_programs import MAX_NODES, ScalarProgram, parse_program

X = sp.Symbol('x', real=True)


class Refused(ValueError):
    """The adapter cannot establish or represent the requested derivative."""


def _ordinary(expression):
    # Proof-only rewrite. Never use this potentially unstable form for execution.
    return expression.replace(expm1, lambda x: sp.exp(x)-1).replace(
        log1p, lambda x: sp.log(1+x))


def _finite_real(value):
    return value.is_real is True and value.is_finite is True


def _number(value, dtype):
    with np.errstate(all='ignore'):
        represented = float(dtype(value))
    if not math.isfinite(represented):
        raise Refused('Constant is not finite in both supported dtypes')
    return sp.Rational(represented)


def _at_boundary(node, threshold, dtype):
    """Check the original selected path before CAS can cancel domain holes."""
    if 'input' in node:
        value = threshold
    elif 'const' in node:
        value = _number(node['const'], dtype)
    elif node['op'] == 'where':
        condition, left, right = node['args']
        if condition['op'] != 'le':
            raise Refused('Unsupported boundary predicate')
        a, b = [_at_boundary(child, threshold, dtype) for child in condition['args']]
        selected = sp.Le(a, b)
        if selected not in (sp.true, sp.false):
            raise Refused('Boundary predicate not proved')
        value = _at_boundary(left if selected == sp.true else right, threshold, dtype)
    else:
        values = [_at_boundary(child, threshold, dtype) for child in node['args']]
        op = node['op']
        functions = {'neg': lambda a: -a, 'add': lambda a, b: a+b,
                     'sub': lambda a, b: a-b, 'mul': lambda a, b: a*b,
                     'div': lambda a, b: a/b, 'exp': sp.exp,
                     'expm1': lambda a: sp.exp(a)-1,
                     'log': sp.log, 'log1p': lambda a: sp.log(1+a)}
        if op not in functions:
            raise Refused('Unsupported boundary operation')
        value = functions[op](*values)
    if not _finite_real(value):
        raise Refused('Original selected boundary intermediate is not finite and real')
    return value


def _has_input(node):
    return 'input' in node or any(_has_input(child) for child in node.get('args', []))


def _boundary(left, right, threshold):
    if threshold.free_symbols or not _finite_real(threshold):
        raise Refused('Threshold must be a finite real constant expression')
    left, right = _ordinary(left), _ordinary(right)
    values = [sp.limit(left, X, threshold, dir='-'),
              sp.limit(right, X, threshold, dir='+'), left.subs(X, threshold)]
    derivatives = [sp.limit(sp.diff(left, X), X, threshold, dir='-'),
                   sp.limit(sp.diff(right, X), X, threshold, dir='+')]
    if not all(_finite_real(value) for value in values+derivatives):
        raise Refused('Boundary values/derivatives are not proved finite and real')
    if any(sp.simplify(value-values[0]) != 0 for value in values[1:]):
        raise Refused('Boundary continuity not proved')
    if sp.simplify(derivatives[0]-derivatives[1]) != 0:
        raise Refused('Boundary differentiability not proved')


def _translate(node, dtype=np.float64):
    if 'input' in node:
        return X
    if 'const' in node:
        return _number(node['const'], dtype)
    op, args = node['op'], node['args']
    if op == 'where':
        condition, a, b = args
        if condition['op'] != 'le' or condition['args'][0] != {'input': 'x'}:
            raise Refused('Only x<=constant piecewise conditions are supported')
        if _has_input(condition['args'][1]):
            raise Refused('Variable threshold syntax is not supported')
        if set(condition['args'][1]) != {'const'}:
            raise Refused('Only literal thresholds are qualified; expression rounding can move a boundary')
        bound = _translate(condition['args'][1], dtype)
        _at_boundary(a, bound, dtype)
        left, right = _translate(a, dtype), _translate(b, dtype)
        _boundary(left, right, bound)
        return sp.Piecewise((left, sp.Le(X, bound)), (right, True), evaluate=False)
    values = [_translate(child, dtype) for child in args]
    functions = {'neg': lambda a: -a, 'add': lambda a, b: a+b,
                 'sub': lambda a, b: a-b, 'mul': lambda a, b: a*b,
                 'div': lambda a, b: a/b, 'exp': sp.exp, 'expm1': expm1,
                 'log': sp.log, 'log1p': log1p}
    if op not in functions:
        raise Refused('Unsupported structural operation')
    return functions[op](*values)


def _op(name, *args):
    return {'op': name, 'args': list(args)}


def _constant(value):
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError) as error:
        raise Refused('Unrepresentable symbolic constant') from error
    if not math.isfinite(number) or sp.Rational(number) != value:
        raise Refused('Constant is not exactly representable as binary64')
    return {'const': number}


def _lower(expression, budget=None):
    if budget is None:
        budget = [MAX_NODES]
    def emit(node):
        budget[0] -= 1
        if budget[0] < 0:
            raise Refused('Generated JSON exceeds the node budget')
        return node
    def lower(child):
        return _lower(child, budget)
    def op(name, *args):
        return emit(_op(name, *args))
    def fold(name, values):
        if len(values) == 1:
            return values[0]
        middle = len(values)//2
        return op(name, fold(name, values[:middle]), fold(name, values[middle:]))
    if expression == X:
        return emit({'input': 'x'})
    if isinstance(expression, sp.Rational):
        try:
            constant = _constant(expression)
        except Refused:
            return op('div', emit(_constant(expression.p)), emit(_constant(expression.q)))
        return emit(constant)
    if expression.func in (sp.Add, sp.Mul):
        return fold('add' if expression.func == sp.Add else 'mul',
                    [lower(a) for a in expression.args])
    if expression.func == sp.Pow:
        base, power = expression.args
        if not isinstance(power, sp.Integer) or abs(power) > MAX_NODES:
            raise Refused('Only bounded integer powers are supported')
        if power == 0:
            return emit({'const': 1.0})
        product = fold('mul', [lower(base) for _ in range(abs(int(power)))])
        return op('div', emit({'const': 1.0}), product) if power < 0 else product
    functions = {sp.exp: 'exp', expm1: 'expm1', sp.log: 'log', log1p: 'log1p'}
    if expression.func in functions and len(expression.args) == 1:
        return op(functions[expression.func], lower(expression.args[0]))
    if expression.func == sp.Piecewise and len(expression.args) == 2:
        (left, condition), (right, fallback) = expression.args
        if (fallback != sp.true or condition.func != sp.LessThan
                or condition.lhs != X or condition.rhs.free_symbols):
            raise Refused('Unsupported derived piecewise condition')
        return op('where', op('le', emit({'input': 'x'}), lower(condition.rhs)),
                  lower(left), lower(right))
    raise Refused('Unsupported symbolic output: ' + expression.func.__name__)


def derive(program: ScalarProgram) -> ScalarProgram:
    """Differentiate only the validated loss; keep its original execution JSON.

    Run in an owned worker with a wall deadline: finite input syntax alone does
    not bound symbolic limit/simplification cost. This is not a hostile OS sandbox.
    """
    if type(program) is not ScalarProgram:
        raise TypeError('A validated SDK ScalarProgram is required')
    original = program.to_dict()
    try:
        # Admission must hold at the effective literal threshold in both dtypes.
        # This is still not a proof of all finite-precision program behavior.
        _translate(original['loss'], np.float32)
        derivative = sp.diff(_translate(original['loss']), X)
        # Bound the symbolic output before potentially expanding integer powers.
        if sum(1 for _ in sp.preorder_traversal(derivative)) > MAX_NODES:
            raise Refused('Symbolic derivative exceeds the node budget')
        result = {'loss': original['loss'], 'gradient': _lower(derivative)}
        return parse_program(json.dumps(result, allow_nan=False))
    except Refused:
        raise
    except (ValueError, TypeError, ArithmeticError, NotImplementedError, RecursionError) as error:
        raise Refused('Unproved or unrepresentable derivative: ' + str(error)) from error
