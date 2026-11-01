"""A bounded scalar numerical language, with no Python eval or candidate imports.

This interpreter is an execution restriction for the declared development task,
not a general OS sandbox. It never loads a model or promotes a candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math

import numpy as np


MAX_BYTES = 32768
MAX_DEPTH = 16
MAX_NODES = 256
ARITIES = {"neg": 1, "exp": 1, "expm1": 1, "log": 1, "log1p": 1,
           "add": 2, "sub": 2, "mul": 2, "div": 2, "le": 2, "where": 3}
NUMERIC_OPS = {"neg": np.negative, "exp": np.exp, "expm1": np.expm1,
               "log": np.log, "log1p": np.log1p, "add": np.add,
               "sub": np.subtract, "mul": np.multiply, "div": np.divide,
               "le": np.less_equal}


@dataclass(frozen=True)
class Node:
    operation: str
    arguments: tuple[Node, ...] = ()
    constant: float = 0.0


@dataclass(frozen=True)
class Program:
    loss: Node
    gradient: Node


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def parse_program(payload: str) -> Program:
    """Validate the entire grammar, including branches that will not execute."""
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_BYTES:
        raise ValueError("candidate size exceeds the UTF-8 byte limit")
    try:
        source = json.loads(payload, object_pairs_hook=_object, parse_constant=_nonfinite)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("malformed or excessively nested candidate JSON") from error
    if not isinstance(source, dict) or set(source) != {"loss", "gradient"}:
        raise ValueError("program requires exactly loss and gradient")
    count = 0

    def node(value, depth=1):
        nonlocal count
        count += 1
        if count > MAX_NODES:
            raise ValueError("candidate node budget exceeded")
        if depth > MAX_DEPTH:
            raise ValueError("candidate depth budget exceeded")
        if not isinstance(value, dict):
            raise ValueError("each expression must be a node object")
        if set(value) == {"input"} and value["input"] == "x":
            return Node("input"), "number"
        if set(value) == {"const"}:
            constant = value["const"]
            if type(constant) not in (int, float):
                raise ValueError("constants must be finite numbers, excluding booleans")
            try:
                constant = float(constant)
            except OverflowError as error:
                raise ValueError("constant exceeds finite numeric range") from error
            if not math.isfinite(constant):
                raise ValueError("constant must be finite")
            return Node("const", constant=constant), "number"
        if set(value) != {"op", "args"}:
            raise ValueError("unknown expression fields or input name")
        operation, args = value["op"], value["args"]
        if (not isinstance(operation, str) or operation not in ARITIES
                or not isinstance(args, list) or len(args) != ARITIES[operation]):
            raise ValueError("unknown operator or wrong arity")
        children = [node(child, depth + 1) for child in args]
        expected = ["boolean", "number", "number"] if operation == "where" else ["number"] * len(args)
        if [kind for _, kind in children] != expected:
            raise ValueError("wrong expression operand types")
        return Node(operation, tuple(child for child, _ in children)), (
            "boolean" if operation == "le" else "number")

    loss, loss_type = node(source["loss"])
    gradient, gradient_type = node(source["gradient"])
    if loss_type != "number" or gradient_type != "number":
        raise ValueError("loss and gradient must be numeric expressions")
    return Program(loss, gradient)


def execute(program: Program, value: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate only typed scalar operators; preserve input dtype at every step."""
    if (not isinstance(value, np.ndarray) or value.shape != ()
            or value.dtype.name not in ("float32", "float64")
            or not np.isfinite(value) or value <= 0):
        raise ValueError("execution requires a positive finite float32/64 scalar array")
    dtype = value.dtype
    x = value.copy()
    x.setflags(write=False)

    def evaluate(node: Node):
        if node.operation == "input":
            return x
        if node.operation == "const":
            return np.asarray(node.constant, dtype=dtype)
        if node.operation == "where":
            condition = evaluate(node.arguments[0])
            return evaluate(node.arguments[1] if bool(condition) else node.arguments[2])
        operation = NUMERIC_OPS[node.operation]
        result = operation(*(evaluate(child) for child in node.arguments))
        return np.asarray(result, dtype=np.bool_ if node.operation == "le" else dtype)

    with np.errstate(all="ignore"):
        return np.asarray(evaluate(program.loss)), np.asarray(evaluate(program.gradient))
