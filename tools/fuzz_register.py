"""Mutation testing in four directions, because one direction is easy to fool.

1. **Wrong registers must be rejected.**
2. **Equivalent registers must pass.** The same rate as 92%, as 92 of 100, with a trailing zero,
   or with a sample size beside it, is not a different claim. A gate that rejects everything
   scores perfectly on direction 1 and is useless; direction 2 makes direction 1 mean something.
3. **Wrong evidence must be rejected.** A missing key, a string where a number belongs, a NaN,
   a negative rate, a list. The register can be perfect and the artefact wrong.
4. **Combinations must be rejected.** Two independent errors at once is the realistic case.

Every run appends to docs/fuzz_history.jsonl: the number of blind spots over time is evidence
about the framework, not a snapshot.

    python tools/fuzz_register.py
    python tools/fuzz_register.py --verbose
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import itertools
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.validity import ScientificValidityGate  # noqa: E402

CLEAN = ROOT / "reference" / "fixtures" / "clean"
HISTORY = ROOT / "docs" / "fuzz_history.jsonl"


def _claim(register: dict) -> dict:
    return register["claims"][0]


def _report(root: Path, text: str) -> None:
    (root / "docs/REPORT.md").write_text(f"# Fixture study\n\n{text}\n", encoding="utf-8")


def _evidence(root: Path, **changes) -> None:
    path = root / "docs/evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is KeyError:
            data.pop(key, None)
        else:
            data[key] = value
    path.write_text(json.dumps(data), encoding="utf-8")


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
    # a declared rate stored as a percentage: the number is right, its unit is not
    "rate_stored_as_percent": lambda reg, root: _claim(reg).update(
        units="rate", evidence={**_claim(reg)["evidence"], "value": 92}),
    # a rate whose span carries only a count: nothing in the text can be the value
    "rate_without_a_rate": lambda reg, root: (_claim(reg).update(units="rate"),
                                              _report(root, "The operator answers 100 items.")),
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


def _with_sample_size(reg: dict, root: Path) -> None:
    _claim(reg).update(units="rate", span="operator answers 0.92 of the items (n=100)")
    _report(root, "The operator answers 0.92 of the items (n=100) on the constructed set.")


def _percent_with_trials(reg: dict, root: Path) -> None:
    _claim(reg).update(units="rate", span="operator answers 92% over 100 items")
    _report(root, "The operator answers 92% over 100 items on the constructed set.")


#: name -> function(register, root). Each is the *same claim*, written differently.
EQUIVALENT = {
    "same_rate_as_percent": _as_percent,
    "same_rate_as_ratio": _as_ratio,
    "same_rate_trailing_zero": _trailing_zero,
    "rate_with_sample_size": _with_sample_size,
    "rate_percent_with_trials": _percent_with_trials,
    "extra_assumption": lambda reg, root: _claim(reg)["assumptions"].append("one machine"),
    "scope_wording": lambda reg, root: reg["scope"].update(
        items=["one hundred constructed items, worded differently"]),
    "key_order": lambda reg, root: reg.update({k: reg[k] for k in reversed(list(reg))}),
}

#: name -> function(register, root). The artefact is wrong, the register is untouched.
WRONG_EVIDENCE = {
    "evidence_key_missing": lambda reg, root: _evidence(root, rate=KeyError),
    "evidence_null": lambda reg, root: _evidence(root, rate=None),
    "evidence_string": lambda reg, root: _evidence(root, rate="0.92"),
    "evidence_nan": lambda reg, root: _evidence(root, rate=float("nan")),
    "evidence_negative": lambda reg, root: _evidence(root, rate=-0.92),
    "evidence_list": lambda reg, root: _evidence(root, rate=[0.92]),
    "evidence_bool": lambda reg, root: _evidence(root, rate=True),
}

#: The artefact gains a field nobody cites. That is not a lie.
EQUIVALENT_EVIDENCE = {
    "evidence_extra_field": lambda reg, root: _evidence(root, notes="unused by the claim"),
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


def _section(title: str, cases: dict, want: str, verbose: bool, rows: list) -> list[str]:
    print(f"\n{title}")
    misses = []
    for name, fn in cases.items():
        verdict, checks, first = run([fn])
        ok = verdict == want
        rows.append({"mutation": name, "expected": want, "verdict": verdict,
                     "checks": checks, "ok": ok})
        label = "ok" if ok else ("BLIND SPOT" if want == "FAIL" else "OVER-REJECTED")
        print(f"  {name:<26} {verdict:<5} {','.join(checks) or '—':<10} {label}")
        if not ok:
            misses.append(name)
            if verbose:
                print(f"      {first[:110]}")
    if not misses:
        print(f"  all {len(cases)} behave as required")
    return misses


KEYS = ("wrong", "equivalent", "wrong_evidence", "pairs", "blind_spots",
        "over_rejections", "ok")


def _compact_history() -> None:
    """Collapse consecutive identical outcomes.

    Two runs of this tool — the hook's and a manual one — can append the same state within a
    minute of each other, and a log of states that repeats itself is a log of keystrokes.
    """
    try:
        rows = [json.loads(line) for line in HISTORY.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except (OSError, json.JSONDecodeError):
        return
    kept, previous = [], None
    for row in rows:
        signature = tuple(row.get(k) for k in KEYS)
        if signature != previous:
            kept.append(row)
            previous = signature
    if len(kept) != len(rows):
        HISTORY.write_text("".join(json.dumps(r) + chr(10) for r in kept), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-record", action="store_true",
                    help="do not rewrite docs/FUZZ.json or append to the history")
    args = ap.parse_args(argv)

    wrong_rows: list[dict] = []
    blind = _section("wrong registers (must FAIL)", WRONG, "FAIL", args.verbose, wrong_rows)

    equiv_rows: list[dict] = []
    over = _section("equivalent registers (must PASS)", EQUIVALENT, "PASS", args.verbose,
                    equiv_rows)

    ev_wrong_rows: list[dict] = []
    ev_blind = _section("wrong evidence (must FAIL)", WRONG_EVIDENCE, "FAIL", args.verbose,
                        ev_wrong_rows)

    ev_equiv_rows: list[dict] = []
    ev_over = _section("equivalent evidence (must PASS)", EQUIVALENT_EVIDENCE, "PASS",
                       args.verbose, ev_equiv_rows)

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

    blind_spots = blind + ev_blind + pair_blind
    over_rejections = over + ev_over
    record = {"wrong": wrong_rows, "equivalent": equiv_rows,
              "wrong_evidence": ev_wrong_rows, "equivalent_evidence": ev_equiv_rows,
              "pairs": pair_rows, "blind_spots": blind_spots,
              "over_rejections": over_rejections,
              "ok": not blind_spots and not over_rejections}
    # The commit gate runs this audit on every commit; writing the record there would change
    # the page it just validated, so the gate passes --no-record.
    if not args.no_record:
        (ROOT / "docs" / "FUZZ.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

    # History: a single run is a snapshot; the trend is the evidence.
    entry = {"ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
             "wrong": len(wrong_rows), "equivalent": len(equiv_rows),
             "wrong_evidence": len(ev_wrong_rows), "pairs": len(pairs),
             "blind_spots": len(blind_spots), "over_rejections": len(over_rejections),
             "ok": record["ok"]}
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")

    print()
    failed = False
    if blind_spots:
        print(f"[FAIL] accepted despite being wrong: {', '.join(blind_spots)}")
        failed = True
    if over_rejections:
        print(f"[FAIL] rejected despite being equivalent: {', '.join(over_rejections)}")
        failed = True
    if failed:
        return 1
    total = len(WRONG) + len(EQUIVALENT) + len(WRONG_EVIDENCE) + len(EQUIVALENT_EVIDENCE) + len(pairs)
    print(f"[OK] {total} cases: {len(WRONG) + len(WRONG_EVIDENCE)} wrong and {len(pairs)} pairs "
          f"rejected, {len(EQUIVALENT) + len(EQUIVALENT_EVIDENCE)} equivalent accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
