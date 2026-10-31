"""The converted paper is an agent only if a run exists and the gate accepted it.

The heavy part — starting the MCP server over stdio — runs in the `agent-e2e` CI job, because it needs
`fastmcp`, which the unit-test environment does not carry. What is checked here is the artefact that run
produced: the evidence it wrote, the register that cites it, and the project that exposes it to Eidos.
A stale or hand-edited artefact fails here.
"""

import json
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "reference" / "barron2026_agent"
PROJECT = ROOT / "projects" / "barron2026_agent" / "project.yaml"


@pytest.fixture
def agent_module():
    spec = importlib.util.spec_from_file_location("barron_agent_test", AGENT / "agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def v3_run():
    pytest.importorskip("fastmcp")
    server_path = ROOT / "reference/reproduction/barron2026/mcp/server.py"
    spec = importlib.util.spec_from_file_location("barron_server_test", server_path)
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    teacher = np.array([2, 1, 0], dtype=np.float32)
    student = teacher + np.array([-1e-7, 1e-7, 0], dtype=np.float32)
    return {
        "inventory": ["hard_cross_entropy", "log_softmax", "soft_target_cross_entropy", "softmax"],
        "log_softmax": server.log_softmax([9, -9, -9]),
        "softmax": server.softmax([9, -9, -9]),
        "hard": server.hard_cross_entropy([9, -9, -9], 0),
        "control": server.hard_cross_entropy([40, 0, 0], 0),
        "soft_equal": server.soft_target_cross_entropy(teacher.tolist(), teacher.tolist(),
                                                       teacher_kind="logits", dtype="float32"),
        "soft_near": server.soft_target_cross_entropy(student.tolist(), teacher.tolist(),
                                                      teacher_kind="logits", dtype="float32"),
        "soft_inputs": {"student": student.tolist(), "teacher": teacher.tolist()},
        "calls": [],
    }


def test_v3_agent_independently_qualifies_logits_and_collapse(agent_module, v3_run):
    evidence = agent_module.build_evidence(v3_run)
    assert evidence["control"]["fired"] is True
    assert evidence["control"]["standard_target"] == 0
    assert evidence["control"]["fixed_target"] < 0
    assert evidence["qualification"]["verdict"] == "PASS"
    for name in ("soft_equal", "soft_near"):
        assert evidence["qualification"][name]["verdict"] == "PASS"
    assert evidence["qualification"]["design"] == "posthoc regression qualification"


@pytest.mark.parametrize("case", ["soft_equal", "soft_near"])
def test_v3_agent_rejects_inaccurate_gradients_even_with_true_server_flags(agent_module, v3_run, case):
    v3_run[case]["grad"] = [1e-12, -1e-12, 0.0]
    v3_run[case]["grad_sum_is_zero"] = True
    evidence = agent_module.build_evidence(v3_run)
    assert evidence["qualification"]["verdict"] == "FAIL"
    assert evidence["qualification"][case]["verdict"] == "FAIL"


def test_v3_agent_rejects_collapsed_target_despite_server_flag(agent_module, v3_run):
    v3_run["control"]["grad"][0] = 0.0
    v3_run["control"]["grad_sum_is_zero"] = True
    assert agent_module.build_evidence(v3_run)["control"]["fired"] is False


def test_the_agent_project_is_registered_with_the_framework():
    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))
    assert project["role"].startswith("paper-to-agent")
    assert project["expected_gate_s"] == "PASS"
    assert (PROJECT.parent / project["root"]).resolve() == AGENT.resolve()
    assert (AGENT / project["validity_document"]).is_file()
    assert (AGENT / project["validity_register"]).is_file()


def test_the_run_recorded_all_four_tools():
    evidence = json.loads((AGENT / "docs" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["server"]["inventory"] == ["hard_cross_entropy", "log_softmax",
                                              "soft_target_cross_entropy", "softmax"]


def test_the_two_claims_hold_and_the_control_fired():
    evidence = json.loads((AGENT / "docs" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["claims"]["C1"]["matches_paper_value"] is True
    assert evidence["claims"]["C2"]["grad_sum_is_zero"] is True
    assert evidence["control"]["fired"] is True
    assert evidence["control"]["standard_target"] == 0
    assert evidence["control"]["fixed_target"] < 0
    assert evidence["control"]["zero_sum_relative_residual"] <= 8 * np.finfo(np.float64).eps
    assert evidence["qualification"]["verdict"] == "PASS"


def test_the_trace_shows_every_call_was_made():
    trace = json.loads((AGENT / "docs" / "agent_trace.json").read_text(encoding="utf-8"))
    assert [call["case"] for call in trace["calls"]] == [
        "log_softmax", "softmax", "hard", "control", "soft_equal", "soft_near"]
    assert [call["tool"] for call in trace["calls"]] == [
        "log_softmax", "softmax", "hard_cross_entropy", "hard_cross_entropy",
        "soft_target_cross_entropy", "soft_target_cross_entropy"]
    for call in trace["calls"]:
        assert call["arguments"] and call["result"]
    for call in trace["calls"][-2:]:
        assert call["arguments"]["teacher_kind"] == "logits"
        assert call["arguments"]["dtype"] == "float32"


def test_the_register_is_pre_registered_and_cites_resolving_pointers():
    register = yaml.safe_load((AGENT / "analysis" / "CLAIMS.yaml").read_text(encoding="utf-8"))
    evidence = json.loads((AGENT / "docs" / "evidence.json").read_text(encoding="utf-8"))
    def moment(value):
        from datetime import datetime
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    assert moment(register["registered_at"]) <= moment(evidence["recorded_at"])
    for claim in register["claims"]:
        pointer = claim["evidence"]["pointer"].strip("/").split("/")
        node = evidence
        for key in pointer:
            node = node[key]
        assert node == claim["evidence"]["value"] == True  # noqa: E712 - the register stores a bool
