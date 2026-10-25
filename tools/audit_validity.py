#!/usr/bin/env python
"""Run Gate S (scientific validity) against a project.

    python tools/audit_validity.py --project ../keystroke-observatory
    python tools/audit_validity.py --project . --json

Exit codes: 0 PASS, 1 FAIL, 2 the register is missing or unreadable.

The gate reads ``analysis/CLAIMS.yaml`` in the project and re-resolves every evidence
handle, so it answers one question: *is each sentence the paper argues for backed by an
artefact that still says what the register claims it says?*
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.validity import ScientificValidityGate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="project root (default: cwd)")
    ap.add_argument("--register", default=None, help="path to CLAIMS.yaml")
    ap.add_argument("--manuscript", default=None, help="path to the manuscript HTML")
    ap.add_argument("--document", action="append", default=None,
                    help="deliverable the claims must appear in; repeatable")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    spec = None
    if not project.is_dir():
        # A registered name is a better argument than a path: the registry already knows
        # where the project lives, and a path that does not exist silently becomes a bare
        # directory name under the repository root.
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from framework.project import load_projects
            spec = load_projects().get(args.project)
        except Exception:  # noqa: BLE001 - registry problems surface below
            spec = None
        if spec is not None:
            project = spec.root
    if spec is not None:
        # The registry already declares where the claims and the deliverable live; asking the
        # caller to repeat them is how a project gets judged against the wrong document.
        args.register = args.register or (spec.validity_register or "")
        args.manuscript = args.manuscript or (spec.validity_document or "")

    register = Path(args.register) if args.register else None
    if register is not None and not register.is_absolute():
        register = project / register
    manuscript = Path(args.manuscript) if args.manuscript else None
    if manuscript is not None and not manuscript.is_absolute():
        manuscript = project / manuscript

    if not (register or project / "analysis" / "CLAIMS.yaml").is_file():
        message = (f"no claim register at {(register or project / 'analysis' / 'CLAIMS.yaml')}; "
                   f"Gate S cannot judge evidence without the claims it is judging")
        if args.json:
            print(json.dumps({"status": "FAIL", "findings": [message]}))
        else:
            print(f"[FAIL] {message}")
        return 2

    document = None
    if args.document:
        document = [Path(d) if Path(d).is_absolute() else project / d for d in args.document]
    result = ScientificValidityGate(project, register=register,
                                    manuscript=manuscript, document=document).run()
    if args.json:
        print(json.dumps({"status": result.status, **result.details}, indent=2))
    else:
        print(f"Gate S - {project.name}: {result.status} "
              f"({result.details.get('claims', 0)} claims, "
              f"{result.details.get('formal_claims', 0)} formal)")
        for finding in result.details.get("findings", []):
            print("  " + finding)
        if result.status == "PASS":
            print("  every span is in the manuscript, every evidence handle resolves, "
                  "and no referee objection is open")
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
