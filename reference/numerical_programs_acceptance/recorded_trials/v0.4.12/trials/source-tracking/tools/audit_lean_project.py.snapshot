"""Audit a Lean project's theorems and write the result as a Gate S evidence artefact.

Gate S resolves a JSON pointer; it cannot run Lean. This tool runs the Lean chain for each
theorem a project declares and records the outcome, so the register can point at a file
that a machine produced:

    python tools/audit_lean_project.py --project ../lean-nhb \
        --theorem NHB.PhaseI.Core:PhaseI.Selective.silent_iff_acceptedAndWrong \
        --theorem NHB.PhaseI.Core:PhaseI.Selective.accepted_mono

Output: ``<project>/docs/LEAN_AUDIT.json`` with, per theorem, ``ok``, ``axioms`` and the
kernel-control result. The file is overwritten on every run: it is evidence, not a log.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.validity.lean_audit import LeanAudit  # noqa: E402


def parse(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise SystemExit(f"--theorem must be MODULE:NAME, got {spec!r}")
    module, name = spec.split(":", 1)
    return module.strip(), name.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--theorem", action="append", default=[],
                    help="MODULE:NAME; repeatable")
    ap.add_argument("--out", default="docs/LEAN_AUDIT.json")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    if not args.theorem:
        raise SystemExit("at least one --theorem is required")

    results = {}
    ok_all = True
    for spec in args.theorem:
        module, name = parse(spec)
        ok, messages = LeanAudit(project=project, theorem=name, module=module).run()
        ok_all = ok_all and ok
        results[name] = {"module": module, "ok": ok, "messages": messages}

    payload = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(
                   timespec="seconds"),
               "project": project.name,
               "theorems": results,
               "all_ok": ok_all}
    out = project / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    for name, row in results.items():
        print(f"{'PASS' if row['ok'] else 'FAIL'}  {name}"
              + ("" if row["ok"] else f"  ({'; '.join(row['messages'])[:110]})"))
    print(f"wrote {out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
