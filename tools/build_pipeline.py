"""Compose the pipeline document the status page renders.

One artefact, several sources, no duplication:

    docs/traces/latest.json   spans from the last chain audit (Langfuse-shaped)
    docs/_coupling.json       the import graph, measured by AST
    docs/RENDER_CHECK.json    the last end-to-end render
    docs/SELF_AUDIT.json      the framework's own Gate S verdict
    the registry              consumers and their Gate S verdicts (measured here)

Output: docs/pipeline.json. The page reads it once when opened from disk and polls
`/api/pipeline` when it is served by tools/serve_site.py, so the same file feeds a static
snapshot and a near-real-time view.

Usage:
    python tools/build_pipeline.py            # compose from existing artefacts
    python tools/build_pipeline.py --probe    # also re-probe the live services
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "pipeline.json"


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def coupling_graph() -> dict:
    data = read_json(ROOT / "docs" / "_coupling.json", {}) or {}
    edges = []
    for kind in ("hard", "soft"):
        for source, targets in (data.get(kind) or {}).items():
            for target in targets or []:
                edges.append({"source": source, "target": target, "kind": kind})
    # process/network map a module to a count, not to a target: they are node attributes.
    names = set()
    for kind in ("hard", "soft", "process", "network"):
        block = data.get(kind) or {}
        if isinstance(block, dict):
            names |= set(block) | {t for v in block.values()
                                   if isinstance(v, list) for t in v}
    nodes = sorted(names | {e["source"] for e in edges} | {e["target"] for e in edges})
    attrs = {n: {"process": int((data.get("process") or {}).get(n, 0)),
                 "network": int((data.get("network") or {}).get(n, 0)),
                 "fan_in": int((data.get("fan_in") or {}).get(n, 0))} for n in nodes}
    return {"nodes": nodes, "edges": edges, "attrs": attrs,
            "cycles": data.get("cycles", 0),
            "fan_in": data.get("fan_in", {}),
            "absolute_paths": sum((data.get("absolute_paths") or {}).values())}


def levels(nodes: list[str], edges: list[dict]) -> dict[str, int]:
    """Longest-path layering on the hard/soft subgraph; cycles are already gated to zero."""
    deps: dict[str, set[str]] = {n: set() for n in nodes}
    for e in edges:
        if e["kind"] in ("hard", "soft") and e["source"] in deps:
            deps[e["source"]].add(e["target"])
    level: dict[str, int] = {}

    def depth(n: str, seen: tuple[str, ...] = ()) -> int:
        """Distance from the leaves: a module sits one level above everything it imports."""
        if n in level:
            return level[n]
        if n in seen:            # defensive: the gate says zero cycles, but never hang
            return 0
        value = 0 if not deps[n] else 1 + max(depth(p, seen + (n,)) for p in deps[n])
        level[n] = value
        return value

    for n in nodes:
        depth(n)
    return level


# The seven delivery layers and the chains that report into each. Kept beside the chain list so
# a page cannot invent its own grouping: the document and the monitor read the same structure.
LAYERS = [
    {"name": "Multi-format delivery", "chains": ["quarto"]},
    {"name": "Dual quality gates",
     "chains": ["gates", "gates+project checker", "validity (Gate S)"]},
    {"name": "Analysis and critique", "chains": ["diagnosis"]},
    {"name": "Decision layer", "chains": ["decision"]},
    {"name": "Evaluation and robustness", "chains": ["demo (NO)", "surrogate (local NO)"]},
    {"name": "Orchestration", "chains": ["registry", "tracking"]},
    {"name": "Inference serving", "chains": ["inference"]},
]


def chain_modules() -> dict[str, list[str]]:
    """Which framework modules each chain exercises, read from the audit's own source.

    The mapping is structural, not declared: it walks the AST of audit_chains.py, finds
    each `@chain(...)` function, and collects the imports inside its body. A module shared
    by several chains is where a change to one chain can break another.
    """
    import ast

    source = (ROOT / "tools" / "audit_chains.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    mapping: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = []
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Name) and target.id == "chain":
                args = getattr(decorator, "args", [])
                if args and isinstance(args[0], ast.Constant):
                    names.append(str(args[0].value))
        if not names:
            continue
        modules = set()
        for child in ast.walk(node):
            if isinstance(child, ast.ImportFrom) and child.module:
                if child.module.startswith(("framework", "tools")):
                    modules.add(child.module)
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    if alias.name.startswith(("framework", "tools")):
                        modules.add(alias.name)
        for name in names:
            mapping[name] = sorted(modules)
    return mapping


def consumers(specs: dict | None = None) -> list[dict]:
    from framework.project import load_projects
    from tools.consumer_snapshot import capture_inputs

    rows = []
    if specs is None:
        specs = load_projects(allow_missing=True)
    for name, spec in sorted(specs.items()):
        before = capture_inputs(spec)
        row = {"name": name, "root": str(spec.root), "available": spec.available,
               "gate_s": "—", "expected": None, "generated": None,
               "input_digest": None, "input_error": before["error"],
               # The role says what kind of evidence this project is: a measured LLM consumer,
               # a negative control, or a chain fixture. Without it four entries look identical.
               "role": (spec.role or "").strip()}
        register = getattr(spec, "validity_register", None)
        document = getattr(spec, "validity_document", None)
        row["expected"] = getattr(spec, "expected_gate_s", None)
        if spec.available and register and document and before["digest"]:
            docs = [d.strip() for d in str(document).split(",") if d.strip()]
            args = [sys.executable, "tools/audit_validity.py", "--project", str(spec.root),
                    "--register", register]
            for doc in docs:
                args += ["--document", doc]
            try:
                run = subprocess.run(args + ["--json"], cwd=ROOT, capture_output=True,
                                     text=True, encoding="utf-8", timeout=900)
                checked = json.loads(run.stdout)
                verdict = checked.get("status", "ERROR")
                row["gate_s"] = verdict if ((verdict == "PASS" and run.returncode == 0)
                                              or (verdict == "FAIL" and run.returncode == 1)) else "ERROR"
                row["checked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
                row["findings"] = checked.get("findings", [])
            except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
                row["gate_s"] = "ERROR"
            after = capture_inputs(spec)
            if not before["digest"] or before != after:
                row["gate_s"] = "ERROR"
                row["input_error"] = after["error"] or "inputs changed during verification"
            else:
                row["input_digest"] = before["digest"]
        elif row["expected"]:
            row["gate_s"] = "ERROR"
        evidence = Path(row["root"]) / "docs" / "evidence.json"
        payload = read_json(evidence, {}) if spec.available else {}
        row["generated"] = payload.get("generated") or payload.get("recorded_at") or payload.get("finished_at")
        rows.append(row)
    return rows


def audit_summary(audit: dict) -> dict:
    return {"gate_s": (audit.get("self_gate_s") or {}).get("status"),
            "fixture_status": (audit.get("gate_s") or {}).get("fixture_status"),
            "chains": (audit.get("chains") or {}).get("total"),
            "tests": (audit.get("tests") or {}).get("passed")}


def probe() -> dict:
    state = {}

    def get(url: str, timeout: float = 2.0, key: str | None = None):
        request = urllib.request.Request(url)
        if key:
            request.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            # A service that answers 401 is running and refusing, not absent. Reporting it as DOWN
            # is how a healthy runtime sat in ALARM for a day: the probe sent no key and read the
            # refusal as a corpse.
            return exc.code, {"error": f"HTTP {exc.code}"}
        except Exception as exc:  # noqa: BLE001 - absence is the datum
            return 0, {"error": type(exc).__name__}

    code, body = get("http://127.0.0.1:8090/health")
    state["decision"] = {"up": bool(code == 200 and body.get("status") == "ok"),
                         "model": body.get("model")}
    key = os.environ.get("HERMES_LOCAL_LLAMACPP_KEY") or os.environ.get("LLAMACPP_API_KEY")
    code, body = get("http://127.0.0.1:18434/v1/models", key=key)
    state["runtime_18434"] = {"up": code in (200, 401, 403),
                              "note": ("auth required" if code in (401, 403)
                                       else None if code == 200 else body.get("error"))}
    return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true", help="re-probe live services")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    graph = coupling_graph()
    graph["levels"] = levels(graph["nodes"], graph["edges"])
    traces = read_json(ROOT / "docs" / "traces" / "latest.json", {}) or {}
    render = read_json(ROOT / "docs" / "RENDER_CHECK.json", {}) or {}
    render = render if isinstance(render, dict) else {}
    audit = read_json(ROOT / "docs" / "SELF_AUDIT.json", {}) or {}
    audit = audit if isinstance(audit, dict) else {}
    from framework.project import load_projects
    from tools.consumer_snapshot import atomic_json, registry_digest, SCOPE
    specs = load_projects(allow_missing=True)

    doc = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "coupling": graph,
        "trace": traces.get("trace"),
        "spans": traces.get("spans", []),
        "chains": [{"name": s["name"], "status": s["status"], "ms": s["duration_ms"],
                    "detail": s["attributes"]["detail"]} for s in traces.get("spans", [])],
        "render": render,
        "self_audit": audit_summary(audit),
        "consumers": consumers(specs),
        "consumer_snapshot": {"schema": 1, "registry_digest": registry_digest(specs), "scope": SCOPE},
        "chain_modules": chain_modules(),
        "layers": LAYERS,
        "health": probe() if args.probe else {},
    }
    out = Path(args.out)
    atomic_json(out, doc)
    print(f"chains {len(doc['chains'])}, modules {len(graph['nodes'])}, "
          f"edges {len(graph['edges'])}, consumers {len(doc['consumers'])}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
