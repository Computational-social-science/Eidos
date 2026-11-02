"""Preserve historical lock evidence across local release-label changes."""
from __future__ import annotations
import hashlib
import re
import tomllib
from pathlib import Path


def source_hash(content: bytes) -> str:
    return hashlib.sha256(content.decode('utf-8-sig').replace('\r\n', '\n').encode()).hexdigest()


def _typed_equal(left, right) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_typed_equal(v,right[k]) for k,v in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a,b) for a,b in zip(left,right))
    return left == right


def historical_lock_matches(root: Path, recorded: str) -> bool:
    """Require the original hash and identical TOML except eidos editable version.

    Added fields, sources, markers, artifact hashes and third-party pin changes
    still reject. Original reports and locks are never rewritten.
    """
    try:
        if not isinstance(recorded, str) or not re.fullmatch(r'[0-9a-f]{64}', recorded):
            return False
        current = (root / 'uv.lock').read_bytes()
        if source_hash(current) == recorded:
            return True
        archived = (root / 'lock/snapshots/uv' / f'{recorded}.lock').read_bytes()
        if source_hash(archived) != recorded:
            return False
        old, new = (tomllib.loads(b.decode('utf-8-sig')) for b in (archived, current))
        def local(doc):
            found = [p for p in doc['package'] if p.get('name') == 'eidos'
                     and p.get('source') == {'editable': '.'}]
            if len(found) != 1:
                raise ValueError('one local editable package required')
            return found[0]
        old_local, new_local = local(old), local(new)
        if any(not isinstance(p.get('version'),str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',p['version']) for p in (old_local,new_local)):
            return False
        old_local['version'] = new_local['version']
        return _typed_equal(old,new)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return False
