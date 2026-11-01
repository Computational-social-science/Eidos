"""Inspect external candidates without claiming ownership from a generic tmp name.

Top-level inspection only; no external directories are moved or deleted.
Exit 0: no attributed blockers (warnings possible); 1: blockers; 2: incomplete
inspection or invalid explicit ownership metadata. This is a scoped check,
not proof that every write on the host belongs to a known project.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

SCRATCH_NAMES = {
    "tmp",
    "p2a",
    "p2a_work",
    "p2a-work",
    "stage",
    "stage_native",
    "_eidos",
}
SCRATCH_PREFIXES = ("p2a", "tmp_", "stage_", "tmp-")
ALLOWED = {".scratch", ".git", "node_modules", ".venv"}
OWNER_MARKER = ".eidos-owner.json"
OWNER_SCHEMA = "eidos.scratch-owner.v1"


def _suspicious(name: str) -> bool:
    if name in ALLOWED:
        return False
    return (
        ":" in name
        or name.lower() in SCRATCH_NAMES
        or name.lower().startswith(SCRATCH_PREFIXES)
    )


def _key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def mangled_name(project: str) -> str:
    """Exact damage caused by unquoted Windows backslashes in bash."""
    return project.replace("\\", "").replace("/", "")


def default_roots(project: Path) -> list[Path]:
    project = project.resolve()
    roots = [project.parent]
    if project.drive:
        roots.append(Path(project.drive + "/"))
    return list({_key(root): root for root in roots}.values())


def _owner(entry: Path) -> Path | None:
    marker = entry / OWNER_MARKER
    try:
        before = marker.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"Ownership marker must be a regular file: {marker}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(marker, flags), "rb") as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise ValueError(f"Ownership marker changed during inspection: {marker}")
        body = handle.read(4097)
        after = os.fstat(handle.fileno())
    final = marker.lstat()
    if any(
        (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        for item in (opened, after, final)
    ):
        raise ValueError(f"Ownership marker changed during inspection: {marker}")
    if len(body) > 4096:
        raise ValueError(f"Ownership marker exceeds 4096 bytes: {marker}")

    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("Duplicate ownership field")
            result[name] = value
        return result

    value = json.loads(body, object_pairs_hook=unique)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "project_root"}
        or value["schema"] != OWNER_SCHEMA
        or not isinstance(value["project_root"], str)
        or not value["project_root"]
        or not Path(value["project_root"]).is_absolute()
    ):
        raise ValueError(f"Invalid ownership marker: {marker}")
    return Path(value["project_root"]).resolve()


def scan(
    roots: list[Path], exclude: list[Path] | None = None, *, project: Path | None = None
) -> list[dict]:
    project = (project or Path(__file__).resolve().parents[1]).resolve()
    excluded = {_key(path) for path in (exclude or [])}
    seen = set()
    findings = []
    own_mangle = os.path.normcase(mangled_name(str(project)))
    for root in roots:
        # Unknown inspection is an error, not an empty clean result.
        for entry in Path(root).iterdir():
            if not stat.S_ISDIR(entry.stat().st_mode):
                continue
            key = _key(entry)
            if key in excluded or key in seen:
                continue
            seen.add(key)
            owner = _owner(entry)
            if owner is not None:
                attribution = (
                    "project-marker"
                    if _key(owner) == _key(project)
                    else "other-project"
                )
                reason = (
                    "explicit owner matches this project"
                    if attribution == "project-marker"
                    else "explicit owner is another project"
                )
                blocking = attribution == "project-marker"
            elif os.path.normcase(entry.name) == own_mangle:
                attribution, blocking = "project-path-mangle", True
                reason = "exact mangling of this project's absolute path"
            elif entry.name.lower() == "_eidos" or entry.name.lower().startswith(
                ("eidos-scratch-", "eidos-stage-", "eidos-p2a-")
            ):
                attribution, blocking = "project-namespace-policy", True
                reason = "reserved Eidos scratch namespace outside .scratch/; creator not established"
            elif _suspicious(entry.name):
                attribution, blocking = "unattributed", False
                reason = "generic scratch/colon name; current-project ownership not established"
            else:
                continue
            findings.append(
                {
                    "path": str(entry),
                    "name": entry.name,
                    "reason": reason,
                    "attribution": attribution,
                    "blocking": blocking,
                }
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="top-level directory; defaults to project parent and drive root",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    roots = args.root or default_roots(project)
    try:
        findings = scan(roots, exclude=[project / ".scratch", project], project=project)
    except (OSError, ValueError) as exc:
        report = {
            "status": "ERROR",
            "roots": [str(root) for root in roots],
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(
            json.dumps(report, indent=2) if args.json else f"ERROR  {report['error']}"
        )
        return 2
    blockers = sum(item["blocking"] for item in findings)
    report = {
        "status": "FAIL" if blockers else "PASS",
        "roots": [str(root) for root in roots],
        "blocking_count": blockers,
        "warning_count": len(findings) - blockers,
        "findings": findings,
        "scope": "Top-level ownership and namespace inspection; no external files changed.",
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for item in findings:
            print(
                f"{'BLOCK' if item['blocking'] else 'WARNING'}  {item['path']}  ({item['reason']})"
            )
        print(
            f"{report['status']}  {blockers} blockers, {report['warning_count']} warnings"
        )
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
