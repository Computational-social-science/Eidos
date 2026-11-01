"""Parse a small formula syntax into the existing typed scalar language.

No candidate text is evaluated as Python. Translation is not mathematical
qualification; callers must separately test a method's actual outputs.
"""
from __future__ import annotations

import ast
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from reference.rsi_bootstrap import expressions

CATALOG = Path(__file__).with_name('catalog.json')
BANK = Path(__file__).parents[1] / 'rsi_bootstrap/methods/cards.json'
MAX_SOURCE_BYTES = 2048
BINARY = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'div'}
CALLS = {'exp': 1, 'expm1': 1, 'log': 1, 'log1p': 1, 'where': 3}


def strict_json(raw: bytes):
    if not isinstance(raw, bytes):
        raise ValueError('JSON input must be UTF-8 bytes')
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
                raise ValueError('JSON nesting exceeds 64 levels')
        elif character in ']}':
            depth -= 1
            if depth < 0:
                raise ValueError('Malformed JSON nesting')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError('Nonfinite JSON constant')

    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError('Overflowing JSON number')
        return value

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=finite_float)
    except RecursionError as error:
        raise ValueError('JSON nesting exceeds the decoder limit') from error


def card_identity(card: dict) -> str:
    """Semantic origin pin, independent of JSON layout/newline conversion."""
    raw = json.dumps(card, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def compile_formulas(loss: str, gradient: str) -> dict:
    """Return a validated, dtype-preserving program, without executing formulas."""
    count = 0

    def lower(node, depth=1):
        nonlocal count
        count += 1
        if depth > expressions.MAX_DEPTH or count > expressions.MAX_NODES:
            raise ValueError('Formula expression depth/node budget exceeded')
        if isinstance(node, ast.Name) and node.id == 'x':
            return {'input': 'x'}
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            try:
                finite = math.isfinite(float(node.value))
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError('Formula constant must be finite')
            return {'const': node.value}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return {'op': 'neg', 'args': [lower(node.operand, depth+1)]}
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            return {'op': BINARY[type(node.op)],
                    'args': [lower(node.left, depth+1), lower(node.right, depth+1)]}
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.LtE):
            return {'op': 'le', 'args': [lower(node.left, depth+1), lower(node.comparators[0], depth+1)]}
        if isinstance(node, ast.IfExp):
            return {'op': 'where', 'args': [lower(value, depth+1)
                                           for value in (node.test, node.body, node.orelse)]}
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in CALLS and not node.keywords
                and len(node.args) == CALLS[node.func.id]):
            return {'op': node.func.id, 'args': [lower(value, depth+1) for value in node.args]}
        raise ValueError('Unsupported formula syntax, name or operation')

    program = {}
    for name, source in (('loss', loss), ('gradient', gradient)):
        if not isinstance(source, str) or not source or len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
            raise ValueError('Formula source must be a nonempty bounded string')
        try:
            tree = ast.parse(source, mode='eval')
        except (SyntaxError, RecursionError) as error:
            raise ValueError('Invalid formula syntax') from error
        program[name] = lower(tree.body)
    expressions.parse_program(json.dumps(program, allow_nan=False))  # Full operand/type/branch validation.
    return program


def load_method(method_id: str, path: Path = CATALOG) -> dict:
    if not isinstance(method_id, str):
        raise ValueError('Method ID must be explicit')
    raw = Path(path).read_bytes()
    if len(raw) > 32768:
        raise ValueError('Catalog exceeds size limit')
    catalog = strict_json(raw)
    if (not isinstance(catalog, dict) or set(catalog) != {'schema', 'notice', 'methods'}
            or catalog['schema'] != 'eidos.numerical-method-catalog.v1'
            or not isinstance(catalog['notice'], str) or not catalog['notice'].strip()
            or not isinstance(catalog['methods'], list) or not 1 <= len(catalog['methods']) <= 32):
        raise ValueError('Invalid method catalog')
    bank_raw = BANK.read_bytes()
    cards = strict_json(bank_raw)['cards']
    fields = {'id', 'version', 'task', 'domain', 'loss', 'gradient', 'source_urls',
              'checked_on', 'derivative_attribution', 'origin_card_id', 'origin_card_sha256'}
    seen = set()
    selected = None
    for item in catalog['methods']:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError('Invalid method fields')
        if any(not isinstance(item[key], str) or not item[key].strip()
               for key in fields - {'source_urls', 'version'}):
            raise ValueError('Invalid method text')
        if not re.fullmatch('[a-z0-9-]{1,80}', item['id']) or item['id'] in seen:
            raise ValueError('Invalid or duplicate method identity')
        seen.add(item['id'])
        if (type(item['version']) is not int or item['version'] != 1
                or item['task'] != 'log1mexp-loss-and-first-derivative'
                or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item['checked_on'])):
            raise ValueError('Method task/version/origin differs')
        date.fromisoformat(item['checked_on'])
        urls = item['source_urls']
        if not isinstance(urls, list) or not 1 <= len(urls) <= 4:
            raise ValueError('Method requires source citations')
        for url in urls:
            if not isinstance(url, str):
                raise ValueError('Invalid source citation')
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError('Source must be a credential-free HTTPS citation')
        if not any(card['id'] == item['origin_card_id'] and card['source_url'] in urls
                   and card_identity(card) == item['origin_card_sha256'] for card in cards):
            raise ValueError('Method source does not bind an existing method card')
        compile_formulas(item['loss'], item['gradient'])
        if item['id'] == method_id:
            selected = item
    if selected is None:
        raise ValueError('Unknown method; no fallback is permitted')
    return selected
