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
        # A boolean matches a boolean and nothing else. Comparing truthiness let a `true`
        # artefact satisfy a claim of 0.92, because bool(0.92) is True.
        return (isinstance(actual, bool) and isinstance(expected, bool)
                and actual is expected)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-9)
    return actual == expected


@dataclass
class Finding:
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_OF_PAIR = re.compile(r"(\d+(?:\.\d+)?)\s+of\s+(\d+(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_WORD_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
                "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}


def _numbers_in(text: str) -> list[float]:
    """Every way a claim can state a number: digits, 'a of b' ratios, percentages, words."""
    values = [float(m) for m in _NUMBER.findall(text)]
    values += [float(a) / float(b) for a, b in _OF_PAIR.findall(text) if float(b)]
    values += [float(p) / 100.0 for p in _PERCENT.findall(text)]
    values += [float(v) for word, v in _WORD_NUMBER.items()
               if re.search(r"" + word + r"", text, re.IGNORECASE)]
    return values


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
        # A project's claims need not live in one file: a Lean library has one file per
        # module, so the deliverable is a set. `document` accepts a path or a sequence.
        if chosen is None:
            self.document_paths = [self.root / "docs" / "MANUSCRIPT.html"]
        elif isinstance(chosen, (list, tuple)):
            self.document_paths = [Path(p) for p in chosen]
        else:
            self.document_paths = [Path(chosen)]
        self.document_path = self.document_paths[0]
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

    def _numeric_agreement(self, claim: dict, cid: str) -> list[Finding]:
        """S9: a claim may cite evidence, yet say a different number than the evidence holds.

        S3 compares the register's `value` with the file; it never reads the prose. So a
        register that points at the right file and then writes a better number in the paper
        passes S2 and S3. This closes that: every number the span states must include the
        evidence value, or the claim fails.
        """
        evidence = claim.get("evidence") or {}
        if not isinstance(evidence, dict) or "value" not in evidence:
            return []
        value = evidence["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return []
        span = str(claim.get("span") or "")
        # Units matter: "19 of 19" is a count statement whose ratio happens to be 1.0, and
        # a count of 1 must not be satisfied by that ratio. A register that means a rate
        # says `units: rate`; otherwise a value >= 1 is read as a count.
        units = str(claim.get("units") or ("rate" if 0 < float(value) < 1 else "count"))
        if units == "count":
            candidates = [float(m) for m in _NUMBER.findall(span)]
            candidates += [float(v) for word, v in _WORD_NUMBER.items()
                           if re.search(r"" + word + r"", span, re.IGNORECASE)]
        else:
            candidates = _numbers_in(span)
            # A rate lives in [0, 1]. A sample size written next to the rate — "accuracy 0.92
            # (n=100)" — is not a candidate value, and letting it through means a claim about
            # 0.92 is satisfied by the count 100 when the evidence holds 100 by mistake.
            if units == "rate":
                if not 0.0 <= float(value) <= 1.0:
                    return [Finding("S9", f"{cid}: units are 'rate' but the evidence holds "
                                           f"{value!r}, outside [0, 1]")]
                candidates = [c for c in candidates if c <= 1.0 + 1e-9]
        if not candidates:
            return []          # nothing numeric in the text: this check does not apply
        tolerance = max(1e-9, abs(float(value)) * 1e-6)
        if any(abs(candidate - float(value)) <= tolerance for candidate in candidates):
            return []
        shown = sorted({round(c, 4) for c in candidates})
        return [Finding("S9", f"{cid}: the text states {shown[:6]} but the evidence holds "
                               f"{value!r}")]

    def _manuscript_text(self) -> str:
        parts = []
        for path in self.document_paths:
            try:
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
        raw = "\n".join(parts)
        # HTML only: in Lean or Markdown a "<" is an operator, and stripping "tags"
        # from source deleted whole expressions ("h : a <= b" vanished), so a theorem
        # span could never match its own file.
        if all(p.suffix.lower() in (".html", ".htm") for p in self.document_paths):
            text = _html.unescape(_TAG.sub(" ", raw))
        else:
            text = raw
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

    # -- verifiers ---------------------------------------------------------------
    def _verifier_findings(self, claims: list[dict]) -> tuple[list[Finding], list[str]]:
        """S10: a claim that cites or reports numbers needs the verifier artefacts behind it.

        Missing artefact -> BLOCKED (nothing judged the claim yet), not FAIL (which would claim the
        claim is wrong). A present artefact that says no is a FAIL, and the refusal is quoted.
        """
        findings: list[Finding] = []
        blocked: list[str] = []
        root = self.root

        citations_path = root / "artifacts" / "literature" / "proofpath.json"
        stats_path = root / "artifacts" / "evaluation" / "stat_recompute.json"
        citations = None
        if citations_path.is_file():
            citations = json.loads(citations_path.read_text(encoding="utf-8"))
        stats = None
        if stats_path.is_file():
            stats = json.loads(stats_path.read_text(encoding="utf-8"))

        for claim in claims:
            cid = claim.get("id", "?")
            refs = claim.get("citations") or []
            if refs:
                if citations is None:
                    blocked.append(f"{cid}: cites {len(refs)} reference(s) but "
                                   f"artifacts/literature/proofpath.json does not exist")
                else:
                    by_ref = {r.get("reference"): r for r in citations.get("records") or []}
                    for ref in refs:
                        record = by_ref.get(ref)
                        if record is None:
                            blocked.append(f"{cid}: {ref} is not in the proofpath artefact")
                        elif record.get("status") != "VERIFIED":
                            findings.append(Finding(
                                "S10", f"{cid}: cited {ref} is {record.get('status')} "
                                       f"({record.get('reason') or 'no reason'})"))
            if claim.get("statistics"):
                if stats is None:
                    blocked.append(f"{cid}: reports statistics but "
                                   f"artifacts/evaluation/stat_recompute.json does not exist")
                elif stats.get("verdict") != "PASS":
                    bad = [c for c in stats.get("checks") or [] if c.get("status") != "PASS"]
                    findings.append(Finding(
                        "S10", f"{cid}: statistics do not recompute "
                               f"({', '.join(c.get('id', '?') for c in bad) or 'verdict FAIL'})"))
            if claim.get("support") == "required":
                from framework.verifiers import support
                allowed, reason = support.passable(cid)
                if not allowed:
                    blocked.append(f"{cid}: support {reason}")
            if claim.get("s4"):
                findings_s4, blocked_s4 = self._s4_verdict(cid, claim["s4"])
                findings.extend(findings_s4)
                blocked.extend(blocked_s4)
        return findings, blocked

    def _s4_verdict(self, claim_id: str, record: dict) -> tuple[list[Finding], list[str]]:
        """S11: the design verdict is arithmetic, and arithmetic is not a model's opinion.

        The record must carry the fields, not a paragraph: extraction from prose reads 7/10 on unseen
        paraphrases (docs/S4_VERDICT.md), so a prose claim cannot be adjudicated here at all. When the
        fields are present the rule decides; an asserted verdict that disagrees is a FAIL, whoever
        wrote it — including a model.
        """
        from framework.verifiers import extract_s4

        fields = {k: record.get(k) for k in ("power", "required", "prereg", "named", "adjusted",
                                             "declared")}
        if not extract_s4.complete(fields):
            missing = [k for k in ("prereg", "named", "adjusted", "declared") if fields[k] is None]
            return [], [f"{claim_id}: S4 record is incomplete ({', '.join(missing)} unread); "
                        f"a verdict here would be a guess"]
        decided = extract_s4.verdict(fields)
        asserted = record.get("verdict")
        if not asserted:
            return [], [f"{claim_id}: S4 record states no verdict to check"]
        if asserted != decided:
            return [Finding("S11", f"{claim_id}: design verdict {asserted} does not follow from the "
                                    f"fields (power {fields['power']}, required {fields['required']}, "
                                    f"named {fields['named']}, adjusted {fields['adjusted']}, "
                                    f"prereg {fields['prereg']}, declared {fields['declared']}) "
                                    f"-> {decided}")], []
        return [], []

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
                                               f"({', '.join(p.name for p in self.document_paths)} missing)"))
            elif span not in text:
                findings.append(Finding("S2", f"{cid}: the register's span does not "
                                               f"appear in {', '.join(p.name for p in self.document_paths)}"))

            # S3 -- evidence resolves and matches
            findings.extend(self._evidence(claim.get("evidence"), cid, "evidence"))

            # S9 -- the number in the prose must be the number in the evidence
            findings.extend(self._numeric_agreement(claim, cid))

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

        verifier_findings, blocked = self._verifier_findings(claims)
        findings.extend(verifier_findings)

        passed = not findings and not blocked
        if passed:
            verdict = "PASS"
        elif blocked and not findings:
            verdict = "BLOCKED"
        else:
            verdict = "FAIL"
        return GateResult(
            self.name, passed, score=1.0 if passed else 0.0,
            status=verdict,
            details={
                "register": str(self.register_path.relative_to(self.root))
                if self.register_path.is_relative_to(self.root) else str(self.register_path),
                "claims": len(claims),
                "formal_claims": len(formal),
                "findings": [str(f) for f in findings],
                "blocked": blocked,
            },
            artifacts=[str(self.register_path)],
        )
