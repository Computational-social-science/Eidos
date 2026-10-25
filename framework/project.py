"""External project registry: run a project's own gates without owning its files.

WHY A REGISTRY AND NOT A MOVE
    keystroke-observatory already carries a gate layer that is stronger than this
    framework's skeleton: a five-status vocabulary (PASS / FAIL / OPEN / REFUSED /
    SKIP), structured findings, and a validation rule that forbids an OPEN or SKIP
    without a next action. Its own MIGRATION.md (section 7.3) rejects moving the
    repository into ``projects/``: ~80 tests import by bare module name, the handoff
    gate hard-codes ``docs/``, and the JSON artefacts double as the manuscript's
    data source.

    So the framework does not copy the project and does not reimplement its gates.
    It keeps a *pointer*: each ``projects/<name>/project.yaml`` names a repository
    root and the command that runs that repository's gate suite. The framework's
    job is discovery, execution, and one comparable verdict — not ownership.

    This is also the only arrangement that satisfies a single-source-of-truth rule:
    the gate logic exists once, in the project, where its tests are.

CONTRACT WITH A PROJECT
    ``project.yaml`` fields:

        name           str   stable identifier (defaults to the directory name)
        root           str   repository root, relative to this file or absolute
        gate_command   list  argv that runs the gate suite; ``{python}`` is replaced
                             with the interpreter running this framework
        test_command   list  optional argv for the project's test suite
        reports        list  optional repository-relative paths a reader should open
        notes          str   free text, not interpreted

    Exit-code mapping is deliberately coarse: 0 = PASS, 1 = FAIL, anything else =
    ERROR (the gate did not reach a verdict). A project whose gate distinguishes
    OPEN from FAIL should print that distinction; parsing project-specific output is
    out of scope here.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROJECTS_DIR = Path(__file__).resolve().parents[1] / "projects"


@dataclasses.dataclass(frozen=True)
class ProjectSpec:
    """One external repository registered with the framework."""

    name: str
    root: Path
    gate_command: list[str]
    test_command: list[str] = dataclasses.field(default_factory=list)
    render_command: list[str] = dataclasses.field(default_factory=list)
    reports: list[str] = dataclasses.field(default_factory=list)
    #: Files the gate must leave behind. A gate that exits 0 without producing them has
    #: not judged anything, and calling that PASS is the vacuous pass this field prevents.
    expects: list[str] = dataclasses.field(default_factory=list)
    notes: str = ""
    #: What kind of consumer this is: measured LLM consumer, negative control, chain fixture.
    role: str = ""
    #: Gate S registration: the claim register, the deliverable(s) the claims live in,
    #: and the verdict the consumer is expected to produce (a negative control FAILs).
    validity_register: str = ""
    validity_document: str = ""
    expected_gate_s: str = ""
    #: False when the checkout is absent. Loading a missing project is allowed only
    #: for enumeration (``list``); running it always raises.
    available: bool = True
    missing_reason: str = ""


@dataclasses.dataclass
class ProjectRun:
    """The outcome of running one project's gate command."""

    name: str
    status: str          # PASS | FAIL | SKIP | ERROR
    exit_code: int
    duration_s: float
    command: list[str]
    stdout_tail: str = ""
    stderr_tail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _as_argv(value: Any, field: str, where: Path) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raise ValueError(
            f"{where}: {field} must be a list of arguments, not a string "
            f"(got {value!r}); a shell string would hide quoting bugs"
        )
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{where}: {field} must be a list of strings")
    return [str(v) for v in value]


def load_project(project_file: Path, allow_missing: bool = False) -> ProjectSpec:
    """Load and validate one project.yaml.

    ``allow_missing`` exists for enumeration only: ``list`` must be able to report a
    detached checkout as MISSING, while ``check`` and ``exec`` must refuse to run it.
    A silent skip would read exactly like a passing project.
    """
    raw: Any = yaml.safe_load(project_file.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"{project_file}: expected a mapping at the top level")
    data: dict[str, Any] = raw

    root_raw = data.get("root")
    if not root_raw:
        raise ValueError(f"{project_file}: 'root' is required")
    root = Path(str(root_raw))
    if not root.is_absolute():
        root = (project_file.parent / root).resolve()
    available = root.is_dir()
    if not available and not allow_missing:
        raise FileNotFoundError(
            f"{project_file}: root does not exist: {root} "
            "(a registered project must be present; a silent skip would hide a "
            "detached checkout)"
        )

    gate_command = _as_argv(data.get("gate_command"), "gate_command", project_file)
    if not gate_command:
        raise ValueError(f"{project_file}: 'gate_command' is required")

    return ProjectSpec(
        name=str(data.get("name") or project_file.parent.name),
        root=root,
        gate_command=gate_command,
        test_command=_as_argv(data.get("test_command"), "test_command", project_file),
        render_command=_as_argv(data.get("render_command"), "render_command", project_file),
        reports=[str(r) for r in (data.get("reports") or [])],
        expects=[str(r) for r in (data.get("expects") or [])],
        notes=str(data.get("notes") or ""),
        role=str(data.get("role") or ""),
        validity_register=str(data.get("validity_register") or ""),
        validity_document=str(data.get("validity_document") or ""),
        expected_gate_s=str(data.get("expected_gate_s") or ""),
        available=available,
        missing_reason="" if available else f"checkout not found: {root}",
    )


