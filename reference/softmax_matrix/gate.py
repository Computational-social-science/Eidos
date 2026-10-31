"""Expose completion to Gate S only after independent model and gradient checks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from reference.softmax_matrix.verify import validate, validate_final_check
from framework.validity import ScientificValidityGate


def main():
    try:
        p = json.loads((HERE / "protocol.json").read_text())
        r = json.loads((HERE / "docs/evidence.json").read_text())
        errors = validate(r, p)
        if not errors:
            errors = validate_final_check(r)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    evidence = {"generated": datetime.now(timezone.utc).isoformat(), "complete_and_checked": not errors,
                "status": "FAIL" if errors else "PASS", "findings": errors,
                "scope": "supported-precision paired reconstruction; completion does not imply superiority or a full paper reproduction"}
    (HERE / "docs").mkdir(exist_ok=True)
    (HERE / "docs/gate_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
    gate = ScientificValidityGate(HERE, document=HERE / "docs/REPORT.md").run()
    print(json.dumps({**evidence, "gate_s": gate.status, "gate_details": gate.details}, indent=2))
    return int(bool(errors) or gate.status != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
