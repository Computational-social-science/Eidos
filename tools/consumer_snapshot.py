"""Bind cached Gate S verdicts to registry, gate code and declared file inputs.

This is local change detection, not attestation or a rerun of a consumer's
training/model validator. Large underlying datasets/models are checked by that
validator; their manifests are bound here only when declared as gate inputs.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCOPE = "registry, framework Python sources, Python gate entry, explicit validity_inputs and Gate S file handles"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def registry_digest(specs: dict) -> str:
    return _digest({name: dataclasses.asdict(spec) for name, spec in sorted(specs.items())})


def capture_inputs(spec, root: Path = ROOT) -> dict:
    """Missing files have a digest; unreadable/unsafe inputs cannot bind a verdict."""
    files = {}
    project = spec.root.resolve()
    external = {(project / rel).resolve() for rel in spec.validity_external_inputs}

    def add(rel, base=project, *, mtime=False):
        path = (base / str(rel)).resolve()
        if not path.is_relative_to(base.resolve()) and not (base == project and path in external):
            raise ValueError(f"input outside project: {rel}")
        key = str(path)
        try:
            # Stream large declared records; memory use does not scale with file size.
            with path.open("rb") as stream:
                value = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
            if mtime or "mtime_ns" in files.get(key, {}):
                value["mtime_ns"] = path.stat().st_mtime_ns
            files[key] = value
        except FileNotFoundError:
            files[key] = {"missing": True}

    def handles(value):
        pending, visited = [value], set()
        while pending:
            node = pending.pop()
            if not isinstance(node, (dict, list)) or id(node) in visited:
                continue
            visited.add(id(node))
            if isinstance(node, dict):
                if node.get("file"):
                    # Gate S can use mtime for preregistration evidence.
                    add(node["file"], mtime=True)
                pending.extend(node.values())
            else:
                pending.extend(node)

    try:
        if not project.is_dir():
            raise ValueError("project checkout missing")
        for path in sorted((root / "framework").rglob("*.py")):
            add(path.relative_to(root), root)
        for rel in ("tools/audit_validity.py", "tools/consumer_snapshot.py"):
            add(rel, root)
        # Bind the directly executed Python script, not just the argv spelling.
        # Imported helpers and module-mode/non-Python commands need validity_inputs.
        command=spec.gate_command
        entry=None
        if command and Path(command[0]).suffix.lower() in {'.py','.pyw'}:
            entry=command[0]
        elif len(command)>1 and (command[0]=='{python}' or
                re.fullmatch(r'python(?:\d+(?:\.\d+)*)?(?:\.exe)?',Path(command[0]).name,re.I)):
            args=iter(command[1:])
            for arg in args:
                if arg.startswith('-m'):
                    if not spec.validity_inputs:
                        raise ValueError('module-mode gate requires explicit validity_inputs')
                    break
                if arg.startswith('-c') or arg=='-':
                    break
                if arg in {'-X','-W','--check-hash-based-pycs'}:
                    if next(args,None) is None:
                        raise ValueError('Python gate option has no value')
                elif arg.startswith(('-X','-W','--check-hash-based-pycs=')):
                    continue
                elif arg=='--':
                    entry=next(args,None)
                    break
                elif arg.startswith('-'):
                    if len(arg)<2 or any(c not in 'bBdEiIOPqRsSuvVx' for c in arg[1:]):
                        raise ValueError(f'cannot bind unknown Python gate option: {arg}')
                elif not arg.startswith('-'):
                    entry=arg
                    break
        for rel in ([entry] if entry else []) + spec.validity_inputs:
            add(rel)
        for rel in [spec.validity_register, *spec.validity_document.split(","),
                    *spec.expects, "docs/evidence.json",
                    "artifacts/literature/proofpath.json", "artifacts/evaluation/stat_recompute.json"]:
            if str(rel).strip():
                add(str(rel).strip())
        register = (project / spec.validity_register).resolve()
        if register.is_file():
            data = yaml.safe_load(register.read_text(encoding="utf-8"))
            handles(data)
            for claim in (data or {}).get("claims", []):
                if claim.get("reproduction"):
                    safe = "".join(c if c.isalnum() or c in "-_." else "_"
                                   for c in claim["reproduction"])
                    add(f"artifacts/reproduction/{safe}.json")
                if claim.get("support") == "required":
                    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in claim["id"])
                    add(f"artifacts/literature/support/{safe}.json", root)
                if claim.get("formal"):
                    # Toolchain execution is not a portable file snapshot contract yet.
                    raise ValueError("formal toolchain snapshot binding is not qualified")
        return {"digest": _digest({"spec": dataclasses.asdict(spec), "files": files}),
                "error": None}
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError) as exc:
        return {"digest": None, "error": f"{type(exc).__name__}: {exc}"}


def snapshot_state(pipeline: dict, specs: dict | None = None, root: Path = ROOT) -> dict:
    """Fail closed for a missing, legacy or mismatched snapshot."""
    if specs is None:
        from framework.project import load_projects
        specs = load_projects(root / "projects", allow_missing=True)
    meta = pipeline.get("consumer_snapshot") or {}
    rows = {row["name"]: row for row in pipeline.get("consumers", [])}
    stale, errors = [], {}
    stale.extend(name for name in rows if name not in specs)
    for name, spec in specs.items():
        if spec.expected_gate_s.upper() not in ("PASS", "FAIL"):
            continue
        current = capture_inputs(spec, root)
        if (meta.get("schema") != 1 or not current["digest"]
                or rows.get(name, {}).get("input_digest") != current["digest"]):
            stale.append(name)
            errors[name] = current["error"] or "inputs changed or have not been verified"
    if meta.get("registry_digest") != registry_digest(specs):
        stale.append("registry")
    return {"stale": stale, "errors": errors}


def atomic_json(path: Path, payload: dict) -> None:
    """Publish one complete document; leave the last good file on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
