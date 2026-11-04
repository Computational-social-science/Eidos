"""Normalize a real historical Git identity without changing repair acceptance.

The CLI is an explicit supplement for the frozen v1 producer. It retains the
failed proof and records the raw ancestry and this adapter's exact source.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys


def _hex(value, minimum=40):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(minimum) + ',40}', value) is not None


def canonical_source(proof: dict, comparison: dict) -> dict:
    """Resolve only source_commit using a complete matching ancestry response."""
    if not isinstance(proof, dict) or not isinstance(comparison, dict):
        raise ValueError('Publication identity records must be objects')
    short, head = proof.get('source_commit'), proof.get('head_commit')
    base, merged = comparison.get('base_commit'), comparison.get('merge_base_commit')
    if not isinstance(base, dict) or not isinstance(merged, dict):
        raise ValueError('Source/merge-base resolution is missing')
    full = base.get('sha')
    if not _hex(short, 7) or not _hex(full) or not _hex(head) or not full.startswith(short):
        raise ValueError('Source identity is unresolved or rebound')
    if merged.get('sha') != full:
        raise ValueError('Resolved source is not the delivery ancestor')
    commits, total = comparison.get('commits'), comparison.get('total_commits')
    if not isinstance(commits, list) or type(total) is not int or len(commits) != total:
        raise ValueError('Ancestry is missing or truncated')
    if comparison.get('status') == 'identical':
        valid = full == head and total == 0
    elif comparison.get('status') == 'ahead':
        valid = total > 0 and isinstance(commits[-1], dict) and commits[-1].get('sha') == head
    else:
        valid = False
    if not valid:
        raise ValueError('Ancestry does not end at the exact delivery head')
    return dict(proof, source_commit=full)


def main() -> int:
    from framework import feedback
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--producer', type=Path, default=Path(__file__).with_name('campaign.py'))
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error('Optimized producer execution is not qualified')
    workspace, source = args.workspace.resolve(), args.producer.resolve()
    config = json.loads((workspace / 'campaign.json').read_bytes())
    if Path(os.path.abspath(sys.executable)) != Path(config['workers']['new']):
        raise ValueError('Use the selected normal installed candidate interpreter')
    if config['protected'].get(str(source)) != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError('The supplemental producer does not match its sealed source')
    project = Path(config['project'])
    if feedback.status(project, config['incident_id'])['state'] != 'VALIDATED':
        raise ValueError('Normalization requires the still-validated unreleased ledger state')
    spec = importlib.util.spec_from_file_location('sealed_publication_producer', source)
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    producer.verify_inputs(config['protected'])
    before = set((workspace / 'publication').glob('*/ancestry.json'))
    artifacts = producer.publication_artifacts(config)
    fresh = set((workspace / 'publication').glob('*/ancestry.json')) - before
    if len(fresh) != 1:
        raise ValueError('Cannot bind a unique fresh genuine ancestry response')
    raw = fresh.pop().read_bytes()
    original = artifacts['publication']
    artifacts['publication'] = canonical_source(original, json.loads(raw))
    own_source = Path(__file__).read_bytes()
    artifacts.update(normalization_input=original, source_resolution=raw,
                     normalizer_source=own_source)
    producer.verify_inputs(config['protected'])
    result = producer.receipt(config, 'release', artifacts=artifacts,
                              normalization={'field': 'source_commit', 'from': original['source_commit'],
                                             'to': artifacts['publication']['source_commit'],
                                             'adapter_sha256': hashlib.sha256(own_source).hexdigest()})
    producer.put(workspace / 'publication-identity-normalization.json', result)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
