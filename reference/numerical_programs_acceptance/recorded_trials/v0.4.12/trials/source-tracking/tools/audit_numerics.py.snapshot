"""Audit consumer code for the two softmax failures, and prove the guard itself can fail.

    python tools/audit_numerics.py                # scan the framework and every consumer
    python tools/audit_numerics.py --projects     # only projects that declare `numerics: required`
    python tools/audit_numerics.py --json

Exit 0 clean, 1 findings, 2 error. Findings go to docs/NUMERICS.json so the site can show them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.verifiers import numerics  # noqa: E402


def _project_roots(only_required: bool) -> list[tuple[str, Path]]:
    from framework.project import load_projects
    return [(spec.name, spec.root) for spec in load_projects(ROOT / "projects", allow_missing=True).values()
            if not only_required or spec.numerics == "required"]


def _default_targets() -> list[Path]:
    targets = [ROOT / "framework", ROOT / "tools"]
    targets += [root for _, root in _project_roots(only_required=False)]
    return targets


def _python_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_file() and target.suffix == ".py":
            files.append(target)
        elif target.is_dir():
            for parent, directories, names in os.walk(target):
                directories[:] = [d for d in directories if not d.startswith(".venv")
                                  and d not in {"__pycache__", ".scratch", ".git", "node_modules", "venv"}]
                files.extend(Path(parent) / name for name in names if name.endswith(".py"))
    return sorted(set(files))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", action="append", type=Path, help="file or directory (repeatable)")
    parser.add_argument("--projects", action="store_true",
                        help="only projects whose project.yaml declares numerics: required")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.path:
        targets = [p if p.is_absolute() else (ROOT / p) for p in args.path]
    elif args.projects:
        targets = [root for _, root in _project_roots(only_required=True)]
    else:
        targets = _default_targets()

    files = _python_files(targets)
    absent = [str(target) for target in targets if not target.exists()]
    if absent:
        print("ERROR missing scan target(s): " + ", ".join(absent), file=sys.stderr)
        return 2
    findings = numerics.audit_source(files)
    runtime = numerics.kernel_regression_report()
    report = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "scanned": len(files), "findings": findings, "kernel_regression": runtime,
              "static_scope": "heuristic patterns; a clean scan does not certify consumer gradients"}
    (ROOT / "docs" / "NUMERICS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    elif findings:
        print(f"FAIL {len(findings)} numerical risk(s) in {len(files)} files")
        for item in findings:
            print(f"  {item['file']}:{item['line']}  {item['kind']}  {item['detail'][:90]}")
    else:
        print(f"clean {len(files)} files")
    if not args.json:
        print(f"{runtime['verdict']} numerical kernels: {len(runtime['cases'])} cases; "
              f"{sum(c['rejected'] for c in runtime['negative_controls'])} negative controls rejected")
    return 1 if findings or runtime["verdict"] != "PASS" else 0


if __name__ == "__main__":
    sys.exit(main())
