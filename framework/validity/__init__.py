"""Gate S -- scientific validity: does the evidence support the assertion?

Every other gate in this framework answers a question about an artefact: did the
pipeline run, is the figure legible, does the reference resolve. None of them asks the
only question that decides whether a result may be published -- *is the claim the paper
makes the claim the evidence licenses?*  A project can pass twenty artefact gates while
its central sentence is unsupported; that failure mode is invisible to any check that
reads files instead of arguments.

The register is a YAML file, ``analysis/CLAIMS.yaml``, with one entry per claim:

    scope:
      corpus: [136M Keystrokes]
      task: [restoration]
      models: [qwen2.5-7b]
      writing_system: [Latin]
      genre: [desktop typing]
      out_of_scope:
        - axis: writing_system
          value: non-Latin
          reason: no corpus in this study
    claims:
      - id: C1
        text: "Damage operators are separable at matched severity"
        span: "separable at matched severity"
        strength: supported          # supported | tentative | exploratory
        design: preregistered        # preregistered | observational | exploratory
        evidence:
          file: docs/measurement.json
          pointer: /cross_arm/separated
          value: true
        control:
          file: docs/measurement.json
          pointer: /negative_control/fired
        assumptions: ["severity matched within 0.5 edits"]
        formal: false                # true -> Lean audit chain required

Checks, each with its own code:

    S1  register parses and has at least one claim
    S2  the claim's span appears in the manuscript (a claim not in the paper is not a
        claim, and a paper sentence absent from the register is unregistered)
    S3  every evidence pointer resolves and its value matches the register
    S4  strength is earned: ``supported`` requires a preregistered design AND a control
    S5  scope declares all five axes, or names the axis out of scope with a reason
    S6  power and multiplicity are stated and point at a file
    S7  the referee simulation exists and has no unresolved objection
    S8  a claim marked ``formal`` passes the Lean audit (see lean_audit.py)

The gate is deliberately strict about S8: a claim that *declares* itself machine-checked
but whose toolchain is missing is a FAIL, not a SKIP -- the declaration cannot be
honoured, and a silent skip would let the strongest claims be the least checked.
"""

from __future__ import annotations

import html as _html
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

from ..gates import GateResult, ToolMissing

ALLOWED_STRENGTH = {"supported", "tentative", "exploratory"}
ALLOWED_DESIGN = {"preregistered", "observational", "exploratory"}
REQUIRED_SCOPE = ("corpus", "task", "models", "writing_system", "genre")
MIN_SPAN_CHARS = 12

_TAG = re.compile(r"<[^>]+>")


class RegisterError(ValueError):
    """The register is malformed in a way that cannot be checked."""


