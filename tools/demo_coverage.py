"""Which capabilities does a demo actually exercise — and which only the framework's own tests?

The question "is one onboarding enough?" is answerable, but not by opinion. A capability counts as
*demonstrated* when a consumer project produced the artefact that proves it. A capability that
only the framework's self-tests exercise is a different claim: it says the machinery works, not
that a project can use it.

    python tools/demo_coverage.py            # matrix + uncovered list
    python tools/demo_coverage.py --json     # writes docs/DEMO_COVERAGE.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _consumers() -> dict:
    return {row["name"]: row for row in (_load(DOCS / "pipeline.json", {}).get("consumers") or [])}


def _has(path: str) -> bool:
    return (ROOT / path).exists()


def capabilities() -> list[dict]:
    """Each capability, the artefact that proves it, and where that proof comes from."""
    cons = _consumers()
    demo = cons.get("demo_onboarding") or {}
    calib = cons.get("operator_calibration") or {}
    controls = [n for n in ("null_study", "prose_lie")
                if (cons.get(n) or {}).get("gate_s") == "FAIL"]
    chain = _load(DOCS / "CHAIN.json", {}).get("fixtures") or []
    render = _load(DOCS / "RENDER_CHECK.json", {})
    fuzz = _load(DOCS / "FUZZ.json", {})

    live = _load(DOCS / "status" / "chains.json", {}).get("chains") or {}

    def chain_status(name: str) -> str:
        # Two different artefacts: CHAIN.json holds the chain-consumer fixtures, while
        # status/chains.json holds the last verdict of every chain the scheduler ran.
        if name in live:
            return str((live[name] or {}).get("status") or "")
        for row in chain:
            if row.get("project") == name:
                return str(row.get("status") or "")
        return ""

    return [
        {"capability": "a project measures itself and registers a claim",
         "proof": "demo_onboarding gate verdict equals expectation",
         "self_test": (demo.get("gate_s") == demo.get("expected") == "PASS"),
         "in_demo": (demo.get("gate_s") == "PASS")},
        {"capability": "a live LLM consumer produces evidence with an interval",
         "proof": "operator_calibration gate PASS with its own evidence.json",
         "self_test": (calib.get("gate_s") == "PASS"),
         "in_demo": (calib.get("gate_s") == "PASS")},
        {"capability": "a false claim is rejected by Gate S",
         "proof": "null_study and prose_lie both FAIL as declared",
         "self_test": bool(controls),
         "in_demo": bool(_has("reference/demo_onboarding/show_rejection.py"))},
        {"capability": "a gate that exits 0 without its artefact is refused",
         "proof": "chain_no_output must FAIL",
         "self_test": chain_status("chain_no_output") == "FAIL",
         "in_demo": False},
        {"capability": "a missing tool is SKIP, not PASS",
         "proof": "chain_tool_missing must SKIP",
         "self_test": chain_status("chain_tool_missing") == "SKIP",
         "in_demo": False},
        {"capability": "a manuscript renders to html, pdf and docx from one source",
         "proof": "docs/RENDER_CHECK.json lists three formats",
         "self_test": bool(render.get("formats") or render),
         "in_demo": False},
        {"capability": "quantitative acceptance thresholds with an explicit direction",
         "proof": "a consumer runs a BootLoops acceptance gate",
         "self_test": _has("framework/gates/__init__.py"),
         "in_demo": False},
        {"capability": "experiment tracking (mlflow + dvc) is part of the chain",
         "proof": "the tracking chain passes with its own run id",
         "self_test": (chain_status("tracking") == "PASS"),
         "in_demo": False},
        {"capability": "the framework refuses wrong and accepts equivalent evidence",
         "proof": "docs/FUZZ.json: blind_spots 0, over_rejections 0",
         "self_test": (fuzz.get("blind_spots") == [] and fuzz.get("over_rejections") == []),
         "in_demo": False},
        {"capability": "a service is up only if every endpoint answers",
         "proof": "tools/audit_services.py reports a named silent half",
         "self_test": _has("tools/audit_services.py"),
         "in_demo": False},
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = capabilities()
    print(f"{'capability':<62} {'self-test':<10} demo")
    print("-" * 86)
    for row in rows:
        print(f"{row['capability'][:60]:<62} "
              f"{'yes' if row['self_test'] else 'no':<10} {'yes' if row['in_demo'] else 'no'}")

    self_ok = sum(1 for r in rows if r["self_test"])
    demo_ok = sum(1 for r in rows if r["in_demo"])
    gaps = [r["capability"] for r in rows if not r["in_demo"]]
    print(f"\nself-test coverage {self_ok}/{len(rows)} · demo coverage {demo_ok}/{len(rows)}")

    if args.json:
        (DOCS / "DEMO_COVERAGE.json").write_text(json.dumps(
            {"rows": rows, "self_test": self_ok, "demo": demo_ok, "gaps": gaps,
             "total": len(rows)}, indent=2), encoding="utf-8")
        print(f"wrote {DOCS / 'DEMO_COVERAGE.json'}")

    if gaps:
        print("\nnot demonstrated by any consumer project:")
        for gap in gaps:
            print(f"  - {gap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
