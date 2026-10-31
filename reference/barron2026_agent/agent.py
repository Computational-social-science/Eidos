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

import numpy as np

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
        teacher = np.array([2, 1, 0], dtype=np.float32)
        student = teacher + np.array([-1e-7, 1e-7, 0], dtype=np.float32)
        run = {"inventory": inventory, "calls": [],
               "soft_inputs": {"student": student.tolist(), "teacher": teacher.tolist()}}
        cases = [
            ("log_softmax", "log_softmax", {"z": PAPER_INPUT, "dtype": "float64"}),
            ("softmax", "softmax", {"z": PAPER_INPUT, "dtype": "float64"}),
            ("hard", "hard_cross_entropy", {"z": PAPER_INPUT, "target": 0, "dtype": "float64"}),
            ("control", "hard_cross_entropy", {"z": [40, 0, 0], "target": 0, "dtype": "float64"}),
            ("soft_equal", "soft_target_cross_entropy", {"student": teacher.tolist(),
                "teacher": teacher.tolist(), "teacher_kind": "logits", "dtype": "float32"}),
            ("soft_near", "soft_target_cross_entropy", {"student": student.tolist(),
                "teacher": teacher.tolist(), "teacher_kind": "logits", "dtype": "float32"}),
        ]
        for name, tool, arguments in cases:
            result = (await client.call_tool(tool, arguments)).data
            run[name] = result
            run["calls"].append({"case": name, "tool": tool, "arguments": arguments, "result": result})
    return run


def build_evidence(run: dict) -> dict:
    sys.path.insert(0, str(REPO))
    from framework.verifiers.numerics import probe_logit_distillation

    spec = _spec("log_softmax")
    matches_spec = _agrees(float(run["log_softmax"]["first"]), spec)
    control = run["control"]
    gradient = np.asarray(control["grad"], dtype=np.float64)
    scale = float(np.abs(gradient).sum())
    residual = abs(float(gradient.sum())) / scale if scale else float("inf")
    control_fired = bool(np.isfinite(gradient).all() and gradient[0] < 0
                         and control["standard_grad"][0] == 0
                         and not control["standard_grad_sum_is_zero"]
                         and residual <= 8 * np.finfo(np.float64).eps)
    teacher = np.asarray(run["soft_inputs"]["teacher"], dtype=np.float32)
    student = np.asarray(run["soft_inputs"]["student"], dtype=np.float32)
    qualification = {"design": "posthoc regression qualification",
                     "inputs": {"student": student.tolist(), "teacher": teacher.tolist(),
                                "represented_perturbation": (student - teacher).tolist()}}
    for name, values in (("soft_equal", teacher), ("soft_near", student)):
        response = run[name]
        def candidate(s, t):
            return response["loss"], np.asarray(response["grad"], dtype=np.float32)
        result = probe_logit_distillation(candidate, values, teacher)
        result["contract_matches"] = (response.get("teacher_kind") == "logits"
                                       and response.get("dtype") == "float32"
                                       and response.get("cancellation_fix") is True)
        if not result["contract_matches"]:
            result["verdict"] = "FAIL"
        qualification[name] = result
    qualification["verdict"] = ("PASS" if all(qualification[name]["verdict"] == "PASS"
                                             for name in ("soft_equal", "soft_near")) else "FAIL")

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paper": "barron2026-softmax-fix",
        "provenance": {"paper_version": "arxiv:2610.31642v3", "backend": f"numpy {np.__version__}",
                       "python": sys.version.split()[0],
                       "scope": "bounded NumPy float64 hard-target and float32 logits-distillation regression; no training reproduction"},
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
        "control": {"input": [40, 0, 0], "dtype": "float64", "target": 0,
                    "standard_target": float(control["standard_grad"][0]),
                    "fixed_target": float(gradient[0]), "zero_sum_relative_residual": residual,
                    "design": "posthoc regression qualification", "fired": control_fired},
        "qualification": qualification,
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
                    "provenance": evidence["provenance"], "calls": run["calls"]},
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
    if evidence["qualification"]["verdict"] != "PASS":
        problems.append("v3 soft-target independent qualification failed")

    sys.path.insert(0, str(REPO))
    from framework.validity import ScientificValidityGate

    result = ScientificValidityGate(HERE, document=HERE / "docs" / "REPORT.md").run()
    if result.status != "PASS":
        problems.append(f"Gate S {result.status}: {result.details.get('findings')}")

    print(json.dumps({"server": evidence["server"]["inventory"],
                      "C1": evidence["claims"]["C1"],
                      "C2": evidence["claims"]["C2"]["grad_sum"],
                      "control": evidence["control"],
                      "v3_qualification": evidence["qualification"]["verdict"],
                      "gate_s": result.status}, indent=2))
    if problems:
        print("FAIL " + "; ".join(problems))
        return 1
    print("PASS barron2026 agent: server answered, paper value reproduced, v3 regressions qualified, Gate S PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
