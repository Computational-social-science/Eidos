"""
Quality Gates Module
Wrappers for BootLoops (quantitative) and Inspect/DeepEval/Promptfoo/Ragas (semantic)
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
import os
import sys
import yaml
from abc import ABC, abstractmethod


def _bootloops_from_user_config() -> Optional[str]:
    """The toolkit's own discovery file, so no machine path is compiled in.

    BootLoops documents `~/.bootloops/config.json` as the place that records where the
    install lives; reading it keeps this framework portable (a CI checkout simply has
    no such file and gets the error below).
    """
    path = Path.home() / ".bootloops" / "config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    root = data.get("bootloops_root") or data.get("root")
    return str(root) if root else None


def resolve_bootloops_root(config: Optional[Dict[str, Any]] = None) -> Path:
    """Resolve the shared BootLoops install; never a vendored copy.

    Order: $BOOTLOOPS_ROOT -> config quality_gates.quantitative.root ->
    ~/.bootloops/config.json. Raises when none exists, because a project that
    declares quantitative gates but has no toolbox is misconfigured, and a
    silent pass would be worse than the error.
    """
    from_env = os.environ.get("BOOTLOOPS_ROOT")
    from_cfg = (
        ((config or {}).get("quality_gates") or {})
        .get("quantitative", {})
        .get("root")
    )
    for candidate in (from_env, from_cfg, _bootloops_from_user_config()):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise FileNotFoundError(
        "BootLoops root not found (tried $BOOTLOOPS_ROOT, config "
        "quality_gates.quantitative.root, ~/.bootloops/config.json). "
        "Install BootLoops or point BOOTLOOPS_ROOT at it."
    )

@dataclass
class GateResult:
    """Result of a quality gate check.

    ``status`` is the honest verdict; ``passed`` is a convenience flag that is true
    only for PASS. A missing external tool yields SKIP, never FAIL: a tool that is
    not installed has not judged the artefact, and failing it would train a reader
    to ignore the gate (the vocabulary is keystroke-observatory's, which learned
    this the hard way).
    """
    gate_name: str
    passed: bool
    score: float = 0.0
    details: Dict[str, Any] = None
    artifacts: List[str] = None
    human_review_required: bool = False
    status: str = "PASS"

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.artifacts is None:
            self.artifacts = []
        # A gate that returns passed=False without naming a status is a FAIL, not
        # a PASS with a negative score.
        if self.status == "PASS" and not self.passed:
            self.status = "FAIL"


class ToolMissing(RuntimeError):
    """The gate's external command is not installed.

    Distinct from FAIL: the artefact was never examined. Carries the tool name and
    an install hint so the skip is actionable.
    """

    def __init__(self, tool: str, hint: str = ""):
        self.tool = tool
        self.hint = hint
        super().__init__(f"external tool not found: {tool}" + (f" ({hint})" if hint else ""))

class BaseGate(ABC):
    """Abstract base class for quality gates"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    def run(self, context: Dict[str, Any]) -> GateResult:
        """Run the gate check"""
        pass
    
    def _run_cmd(self, cmd: List[str], cwd: Path = None, timeout: int = 300) -> subprocess.CompletedProcess:
        """Run a command with timeout.

        A missing executable is raised as ToolMissing rather than escaping as a
        bare FileNotFoundError: in the latter case one absent tool aborted the
        entire gate suite with a traceback (verified on this host for both
        ``ref-check`` and ``vale``).
        """
        try:
            return subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
        except FileNotFoundError as exc:
            raise ToolMissing(cmd[0]) from exc


def _skipped(gate_name: str, tool: str, install: str) -> GateResult:
    """A gate whose external tool is absent: not a pass, not a failure."""
    return GateResult(
        gate_name=gate_name,
        passed=False,
        score=0.0,
        details={"missing_tool": tool, "install": install,
                 "meaning": "the artefact was not examined"},
        human_review_required=False,
        status="SKIP",
    )

