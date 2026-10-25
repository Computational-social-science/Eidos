"""Three directions of mutation testing, because one direction is easy to fool.

1. **Wrong mutants must be rejected.**
2. **Equivalent mutants must pass.** The same rate written as 92%, as 92 of 100, or with a
   trailing zero is not a different claim. A gate that rejects everything scores perfectly on
   direction 1 and is useless; direction 2 is what makes direction 1 mean something.
3. **Combinations must be rejected.** Two independent errors at once is the realistic case:
   a value that drifted and a control that was removed.

    python tools/fuzz_register.py
    python tools/fuzz_register.py --verbose
"""

from __future__ import annotations

import argparse
import copy
import itertools
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


def _report(root: Path, text: str) -> None:
    (root / "docs/REPORT.md").write_text(f"# Fixture study\n\n{text}\n", encoding="utf-8")


#: name -> function(register, root) that makes the register wrong in one way.
WRONG = {
    "no_claims": lambda reg, root: reg.update(claims=[]),
    "value_drift": lambda reg, root: _claim(reg)["evidence"].update(value=0.85),
    "pointer_gone": lambda reg, root: _claim(reg)["evidence"].update(pointer="/nope"),
    "evidence_file_gone": lambda reg, root: _claim(reg)["evidence"].update(file="docs/none.json"),
    "prose_number_drift": lambda reg, root: _report(root,
                                                    "The operator answers 0.85 of the items."),
    "span_removed": lambda reg, root: _report(root, "Something else entirely."),
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


def _as_percent(reg: dict, root: Path) -> None:
    _claim(reg)["span"] = "operator answers 92% of the items"
    _report(root, "The operator answers 92% of the items on the constructed set.")


def _as_ratio(reg: dict, root: Path) -> None:
    _claim(reg)["span"] = "operator answers 92 of 100 items"
    _report(root, "The operator answers 92 of 100 items on the constructed set.")


def _trailing_zero(reg: dict, root: Path) -> None:
    _claim(reg)["span"] = "operator answers 0.920 of the items"
    _report(root, "The operator answers 0.920 of the items on the constructed set.")


#: name -> function(register, root). Each is the *same claim*, written differently.
EQUIVALENT = {
    "same_rate_as_percent": _as_percent,
    "same_rate_as_ratio": _as_ratio,
    "same_rate_trailing_zero": _trailing_zero,
    "extra_assumption": lambda reg, root: _claim(reg)["assumptions"].append("one machine"),
    "scope_wording": lambda reg, root: reg["scope"].update(
        items=["one hundred constructed items, worded differently"]),
    "key_order": lambda reg, root: reg.update({k: reg[k] for k in reversed(list(reg))}),
}

#: Pairs of independent errors. Real registers are wrong in more than one way.
PAIR_POOL = ("value_drift", "pointer_gone", "unearned_supported", "no_control",
             "scope_axis_gone", "power_gone", "referee_file_gone", "formal_without_proof")


def run(mutators: list) -> tuple[str, list[str], str]:
    tmp = Path(tempfile.mkdtemp(prefix="eidos-fuzz-"))
    try:
        root = tmp / "clean"
        shutil.copytree(CLEAN, root)
        register_path = root / "analysis" / "CLAIMS.yaml"
        register = yaml.safe_load(register_path.read_text(encoding="utf-8"))
        for fn in mutators:
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

    wrong_rows, blind = [], []
    print("wrong mutants (must FAIL)")
    for name, fn in WRONG.items():
        verdict, checks, first = run([fn])
        ok = verdict == "FAIL"
        wrong_rows.append({"mutation": name, "verdict": verdict, "checks": checks, "ok": ok})
        print(f"  {name:<26} {verdict:<5} {','.join(checks) or '—':<10} "
              f"{'caught' if ok else 'BLIND SPOT'}")
        if not ok:
            blind.append(name)
        elif args.verbose:
            print(f"      {first[:110]}")

    equiv_rows, over = [], []
    print("\nequivalent mutants (must PASS)")
    for name, fn in EQUIVALENT.items():
        verdict, checks, first = run([fn])
        ok = verdict == "PASS"
        equiv_rows.append({"mutation": name, "verdict": verdict, "checks": checks, "ok": ok})
        print(f"  {name:<26} {verdict:<5} {','.join(checks) or '—':<10} "
              f"{'accepted' if ok else 'OVER-REJECTED'}")
        if not ok:
            over.append(name)
            if args.verbose:
                print(f"      {first[:110]}")

    pairs = list(itertools.combinations(PAIR_POOL, 2))
    pair_rows, pair_blind = [], []
    print(f"\ncombinations ({len(pairs)} pairs, must FAIL)")
    for a, b in pairs:
        verdict, checks, _ = run([WRONG[a], WRONG[b]])
        ok = verdict == "FAIL"
        pair_rows.append({"pair": [a, b], "verdict": verdict, "checks": checks, "ok": ok})
        if not ok:
            pair_blind.append(f"{a}+{b}")
            print(f"  {a + '+' + b:<42} PASS  BLIND SPOT")
    if not pair_blind:
        print(f"  all {len(pairs)} pairs rejected")

    (ROOT / "docs" / "FUZZ.json").write_text(
        json.dumps({"wrong": wrong_rows, "equivalent": equiv_rows, "pairs": pair_rows,
                    "blind_spots": blind + pair_blind, "over_rejections": over,
                    "ok": not blind and not pair_blind and not over}, indent=2),
        encoding="utf-8")

    print()
    failed = False
    if blind:
        print(f"[FAIL] the gate accepts {len(blind)} wrong register(s): {', '.join(blind)}")
        failed = True
    if pair_blind:
        print(f"[FAIL] the gate accepts {len(pair_blind)} wrong pair(s): {', '.join(pair_blind)}")
        failed = True
    if over:
        print(f"[FAIL] the gate rejects {len(over)} equivalent register(s): {', '.join(over)}")
        failed = True
    if failed:
        return 1
    print(f"[OK] {len(WRONG)} wrong mutants and {len(pairs)} pairs rejected; "
          f"{len(EQUIVALENT)} equivalent mutants accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
