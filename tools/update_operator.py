"""The update operator: sense, try in isolation, then promote or roll back.

    python tools/update_operator.py status
    python tools/update_operator.py sense [--offline]
    python tools/update_operator.py try dvc 3.59.0
    python tools/update_operator.py promote dvc 3.59.0
    python tools/update_operator.py rollback dvc

Sensing is safe to run on a timer: it writes a report and never touches a pin. Promotion is the
only command that changes what production runs, and it refuses without a passing try for the
exact version being promoted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework import updates  # noqa: E402


def cmd_status(args) -> int:
    data = updates.report()
    rows = []
    for name, item in data["items"].items():
        rows.append((name, item.get("pinned") or "—", item.get("installed") or "—",
                     item.get("available") or "—", item.get("state") or "unknown"))
    width = max(len(r[0]) for r in rows)
    print(f"{'dependency':{width}}  {'pinned':14s} {'installed':14s} {'available':14s} state")
    for name, pin, have, offer, state in rows:
        print(f"{name:{width}}  {str(pin)[:14]:14s} {str(have)[:14]:14s} {str(offer)[:14]:14s} {state}")
    if data.get("ts"):
        print(f"\nlast sense: {data['ts']}")
    return 0


def cmd_sense(args) -> int:
    report = updates.sense(offline=args.offline)
    behind = {n: i for n, i in report["items"].items() if i["state"] == "behind"}
    for name, item in report["items"].items():
        mark = "!" if item["state"] == "behind" else " "
        print(f"{mark} {name:14s} pinned {str(item['pinned']):10s} available "
              f"{str(item['available']):10s} {item['state']}")
    print(f"\nwrote {updates.SENSE.relative_to(updates.ROOT)}")
    if behind:
        print(f"behind: {', '.join(behind)} — try before promoting")
    return 0


def cmd_try(args) -> int:
    artifact = Path(args.artifact) if args.artifact else None
    print(f"trying {args.name} {args.version} in an isolated environment …")
    record = updates.try_candidate(args.name, args.version, artifact=artifact,
                                   python=args.python)
    detail = record.get("detail") or {}
    print(f"{'PASS' if record['ok'] else 'FAIL'}  {args.name} {args.version}")
    if detail.get("reason"):
        print(f"  reason: {detail['reason']}")
    if detail.get("version"):
        print(f"  probe reports: {detail['version']}")
    print(f"  record: {(updates.TRIES / f'{args.name}-{args.version}.json').relative_to(updates.ROOT)}")
    return 0 if record["ok"] else 1


def cmd_promote(args) -> int:
    try:
        pin = updates.promote(args.name, args.version, note=args.note or "")
    except PermissionError as exc:
        print(f"refused: {exc}")
        return 2
    print(f"promoted {args.name} -> {pin['version']}")
    print(f"  lock: {updates.LOCK.relative_to(updates.ROOT)}")
    return 0


def cmd_rollback(args) -> int:
    pin = updates.rollback(args.name)
    print(f"rolled back {args.name} -> {(pin or {}).get('version')}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)

    p = sub.add_parser("sense")
    p.add_argument("--offline", action="store_true", help="record what this host has, ask nobody")
    p.set_defaults(fn=cmd_sense)

    p = sub.add_parser("try")
    p.add_argument("name")
    p.add_argument("version")
    p.add_argument("--artifact", help="candidate binary, for quarto / llama.cpp")
    p.add_argument("--python", help="interpreter for the throwaway environment")
    p.set_defaults(fn=cmd_try)

    p = sub.add_parser("promote")
    p.add_argument("name")
    p.add_argument("version")
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("rollback")
    p.add_argument("name")
    p.set_defaults(fn=cmd_rollback)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
