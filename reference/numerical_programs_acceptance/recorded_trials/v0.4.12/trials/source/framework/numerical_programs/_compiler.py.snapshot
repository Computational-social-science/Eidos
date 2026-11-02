"""Lower a bounded formula syntax into validated scalar programs; never eval."""
from __future__ import annotations

import ast
import json

from ._language import MAX_DEPTH, MAX_NODES, ScalarProgram, parse_program

MAX_SOURCE_BYTES = 2048
_BINARY = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'div'}
_CALLS = {'exp': 1, 'expm1': 1, 'log': 1, 'log1p': 1, 'where': 3}


def compile_formulas(loss: str, gradient: str) -> ScalarProgram:
    """Compile supplied value/gradient formulas; do not derive or verify either."""
    count = 0

    def lower(node, depth=1):
        nonlocal count
        count += 1
        if depth > MAX_DEPTH or count > MAX_NODES:
            raise ValueError('Formula exceeds its combined node/depth budget')
        if isinstance(node, ast.Name) and node.id == 'x':
            return {'input': 'x'}
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return {'const': node.value}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return {'op': 'neg', 'args': [lower(node.operand, depth+1)]}
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return {'op': _BINARY[type(node.op)], 'args': [lower(node.left, depth+1), lower(node.right, depth+1)]}
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.LtE):
            return {'op': 'le', 'args': [lower(node.left, depth+1), lower(node.comparators[0], depth+1)]}
        if isinstance(node, ast.IfExp):
            return {'op': 'where', 'args': [lower(value, depth+1) for value in (node.test, node.body, node.orelse)]}
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _CALLS and not node.keywords and len(node.args) == _CALLS[node.func.id]):
            return {'op': node.func.id, 'args': [lower(value, depth+1) for value in node.args]}
        raise ValueError('Unsupported formula syntax, name or operation')

    program = {}
    for name, source in (('loss', loss), ('gradient', gradient)):
        if not isinstance(source, str):
            raise TypeError('Formula must be text')
        if not source.strip() or len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
            raise ValueError('Formula must be nonempty and at most 2048 UTF-8 bytes')
        try:
            tree = ast.parse(source.strip(), mode='eval')
        except (SyntaxError, RecursionError) as error:
            raise ValueError('Invalid formula syntax') from error
        program[name] = lower(tree.body)
    return parse_program(json.dumps(program, allow_nan=False))
