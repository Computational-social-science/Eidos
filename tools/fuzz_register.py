"""Mutate a valid register and require the gate to reject every mutant.

Hand-written fixtures test the failure modes someone thought of. Mutation testing asks the
complementary question: is there a wrong register the gate *accepts*? Each mutant below is the
clean fixture with exactly one field changed; a mutant that passes is a blind spot, and this
audit fails on it.

    python tools/fuzz_register.py
    python tools/fuzz_register.py --verbose
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.validity import ScientificValidityGate  # noqa: E402

CLEAN = ROOT / "reference" / "fixtures" / "clean"


def _claim(register: dict) -> dict:
    return register["claims"][0]


#: name -> function(register, root) that makes the register wrong in one way.
MUTATIONS = {
    "no_claims": lambda reg, root: reg.update(claims=[]),
    "value_drift": lambda reg, root: _claim(reg)["evidence"].update(value=0.85),
    "pointer_gone": lambda reg, root: _claim(reg)["evidence"].update(pointer="/nope"),
    "evidence_file_gone": lambda reg, root: _claim(reg)["evidence"].update(file="docs/none.json"),
    "prose_number_drift": lambda reg, root: (root / "docs/REPORT.md").write_text(
        "# Fixture study\n\nThe operator answers 0.85 of the items.\n", encoding="utf-8"),
    "span_removed": lambda reg, root: (root / "docs/REPORT.md").write_text(
        "# Fixture study\n\nSomething else entirely.\n", encoding="utf-8"),
    "unearned_supported": lambda reg, root: _claim(reg).update(design="exploratory"),
    "no_control": lambda reg, root: _claim(reg).pop("control", None),
    "bad_strength": lambda reg, root: _claim(reg).update(strength="proven"),
    "scope_axis_gone": lambda reg, root: reg["scope"].pop("threshold", None),
    "scope_oos_without_reason": lambda reg, root: (reg["scope"].pop("threshold", None),
                                                   reg["scope"].update(
                                                       out_of_scope=[{"axis": "threshold"}])),
    "power_gone": lambda reg, root: reg.pop("power", None),
    "multiplicity_gone": lambda reg, root: reg.pop("multiplicity", None),
    "referee_file_gone": lambda reg, root: reg["journal_fit"].update(file="docs/nope.md"),
    "referee_under_reported": lambda reg, root: reg["journal_fit"].update(unresolved=0,
                                                                         objections=3),
    "formal_without_proof": lambda reg, root: _claim(reg).update(
        formal=True, lean={"project": ".", "theorem": "nothing_here"}),
    "duplicate_id": lambda reg, root: reg["claims"].append(copy.deepcopy(_claim(reg))),
    "value_as_string": lambda reg, root: _claim(reg)["evidence"].update(value="0.92"),
    "second_claim_wrong": lambda reg, root: reg["claims"].append(
        {**_claim(reg), "id": "F2", "evidence": {**_claim(reg)["evidence"], "value": 0.5}}),
}


def run_one(mutation: str, fn) -> tuple[str, list[str], str]:
    tmp = Path(tempfile.mkdtemp(prefix="eidos-fuzz-"))
    try:
        root = tmp / "clean"
        shutil.copytree(CLEAN, root)
        register_path = root / "analysis" / "CLAIMS.yaml"
        register = yaml.safe_load(register_path.read_text(encoding="utf-8"))
        fn(register, root)
        register_path.write_text(yaml.safe_dump(register, sort_keys=False), encoding="utf-8")

        gate = ScientificValidityGate(root, register=register_path,
                                      document=root / "docs" / "REPORT.md")
        result = gate.run()
        findings = [str(f) for f in (getattr(result, "details", {}) or {}).get("findings", [])]
        verdict = "PASS" if result.passed else "FAIL"
        checks = sorted({f.split("]")[0].lstrip("[") for f in findings if f.startswith("[S")})
        return verdict, checks, findings[0] if findings else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    rows, blind = [], []
    for name, fn in MUTATIONS.items():
        verdict, checks, first = run_one(name, fn)
        ok = verdict == "FAIL"
        rows.append({"mutation": name, "verdict": verdict, "checks": checks, "caught": ok})
        print(f"{name:<26} {verdict:<5} {','.join(checks) or '—':<10} "
              f"{'caught' if ok else 'BLIND SPOT'}")
        if not ok:
            blind.append(name)
        elif args.verbose:
            print(f"    {first[:120]}")

    (ROOT / "docs" / "FUZZ.json").write_text(
        json.dumps({"mutations": rows, "blind_spots": blind, "ok": not blind}, indent=2),
        encoding="utf-8")

    print()
    if blind:
        print(f"[FAIL] the gate accepts {len(blind)} wrong register(s): {', '.join(blind)}")
        return 1
    print(f"[OK] all {len(MUTATIONS)} mutations rejected; no wrong register passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
