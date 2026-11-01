"""Bounded JSON decoding for the scalar program language."""
from __future__ import annotations

import json
import math

MAX_BYTES = 32768


def decode(payload: str | bytes):
    if not isinstance(payload, (str, bytes)):
        raise TypeError('Program JSON must be text or UTF-8 bytes')
    raw = payload.encode('utf-8') if isinstance(payload, str) else payload
    if len(raw) > MAX_BYTES:
        raise ValueError('Program JSON exceeds the 32768-byte limit')
    text = raw.decode('utf-8')
    depth, quoted, escaped = 0, False, False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in '[{':
            depth += 1
            if depth > 64:
                raise ValueError('Program JSON exceeds 64 nesting levels')
        elif character in ']}':
            depth -= 1
            if depth < 0:
                raise ValueError('Malformed program JSON')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate program JSON field')
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError('Nonfinite program JSON constant')

    def floating(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError('Overflowing program JSON number')
        return value

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=floating)
    except RecursionError as error:
        raise ValueError('Program JSON nesting exceeds decoder capacity') from error
