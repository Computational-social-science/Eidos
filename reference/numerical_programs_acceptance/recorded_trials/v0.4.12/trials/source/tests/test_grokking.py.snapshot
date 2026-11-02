"""Grokking completion must not be confused with favorable scientific outcomes."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_stripped_actual_report_cannot_pass():
    from reference.softmax_grokking.verify import validate
    base = ROOT / 'reference/softmax_grokking'
    report = json.loads((base/'docs/evidence.json').read_text())
    protocol = json.loads((base/'protocol.json').read_text())
    report['artifacts'] = {}
    report['backend_preflight'] = {'verdict': 'PASS'}
    for run in report['runs']:
        run.pop('distillation', None)
        run.pop('initial_state_sha256', None)
        for arm in run['arms'].values():
            arm.pop('initial_state_sha256', None)
            arm.pop('final_state_sha256', None)
    assert validate(report, protocol)


def test_extension_requires_parent_replay_and_distillation():
    from reference.softmax_grokking_extension.verify import validate
    base = ROOT / 'reference/softmax_grokking_extension'
    report = json.loads((base/'docs/evidence.json').read_text())
    protocol = json.loads((base/'protocol.json').read_text())
    for mutate in ('replay', 'distillation'):
        broken = copy.deepcopy(report)
        if mutate == 'replay':
            broken['parent_replay_checks'] = []
        else:
            broken['runs'][0]['distillation'] = {'status': 'SKIP'}
        assert validate(broken, protocol, check_files=False)


def test_missing_grokking_evidence_cannot_pass():
    from reference.softmax_grokking.verify import validate
    assert validate({}, {}, check_files=False)


def test_metric_recompute_uses_actual_labels_and_heldout_split():
    from reference.softmax_grokking.verify import classification_metrics
    import numpy as np
    logits = np.array([[5., 0.], [0., 5.], [5., 0.], [0., 5.]])
    result = classification_metrics(logits, np.array([0, 1, 1, 0]), [0, 1], [2, 3])
    assert result["train_accuracy"] == 1 and result["test_accuracy"] == 0


def test_repeated_or_missing_arms_are_rejected_even_if_they_say_pass():
    from reference.softmax_grokking.verify import validate
    report = {"status": "COMPLETE", "runs": [{"seed": 0, "arms": {"fixed": {}}}]}
    assert validate(report, {"seeds": [0, 1, 2]}, check_files=False)
