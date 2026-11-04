"""Identity normalization changes no verdict or immutable acceptance input."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SOURCE = 'a' * 40
HEAD = 'b' * 40


def normalizer():
    path = Path(__file__).with_name('publication_identity.py')
    spec = importlib.util.spec_from_file_location('publication_identity', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records(source=SOURCE[:7]):
    proof = {'source_commit': source, 'head_commit': HEAD, 'ci_head': HEAD,
             'artifact_sha256': 'c' * 64, 'published': True}
    comparison = {'status': 'ahead', 'base_commit': {'sha': SOURCE},
                  'merge_base_commit': {'sha': SOURCE}, 'total_commits': 1,
                  'commits': [{'sha': HEAD}]}
    return proof, comparison


def test_short_identity_expands_without_mutating_any_other_field_or_input():
    proof, comparison = records()
    before = deepcopy((proof, comparison))
    actual = normalizer().canonical_source(proof, comparison)
    assert actual == dict(proof, source_commit=SOURCE)
    assert (proof, comparison) == before


def test_complete_identity_is_preserved():
    proof, comparison = records(SOURCE)
    assert normalizer().canonical_source(proof, comparison) == proof


@pytest.mark.parametrize('fault', ['short', 'nonhex', 'wrong_base', 'wrong_merge_base',
                                  'wrong_head', 'truncated', 'diverged', 'missing_commits'])
def test_unresolved_rebound_or_incomplete_ancestry_cannot_be_canonicalized(fault):
    proof, comparison = records()
    if fault == 'short':
        proof['source_commit'] = 'a' * 6
    elif fault == 'nonhex':
        comparison['base_commit']['sha'] = 'z' * 40
    elif fault == 'wrong_base':
        comparison['base_commit']['sha'] = 'd' * 40
    elif fault == 'wrong_merge_base':
        comparison['merge_base_commit']['sha'] = 'd' * 40
    elif fault == 'wrong_head':
        comparison['commits'][-1]['sha'] = 'd' * 40
    elif fault == 'truncated':
        comparison['total_commits'] = 2
    elif fault == 'diverged':
        comparison['status'] = 'diverged'
    elif fault == 'missing_commits':
        comparison['commits'] = None
    with pytest.raises(ValueError):
        normalizer().canonical_source(proof, comparison)


def test_identical_source_and_delivery_accepts_only_that_actual_identity():
    proof, comparison = records()
    comparison.update(status='identical', commits=[], total_commits=0)
    with pytest.raises(ValueError):
        normalizer().canonical_source(proof, comparison)
    proof.update(head_commit=SOURCE, ci_head=SOURCE)
    assert normalizer().canonical_source(proof, comparison)['source_commit'] == SOURCE


@pytest.mark.parametrize('proof,comparison', [(None, {}), ({}, []), ({}, {})])
def test_malformed_records_refuse(proof, comparison):
    with pytest.raises(ValueError):
        normalizer().canonical_source(proof, comparison)
