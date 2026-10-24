"""One gate for the two pages: build, check structure, check layout, check contrast.

The pages were changed dozens of times with no gate between "looks wrong to me" and "looks
right to me", which is why the same defects came back: a colour that passed in one theme and
failed in the other, a caption that collided in one width, a table that overflowed in another.
Those are all machine-checkable. This script is the turnstile: a page change is finished when
this exits 0, and not before.

    python tools/audit_site.py            # build both pages, then audit them
    python tools/audit_site.py --no-build # audit what is on disk
    python tools/audit_site.py --loop 3   # re-run up to 3 times, stopping at the first pass
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd: list[str], label: str) -> tuple[bool, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        for line in out.strip().splitlines()[:8]:
            print(f"         {line}")
    return ok, out


def invariants() -> list[str]:
    """Facts the pages must state, independent of style."""
    problems = []
    dash = (ROOT / "site" / "dashboard.html")
    index = (ROOT / "site" / "index.html")
    if not dash.is_file() or not index.is_file():
        return ["one of the pages was not built"]
    d = dash.read_text(encoding="utf-8")
    i = index.read_text(encoding="utf-8")

    chains = len(re.findall(r"data-chain='", d))
    services = len(re.findall(r"data-service='", d))
    rows = d.count("class='srow'")
    if chains < 1:
        problems.append("dashboard states no chains")
    if services < 1:
        problems.append("dashboard states no services")
    if rows != chains:
        problems.append(f"history rows ({rows}) disagree with chains ({chains})")
    for token in ("id=\"ov\"", "id='faults'", "id=\"strip\"", "/api/status"):
        if token not in d:
            problems.append(f"dashboard is missing {token}")

    if "MONITOR" not in i.upper():
        problems.append("index carries no monitor snapshot")
    if "/dashboard.html" not in i:
        problems.append("index does not link to the monitor")
    if "--bg:#0e1013" not in i or "--bg:#0e1013" not in d:
        problems.append("the two pages do not share the same background token")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the site quality gate")
    ap.add_argument("--no-build", action="store_true", help="audit what is already on disk")
    ap.add_argument("--loop", type=int, default=1, help="attempts before giving up")
    args = ap.parse_args(argv)

    for attempt in range(1, max(args.loop, 1) + 1):
        if args.loop > 1:
            print(f"attempt {attempt}/{args.loop}")
        checks: list[bool] = []

        if not args.no_build:
            ok, _ = run([PY, "tools/build_site.py"], "build the document")
            checks.append(ok)
            ok, _ = run([PY, "tools/dashboard.py"], "build the monitor")
            checks.append(ok)

        ok, _ = run([PY, "tools/build_site.py", "--check"], "document is current")
        checks.append(ok)
        ok, _ = run([PY, "tools/dashboard.py", "--check", "--no-age"], "monitor structure")
        checks.append(ok)

        ok, _ = run([PY, "tools/audit_layout.py", "--widths", "1100,1280,1440,1920"],
                    "monitor layout")
        checks.append(ok)
        ok, _ = run([PY, "tools/audit_layout.py", "--page", "site/index.html",
                     "--widths", "1100,1280,1440"], "document layout")
        checks.append(ok)

        ok, _ = run([PY, "tools/audit_contrast.py"], "both pages, WCAG AA")
        checks.append(ok)

        gaps = invariants()
        print(f"  {'PASS' if not gaps else 'FAIL'}  content invariants")
        for gap in gaps:
            print(f"         {gap}")
        checks.append(not gaps)

        if all(checks):
            print(f"\nsite gate: PASS ({len(checks)} checks)")
            return 0
        print(f"\nsite gate: FAIL ({sum(1 for c in checks if not c)} of {len(checks)})")

    return 1


if __name__ == "__main__":
    sys.exit(main())
