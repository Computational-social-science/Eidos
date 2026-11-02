#!/usr/bin/env python
"""audit_chains.py -- exercise every Eidos chain on a minimal real input.

WHY THIS EXISTS
    A framework's modules can each import cleanly while the chains between them are
    broken. This audit runs one real operation per chain and reports a verdict, so
    "the framework has a tracking layer" is backed by a run rather than by a file
    that exists. It found two such breaks on first use: `ExperimentTracker` raised
    out of its constructor because `dvc` was not on PATH, and the Quarto bridge
    reported Quarto absent while a working binary sat in the toolchain.

VOCABULARY
    PASS   the chain performed its operation
    FAIL   the chain ran and produced a wrong result
    SKIP   the chain could not run here (optional dependency or input absent)
    ERROR  the chain raised -- a defect in the framework, not in the input

USAGE
    python tools/audit_chains.py [--project roots...] [--json]
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, nullcontext, redirect_stdout
from contextvars import ContextVar
import math
import threading
import importlib.util
import json
import shutil
import sys
import time
import uuid
import tempfile
import traceback
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_OPTIONS = ContextVar("audit_options", default=None)
_EXECUTION_LOCK = threading.Lock()


def _option(flag: str):
    options = _OPTIONS.get()
    return getattr(options, flag.lstrip("-").replace("-", "_"), "") if options else ""


CHAINS: list[tuple[str, Callable, str, tuple]] = []


def chain(name: str, requires: str = "", deps: tuple = ()) -> Callable:
    """Register a chain; main() runs it after argparse has been read.

    Running at import time (the earlier design) meant `--ci` was parsed after every
    chain had already executed with STRICT_REGISTRY=True, so the flag could not change
    any verdict -- which is why the CI audit job stayed red while passing locally.
    """
    def deco(fn):
        CHAINS.append((name, fn, requires, tuple(deps)))
        return fn
    return deco


@chain("registry", "nothing")
def audit_registry():
    from framework.project import load_projects
    # In CI the external checkouts are absent by design: a pointer that resolves to
    # nothing is "not exercised", not "broken". Locally it is still an error, because a
    # detached checkout must not pass as if the project had been audited.
    specs = load_projects(allow_missing=bool(_option("--ci")))
    if not specs:
        return "FAIL", "no project registered"
    missing = [s.name for s in specs.values() if not s.available]
    detail = f"{len(specs)} project(s): " + ", ".join(
        f"{s.name}{'' if s.available else ' [MISSING]'}" for s in specs.values())
    if missing and _option("--ci"):
        # Projects are pointers, deliberately not copies. A CI checkout has none of
        # them, so an absent root is "not exercised", not "broken".
        return "SKIP", detail + " (external checkouts absent)"
    return ("FAIL" if missing else "PASS"), detail


@chain("gates", "pyyaml", deps=("yaml",))
def audit_gates():
    from framework.gates import GateRegistry
    ok = GateRegistry.run_gate("acceptance-gate", {},
                               {"results": {"acc": 0.95}, "criteria": {"acc": 0.90}})
    bad = GateRegistry.run_gate("acceptance-gate", {},
                                {"results": {"acc": 0.50}, "criteria": {"acc": 0.90}})
    skip = GateRegistry.run_gate("ref-check", {"command": ["definitely-not-a-tool-xyz"]},
                                 {"bibliography_path": "x.bib"})
    if not (ok.status == "PASS" and bad.status == "FAIL" and skip.status == "SKIP"):
        return "FAIL", f"expected PASS/FAIL/SKIP, got {ok.status}/{bad.status}/{skip.status}"
    return "PASS", "acceptance PASS+FAIL both correct; missing tool -> SKIP"


@chain("gates+project checker", "a project ref checker")
def audit_project_checker():
    checker = _option("--project-checker")
    if not checker:
        return "SKIP", "no --project-checker given"
    from framework.gates import GateRegistry
    result = GateRegistry.run_gate(
        "ref-check", {"command": [sys.executable, checker]}, {"bibliography_path": "x"})
    if result.status == "PASS":
        return "PASS", f"the project's own checker passed through ref-check: {result.details}"
    return "FAIL", f"{result.status}: {result.details}"


@chain("diagnosis", "nothing")
def audit_diagnosis():
    from framework.diagnosis import diagnose_gate_results
    from framework.gates import GateRegistry

    # Pass the GateResult itself, not its name: the point of the chain is that the
    # gate's details reach the rules. A name-only call would pass even if the
    # adapter were dropped.
    bad = GateRegistry.run_gate("acceptance-gate", {},
                                {"results": {"acc": 0.5}, "criteria": {"acc": 0.9}})
    report = diagnose_gate_results([bad], {"pipeline_id": "audit"})
    diagnoses = getattr(report, "diagnoses", [])
    if not diagnoses:
        return "FAIL", "a failed gate produced no diagnosis"
    first = diagnoses[0]
    if "acc" not in first.root_cause:
        return "FAIL", f"the gate's details did not reach the diagnosis: {first.root_cause!r}"
    return "PASS", f"{len(diagnoses)} diagnosis naming the metric: {first.root_cause}"


@chain("tracking", "mlflow + dvc", deps=("mlflow", "dvc"))
def audit_tracking():
    import hashlib
    from framework import tracking

    tracking._require_mlflow()
    tracking._require_dvc()

    # The worker releases database/cache handles before strict workspace cleanup.
    # Interleaved records exercise identity; a single fluent run cannot prove it.
    with tempfile.TemporaryDirectory(prefix='eidos-tracking-audit-') as tmp:
        result = tracking._operation(Path(tmp), 'smoke', 90)
        expected = {'isolated_runs', 'metrics', 'terminal_states', 'dvc_content', 'private_dvc_cache'}
        checks = result.get('checks') if isinstance(result, dict) else None
        if (not isinstance(checks, dict) or set(checks) != expected
                or not all(type(value) is bool and value for value in checks.values())):
            return 'FAIL', 'tracking did not verify independent runs and actual DVC content'
        fingerprints = result.get('source_sha256_lf')
        paths = {'module': Path(tracking.__file__),
                 'worker': Path(tracking.__file__).with_name('_worker.py')}
        if fingerprints != {key: hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest()
                            for key, path in paths.items()}:
            return 'FAIL', 'tracking smoke executed another source version'
        return 'PASS', 'two isolated runs, verified metrics/terminal states and actual DVC content; worker closed'


@chain("quarto", "quarto binary", deps=("bin:quarto",))
def audit_quarto():
    from framework.quarto_bridge import QuartoBridge
    import shutil

    source = _option("--manuscript")
    # ignore_cleanup_errors: Quarto may still hold a file handle on Windows.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        project = Path(tmp)
        manuscript = project / "manuscript"
        if source:
            shutil.copytree(source, manuscript)
            files = sum(1 for p in manuscript.rglob("*") if p.is_file())
            label = f"project manuscript ({files} files)"
        else:
            manuscript.mkdir()
            (manuscript / "_quarto.yml").write_text("project:\n  type: default\n",
                                                    encoding="utf-8")
            (manuscript / "index.qmd").write_text("# Probe\n\nA sentence.\n",
                                                  encoding="utf-8")
            label = "minimal document"
        bridge = QuartoBridge({"project_root": project})
        if not bridge.quarto_available:
            return "SKIP", "quarto not found by any candidate path"
        result = bridge.render("html")
        html = result.get("formats", {}).get("html", {})
        ok = html.get("success")
        name = Path(bridge.quarto_cmd).name if bridge.quarto_cmd else "?"
        detail = f"{label}; quarto={name}, render ok={ok}"
        if not ok:
            detail += "; " + (html.get("stderr") or html.get("error") or "")[-240:]
        return ("PASS" if ok else "FAIL"), detail


@chain("validity (Gate S)", "pyyaml", deps=("yaml",))
def audit_validity():
    """Gate S must pass a valid register and refuse an under-reported one.

    The fixture is a complete miniature project, so the check is the gate itself, not the
    presence of a file. The second half mutates the fixture in a temporary copy and
    requires a FAIL: a gate that cannot fail is not a gate.
    """
    import shutil
    import tempfile

    from framework.validity import ScientificValidityGate

    fixture = ROOT / "tests" / "fixtures" / "valid_project"
    good = ScientificValidityGate(fixture).run()
    if good.status != "PASS":
        return "FAIL", f"valid fixture did not pass: {good.details['findings']}"

    with tempfile.TemporaryDirectory(prefix="gate_s_") as td:
        copy = Path(td) / "project"
        shutil.copytree(fixture, copy)
        register = copy / "analysis" / "CLAIMS.yaml"
        text = register.read_text(encoding="utf-8")
        register.write_text(text.replace("unresolved: 0", "unresolved: 2"), encoding="utf-8")
        bad = ScientificValidityGate(copy).run()
    if bad.status != "FAIL":
        return "FAIL", "a register with a false objection count was not caught"
    return "PASS", "valid register PASS; overstated count FAIL"


@chain("surrogate (local NO)", "numpy", deps=("numpy",))
def audit_surrogate():
    """A learned short-time stepper must recover a planted fixed point, and fail when
    the training labels are shuffled."""
    import json as _json
    import subprocess

    tool = ROOT / "tools" / "audit_surrogate.py"
    run = subprocess.run([sys.executable, str(tool), "--json"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    if run.returncode != 0:
        return "FAIL", f"planted fixed point not recovered: {run.stderr[-200:]}"
    data = _json.loads(run.stdout)
    control = subprocess.run([sys.executable, str(tool), "--negative-test"], cwd=ROOT,
                             capture_output=True, text=True, timeout=300)
    if control.returncode != 0:
        return "FAIL", "shuffled-label control was not caught"
    return "PASS", (f"{data['within_5pct']}/{data['points']} fixed points within 5%, "
                    f"{data['stable']} stable; shuffled-label control caught")


@chain("demo (NO)", "numpy", deps=("numpy",))
def audit_lab():
    """The interactive lab must be backed by numbers that meet the same tolerance as the
    audit: a demo that drifts from the gate is worse than no demo."""
    from framework.surrogate.demo import build_demo

    data = build_demo()
    if data["max_rel_error"] is None or data["max_rel_error"] >= 0.05:
        return "FAIL", f"lab max relative error {data['max_rel_error']}"
    return "PASS", (f"{len(data['rows'])} λ points, max relative error "
                    f"{100 * data['max_rel_error']:.4f}%")


@chain("decision", "StartLux service")
def audit_decision():
    """A known-answer probe: typed decisions must be correct AND measured.

    A down service is a SKIP, not a FAIL. When it is up, two arithmetic facts the
    model cannot have memorised from the repository decide whether the operator is
    actually answering rather than emitting a plausible-looking probability.
    """
    import statistics
    import time
    from framework.decision import DecisionClient

    client = DecisionClient()
    if not client.health().get("up"):
        return "SKIP", (f"decision service not running at {client.url}; start it with "
                        f"decision-service/scripts/serve.ps1 (weights ~4.3 GB, CC BY-NC 4.0)")

    questions = {
        "prime17": {"type": "noul", "instructions": "Is 17 a prime number?"},
        "larger": {"type": "choice", "instructions": "Which number is larger?",
                   "criteria": {"a": "0.9", "b": "0.11"}},
    }
    latencies = []
    answers = {}
    for _ in range(3):
        started = time.perf_counter()
        answers = client.decide({"text": "Arithmetic facts."}, questions)
        latencies.append((time.perf_counter() - started) * 1000)

    prime = answers["prime17"].probability or 0.0
    larger = answers["larger"].choice_or_none()
    if prime < 0.5 or larger != "a":
        return "FAIL", (f"known-answer probe wrong: p(17 prime)={prime:.3f}, "
                        f"larger={larger!r}")
    median = statistics.median(latencies)
    return "PASS", (f"known answers correct; median {median:.0f} ms for 2 questions "
                    f"(n={len(latencies)}, wall clock)")


@chain("inference", "nothing")
def audit_inference():
    from framework.inference import ModelManager, create_stage_scheduler
    manager = ModelManager({"vram_budget_gb": 12})
    scheduler = create_stage_scheduler({"vram_budget_gb": 12})
    models = scheduler.get_stage_models("evaluation")
    # The budget must be enforced, not merely stored: 4 GB cannot hold the 5 GB
    # llama3.1:8b entry, 12 GB can.
    refuses = ModelManager({"vram_budget_gb": 4}).can_load("llama3.1:8b")
    admits = manager.can_load("llama3.1:8b")
    # Every judgement stage routes to the decision operator; no generative stage does.
    judgement = ("routing", "hypothesis_screening", "gate_triage", "failure_classification")
    wired = all("StartLux-Decision-4B-Q8_0" in scheduler.get_stage_models(s) for s in judgement)
    leaked = any("StartLux" in model
                 for s in ("manuscript_drafting", "hypothesis_generation")
                 for model in scheduler.get_stage_models(s))
    tools_only = all(not scheduler.get_stage_models(s) for s in ("experiment_execution", "evaluation_gates"))
    unqualified = scheduler.describe_stage("evaluation")["task_qualification"] == "UNQUALIFIED"
    if manager.vram_budget != 12 or not models or refuses or not admits or not wired or leaked or not tools_only or not unqualified:
        return "FAIL", (f"budget={manager.vram_budget}, models={models}, "
                        f"refuses@4GB={refuses}, admits@12GB={admits}, "
                        f"judgement_wired={wired}, leaked_into_generation={leaked}")
    return "PASS", ("budget and routing contract checked; execution/gates use tools; "
                    "scientific model stages remain UNQUALIFIED; StartLux is triage only")



def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="exercise every Eidos chain")
    ap.add_argument("--project-checker", default="",
                    help="path to a project's referential checker to pass through ref-check")
    ap.add_argument("--manuscript", default="",
                    help="directory of a real Quarto manuscript to render instead of a minimal probe")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ci", action="store_true",
                    help="treat absent external checkouts as SKIP (no project roots in CI)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--spans", default="",
                    help="write a Langfuse-shaped trace (spans with start/end/status) here")
    ap.add_argument("--only", default="",
                    help="run one chain by name (the monitor refreshes a single node)")
    ap.add_argument("--status-dir", type=Path, default=ROOT/"docs/status",
                    help="owned chain records and marker directory")
    ap.add_argument("--lock-timeout", type=float, default=120.0,
                    help="maximum seconds to wait for another audit; zero refuses immediately")
    args = ap.parse_args(argv)
    if not math.isfinite(args.lock_timeout) or args.lock_timeout < 0:
        ap.error("--lock-timeout must be finite and nonnegative")
    selected = [row for row in CHAINS if not args.only or row[0] == args.only]
    if args.only and not selected:
        selected = [row for row in CHAINS if row[0].startswith(args.only)]
        if len(selected) != 1:
            print(f"unknown or ambiguous chain {args.only!r}; known: {[row[0] for row in CHAINS]}",file=sys.stderr)
            return 2
    if not selected or len({row[0] for row in CHAINS}) != len(CHAINS):
        print("chain registry is empty or contains duplicate names",file=sys.stderr)
        return 2
    if _OPTIONS.get() is not None:
        print("nested audit is busy; no work started",file=sys.stderr)
        return 75
    if not _EXECUTION_LOCK.acquire(timeout=args.lock_timeout):
        print("audit is busy in this process; no work started",file=sys.stderr)
        return 75
    try:
        return _owned(args,selected)
    finally:
        _EXECUTION_LOCK.release()


def _unique_pairs(items):
    value = {}
    for key,item in items:
        if key in value:
            raise ValueError("duplicate state field: "+key)
        value[key] = item
    return value


def _load_state(path):
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=_unique_pairs)
    json.dumps(value,allow_nan=False)
    if not isinstance(value,dict) or not isinstance(value.get("chains"),dict):
        raise ValueError("existing chain state requires a chains mapping")
    for row in value["chains"].values():
        if not isinstance(row,dict) or row.get("status") not in {"PASS","SKIP","FAIL","ERROR"}:
            raise ValueError("invalid previous chain result")
        stamp = row.get("ts")
        if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp < 0:
            raise ValueError("invalid previous chain timestamp")
    return value


def _owned(args,selected):
    status_dir = args.status_dir.resolve()
    state_path = status_dir/"chains.json"
    marker_path = status_dir/"running.json"
    trace_path = Path(args.spans).resolve() if args.spans else None
    if trace_path is not None and (
            trace_path.name.casefold() in {"chains.json","running.json","scheduler.json"}
            or trace_path.name.casefold().startswith(".eidos-export-")
            or trace_path.suffix.lower() != ".json"):
        print("trace must be a JSON trace, not a reserved state or lock path",file=sys.stderr)
        return 2
    if trace_path in (state_path, marker_path):
        print("trace must not overwrite a state or marker file",file=sys.stderr)
        return 2
    from framework.artifacts import output_lock
    from tools import chain_states
    with ExitStack() as ownership:
        targets = [state_path,marker_path] + ([trace_path] if trace_path else [])
        resources = [path.parent/("audit-target-"+path.name) for path in targets]
        try:
            for resource in sorted(set(resources)):
                ownership.enter_context(output_lock(resource,timeout=args.lock_timeout))
        except TimeoutError:
            print("audit is busy; no chain ran or evidence was refreshed",file=sys.stderr)
            return 75
        try:
            previous = _load_state(state_path)
            if trace_path is not None and trace_path.exists():
                trace = json.loads(trace_path.read_text(encoding="utf-8"),object_pairs_hook=_unique_pairs)
                json.dumps(trace,allow_nan=False)
                if (not isinstance(trace,dict) or not isinstance(trace.get("trace"),dict)
                        or trace["trace"].get("name") != "eidos.chains"
                        or not isinstance(trace.get("spans"),list)):
                    raise ValueError("existing trace target is not an Eidos chain trace")
        except (OSError,ValueError,TypeError,OverflowError) as exc:
            print("previous evidence is unreadable; preserved: "+str(exc),file=sys.stderr)
            return 2
        token = _OPTIONS.set(args)
        owner = None
        try:
            owner = chain_states.mark_running(path=marker_path)
            return _execute(args,selected,state_path,trace_path,previous)
        finally:
            try:
                if owner is not None:
                    chain_states.clear_running(path=marker_path,owner=owner)
            finally:
                _OPTIONS.reset(token)


def _execute(args,selected,state_path,trace_path,previous) -> int:
    results = []
    for name, fn, requires, deps in selected:
        started = time.time()
        try:
            with redirect_stdout(sys.stderr) if args.json else nullcontext():
                status, detail = fn()
            if status not in {"PASS","SKIP","FAIL","ERROR"}:
                raise ValueError("unknown chain verdict")
        except ImportError as exc:
            status, detail = "SKIP", f"optional dependency missing: {exc}"
        except (Exception, SystemExit) as exc:  # a chain must return a verdict, not exit the audit
            status = "ERROR"
            detail = f"{type(exc).__name__}: {exc}"
            if args.verbose:
                traceback.print_exc()
        ended = time.time()
        # A dependency counts as missing only when it explains a non-pass: quarto is found
        # through QUARTO_BIN rather than PATH, and calling that "missing" while the chain
        # passes would be a false accusation.
        absent = [dep for dep in deps
                  if (shutil.which(dep[4:]) is None if dep.startswith("bin:")
                      else importlib.util.find_spec(dep) is None)]
        missing = absent if status != "PASS" else []
        results.append({"chain": name, "status": status, "detail": str(detail),
                        "requires": requires, "deps": list(deps), "missing": missing,
                        "start_ts": started, "end_ts": ended,
                        "ms": round((ended - started) * 1000, 1)})

    # Per-chain state with its own timestamp: the monitor needs to know when THIS chain
    # last ran, not when the trace file was last touched.
    merged = dict(previous.get("chains") or {})
    for row in results:
        merged[row["chain"]] = {"status": row["status"], "ts": row["end_ts"],
                                "ms": row["ms"], "requires": row["requires"],
                                "deps": row.get("deps") or [],
                                "missing": row.get("missing") or [],
                                "detail": row["detail"][:240]}
    from framework.artifacts import atomic_output
    with atomic_output(state_path) as temporary:
        temporary.write_text(json.dumps({"ts": max(r["end_ts"] for r in results),
                                         "chains": merged}, indent=2),encoding="utf-8")

    width = max(len(r["chain"]) for r in results) if results else 10

    if args.spans:
        started = min(r["start_ts"] for r in results)
        ended = max(r["end_ts"] for r in results)
        doc = {
            "trace": {"id": uuid.uuid4().hex, "name": "eidos.chains",
                      "start_ts": started, "end_ts": ended,
                      "duration_ms": round((ended - started) * 1000, 1),
                      "status": "OK" if not any(
                          r["status"] in ("FAIL", "ERROR") for r in results) else "ERROR",
                      "attributes": {"chains": len(results)}},
            "spans": [{"id": uuid.uuid4().hex, "name": r["chain"],
                       "start_ts": r["start_ts"], "end_ts": r["end_ts"],
                       "duration_ms": r["ms"], "status": r["status"],
                       "attributes": {"detail": r["detail"], "requires": r["requires"]}}
                      for r in results],
        }
        with atomic_output(trace_path) as temporary:
            temporary.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for row in results:
            print(f"{row['status']:<5} {row['chain']:<{width}}  {row['detail']}")

    bad = [r for r in results if r["status"] in ("FAIL", "ERROR")]
    if not args.json:
        passed = sum(1 for r in results if r["status"] == "PASS")
        skipped = sum(1 for r in results if r["status"] == "SKIP")
        # A SKIP is not evidence, and calling the run "8/8 healthy" would hide that.
        print(f"\n{passed} PASS, {skipped} SKIP, {len(bad)} FAIL/ERROR")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
