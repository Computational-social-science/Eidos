"""Immutable validated scalar programs and finite typed NumPy execution.

Promoted from the project's historical scalar interpreter; the reference copy
retains its original positive-domain/diagnostic behavior for archived trials.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math

import numpy as np

from ._json import decode

MAX_DEPTH = 16
MAX_NODES = 256
_ARITIES = {'neg': 1, 'exp': 1, 'expm1': 1, 'log': 1, 'log1p': 1,
            'add': 2, 'sub': 2, 'mul': 2, 'div': 2, 'le': 2, 'where': 3}
_OPERATIONS = {'neg': np.negative, 'exp': np.exp, 'expm1': np.expm1,
               'log': np.log, 'log1p': np.log1p, 'add': np.add,
               'sub': np.subtract, 'mul': np.multiply, 'div': np.divide,
               'le': np.less_equal}


@dataclass(frozen=True, slots=True)
class _Node:
    operation: str
    arguments: tuple[_Node, ...] = ()
    constant: float = 0.0


@dataclass(frozen=True, slots=True, init=False)
class ScalarProgram:
    """Validated immutable value created by compile_formulas/parse_program.

    A supplied gradient is another expression, not an automatically derived or
    verified derivative. Python value immutability is not an OS security boundary.
    """
    _loss: _Node
    _gradient: _Node

    def __init__(self):
        raise TypeError('Use compile_formulas() or parse_program()')

    def to_dict(self) -> dict:
        """Return independent JSON data; constants are normalized binary64 values."""
        def node(value):
            if value.operation == 'input':
                return {'input': 'x'}
            if value.operation == 'const':
                return {'const': value.constant}
            return {'op': value.operation, 'args': [node(child) for child in value.arguments]}
        return {'loss': node(self._loss), 'gradient': node(self._gradient)}

    def to_json(self) -> str:
        """Serialize the closed loss/gradient-node schema, without Python code."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False)

    def evaluate(self, value: np.ndarray | np.float32 | np.float64) -> tuple[np.ndarray, np.ndarray]:
        return execute(self, value)


def parse_program(payload: str | bytes) -> ScalarProgram:
    """Validate every node, including unselected branches, before construction."""
    source = decode(payload)
    if not isinstance(source, dict) or set(source) != {'loss', 'gradient'}:
        raise ValueError('Program requires exactly loss and gradient')
    count = 0

    def node(value, depth=1):
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('Program exceeds its combined node/depth budget')
        if not isinstance(value, dict):
            raise ValueError('Each expression must be a node object')
        if set(value) == {'input'} and value['input'] == 'x':
            return _Node('input'), 'number'
        if set(value) == {'const'}:
            original = value['const']
            if type(original) not in (int, float):
                raise ValueError('Constants must be finite numbers, excluding booleans')
            try:
                constant = float(original)
            except OverflowError as error:
                raise ValueError('Constant exceeds binary64 range') from error
            if not math.isfinite(constant):
                raise ValueError('Constant must be finite')
            if type(original) is int and int(constant) != original:
                raise ValueError('Integer constant must be exactly representable as binary64')
            return _Node('const', constant=constant), 'number'
        if set(value) != {'op', 'args'}:
            raise ValueError('Unknown expression fields or input')
        operation, args = value['op'], value['args']
        if (not isinstance(operation, str) or operation not in _ARITIES
                or not isinstance(args, list) or len(args) != _ARITIES[operation]):
            raise ValueError('Unknown operator or incorrect arity')
        children = [node(child, depth+1) for child in args]
        expected = ['boolean', 'number', 'number'] if operation == 'where' else ['number']*len(args)
        if [kind for _, kind in children] != expected:
            raise ValueError('Incorrect expression operand types')
        return _Node(operation, tuple(child for child, _ in children)), (
            'boolean' if operation == 'le' else 'number')

    loss, loss_type = node(source['loss'])
    gradient, gradient_type = node(source['gradient'])
    if loss_type != 'number' or gradient_type != 'number':
        raise ValueError('Loss and gradient outputs must be numeric')
    program = object.__new__(ScalarProgram)
    object.__setattr__(program, '_loss', loss)
    object.__setattr__(program, '_gradient', gradient)
    return program


def execute(program: ScalarProgram, value: np.ndarray | np.float32 | np.float64) -> tuple[np.ndarray, np.ndarray]:
    """Execute finite scalar arithmetic with dtype preservation and lazy branches.

    Every selected numeric intermediate must be finite. Finite underflow to zero
    remains possible; execution does not verify mathematical/numerical correctness.
    """
    if type(program) is not ScalarProgram:
        raise TypeError('Execution requires a validated ScalarProgram')
    if type(value) not in (np.ndarray, np.float32, np.float64):
        raise TypeError('Input must be a native NumPy float32/64 scalar or 0D array')
    x = np.asarray(value)
    if x.shape != ():
        raise ValueError('Input must have scalar shape ()')
    if x.dtype not in (np.dtype('float32'), np.dtype('float64')):
        raise TypeError('Input dtype must be native float32 or float64')
    if not np.isfinite(x):
        raise ValueError('Input must be finite')
    x = x.copy()
    x.setflags(write=False)
    dtype = x.dtype

    def finite(array, operation):
        if not np.isfinite(array):
            raise FloatingPointError(f'{operation} produced a nonfinite {dtype.name} intermediate')
        return array

    def evaluate(node):
        if node.operation == 'input':
            return x
        if node.operation == 'const':
            return finite(np.asarray(node.constant, dtype=dtype), 'constant')
        if node.operation == 'where':
            condition = evaluate(node.arguments[0])
            return evaluate(node.arguments[1] if bool(condition) else node.arguments[2])
        values = [evaluate(child) for child in node.arguments]
        result = np.asarray(_OPERATIONS[node.operation](*values),
                            dtype=np.bool_ if node.operation == 'le' else dtype)
        return result if node.operation == 'le' else finite(result, node.operation)

    with np.errstate(all='ignore'):
        loss, gradient = evaluate(program._loss), evaluate(program._gradient)
    return loss.copy(), gradient.copy()
