"""The converted paper is an agent only if a run exists and the gate accepted it.

The heavy part — starting the MCP server over stdio — runs in the `agent-e2e` CI job, because it needs
`fastmcp`, which the unit-test environment does not carry. What is checked here is the artefact that run
produced: the evidence it wrote, the register that cites it, and the project that exposes it to Eidos.
A stale or hand-edited artefact fails here.
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "reference" / "barron2026_agent"
PROJECT = ROOT / "projects" / "barron2026_agent" / "project.yaml"


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
    # The control is arithmetic: an unnormalised teacher leaves exactly 1 - sum(teacher).
    assert abs(evidence["control"]["unnormalised_teacher_grad_sum"] - (-0.1)) < 1e-12


def test_the_trace_shows_every_call_was_made():
    trace = json.loads((AGENT / "docs" / "agent_trace.json").read_text(encoding="utf-8"))
    tools = [call["tool"] for call in trace["calls"]]
    assert tools == ["log_softmax", "softmax", "hard_cross_entropy",
                     "soft_target_cross_entropy", "soft_target_cross_entropy (control)"]


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
