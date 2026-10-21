"""Lean 4 audit chain for claims that assert machine-checked proof.

A paper sentence such as "the tie-break is optimal" is a claim like any other; when the
claim is marked ``formal`` the register must carry a theorem name and this module must
show four things, in this order:

1. **It builds.** ``lake build`` exits zero. A theorem that no longer compiles is not a
   theorem.
2. **It says what it claims.** ``#print axioms <theorem>`` resolves the constant. A name
   that does not exist prints an error, which is a failure, not an empty axiom list.
3. **It rests on nothing smuggled.** The axiom list must be a subset of the permitted
   classical axioms (``propext``, ``Classical.choice``, ``Quot.sound``). ``sorryAx`` is
   never permitted: a ``sorry`` is an unproved step and defeats the point of the audit.
4. **The kernel is actually checking.** A file asserting ``(1 : Nat) = 2`` must FAIL to
   compile. If it compiles, the toolchain is not a checker and every other line of the
   output is worthless -- this is the control that makes the first three meaningful.

The probe files are written into the project root because Lean resolves imports relative
to the package, and removed in a ``finally`` block so a failed audit leaves no residue.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

DEFAULT_AXIOMS = ("propext", "Classical.choice", "Quot.sound")

_PROBE = "_emdash_audit_probe.lean"
_CONTROL = "_emdash_audit_control.lean"

_AXIOM_LINE = re.compile(r"depends on axioms:\s*\[(.*?)\]", re.S)
_NO_AXIOM = re.compile(r"does not depend on any axioms")
_ERROR = re.compile(r"error:|unknown constant|unknown identifier", re.I)


@dataclass
class LeanAudit:
    project: Path
    theorem: str
    module: Optional[str] = None
    allowed_axioms: Optional[Sequence[str]] = None
    lake_cmd: Optional[object] = None
    timeout: int = 900

    def __post_init__(self) -> None:
        self.project = Path(self.project)
        if self.allowed_axioms is None:
            self.allowed_axioms = DEFAULT_AXIOMS

    # -- process plumbing ------------------------------------------------------
    def _lake(self) -> Optional[List[str]]:
        if self.lake_cmd:
            cmd = [self.lake_cmd] if isinstance(self.lake_cmd, str) else list(self.lake_cmd)  # type: ignore[arg-type]
            head = cmd[0]
            if not (shutil.which(head) or Path(head).exists()):
                return None
            return cmd
        found = shutil.which("lake")
        return [found] if found else None

    def _run(self, cmd: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd, cwd=str(self.project), capture_output=True, text=True,
            timeout=timeout or self.timeout, check=False, encoding="utf-8",
            errors="replace",
        )

    # -- the audit -------------------------------------------------------------
    def run(self) -> Tuple[bool, List[str]]:
        if not self.project.is_dir():
            return False, [f"Lean project does not exist: {self.project}"]
        if not self.module:
            return False, ["no Lean module is named, so the theorem cannot be imported"]
        lake = self._lake()
        if lake is None:
            return False, ["`lake` is not installed, so the formal claim cannot be "
                           "audited; a formal claim without a checker is a FAIL, not a "
                           "SKIP (install Lean 4 / elan)"]

        try:
            # Scope the build to the audited module: a whole-library build of a project
            # that depends on mathlib is hours, and it tells us nothing extra about the
            # theorem we are about to print.
            build = self._run(lake + ["build", self.module])
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, [f"`lake build` could not run: {exc}"]
        if build.returncode != 0:
            tail = (build.stderr or build.stdout or "").strip().splitlines()[-6:]
            return False, ["`lake build` failed: " + " | ".join(tail)]

        probe = self.project / _PROBE
        control = self.project / _CONTROL
        messages: List[str] = []
        try:
            probe.write_text(
                f"import {self.module}\n\n#print axioms {self.theorem}\n",
                encoding="utf-8",
            )
            try:
                printed = self._run(lake + ["env", "lean", _PROBE], timeout=300)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, [f"the axiom probe could not run: {exc}"]
            out = (printed.stdout or "") + (printed.stderr or "")
            if printed.returncode != 0 or _ERROR.search(out):
                tail = out.strip().splitlines()[-6:]
                return False, [f"`#print axioms {self.theorem}` failed: " + " | ".join(tail)]

            axioms: List[str] = []
            m = _AXIOM_LINE.search(out)
            if m:
                axioms = [a.strip() for a in m.group(1).split(",") if a.strip()]
            elif not _NO_AXIOM.search(out):
                return False, ["the probe produced no axiom line; the theorem may not "
                               "have been checked"]

            if "sorryAx" in axioms:
                messages.append("the proof depends on `sorryAx`: at least one step is "
                                "admitted rather than proved")
            extra = [a for a in axioms if a not in set(self.allowed_axioms or DEFAULT_AXIOMS)]
            if extra:
                messages.append(f"axioms outside the permitted set: {extra}")

            # The control: a false statement MUST fail to compile.
            control.write_text("example : (1 : Nat) = 2 := rfl\n", encoding="utf-8")
            try:
                false_run = self._run(lake + ["env", "lean", _CONTROL], timeout=300)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, [f"the kernel control could not run: {exc}"]
            if false_run.returncode == 0:
                messages.append("the kernel control compiled `1 = 2`, so this toolchain "
                                "is not checking proofs and the axiom report above is "
                                "worthless")
            return (not messages), messages
        finally:
            for path in (probe, control):
                try:
                    path.unlink()
                except OSError:
                    pass