class AcceptanceGate(BaseGate):
    """BootLoops acceptance-gate: verifies computational results meet criteria.

    A threshold alone does not encode direction: accuracy must be at least its
    threshold, while an error rate must be at most its threshold. Accepting a
    bare number and assuming ">=" silently passes every "lower is better"
    metric (a 0.12 error rate against a 0.05 ceiling passed before this fix).
    Criteria may therefore be either:

        {"acc": 0.90}                                  # default: value >= 0.90
        {"silent": {"threshold": 0.05, "direction": "<="}}

    A bare number keeps the historical ">=" reading, so existing project configs
    stay valid.
    """

    def run(self, context: Dict[str, Any]) -> GateResult:
        results = context.get("results", {})
        criteria = context.get("criteria", {})

        passed = True
        details = {}

        for metric, spec in criteria.items():
            if isinstance(spec, dict):
                threshold = spec.get("threshold")
                direction = spec.get("direction", ">=")
            else:
                threshold = spec
                direction = ">="

            value = results.get(metric)
            if value is None:
                details[metric] = {"status": "MISSING", "direction": direction}
                passed = False
                continue

            if direction == "<=":
                met = value <= threshold
            elif direction == ">=":
                met = value >= threshold
            elif direction == "<":
                met = value < threshold
            elif direction == ">":
                met = value > threshold
            else:
                details[metric] = {"status": f"BAD_DIRECTION({direction})"}
                passed = False
                continue

            details[metric] = {
                "value": value,
                "threshold": threshold,
                "direction": direction,
                "met": met,
            }
            if not met:
                passed = False

        met_count = sum(
            1 for d in details.values() if isinstance(d, dict) and d.get("met")
        )
        return GateResult(
            gate_name="acceptance-gate",
            passed=passed,
            score=met_count / max(len(details), 1),
            details=details,
            human_review_required=not passed,
        )

class PlantedTruthGate(BaseGate):
    """BootLoops planted-truth: synthetic controls with known ground truth"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        # Context should have: planted_controls, expected_outputs
        planted = context.get("planted_controls", [])
        if not planted:
            return GateResult(
                gate_name="planted-truth",
                passed=False,
                score=0.0,
                details={"error": "No planted controls provided"},
                human_review_required=True
            )
        
        passed_count = 0
        details = {}
        
        for i, control in enumerate(planted):
            expected = control.get("expected")
            actual = control.get("actual")
            matched = expected == actual
            details[f"control_{i}"] = {"expected": expected, "actual": actual, "matched": matched}
            if matched:
                passed_count += 1
        
        score = passed_count / len(planted)
        return GateResult(
            gate_name="planted-truth",
            passed=score == 1.0,
            score=score,
            details=details,
            human_review_required=score < 1.0
        )

class IndependenceBookkeepingGate(BaseGate):
    """BootLoops independence-bookkeeping: tracks statistical independence"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        # Checks: no data reuse, proper splits, no leakage
        checks = {
            "train_test_split": context.get("train_test_split", False),
            "no_data_leakage": context.get("no_data_leakage", False),
            "proper_cross_validation": context.get("proper_cross_validation", False),
            "independent_seeds": context.get("independent_seeds", False),
        }
        
        passed = all(checks.values())
        return GateResult(
            gate_name="independence-bookkeeping",
            passed=passed,
            score=sum(checks.values()) / len(checks),
            details=checks,
            human_review_required=not passed
        )

class TimingDisciplineGate(BaseGate):
    """BootLoops timing-discipline: computational budget tracking"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        budget = context.get("compute_budget", {})
        actual = context.get("actual_compute", {})
        
        checks = {}
        for resource in ["gpu_hours", "cpu_hours", "memory_gb", "wall_time"]:
            budgeted = budget.get(resource, 0)
            used = actual.get(resource, 0)
            if budgeted > 0:
                checks[resource] = {"budgeted": budgeted, "used": used, "within": used <= budgeted}
        
        passed = all(c.get("within", True) for c in checks.values())
        return GateResult(
            gate_name="timing-discipline",
            passed=passed,
            score=sum(1 for c in checks.values() if c.get("within", True)) / max(len(checks), 1),
            details=checks,
            human_review_required=not passed
        )

class ToolStewardshipGate(BaseGate):
    """BootLoops tool-stewardship: tool usage tracking and provenance"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        tool_log = context.get("tool_log", [])
        
        checks = {
            "tools_versioned": all(t.get("version") for t in tool_log),
            "provenance_recorded": all(t.get("provenance") for t in tool_log),
            "no_untracked_tools": True  # Would check against registry
        }
        
        passed = all(checks.values())
        return GateResult(
            gate_name="tool-stewardship",
            passed=passed,
            score=sum(checks.values()) / len(checks),
            details=checks,
            human_review_required=not passed
        )

