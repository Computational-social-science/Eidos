"""Validate recorded training, then expose a bounded observational claim to Gate S."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from reference.softmax_training.validate import validate_report, digest
from framework.validity import ScientificValidityGate


def main():
    try:
        report = json.loads((HERE / "docs/evidence.json").read_text(encoding="utf-8"))
        protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
        findings = validate_report(report, protocol)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        findings = [str(exc)]
    evidence = {"status": "FAIL" if findings else "PASS", "fixed_stationarity": not findings,
                "findings": findings, "gate_source_sha256": digest(Path(__file__)),
                "scope": "observational local evidence; not a paper-wide training or generalisation claim"}
    (HERE / "docs/gate_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    gate = ScientificValidityGate(HERE, document=HERE / "docs/REPORT.md").run()
    print(json.dumps({**evidence, "gate_s": gate.status, "gate_details": gate.details}, indent=2))
    return 0 if not findings and gate.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
