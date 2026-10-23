"""Tests for Gate S (scientific validity) and the Lean audit chain.

Both directions are covered for every rule: a good register passes, and each defect
class fails with its own code. The Lean path is exercised through a fake `lake` whose
behaviour is switched by environment variables, so the audit logic is tested without
requiring a Lean toolchain -- except that the missing-tool case must FAIL (a formal
claim cannot silently pass when no checker exists).
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.validity import ScientificValidityGate  # noqa: E402
from framework.validity.lean_audit import LeanAudit  # noqa: E402

FAKE_LAKE = textwrap.dedent(
    """
    import os, sys
    args = sys.argv[1:]
    if args[:1] == ["build"]:
        sys.exit(0)
    target = args[-1]
    if target.endswith("_control.lean"):
        # A control that compiles means the kernel is not checking.
        sys.exit(0 if os.environ.get("FAKE_BAD_KERNEL") == "1" else 1)
    if os.environ.get("FAKE_PROBE_ERROR") == "1":
        print("error: unknown constant 'Demo.thm'", file=sys.stderr)
        sys.exit(1)
    axioms = os.environ.get("FAKE_AXIOMS", "propext, Classical.choice, Quot.sound")
    print(f"'Demo.thm' depends on axioms: [{axioms}]")
    sys.exit(0)
    """
).strip()

MANUSCRIPT = "<h2>Main</h2><p>The operators are separable at matched severity.</p>"

ARTPATH = "data/evidence.json"
ARTIFACT = {"cross_arm": {"separated": True}, "control": {"fired": True},
            "power": {"n": 4200}, "multiplicity": {"family": 3}}


def write_project(root: Path, *, claims=None, scope=None, power=None,
                  multiplicity=None, journal=None, manuscript=MANUSCRIPT) -> Path:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "analysis").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "MANUSCRIPT.html").write_text(manuscript, encoding="utf-8")
    (root / "data" / "evidence.json").write_text(json.dumps(ARTIFACT), encoding="utf-8")
    (root / "docs" / "REFEREE.md").write_text(
        "## O1. Something. `[RESOLVED]` — evidence\n", encoding="utf-8")
    (root / "lakefile.lean").write_text("-- stub\n", encoding="utf-8")

    default_claim = {
        "id": "C1",
        "text": "Operators are separable",
        "span": "separable at matched severity",
        "strength": "supported",
        "design": "preregistered",
        "evidence": {"file": ARTPATH, "pointer": "/cross_arm/separated", "value": True},
        "control": {"file": ARTPATH, "pointer": "/control/fired"},
        "assumptions": ["severity matched"],
        "formal": False,
    }
    register = {
        "scope": scope or {
            "corpus": ["136M Keystrokes"], "task": ["restoration"],
            "models": ["qwen2.5-7b"], "writing_system": ["Latin"],
            "genre": ["desktop typing"], "out_of_scope": [],
        },
        "claims": claims if claims is not None else [default_claim],
        "power": power or {"statement": "simulated power 0.86 at n=4200",
                           "file": ARTPATH, "pointer": "/power/n"},
        "multiplicity": multiplicity or {"family": 3, "correction": "Holm",
                                         "file": ARTPATH, "pointer": "/multiplicity/family"},
        "journal_fit": journal or {"file": "docs/REFEREE.md", "objections": 1,
                                   "unresolved": 0},
    }
    path = root / "analysis" / "CLAIMS.yaml"
    path.write_text(yaml.safe_dump(register, sort_keys=False), encoding="utf-8")
    return path


def gate(root: Path, **kw) -> object:
    return ScientificValidityGate(root, **kw).run()


def codes(result) -> list[str]:
    return [f.split("]")[0].strip("[") for f in result.details["findings"]]


# -- the happy path ------------------------------------------------------------
def test_valid_register_passes(tmp_path: Path) -> None:
    write_project(tmp_path)
    result = gate(tmp_path)
    assert result.status == "PASS", result.details["findings"]


# -- each rule can fail --------------------------------------------------------
def test_claim_absent_from_manuscript_fails(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[{
        "id": "C1", "span": "a sentence the paper never prints", "strength": "tentative",
        "design": "exploratory", "evidence": {"file": ARTPATH, "pointer": "/cross_arm/separated"},
    }])
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S2" in codes(r)


def test_evidence_pointer_must_resolve(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[{
        "id": "C1", "span": "separable at matched severity", "strength": "tentative",
        "design": "exploratory",
        "evidence": {"file": ARTPATH, "pointer": "/no/such/key"},
    }])
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S3" in codes(r)


def test_evidence_value_must_match(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[{
        "id": "C1", "span": "separable at matched severity", "strength": "tentative",
        "design": "exploratory",
        "evidence": {"file": ARTPATH, "pointer": "/cross_arm/separated", "value": False},
    }])
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S3" in codes(r)


def test_supported_requires_preregistration(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[{
        "id": "C1", "span": "separable at matched severity", "strength": "supported",
        "design": "observational",
        "evidence": {"file": ARTPATH, "pointer": "/cross_arm/separated"},
        "control": {"file": ARTPATH, "pointer": "/control/fired"},
    }])
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S4" in codes(r)


def test_supported_requires_a_control(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[{
        "id": "C1", "span": "separable at matched severity", "strength": "supported",
        "design": "preregistered",
        "evidence": {"file": ARTPATH, "pointer": "/cross_arm/separated"},
    }])
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S4" in codes(r)


def test_scope_axis_must_be_declared(tmp_path: Path) -> None:
    write_project(tmp_path, scope={"corpus": ["x"], "task": ["y"], "models": ["z"],
                                   "writing_system": ["Latin"], "genre": []})
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S5" in codes(r)


def test_out_of_scope_axis_needs_a_reason(tmp_path: Path) -> None:
    write_project(tmp_path, scope={
        "corpus": ["x"], "task": ["y"], "models": ["z"], "writing_system": ["Latin"],
        "genre": [], "out_of_scope": [{"axis": "genre"}]})
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S5" in codes(r)


def test_unresolved_referee_objection_fails(tmp_path: Path) -> None:
    write_project(tmp_path, journal={"file": "docs/REFEREE.md", "objections": 1,
                                     "unresolved": 1})
    (tmp_path / "docs" / "REFEREE.md").write_text(
        "## O1. No second corpus. `[UNRESOLVED]`\n", encoding="utf-8")
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S7" in codes(r)


def test_understated_unresolved_count_fails(tmp_path: Path) -> None:
    """A register that declares zero open objections while the document carries two is
    the failure mode the count-parsing exists to catch."""
    write_project(tmp_path, journal={"file": "docs/REFEREE.md", "objections": 2,
                                     "unresolved": 0})
    (tmp_path / "docs" / "REFEREE.md").write_text(
        "## O1. `[UNRESOLVED]`\n\n## O2. `[UNRESOLVED]`\n", encoding="utf-8")
    r = gate(tmp_path)
    assert r.status == "FAIL" and "S7" in codes(r)
    assert any("declares 0 unresolved" in f for f in r.details["findings"])


def test_missing_register_fails(tmp_path: Path) -> None:
    r = gate(tmp_path)
    assert r.status == "FAIL"


# -- the Lean chain ------------------------------------------------------------
def fake_lake(tmp_path: Path) -> list[str]:
    script = tmp_path / "fake_lake.py"
    script.write_text(FAKE_LAKE, encoding="utf-8")
    return [sys.executable, str(script)]


def formal_claim() -> dict:
    return {
        "id": "C2", "span": "separable at matched severity", "strength": "supported",
        "design": "preregistered",
        "evidence": {"file": ARTPATH, "pointer": "/cross_arm/separated"},
        "control": {"file": ARTPATH, "pointer": "/control/fired"},
        "formal": True, "lean": {"project": ".", "module": "Demo", "theorem": "Demo.thm"},
    }


def test_formal_claim_with_clean_axioms_passes(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    r = ScientificValidityGate(tmp_path, lean_cmd=fake_lake(tmp_path)).run()
    assert r.status == "PASS", r.details["findings"]


def test_formal_claim_with_sorry_fails(tmp_path: Path, monkeypatch) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    monkeypatch.setenv("FAKE_AXIOMS", "propext, sorryAx")
    r = ScientificValidityGate(tmp_path, lean_cmd=fake_lake(tmp_path)).run()
    assert r.status == "FAIL" and "S8" in codes(r)
    assert any("sorryAx" in f for f in r.details["findings"])


def test_formal_claim_with_extra_axiom_fails(tmp_path: Path, monkeypatch) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    monkeypatch.setenv("FAKE_AXIOMS", "propext, MyAxiom")
    r = ScientificValidityGate(tmp_path, lean_cmd=fake_lake(tmp_path)).run()
    assert r.status == "FAIL" and "S8" in codes(r)


def test_formal_claim_probe_error_fails(tmp_path: Path, monkeypatch) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    monkeypatch.setenv("FAKE_PROBE_ERROR", "1")
    r = ScientificValidityGate(tmp_path, lean_cmd=fake_lake(tmp_path)).run()
    assert r.status == "FAIL" and "S8" in codes(r)


def test_formal_claim_with_broken_kernel_fails(tmp_path: Path, monkeypatch) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    monkeypatch.setenv("FAKE_BAD_KERNEL", "1")
    r = ScientificValidityGate(tmp_path, lean_cmd=fake_lake(tmp_path)).run()
    assert r.status == "FAIL" and "S8" in codes(r)
    assert any("not checking proofs" in f for f in r.details["findings"])


def test_formal_claim_without_lake_fails_not_skips(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    r = ScientificValidityGate(tmp_path, lean_cmd=["definitely-not-a-real-lake"]).run()
    assert r.status == "FAIL"
    assert any("not installed" in f for f in r.details["findings"])


def test_probe_files_are_removed(tmp_path: Path) -> None:
    write_project(tmp_path, claims=[formal_claim()])
    ScientificValidityGate(tmp_path, lean_cmd=fake_lake(tmp_path)).run()
    assert not list(tmp_path.glob("_emdash_audit_*.lean"))


def test_lean_audit_missing_project_fails(tmp_path: Path) -> None:
    ok, messages = LeanAudit(tmp_path / "nope", "Demo.thm", module="Demo",
                             lake_cmd=["x"]).run()
    assert not ok and any("does not exist" in m for m in messages)


def test_non_html_document_is_not_tag_stripped(tmp_path: Path):
    """A Lean or Markdown deliverable contains "<" as an operator; stripping "tags" from
    it deleted whole expressions and no theorem span could ever match."""
    write_project(tmp_path)
    source = tmp_path / "docs" / "Core.lean"
    source.write_text("theorem mono (h : a <= b) : P := by\n  exact h\n", encoding="utf-8")
    gate = ScientificValidityGate(tmp_path, document=source,
                                  register=tmp_path / "analysis" / "CLAIMS.yaml")
    # the span below lives in the .lean file and would be eaten by tag stripping
    register = tmp_path / "analysis" / "CLAIMS.yaml"
    data = yaml.safe_load(register.read_text(encoding="utf-8"))
    data["claims"][0]["span"] = "theorem mono (h : a <= b) : P := by"
    register.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result = gate.run()
    assert not any("does not appear" in f for f in result.details["findings"])