class ProseLintGate(BaseGate):
    """BootLoops prose-lint: manuscript style and consistency"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        manuscript_path = context.get("manuscript_path")
        if not manuscript_path:
            return GateResult(
                gate_name="prose-lint",
                passed=False,
                score=0.0,
                details={"error": "No manuscript path provided"},
                human_review_required=True
            )
        
        # Run vale (or the command a project configures). A missing tool is a SKIP:
        # the manuscript was never examined.
        cmd = self.config.get("command") or ["vale", str(manuscript_path)]
        try:
            result = self._run_cmd(cmd, timeout=120)
        except ToolMissing:
            return _skipped("prose-lint", cmd[0],
                            "install vale (https://vale.sh) or set quality_gates.command")

        return GateResult(
            gate_name="prose-lint",
            passed=result.returncode == 0,
            score=1.0 if result.returncode == 0 else 0.0,
            details={"stdout": result.stdout, "stderr": result.stderr, "command": cmd},
            artifacts=[str(manuscript_path)],
            human_review_required=result.returncode != 0
        )

class RefCheckGate(BaseGate):
    """BootLoops ref-check: bibliography verification"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        bib_path = context.get("bibliography_path")
        if not bib_path:
            return GateResult(
                gate_name="ref-check",
                passed=False,
                score=0.0,
                details={"error": "No bibliography path"},
                human_review_required=True
            )
        
        # Run the ref-check tool, or the command a project configures.
        cmd = self.config.get("command") or ["ref-check", str(bib_path)]
        try:
            result = self._run_cmd(cmd, timeout=60)
        except ToolMissing:
            return _skipped("ref-check", cmd[0],
                            "install the BootLoops ref-check tool or set quality_gates.command")

        return GateResult(
            gate_name="ref-check",
            passed=result.returncode == 0,
            score=1.0 if result.returncode == 0 else 0.0,
            details={"stdout": result.stdout, "stderr": result.stderr, "command": cmd},
            artifacts=[str(bib_path)],
            human_review_required=result.returncode != 0
        )

class InspectGate(BaseGate):
    """Inspect AI: agent and tool-use evaluation"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        eval_config = context.get("inspect_config", {})
        dataset = context.get("eval_dataset")
        
        if not dataset:
            return GateResult(
                gate_name="inspect",
                passed=False,
                score=0.0,
                details={"error": "No evaluation dataset provided"},
                human_review_required=True
            )
        
        # Run inspect eval
        cmd = ["inspect", "eval", dataset, "--model", "local"]
        if "model" in eval_config:
            cmd.extend(["--model", eval_config["model"]])
        
        try:
            result = self._run_cmd(cmd, timeout=600)
        except ToolMissing:
            return _skipped("inspect", cmd[0], "pip install inspect-ai")
        passed = result.returncode == 0
        score = 1.0 if passed else 0.0
        
        return GateResult(
            gate_name="inspect",
            passed=passed,
            score=score,
            details={"stdout": result.stdout[:2000], "stderr": result.stderr[:2000]},
            human_review_required=not passed
        )

class DeepEvalGate(BaseGate):
    """DeepEval: pytest-style LLM/RAG/Agent evaluation"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        test_file = context.get("deepeval_test_file")
        metrics = context.get("deepeval_metrics", ["faithfulness", "answer_relevancy", "contextual_precision"])
        
        if not test_file:
            return GateResult(
                gate_name="deepeval",
                passed=False,
                score=0.0,
                details={"error": "No DeepEval test file provided"},
                human_review_required=True
            )
        
        # Run pytest with deepeval
        cmd = ["pytest", test_file, "-v", "--tb=short"]
        try:
            result = self._run_cmd(cmd, timeout=600)
        except ToolMissing:
            return _skipped("deepeval", cmd[0], "pip install deepeval pytest")
        
        passed = result.returncode == 0
        # Parse pytest output for pass rate
        pass_rate = 1.0 if passed else 0.0
        
        return GateResult(
            gate_name="deepeval",
            passed=passed,
            score=pass_rate,
            details={
                "metrics": metrics,
                "stdout": result.stdout[-3000:],
                "stderr": result.stderr[-3000:]
            },
            human_review_required=not passed
        )

