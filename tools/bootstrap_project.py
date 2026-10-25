"""Scaffold a new consumer from the onboarding template.

    python tools/bootstrap_project.py --name my_study --dest ../../my_study

Copies reference/demo_onboarding, rewrites the name, registers projects/<name>/project.yaml and
prints the next three commands. It refuses to overwrite: an onboarding that silently replaces an
existing project is worse than no onboarding.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

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

    if not TEMPLATE.is_dir():
        print(f"[FAIL] template missing: {TEMPLATE}")
        return 1
    dest = Path(args.dest).expanduser()
    if not dest.is_absolute():
        dest = (ROOT / dest).resolve()
    if dest.exists() and any(dest.iterdir()):
        print(f"[FAIL] {dest} exists and is not empty; refusing to overwrite")
        return 1

    shutil.copytree(TEMPLATE, dest)
    for rel in ("docs/evidence.json",):
        (dest / rel).unlink(missing_ok=True)

    if args.no_register:
        print(f"created {dest} (not registered)")
        return 0

    registry = ROOT / "projects" / args.name
    registry.mkdir(parents=True, exist_ok=True)
    spec = registry / "project.yaml"
    spec.write_text(
        f"name: {args.name}\n"
        f"root: {Path(os.path.relpath(dest, registry)).as_posix()}\n\n"
        "role: consumer (scaffolded from the onboarding template)\n\n"
        'gate_command: ["python", "build_evidence.py"]\n'
        'test_command: ["python", "build_evidence.py"]\n'
        "expects:\n  - docs/evidence.json\n\n"
        "validity_register: analysis/CLAIMS.yaml\n"
        "validity_document: docs/REPORT.md\n"
        "expected_gate_s: PASS\n", encoding="utf-8")

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
