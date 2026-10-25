"""Watch the gate refuse this project — the lesson that makes the template worth copying.

A demo that only shows success teaches the wrong thing: it suggests the gate is a formality. This
script takes the same project, changes one number in the report so it no longer matches the
evidence, and runs Gate S on the copy. It expects a rejection and says which check fired.

    python show_rejection.py             # exit 0 when the gate rejects as designed
    python show_rejection.py --keep      # leave the copy in place to inspect

Nothing here calls a model: it reuses the evidence this project already measured, so the lesson
costs a second, not half a minute.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def eidos_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "framework" / "validity").is_dir():
            return parent
    raise SystemExit("cannot locate Eidos")


ROOT = eidos_root(HERE)
sys.path.insert(0, str(ROOT))

from framework.validity import ScientificValidityGate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    evidence = HERE / "docs" / "evidence.json"
    if not evidence.is_file():
        print("run build_evidence.py first: there is nothing to contradict")
        return 2
    measured = json.loads(evidence.read_text(encoding="utf-8"))["agreement"]

    tmp = Path(tempfile.mkdtemp(prefix="demo-reject-"))
    root = tmp / "demo_onboarding"
    shutil.copytree(HERE, root,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # The lie: the register is edited, the paper is not. This is the failure that happens in
    # practice — someone rewrites the number in CLAIMS.yaml and forgets the sentence that cites
    # it. S3 will catch the register against the artefact; S9 is the point of the lesson, because
    # it catches the sentence against the number it was supposed to report.
    import yaml
    worse = 0.5
    register_path = root / "analysis" / "CLAIMS.yaml"
    register = yaml.safe_load(register_path.read_text(encoding="utf-8"))
    register["claims"][0]["evidence"]["value"] = worse
    register_path.write_text(yaml.safe_dump(register, sort_keys=False), encoding="utf-8")

    gate = ScientificValidityGate(root, register=root / "analysis" / "CLAIMS.yaml",
                                  document=root / "docs" / "REPORT.md")
    result = gate.run()
    findings = [str(f) for f in (getattr(result, "details", {}) or {}).get("findings", [])]

    print(f"the report still says {measured}; the register now says {worse}; "
          f"the artefact holds {measured}")
    print(f"Gate S: {'PASS  <-- the gate is broken' if result.passed else 'FAIL'}")
    for finding in findings:
        print(f"  {finding}")

    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"copy kept at {root}")

    rejected = not result.passed and any(f.startswith("[S9]") for f in findings)
    if not rejected:
        print("\n[FAIL] the gate did not reject the lie with S9; that is a defect, not a lesson")
        return 1
    print("\n[OK] rejected by S9: the prose number must be the number the evidence holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