def json_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 pointer; raise KeyError when it does not resolve."""
    if pointer in ("", "/"):
        return document
    if not pointer.startswith("/"):
        raise KeyError(f"pointer must start with '/': {pointer!r}")
    node = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict):
            node = node[token]
        else:
            raise KeyError(f"cannot descend into {type(node).__name__} at {token!r}")
    return node


def _values_match(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(actual) is bool(expected)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-9)
    return actual == expected


@dataclass
class Finding:
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ScientificValidityGate:
    """Gate S. Construct with the project root; call ``run()``."""

    name = "scientific_validity"

    def __init__(self, root: Path, register: Optional[Path] = None,
                 manuscript: Optional[Path] = None, document: Optional[Path] = None,
                 lean_cmd: Optional[object] = None,
                 scope_axes: Optional[Iterable[str]] = None):
        self.root = Path(root).resolve()
        self.register_path = Path(register) if register else self.root / "analysis" / "CLAIMS.yaml"
        # `document` is the general name: a framework claim lives in a README, a paper
        # claim in a rendered manuscript. `manuscript` is kept for existing callers.
        chosen = document or manuscript
        self.document_path = (Path(chosen) if chosen
                              else self.root / "docs" / "MANUSCRIPT.html")
        self.manuscript_path = self.document_path
        self.lean_cmd = lean_cmd
        self.scope_axes = tuple(scope_axes) if scope_axes else None

    # -- helpers ---------------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(self.register_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RegisterError(f"cannot read {self.register_path.name}: {exc}") from exc
        if not isinstance(data, dict):
            raise RegisterError("the register must be a mapping")
        return data

    def _manuscript_text(self) -> str:
        try:
            raw = self.manuscript_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
        # Entities first: a span copied from the rendered page ("a&nbsp;misspelling")
        # must match the prose a reader sees, not the source encoding.
        text = _html.unescape(_TAG.sub(" ", raw))
        return re.sub(r"\s+", " ", text)

    def _evidence(self, spec: Any, claim_id: str, label: str) -> List[Finding]:
        out: List[Finding] = []
        if not isinstance(spec, dict):
            return [Finding("S3", f"{claim_id}: {label} must be a mapping with file/pointer")]
        rel = spec.get("file")
        if not rel:
            return [Finding("S3", f"{claim_id}: {label} names no file")]
        path = (self.root / rel).resolve()
        if not path.is_file():
            return [Finding("S3", f"{claim_id}: {label} file does not exist: {rel}")]
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [Finding("S3", f"{claim_id}: {label} file is not JSON ({rel}): {exc}")]
        pointer = spec.get("pointer", "")
        try:
            actual = json_pointer(doc, pointer)
        except (KeyError, IndexError, ValueError) as exc:
            return [Finding("S3", f"{claim_id}: {label} pointer {pointer!r} does not "
                                    f"resolve in {rel}: {exc}")]
        if "value" in spec and not _values_match(actual, spec["value"]):
            out.append(Finding("S3", f"{claim_id}: {label} says {spec['value']!r} but "
                                       f"{rel}{pointer} holds {actual!r}"))
        return out

    # -- checks ----------------------------------------------------------------
    def run(self) -> GateResult:
        findings: List[Finding] = []
        try:
            data = self._load()
        except RegisterError as exc:
            return GateResult(self.name, False, status="FAIL", details={"findings": [str(exc)]})

        claims = data.get("claims") or []
        if not isinstance(claims, list) or not claims:
            return GateResult(self.name, False, status="FAIL",
                              details={"findings": ["[S1] the register has no claims"]})

        text = self._manuscript_text()
        seen_ids: set[str] = set()
        formal: List[Dict[str, Any]] = []

        for claim in claims:
            if not isinstance(claim, dict) or not claim.get("id"):
                findings.append(Finding("S1", "a claim has no id"))
                continue
            cid = str(claim["id"])
            if cid in seen_ids:
                findings.append(Finding("S1", f"duplicate claim id {cid}"))
            seen_ids.add(cid)

            # S2 -- the claim must be in the paper
            span = (claim.get("span") or "").strip()
            if len(span) < MIN_SPAN_CHARS:
                findings.append(Finding("S2", f"{cid}: span is shorter than "
                                               f"{MIN_SPAN_CHARS} characters, so it cannot "
                                               f"identify a claim"))
            elif not text:
                findings.append(Finding("S2", f"{cid}: no manuscript text to search "
                                               f"({self.document_path.name} missing)"))
            elif span not in text:
                findings.append(Finding("S2", f"{cid}: the register's span does not "
                                               f"appear in {self.document_path.name}"))

            # S3 -- evidence resolves and matches
            findings.extend(self._evidence(claim.get("evidence"), cid, "evidence"))

            # S4 -- strength is earned
            strength = claim.get("strength")
            design = claim.get("design")
            if strength not in ALLOWED_STRENGTH:
                findings.append(Finding("S4", f"{cid}: strength {strength!r} is not one "
                                               f"of {sorted(ALLOWED_STRENGTH)}"))
            if design not in ALLOWED_DESIGN:
                findings.append(Finding("S4", f"{cid}: design {design!r} is not one of "
                                               f"{sorted(ALLOWED_DESIGN)}"))
            if strength == "supported":
                if design != "preregistered":
                    findings.append(Finding("S4", f"{cid}: 'supported' requires a "
                                                   f"preregistered design, found {design!r}"))
                if not claim.get("control"):
                    findings.append(Finding("S4", f"{cid}: 'supported' without a negative "
                                                   f"control; nothing shows the analysis "
                                                   f"could have failed"))
                else:
                    findings.extend(self._evidence(claim.get("control"), cid, "control"))

            # S8 -- formal claims need the Lean chain
            if claim.get("formal"):
                formal.append(claim)

        # S5 -- scope
        scope = data.get("scope") or {}
        axes = self.scope_axes or tuple(data.get("scope_axes") or REQUIRED_SCOPE)
        oos = scope.get("out_of_scope") or []
        oos_axes = {o.get("axis") for o in oos if isinstance(o, dict)}
        for axis in axes:
            if scope.get(axis):
                continue
            if axis in oos_axes:
                if not any(o.get("reason") for o in oos if o.get("axis") == axis):
                    findings.append(Finding("S5", f"scope axis {axis!r} is out of scope "
                                                   f"without a reason"))
                continue
            findings.append(Finding("S5", f"scope axis {axis!r} is neither declared nor "
                                           f"explicitly out of scope"))

        # S6 -- power and multiplicity
        for key in ("power", "multiplicity"):
            block = data.get(key)
            if not isinstance(block, dict):
                findings.append(Finding("S6", f"{key} is not declared"))
                continue
            # A software deliverable has no sampling error; saying so explicitly is a
            # declaration, not an omission. An empty or unexplained claim is still caught.
            if block.get("not_applicable"):
                if not str(block["not_applicable"]).strip():
                    findings.append(Finding("S6", f"{key} is not applicable but gives no "
                                                   f"reason"))
                continue
            findings.extend(self._evidence(block, key.upper(), key))
            if key == "power" and not block.get("statement"):
                findings.append(Finding("S6", "power has no statement"))
            if key == "multiplicity" and not block.get("correction"):
                findings.append(Finding("S6", "multiplicity names no correction"))

        # S7 -- referee simulation
        fit = data.get("journal_fit")
        if not isinstance(fit, dict) or not fit.get("file"):
            findings.append(Finding("S7", "journal_fit is not declared"))
        else:
            rel = self.root / fit["file"]
            if not rel.is_file():
                findings.append(Finding("S7", f"referee simulation missing: {fit['file']}"))
            else:
                # The count is parsed, not trusted: a register that declares one open
                # objection while the document carries five is under-reporting, and that
                # is the exact failure this gate exists to catch.
                text = rel.read_text(encoding="utf-8", errors="ignore")
                # Count per objection block, not per marker: the document's own legend
                # explains both tags, and counting raw markers would read the legend as
                # two extra objections.
                blocks = re.split(r"(?m)^##\s+O\d+\.", text)[1:]
                open_markers = sum(1 for b in blocks if "[UNRESOLVED]" in b)
                resolved_markers = sum(1 for b in blocks if "[RESOLVED]" in b)
                untagged = [i for i, b in enumerate(blocks, 1)
                            if "[UNRESOLVED]" not in b and "[RESOLVED]" not in b]
                if untagged:
                    findings.append(Finding("S7", f"objection block(s) {untagged} carry no "
                                                   f"status tag, so they cannot be counted"))
                declared_open = int(fit.get("unresolved", 0))
                declared_total = int(fit.get("objections", len(blocks)))
                if declared_open != open_markers:
                    findings.append(Finding("S7", f"the register declares "
                                                   f"{declared_open} unresolved objection(s) "
                                                   f"but the document carries "
                                                   f"{open_markers} [UNRESOLVED] markers"))
                if declared_total != open_markers + resolved_markers:
                    findings.append(Finding("S7", f"the register declares "
                                                   f"{declared_total} objection(s) but the "
                                                   f"document carries "
                                                   f"{open_markers + resolved_markers}"))
                if open_markers:
                    findings.append(Finding("S7", f"{open_markers} referee objection(s) "
                                                   f"remain unresolved"))

        # S8 -- Lean audit for formal claims
        if formal:
            from .lean_audit import LeanAudit

            for claim in formal:
                spec = claim.get("lean") or {}
                project = (self.root / spec.get("project", ".")).resolve()
                theorem = spec.get("theorem")
                if not theorem:
                    findings.append(Finding("S8", f"{claim['id']}: formal claim names no "
                                                   f"theorem"))
                    continue
                audit = LeanAudit(project=project, theorem=theorem,
                                  module=spec.get("module"),
                                  allowed_axioms=tuple(spec.get("allowed_axioms", ())) or None,
                                  lake_cmd=self.lean_cmd)
                ok, messages = audit.run()
                if not ok:
                    for m in messages:
                        findings.append(Finding("S8", f"{claim['id']}: {m}"))

        passed = not findings
        return GateResult(
            self.name, passed, score=1.0 if passed else 0.0,
            status="PASS" if passed else "FAIL",
            details={
                "register": str(self.register_path.relative_to(self.root))
                if self.register_path.is_relative_to(self.root) else str(self.register_path),
                "claims": len(claims),
                "formal_claims": len(formal),
                "findings": [str(f) for f in findings],
            },
            artifacts=[str(self.register_path)],
        )