def load_projects(projects_dir: Path | None = None,
                  allow_missing: bool = False) -> dict[str, ProjectSpec]:
    """Load every ``<projects_dir>/*/project.yaml``, keyed by project name."""
    directory = Path(projects_dir) if projects_dir else DEFAULT_PROJECTS_DIR
    if not directory.is_dir():
        return {}
    specs: dict[str, ProjectSpec] = {}
    for project_file in sorted(directory.glob("*/project.yaml")):
        spec = load_project(project_file, allow_missing=allow_missing)
        if spec.name in specs:
            raise ValueError(f"duplicate project name {spec.name!r} in {directory}")
        specs[spec.name] = spec
    return specs


def _materialise(argv: list[str]) -> list[str]:
    """Replace the ``{python}`` placeholder with the running interpreter.

    A project must be exercised by the same interpreter that runs the framework;
    bare ``python`` on this host resolves to a 3.15 install that lacks the project's
    dependencies, which would fail for the wrong reason.
    """
    return [part.replace("{python}", sys.executable) for part in argv]


_COMMANDS = {"gate": "gate_command", "test": "test_command", "render": "render_command"}


def run_command(spec: ProjectSpec, kind: str = "gate", timeout: int = 900) -> ProjectRun:
    """Run one of the commands a project declares, in its own root.

    ``kind`` selects the declared argv: gate (required), test or render (optional).
    An absent optional command is a configuration error, not a silent no-op.
    """
    if not spec.available:
        raise FileNotFoundError(
            f"project {spec.name!r} cannot run: {spec.missing_reason or 'checkout missing'}"
        )
    if kind not in _COMMANDS:
        raise ValueError(f"unknown command kind {kind!r}; expected one of {sorted(_COMMANDS)}")
    declared = getattr(spec, _COMMANDS[kind])
    if not declared:
        raise ValueError(f"project {spec.name!r} declares no {kind}_command in project.yaml")

    started = time.monotonic()
    argv = _materialise(declared)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(spec.root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        exit_code = proc.returncode
        stdout, stderr = proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        out = exc.stdout
        if isinstance(out, bytes):
            stdout = out.decode("utf-8", "replace")
        elif isinstance(out, str):
            stdout = out
        else:
            stdout = ""
        stderr = f"timed out after {timeout}s"
    except OSError as exc:
        exit_code = 127
        stdout, stderr = "", f"{type(exc).__name__}: {exc}"

    # A declared binary that does not exist has not judged the artefact. The vocabulary is
    # keystroke-observatory's and it is deliberate: SKIP means "no verdict", and a missing
    # tool that reports FAIL trains a reader to ignore the gate.
    if exit_code == 127:
        status = "SKIP"
    elif exit_code == 0:
        status = "PASS"
    elif exit_code == 1:
        status = "FAIL"
    else:
        status = "ERROR"

    if status == "PASS" and spec.expects:
        missing = [rel for rel in spec.expects if not (spec.root / rel).exists()]
        if missing:
            status = "FAIL"
            note = "declared output missing after a successful run: " + ", ".join(missing)
            stderr = (stderr.rstrip() + chr(10) + note) if stderr else note
    return ProjectRun(
        name=spec.name,
        status=status,
        exit_code=exit_code,
        duration_s=round(time.monotonic() - started, 2),
        command=argv,
        stdout_tail=stdout[-4000:],
        stderr_tail=stderr[-2000:],
    )


def _format(run: ProjectRun, kind: str = "gate") -> str:
    head = f"{run.status:<5} {run.name}[{kind}]  (exit {run.exit_code}, {run.duration_s}s)"
    tail = run.stdout_tail.strip().splitlines()[-6:]
    return "\n".join([head] + [f"      {line}" for line in tail])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m framework.project")
    sub = parser.add_subparsers(dest="action", required=True)

    p_list = sub.add_parser("list", help="list registered projects")
    p_list.add_argument("--projects-dir", default=None)

    p_check = sub.add_parser("check", help="run a project's gate command")
    p_check.add_argument("name")
    p_check.add_argument("--projects-dir", default=None)
    p_check.add_argument("--json", action="store_true")
    p_check.add_argument("--timeout", type=int, default=900)

    p_exec = sub.add_parser("exec", help="run a declared command: gate, test or render")
    p_exec.add_argument("name")
    p_exec.add_argument("kind", choices=sorted(_COMMANDS))
    p_exec.add_argument("--projects-dir", default=None)
    p_exec.add_argument("--json", action="store_true")
    p_exec.add_argument("--timeout", type=int, default=900)

    args = parser.parse_args(argv)
    projects_dir = Path(args.projects_dir) if args.projects_dir else None

    try:
        specs = load_projects(projects_dir, allow_missing=(args.action == "list"))
    except (ValueError, FileNotFoundError) as exc:
        print(f"registry error: {exc}", file=sys.stderr)
        return 2

    if args.action == "list":
        if not specs:
            print("no projects registered")
            return 0
        for spec in specs.values():
            mark = "" if spec.available else "  [MISSING]"
            print(f"{spec.name:<24} {spec.root}{mark}")
        return 0

    spec = specs.get(args.name)
    if spec is None:
        print(f"unknown project {args.name!r}; known: {sorted(specs)}", file=sys.stderr)
        return 2

    kind = "gate" if args.action == "check" else args.kind
    try:
        run = run_command(spec, kind, timeout=args.timeout)
    except (ValueError, FileNotFoundError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(run.as_dict(), indent=2))
    else:
        print(_format(run, kind))
        if run.status != "PASS" and run.stderr_tail.strip():
            print("      --- stderr ---")
            for line in run.stderr_tail.strip().splitlines()[-6:]:
                print(f"      {line}")
    return 0 if run.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