class PromptfooGate(BaseGate):
    """Promptfoo: prompt comparison and red-teaming"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        config_file = context.get("promptfoo_config")
        
        if not config_file:
            return GateResult(
                gate_name="promptfoo",
                passed=False,
                score=0.0,
                details={"error": "No promptfoo config provided"},
                human_review_required=True
            )
        
        cmd = ["promptfoo", "eval", "-c", config_file]
        try:
            result = self._run_cmd(cmd, timeout=300)
        except ToolMissing:
            return _skipped("promptfoo", cmd[0], "npm install -g promptfoo")
        
        passed = result.returncode == 0
        return GateResult(
            gate_name="promptfoo",
            passed=passed,
            score=1.0 if passed else 0.0,
            details={"stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]},
            human_review_required=not passed
        )

class RagasGate(BaseGate):
    """Ragas: RAG-specific evaluation metrics"""
    
    def run(self, context: Dict[str, Any]) -> GateResult:
        dataset = context.get("ragas_dataset")
        metrics = context.get("ragas_metrics", [
            "faithfulness", "context_precision", "context_recall", 
            "answer_relevancy", "answer_correctness"
        ])
        
        if not dataset:
            return GateResult(
                gate_name="ragas",
                passed=False,
                score=0.0,
                details={"error": "No RAGAS dataset provided"},
                human_review_required=True
            )
        
        # A missing library is a SKIP, not a FAIL: nothing was evaluated. The old
        # form shelled out to `python` and turned an ImportError into a red gate.
        import importlib.util
        if importlib.util.find_spec("ragas") is None:
            return _skipped("ragas", "ragas", "pip install ragas datasets")

        cmd = [sys.executable, "-c", f"""
from ragas import evaluate
from datasets import load_dataset
dataset = load_dataset("{dataset}")
result = evaluate(dataset, metrics={metrics})
print(result)
"""]
        result = self._run_cmd(cmd, timeout=600)
        
        passed = result.returncode == 0
        score = 1.0 if passed else 0.0
        
        return GateResult(
            gate_name="ragas",
            passed=passed,
            score=score,
            details={"metrics": metrics, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]},
            human_review_required=not passed
        )

class GateRegistry:
    """Registry of all available gates"""
    
    GATES = {
        # BootLoops quantitative gates
        "acceptance-gate": AcceptanceGate,
        "planted-truth": PlantedTruthGate,
        "independence-bookkeeping": IndependenceBookkeepingGate,
        "timing-discipline": TimingDisciplineGate,
        "tool-stewardship": ToolStewardshipGate,
        "prose-lint": ProseLintGate,
        "ref-check": RefCheckGate,
        # Semantic gates
        "inspect": InspectGate,
        "deepeval": DeepEvalGate,
        "promptfoo": PromptfooGate,
        "ragas": RagasGate,
    }
    
    @classmethod
    def get_gate(cls, name: str, config: Dict) -> BaseGate:
        if name not in cls.GATES:
            raise ValueError(f"Unknown gate: {name}. Available: {list(cls.GATES.keys())}")
        return cls.GATES[name](config)
    
    @classmethod
    def run_gate(cls, name: str, config: Dict, context: Dict) -> GateResult:
        gate = cls.get_gate(name, config)
        return gate.run(context)
    
    @classmethod
    def run_suite(cls, gate_names: List[str], config: Dict, context: Dict) -> List[GateResult]:
        """Run multiple gates in sequence.

        A gate that raises must not take the suite down: before this, an absent
        external tool aborted the whole run with a traceback and the other gates
        never reported. A crash is an ERROR, distinct from a FAIL: nothing was
        judged.
        """
        results = []
        for name in gate_names:
            try:
                result = cls.run_gate(name, config, context)
            except ToolMissing as exc:
                result = _skipped(name, exc.tool, exc.hint)
            except Exception as exc:  # noqa: BLE001 - a crash is a verdict, not a stop
                result = GateResult(
                    gate_name=name,
                    passed=False,
                    score=0.0,
                    details={"error": f"{type(exc).__name__}: {exc}"},
                    human_review_required=True,
                    status="ERROR",
                )
            results.append(result)
            # Stop on a real failure or a crash; a SKIP is not a failure.
            if result.status in ("FAIL", "ERROR") and config.get("stop_on_failure", False):
                break
        return results

def run_quantitative_gates(config: Dict, context: Dict) -> List[GateResult]:
    """Run all BootLoops quantitative gates"""
    quantitative_gates = [
        "acceptance-gate",
        "planted-truth", 
        "independence-bookkeeping",
        "timing-discipline",
        "tool-stewardship",
        "prose-lint",
        "ref-check"
    ]
    return GateRegistry.run_suite(quantitative_gates, config, context)

def run_semantic_gates(config: Dict, context: Dict) -> List[GateResult]:
    """Run all semantic evaluation gates"""
    semantic_gates = [
        "inspect",
        "deepeval",
        "promptfoo",
        "ragas"
    ]
    return GateRegistry.run_suite(semantic_gates, config, context)