"""A report cannot silently promote failed or partial aggregate evidence."""
import copy
import json
from pathlib import Path

import pytest

from reference.hpaf_metric.report import validate_aggregate


def audit():
    path = Path(__file__).resolve().parents[1] / "reference/hpaf_metric/docs/local-audit.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_complete_independently_checked_aggregate_is_renderable():
    validate_aggregate(audit())


@pytest.mark.parametrize("change", [
    lambda r: r.update(accepted=False),
    lambda r: r.update(records=1032),
    lambda r: r["source_sha256"].update({"run.py": "0" * 64}),
    lambda r: r["source_sha256"].pop("verify.py"),
    lambda r: r["joint_cost_counts"].pop(),
    lambda r: r["original_engine"].update(all_legacy_costs_match=False),
    lambda r: r["original_engine"].update(original_code_and_data_modified=True),
    lambda r: r.pop("data_sha256"),
    lambda r: r["data_sha256"].update({"advbench_llm_perturbed_1.json": "invalid"}),
    lambda r: r.update(qualification={}),
    lambda r: r["qualification"].update(legacy_control_mismatches=0),
    lambda r: r["per_corpus"]["advbench_llm_perturbed_1.json"].update(legacy_mismatches=0),
    lambda r: r["joint_cost_counts"][0].update(count=True),
])
def test_failed_changed_or_partial_audit_is_refused(change):
    record = copy.deepcopy(audit())
    change(record)
    with pytest.raises(ValueError):
        validate_aggregate(record)
