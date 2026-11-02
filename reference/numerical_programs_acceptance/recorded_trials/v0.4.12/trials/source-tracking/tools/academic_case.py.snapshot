"""A bounded scientific summary derived from accepted paired experimental records."""
from __future__ import annotations
import json
from pathlib import Path


def summarize_matrix(report: dict) -> dict:
    pairs = {}
    for run in report['runs']:
        key = (run['seed'], run['loss_dtype'], run['epsilon'])
        pair = pairs.setdefault(key, {})
        if run['arm'] in pair:
            raise ValueError('duplicate paired arm')
        pair[run['arm']] = run['checkpoints'][-1]['test_accuracy']
    if not pairs or any(set(pair) != {'standard', 'fixed'} for pair in pairs.values()):
        raise ValueError('complete paired outcomes required')
    deltas = [p['fixed']-p['standard'] for p in pairs.values()]
    return {'status': 'VERIFIED', 'runs': len(report['runs']), 'pairs': len(pairs),
            'higher': sum(d > 0 for d in deltas), 'lower': sum(d < 0 for d in deltas),
            'ties': sum(d == 0 for d in deltas),
            'best_accuracy': max(v for p in pairs.values() for v in p.values())}


def load_matrix_summary(root: Path) -> dict:
    from reference.softmax_matrix.verify import validate, validate_final_check
    base = root / 'reference/softmax_matrix'
    try:
        report = json.loads((base / 'docs/evidence.json').read_text(encoding='utf-8'))
        protocol = json.loads((base / 'protocol.json').read_text(encoding='utf-8'))
        errors = validate(report, protocol, base=base)
        if not errors:
            errors = validate_final_check(report, base=base)
        if errors:
            return {'status': 'UNVERIFIED', 'reason': '; '.join(errors[:2])}
        return summarize_matrix(report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {'status': 'UNVERIFIED', 'reason': type(exc).__name__}
