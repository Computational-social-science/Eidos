"""Scaffold a new consumer from the onboarding template.

    python tools/bootstrap_project.py --name my_study --dest ../../my_study

Copies reference/demo_onboarding, rewrites the name, registers projects/<name>/project.yaml and
prints the next three commands. It refuses to overwrite: an onboarding that silently replaces an
existing project is worse than no onboarding.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "reference" / "demo_onboarding"


def _root_field(dest: Path, registry: Path) -> str:
    """A relative root, unless the destination is on another drive.

    A project outside the repository cannot be described relatively; the honest fallback is an
    absolute path, which the loader accepts. Everything inside the repository stays relative.
    """
    try:
        return Path(os.path.relpath(dest, registry)).as_posix()
    except ValueError:
        return dest.as_posix()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True, help="project name (lowercase, underscores)")
    ap.add_argument("--dest", required=True, help="destination directory for the project root")
    ap.add_argument("--no-register", action="store_true",
                    help="scaffold only; do not add a registry entry (used by the release rehearsal)")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name):
        print("[FAIL] name must start with a lowercase letter and contain only lowercase letters, digits or underscores")
        return 1

    if not TEMPLATE.is_dir():
        print(f"[FAIL] template missing: {TEMPLATE}")
        return 1
    dest = Path(args.dest).expanduser()
    if not dest.is_absolute():
        dest = (ROOT / dest).resolve()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        print(f"[FAIL] {dest} exists and is not empty; refusing to overwrite")
        return 1

    registry = ROOT / "projects" / args.name
    if not args.no_register and registry.exists():
        print(f"[FAIL] {registry} is already registered; refusing to overwrite")
        return 1

    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True)
    for rel in ("docs/evidence.json",):
        (dest / rel).unlink(missing_ok=True)

    if args.no_register:
        print(f"created {dest} (not registered)")
        return 0

    registry.mkdir(parents=True, exist_ok=True)
    spec = registry / "project.yaml"
    registration = {
        "name": args.name,
        "root": _root_field(dest, registry),
        "role": "consumer (scaffolded from the onboarding template)",
        "gate_command": ["python", "build_evidence.py"],
        "test_command": ["python", "build_evidence.py"],
        "expects": ["docs/evidence.json"],
        "validity_register": "analysis/CLAIMS.yaml",
        "validity_document": "docs/REPORT.md",
        "expected_gate_s": "PASS",
    }
    spec.write_text(yaml.safe_dump(registration, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")

    print(f"created {dest}")
    print(f"registered {spec.relative_to(ROOT)}")
    print("\nnext:")
    print(f"  cd {dest}")
    print("  python build_evidence.py")
    print(f"  cd {ROOT} && python -m framework.project check {args.name}")
    print(f"  python tools/audit_validity.py --project {args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
