"""SDK-created nested scopes must remain owned by the outer execution lifetime."""
import time

from framework.project import run_command
from reference.sdk_process_acceptance.check import fixture, handoff_fixture
import sys
import pytest


def test_outer_deadline_closes_a_nested_sdk_scope(tmp_path):
    spec = fixture(tmp_path / "nested sdk", nested=True)
    result = run_command(spec, timeout=3)
    assert result.status == "ERROR" and result.exit_code == 124, result.as_dict()
    assert (spec.root / "ready").exists(), "inner scope must actually start"
    time.sleep(2.5)
    assert not (spec.root / "late").exists(), "inner scope escaped the outer SDK lifetime"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX delayed cleanup handoff")
def test_normal_inner_root_cleans_before_its_caller_can_be_killed(tmp_path):
    spec = handoff_fixture(tmp_path / "handoff")
    result = run_command(spec, timeout=3)
    assert result.status == "ERROR" and result.exit_code == 124
    assert (spec.root / "cleanup-wait").exists(), "the caller must reach the delayed cleanup window"
    time.sleep(2.5)
    assert not (spec.root / "late").exists()
