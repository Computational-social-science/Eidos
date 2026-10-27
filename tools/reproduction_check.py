"""Consume a Paper2Agent delivery: check the tree, run a reproduction spec, record the number.

    python tools/reproduction_check.py check reference/reproduction/valid_delivery
    python tools/reproduction_check.py run reference/reproduction/match.json
    python tools/reproduction_check.py show <paper>

`check` refuses an incomplete delivery. `run` executes the spec's command and compares the value it
prints with the value the paper reports — no model, no network, and `UNRUN` when anything is missing
rather than a benefit of the doubt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework import reproduction  # noqa: E402

OUT = ROOT / "artifacts" / "reproduction"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)

    c = sub.add_parser("check", help="validate a Paper2Agent delivery tree")
    c.add_argument("delivery")

    r = sub.add_parser("run", help="execute a reproduction spec and record the verdict")
    r.add_argument("spec")
    r.add_argument("--out", default=str(OUT))

    s = sub.add_parser("show", help="print the recorded verdict for a paper")
    s.add_argument("paper")
    s.add_argument("--out", default=str(OUT))

    args = ap.parse_args(argv)

    if args.action == "check":
        report = reproduction.check_delivery(args.delivery)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 2

    if args.action == "run":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        record = reproduction.run_spec(spec)
        path = reproduction.write(record, args.out)
        print(f"{record['verdict']:<9} {record.get('paper')}  "
              f"expected {record.get('expected')} observed {record.get('observed')} "
              f"(delta {record.get('delta')})")
        if record.get("reason"):
            print(f"          {record['reason']}")
        print(f"written: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
        return 0 if record["verdict"] == reproduction.MATCH else 1

    record = reproduction.load(args.paper, args.out)
    if record is None:
        print(f"no record for {args.paper!r}")
        return 1
    print(json.dumps(record, indent=2))
    return 0 if record.get("verdict") == reproduction.MATCH else 1


if __name__ == "__main__":
    sys.exit(main())
