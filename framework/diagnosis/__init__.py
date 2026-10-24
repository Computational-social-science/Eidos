"""
Failure Diagnosis Module
Produces structured, actionable diagnosis reports when quality gates fail
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import yaml
from datetime import datetime

class FailureSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class FailureCategory(Enum):
    DATA = "data"
    MODEL = "model"
    COMPUTE = "compute"
    METHODOLOGY = "methodology"
    CONFIGURATION = "configuration"
    ENVIRONMENT = "environment"
    GATE_LOGIC = "gate_logic"

#: Rules for the monitor's own signals. They live here, not in the watcher, so a failing
#: service is diagnosed by the same engine that diagnoses a failing gate.
MONITOR_RULES = {
    "service:runtime_18434": {
        "category": FailureCategory.ENVIRONMENT,
        "common_causes": {
            "no_answer": "the managed llama.cpp runtime is not answering on 18434",
            "auth": "the runtime answers but rejects the API key",
        },
        "actions": ["start the managed runtime", "if it is already up, check the API key"],
    },
    "service:decision_service": {
        "category": FailureCategory.ENVIRONMENT,
        "common_causes": {"no_answer": "the decision service is not answering on 8090"},
        "actions": ["start the decision service", "check its llama.cpp backend"],
    },
    "service:quarto": {
        "category": FailureCategory.CONFIGURATION,
        "common_causes": {"missing": "Quarto is not locatable from this process"},
        "actions": ["set QUARTO_BIN", "install Quarto"],
    },
    "service:dvc": {
        "category": FailureCategory.CONFIGURATION,
        "common_causes": {"missing": "the dvc package is not importable"},
        "actions": ["install dvc into the running interpreter"],
    },
    "chain": {
        "category": FailureCategory.ENVIRONMENT,
        "common_causes": {
            "assertion": "the chain ran and its assertion did not hold",
            "absent": "a tool or checkout the chain needs is absent",
            "timeout": "the chain did not finish inside its budget",
        },
        "actions": ["read the span detail", "rerun that chain alone with --verbose"],
    },
    "service:mlflow": {
        "category": FailureCategory.CONFIGURATION,
        "common_causes": {"missing": "the mlflow package is not importable"},
        "actions": ["install mlflow into the running interpreter"],
    },
}


@dataclass
class FailureDiagnosis:
    """Structured failure diagnosis report"""
    gate_name: str
    severity: FailureSeverity
    category: FailureCategory
    summary: str
    root_cause: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    related_gates: List[str] = field(default_factory=list)
    estimated_effort: str = "unknown"  # "low", "medium", "high", "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    context_snapshot: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DiagnosisReport:
    """Complete diagnosis report for a failed pipeline run"""
    pipeline_id: str
    failed_gates: List[str]
    diagnoses: List[FailureDiagnosis]
    overall_severity: FailureSeverity
    recommended_next_steps: List[str] = field(default_factory=list)
    can_retry_automatically: bool = False
    estimated_total_effort: str = "unknown"
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

class FailureDiagnosisEngine:
    """Diagnoses gate failures and produces actionable reports"""
    
    # Gate-specific diagnosis rules
    DIAGNOSIS_RULES = {
        "acceptance-gate": {
            "category": FailureCategory.METHODOLOGY,
            "common_causes": {
                "metric_below_threshold": "Result metric below acceptance threshold",
                "missing_metric": "Required metric not computed",
                "threshold_too_strict": "Acceptance threshold may be too aggressive"
            },
            "actions": [
                "Verify metric computation is correct",
                "Check if threshold is appropriate for the problem",
                "Consider relaxing threshold or improving method"
            ]
        },
        "planted-truth": {
            "category": FailureCategory.METHODOLOGY,
            "common_causes": {
                "control_mismatch": "Planted control output doesn't match expected",
                "control_not_executed": "Planted control wasn't actually run",
                "expected_output_wrong": "Expected output in control definition is incorrect"
            },
            "actions": [
                "Verify planted control execution completed",
                "Check expected output in control definition",
                "Run control in isolation to debug"
            ]
        },
        "independence-bookkeeping": {
            "category": FailureCategory.METHODOLOGY,
            "common_causes": {
                "train_test_leakage": "Train/test split has leakage",
                "improper_cv": "Cross-validation not properly independent",
                "seed_reuse": "Same seed used across independent runs"
            },
            "actions": [
                "Verify train/test splits are truly independent",
                "Check cross-validation implementation",
                "Ensure unique seeds for each independent run"
            ]
        },
        "timing-discipline": {
            "category": FailureCategory.COMPUTE,
            "common_causes": {
                "budget_exceeded": "Compute budget exceeded",
                "no_budget_tracking": "No budget tracking implemented",
                "inefficient_computation": "Algorithm not optimized for budget"
            },
            "actions": [
                "Implement compute budget tracking",
                "Optimize algorithm or reduce scope",
                "Request budget increase with justification"
            ]
        },
        "tool-stewardship": {
            "category": FailureCategory.ENVIRONMENT,
            "common_causes": {
                "untracked_tools": "Tools used without version tracking",
                "missing_provenance": "Tool provenance not recorded",
                "version_conflict": "Tool version conflicts"
            },
            "actions": [
                "Implement tool version tracking",
                "Record tool provenance for all steps",
                "Resolve version conflicts"
            ]
        },
        "prose-lint": {
            "category": FailureCategory.CONFIGURATION,
            "common_causes": {
                "style_violations": "Manuscript style violations",
                "formatting_errors": "Formatting inconsistencies",
                "vale_config_missing": "Vale configuration missing"
            },
            "actions": [
                "Run vale to see specific violations",
                "Fix reported style issues",
                "Ensure vale configuration is present"
            ]
        },
        "ref-check": {
            "category": FailureCategory.CONFIGURATION,
            "common_causes": {
                "missing_references": "Cited references not in bibliography",
                "format_errors": "Bibliography format errors",
                "doi_mismatch": "DOI mismatches"
            },
            "actions": [
                "Run ref-check to see specific errors",
                "Add missing references to bibliography",
                "Fix bibliography format"
            ]
        },
        "inspect": {
            "category": FailureCategory.METHODOLOGY,
            "common_causes": {
                "agent_failure": "Agent failed to complete task",
                "tool_error": "Tool use error",
                "eval_dataset_issue": "Evaluation dataset problem"
            },
            "actions": [
                "Check inspect eval output for details",
                "Verify evaluation dataset integrity",
                "Check agent/tool configuration"
            ]
        },
        "deepeval": {
            "category": FailureCategory.METHODOLOGY,
            "common_causes": {
                "faithfulness_low": "Generated content not faithful to context",
                "relevancy_low": "Answer not relevant to question",
                "precision_low": "Context precision below threshold"
            },
            "actions": [
                "Check specific metric failures",
                "Improve retrieval or generation quality",
                "Adjust evaluation thresholds"
            ]
        },
        "promptfoo": {
            "category": FailureCategory.CONFIGURATION,
            "common_causes": {
                "prompt_regression": "Prompt performance regressed",
                "red_team_failure": "Red-teaming attack succeeded",
                "config_error": "Promptfoo config error"
            },
            "actions": [
                "Check promptfoo output for details",
                "Review prompt changes",
                "Fix configuration errors"
            ]
        },
        "ragas": {
            "category": FailureCategory.METHODOLOGY,
            "common_causes": {
                "faithfulness_low": "RAG output not faithful to context",
                "context_precision_low": "Retrieved context not precise",
                "recall_low": "Relevant context not retrieved"
            },
            "actions": [
                "Check specific RAGAS metric failures",
                "Improve retrieval quality",
                "Adjust generation parameters"
            ]
        }
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def diagnose(self, failed_gate: str, context: Dict[str, Any]) -> FailureDiagnosis:
        """Diagnose a single failed gate"""
        rules = self.DIAGNOSIS_RULES.get(failed_gate) or MONITOR_RULES.get(failed_gate, {})
        if not rules and str(failed_gate).startswith("chain:"):
            rules = MONITOR_RULES.get("chain", {})
        category = rules.get("category", FailureCategory.METHODOLOGY)
        common_causes = rules.get("common_causes", {})
        actions = rules.get("actions", ["Investigate gate failure manually"])
        
        # Determine severity based on gate type and context
        severity = self._determine_severity(failed_gate, context)
        
        # Match specific cause based on context
        root_cause = self._identify_root_cause(failed_gate, context, common_causes)
        summary = f"Gate '{failed_gate}' failed: {root_cause}"
        
        # Determine related gates
        related = self._find_related_gates(failed_gate)
        
        # Estimate effort
        effort = self._estimate_effort(failed_gate, context)
        
        return FailureDiagnosis(
            gate_name=failed_gate,
            severity=severity,
            category=category,
            summary=summary,
            root_cause=root_cause,
            evidence=context.get("evidence", {}),
            suggested_actions=actions,
            related_gates=related,
            estimated_effort=effort,
            context_snapshot=self._sanitize_context(context)
        )
    
    def _determine_severity(self, gate: str, context: Dict) -> FailureSeverity:
        """Determine failure severity"""
        # Critical gates that block publication
        critical_gates = ["acceptance-gate", "planted-truth", "prose-lint", "ref-check"]
        if gate in critical_gates:
            return FailureSeverity.CRITICAL
        
        # High severity for methodological gates
        high_gates = ["independence-bookkeeping", "inspect", "deepeval", "ragas"]
        if gate in high_gates:
            return FailureSeverity.HIGH
        
        # Medium for compute/configuration
        medium_gates = ["timing-discipline", "tool-stewardship", "promptfoo"]
        if gate in medium_gates:
            return FailureSeverity.MEDIUM
        
        return FailureSeverity.LOW
    
    @staticmethod
    def _gate_and_context(gate: Any, context: Dict) -> tuple:
        """Accept a gate name or a GateResult and return (name, per-gate context).

        A name carries no information about what went wrong. A GateResult carries
        `details` -- which metric missed which threshold, which tool was absent --
        and dropping it left the diagnosis saying "specific cause needs
        investigation" for a failure whose cause was already structured.
        """
        if isinstance(gate, str):
            return gate, context
        details = getattr(gate, "details", {}) or {}
        error = ""
        if isinstance(details, dict):
            error = str(details.get("error") or details.get("missing_tool") or "")
        evidence = {
            "status": getattr(gate, "status", "FAIL"),
            "details": details,
            "error": error,
        }
        return getattr(gate, "gate_name", str(gate)), {**context, "evidence": evidence}

    def _identify_root_cause(self, gate: str, context: Dict, common_causes: Dict) -> str:
        """Identify most likely root cause from context."""
        evidence = context.get("evidence", {})
        error = evidence.get("error", "")
        details = evidence.get("details", {})

        # Structured signals first: a GateResult says exactly which criterion failed.
        if isinstance(details, dict):
            missed = [k for k, v in details.items()
                      if isinstance(v, dict) and v.get("met") is False]
            if missed and "metric_below_threshold" in common_causes:
                return f"{common_causes['metric_below_threshold']}: {', '.join(missed)}"
            unset = [k for k, v in details.items()
                     if isinstance(v, dict) and v.get("status") == "MISSING"]
            if unset and "missing_metric" in common_causes:
                return f"{common_causes['missing_metric']}: {', '.join(unset)}"
            if details.get("missing_tool") and "vale_config_missing" not in common_causes:
                return f"required tool absent: {details['missing_tool']}"

        # Match error patterns to common causes
        for cause_key, cause_desc in common_causes.items():
            if cause_key.replace("_", " ") in str(error).lower():
                return cause_desc
            if cause_key in str(details).lower():
                return cause_desc

        return f"{gate} gate failed (specific cause needs investigation)"
    
    def _find_related_gates(self, failed_gate: str) -> List[str]:
        """Find gates that might be affected by or related to this failure"""
        relations = {
            "acceptance-gate": ["planted-truth", "independence-bookkeeping"],
            "planted-truth": ["acceptance-gate", "independence-bookkeeping"],
            "independence-bookkeeping": ["acceptance-gate", "planted-truth"],
            "timing-discipline": ["tool-stewardship"],
            "tool-stewardship": ["timing-discipline"],
            "prose-lint": ["ref-check"],
            "ref-check": ["prose-lint"],
            "inspect": ["deepeval", "ragas"],
            "deepeval": ["inspect", "ragas"],
            "ragas": ["inspect", "deepeval"],
            "promptfoo": ["inspect"],
        }
        return relations.get(failed_gate, [])
    
    def _estimate_effort(self, gate: str, context: Dict) -> str:
        """Estimate effort to fix"""
        effort_map = {
            "acceptance-gate": "high",
            "planted-truth": "medium",
            "independence-bookkeeping": "high",
            "timing-discipline": "medium",
            "tool-stewardship": "low",
            "prose-lint": "low",
            "ref-check": "low",
            "inspect": "high",
            "deepeval": "medium",
            "promptfoo": "low",
            "ragas": "medium"
        }
        return effort_map.get(gate, "unknown")
    
    def _sanitize_context(self, context: Dict) -> Dict:
        """Remove sensitive data from context snapshot"""
        sanitized = {}
        for k, v in context.items():
            if k in ["api_key", "password", "token", "secret"]:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (str, int, float, bool, type(None))):
                sanitized[k] = v
            elif isinstance(v, (list, dict)):
                sanitized[k] = str(v)[:500]  # Truncate large structures
            else:
                sanitized[k] = str(type(v))
        return sanitized
    
    def diagnose_pipeline(self, failed_gates: List, context: Dict) -> 'DiagnosisReport':
        """Generate complete diagnosis report for multiple failed gates.

        `failed_gates` may hold gate names (historical form) or GateResult objects;
        the latter carry their details into the diagnosis.
        """
        diagnoses = []
        for gate in failed_gates:
            gate_name, gate_context = self._gate_and_context(gate, context)
            diagnoses.append(self.diagnose(gate_name, gate_context))
        
        # Overall severity = max of individual severities
        severity_order = [FailureSeverity.CRITICAL, FailureSeverity.HIGH, 
                         FailureSeverity.MEDIUM, FailureSeverity.LOW]
        overall_severity = min(diagnoses, key=lambda d: severity_order.index(d.severity)).severity
        
        # Collect all recommended actions
        all_actions = []
        for d in diagnoses:
            all_actions.extend(d.suggested_actions)
        
        # Deduplicate while preserving order
        seen = set()
        unique_actions = []
        for action in all_actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)
        
        # Can retry automatically if no CRITICAL failures
        can_retry = not any(d.severity == FailureSeverity.CRITICAL for d in diagnoses)
        
        # Estimate total effort
        effort_order = {"low": 1, "medium": 2, "high": 3, "unknown": 2}
        total_effort = sum(effort_order.get(d.estimated_effort, 2) for d in diagnoses)
        if total_effort <= 2:
            total_effort_str = "low"
        elif total_effort <= 4:
            total_effort_str = "medium"
        else:
            total_effort_str = "high"
        
        return DiagnosisReport(
            pipeline_id=context.get("pipeline_id", "unknown"),
            failed_gates=[d.gate_name for d in diagnoses],
            diagnoses=diagnoses,
            overall_severity=overall_severity,
            recommended_next_steps=unique_actions,
            can_retry_automatically=can_retry,
            estimated_total_effort=total_effort_str
        )
    
    def export_report(self, report: DiagnosisReport, output_path: Path) -> None:
        """Export diagnosis report to file"""
        output = {
            "pipeline_id": report.pipeline_id,
            "generated_at": report.generated_at,
            "overall_severity": report.overall_severity.value,
            "failed_gates": report.failed_gates,
            "can_retry_automatically": report.can_retry_automatically,
            "estimated_total_effort": report.estimated_total_effort,
            "recommended_next_steps": report.recommended_next_steps,
            "diagnoses": [
                {
                    "gate_name": d.gate_name,
                    "severity": d.severity.value,
                    "category": d.category.value,
                    "summary": d.summary,
                    "root_cause": d.root_cause,
                    "evidence": d.evidence,
                    "suggested_actions": d.suggested_actions,
                    "related_gates": d.related_gates,
                    "estimated_effort": d.estimated_effort,
                    "timestamp": d.timestamp
                }
                for d in report.diagnoses
            ],
        }
        
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))


def diagnose_pipeline_failure(failed_gates: List[str], context: Dict[str, Any]) -> DiagnosisReport:
    """Convenience function to diagnose pipeline failure from gate names."""
    engine = FailureDiagnosisEngine()
    return engine.diagnose_pipeline(failed_gates, context)


def diagnose_gate_results(results: List[Any], context: Dict[str, Any] | None = None) -> DiagnosisReport:
    """Diagnose from GateResult objects, keeping their structured details.

    This is the form to use after `GateRegistry.run_suite`: the names alone cannot
    say which criterion missed, while the details can.
    """
    engine = FailureDiagnosisEngine()
    return engine.diagnose_pipeline(list(results), context or {})


def refine_with_operator(report: DiagnosisReport, client: Any = None,
                         min_confidence: float = 0.6) -> DiagnosisReport:
    """Ask the decision operator to classify failures the rules could not name.

    Only diagnoses whose root cause is still "specific cause needs investigation"
    are sent: a rule that already identified a cause is not second-guessed. A
    low-confidence answer or an unreachable operator leaves the report unchanged —
    the original text remains, which is the honest outcome when nothing better was
    established.
    """
    weak = [d for d in report.diagnoses if "needs investigation" in d.root_cause]
    if not weak:
        return report

    from framework.decision import DecisionClient, DecisionUnavailable

    client = client or DecisionClient()
    options = {c.value: c.value.replace("_", " ") for c in FailureCategory}
    for diagnosis in weak:
        try:
            decision = client.choose(
                "Which failure category fits this gate failure?",
                options,
                {"gate": diagnosis.gate_name,
                 "root_cause": diagnosis.root_cause,
                 "evidence": str(diagnosis.evidence)[:1500]},
            )
        except DecisionUnavailable:
            return report
        accepted = decision.accepted(min_confidence) and decision.choice in options
        # Record that the operator was consulted even when it declines: a refusal is
        # informative (often none_probability says "none of these"), and without this
        # the seam looks inert.
        diagnosis.context_snapshot["operator"] = {
            "choice": decision.choice,
            "probability": decision.probability,
            "none_probability": decision.none_probability,
            "accepted": accepted,
        }
        if accepted:
            diagnosis.category = FailureCategory(decision.choice)
            diagnosis.summary = (
                f"{diagnosis.summary} "
                f"[operator: {decision.choice} p={decision.probability:.2f}]"
            )
    return report