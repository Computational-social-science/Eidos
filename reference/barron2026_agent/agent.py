"""E2E: the Barron (2026) MCP server, driven by Eidos and judged by Gate S.

This is the part Paper2Agent does not deliver: a converted tool is not an agent Eidos can use until
something starts it, calls it, checks the answers against the paper, writes an evidence artefact, and
lets the validity gate rule on the resulting claim. That chain is what runs here.

    python reference/barron2026_agent/agent.py        # writes docs/evidence.json + agent_trace.json

Exit 0 only if the server answered, the answers agree with the registered specs, the negative control
fired, and Gate S passes on the register. Any other outcome exits non-zero with the reason.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SERVER = REPO / "reference" / "reproduction" / "barron2026" / "mcp" / "server.py"
SPECS = REPO / "reference" / "reproduction" / "barron2026" / "specs.json"

PAPER_INPUT = [9.0, -9.0, -9.0]


def _spec(name: str) -> dict:
    data = json.loads(SPECS.read_text(encoding="utf-8"))
    for spec in data["specs"]:
        if spec["tool"] == name:
            return spec
    raise KeyError(f"no spec for {name}")


def _agrees(observed: float, spec: dict) -> bool:
    expected = float(spec["expected"])
    if spec.get("relative"):
        return abs(observed - expected) <= abs(expected) * float(spec["tolerance"])
    return abs(observed - expected) <= float(spec["tolerance"])


async def _call_server() -> dict:
    from fastmcp import Client

    config = {"mcpServers": {"barron2026": {"command": sys.executable,
                                            "args": [str(SERVER)], "cwd": str(SERVER.parent)}}}
    async with Client(config) as client:
        inventory = sorted(tool.name for tool in await client.list_tools())

        log_softmax = (await client.call_tool("log_softmax", {"z": PAPER_INPUT})).data
        softmax = (await client.call_tool("softmax", {"z": PAPER_INPUT})).data
        hard = (await client.call_tool("hard_cross_entropy",
                                       {"z": PAPER_INPUT, "target": 0})).data
        soft = (await client.call_tool("soft_target_cross_entropy",
                                       {"student": [1.0, 0.0], "teacher": [0.5, 0.5]})).data
        # Negative control: a teacher that does not sum to one must break the zero-sum gradient.
        control = (await client.call_tool("soft_target_cross_entropy",
                                          {"student": [1.0, 0.0], "teacher": [0.5, 0.6]})).data

    return {"inventory": inventory, "log_softmax": log_softmax, "softmax": softmax,
            "hard": hard, "soft": soft, "control": control}


def build_evidence(run: dict) -> dict:
    spec = _spec("log_softmax")
    matches_spec = _agrees(float(run["log_softmax"]["first"]), spec)
    control_sum = float(run["control"]["grad_sum"])
    # The control is arithmetic, not a threshold: an unnormalised teacher leaves exactly
    # 1 - sum(teacher) in the gradient sum.
    expected_control = 1.0 - (0.5 + 0.6)
    control_fired = (abs(control_sum - expected_control) <= 1e-12
                     and not run["control"]["grad_sum_is_zero"])

    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paper": "barron2026-softmax-fix",
        "server": {"path": str(SERVER.relative_to(REPO)).replace("\\", "/"),
                   "inventory": run["inventory"]},
        "claims": {
            "C1": {"matches_paper_value": bool(matches_spec),
                   "observed": float(run["log_softmax"]["first"]),
                   "expected": float(spec["expected"])},
            "C2": {"grad_sum_is_zero": bool(run["hard"]["grad_sum_is_zero"]),
                   "grad_sum": float(run["hard"]["grad_sum"]),
                   "gradient": [float(v) for v in run["hard"]["grad"]]},
        },
        "control": {"unnormalised_teacher_grad_sum": control_sum,
                    "expected": expected_control,
                    "fired": bool(control_fired)},
        "softmax": {"sum": float(run["softmax"]["sum"]),
                    "is_normalised": bool(run["softmax"]["is_normalised"])},
        "power": {"not_applicable": "deterministic float64 arithmetic, not an estimate"},
        "multiplicity": {"not_applicable": "two claims, each a single equality check"},
    }


def main() -> int:
    if not SERVER.is_file():
        print(f"FAIL server missing: {SERVER}")
        return 2
    run = asyncio.run(_call_server())
    evidence = build_evidence(run)
    (HERE / "docs").mkdir(exist_ok=True)
    (HERE / "docs" / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n",
                                                 encoding="utf-8")
    (HERE / "docs" / "agent_trace.json").write_text(
        json.dumps({"recorded_at": evidence["recorded_at"],
                    "calls": [{"tool": "log_softmax", "result": run["log_softmax"]},
                              {"tool": "softmax", "result": run["softmax"]},
                              {"tool": "hard_cross_entropy", "result": run["hard"]},
                              {"tool": "soft_target_cross_entropy", "result": run["soft"]},
                              {"tool": "soft_target_cross_entropy (control)", "result": run["control"]}]},
                   indent=2) + "\n", encoding="utf-8")

    problems = []
    if evidence["server"]["inventory"] != ["hard_cross_entropy", "log_softmax", "soft_target_cross_entropy", "softmax"]:
        problems.append(f"inventory {evidence['server']['inventory']}")
    if not evidence["claims"]["C1"]["matches_paper_value"]:
        problems.append("C1: the tool does not reproduce the paper's value")
    if not evidence["claims"]["C2"]["grad_sum_is_zero"]:
        problems.append("C2: the gradient does not sum to zero")
    if not evidence["control"]["fired"]:
        problems.append("control did not fire: the zero-sum check accepts a broken gradient")

    sys.path.insert(0, str(REPO))
    from framework.validity import ScientificValidityGate

    result = ScientificValidityGate(HERE, document=HERE / "docs" / "REPORT.md").run()
    if result.status != "PASS":
        problems.append(f"Gate S {result.status}: {result.details.get('findings')}")

    print(json.dumps({"server": evidence["server"]["inventory"],
                      "C1": evidence["claims"]["C1"],
                      "C2": evidence["claims"]["C2"]["grad_sum"],
                      "control": evidence["control"],
                      "gate_s": result.status}, indent=2))
    if problems:
        print("FAIL " + "; ".join(problems))
        return 1
    print("PASS barron2026 agent: server answered, paper value reproduced, control fired, Gate S PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
