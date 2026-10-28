"""Refuse to publish if this project has left directories outside its own tree.

The failure this catches is not hypothetical: this machine accumulated `E:2026-AI4SEidos` (an unquoted
Windows path in bash), `E:\\tmp`, two `p2a_*` trees and a 138 MB probe clone, none of which could be
attributed afterwards. A rule in a document did not prevent any of them, so the rule is a check.

Two predicates matter:

* a colon in a directory name — impossible to create through the Win32 API, easy to create through
  bash, and always an accident (`E:\\2026-AI4S\\Eidos` loses its backslashes and becomes `E:2026-AI4SEidos`);
* a name from this project's own scratch vocabulary (`tmp`, `p2a`, `p2a_work`, `tmp_*`, `stage_*`,
  `_eidos`) appearing next to the project rather than inside `.scratch/`.

Scanning is top-level only: it is a check on the neighbourhood, not a walk of the disk.

Usage:  python tools/audit_stray.py [--root DIR ...] [--json]
Exit:   0 clean, 1 stray directories found, 2 error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRATCH_NAMES = {"tmp", "p2a", "p2a_work", "p2a-work", "stage", "stage_native", "_eidos"}
SCRATCH_PREFIXES = ("p2a", "tmp_", "stage_", "tmp-")
ALLOWED = {".scratch", ".git", "node_modules", ".venv"}


def _suspicious(name: str) -> bool:
    if name in ALLOWED:
        return False
    if ":" in name:
        return True
    lowered = name.lower()
    if lowered in SCRATCH_NAMES:
        return True
    return lowered.startswith(SCRATCH_PREFIXES)


def default_roots(project: Path) -> list[Path]:
    roots = [project.resolve().parent]
    drive = project.resolve().drive
    if drive:
        roots.append(Path(drive + "/"))
    # Keep order, drop duplicates.
    seen, ordered = set(), []
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            ordered.append(root)
    return ordered


def scan(roots: list[Path], exclude: list[Path] | None = None) -> list[dict]:
    excluded = {str(p.resolve()).lower() for p in (exclude or [])}
    findings = []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if str(entry.resolve()).lower() in excluded:
                continue
            if _suspicious(entry.name):
                findings.append({"path": str(entry), "name": entry.name,
                                 "reason": "colon in name" if ":" in entry.name
                                 else "scratch name outside .scratch/"})
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", action="append", type=Path,
                        help="directory to scan (repeatable); defaults to the project's parent and "
                             "its drive root")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    roots = args.root or default_roots(project)
    findings = scan(roots, exclude=[project / ".scratch", project])
    if args.json:
        print(json.dumps({"roots": [str(r) for r in roots], "findings": findings}, indent=2))
    elif findings:
        for item in findings:
            print(f"STRAY  {item['path']}  ({item['reason']})")
    else:
        print(f"clean  {', '.join(str(r) for r in roots)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
