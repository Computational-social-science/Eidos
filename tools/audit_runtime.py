"""Runtime audit: does the page actually run?

The demo section once rendered perfectly — canvases in place, layout clean, contrast fine —
while every number stayed at an em dash, because the script threw on a renamed element id.
Static checks cannot see that: the markup is valid, the boxes are where they should be, and
nothing is clipped. Only executing the page shows it.

    python tools/audit_runtime.py                 # both pages
    python tools/audit_runtime.py --page site/index.html
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def audit(page: pathlib.Path) -> list[str]:
    from playwright.sync_api import sync_playwright

    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        tab = browser.new_page(viewport={"width": 1280, "height": 900})
        tab.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        tab.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}")
               if m.type == "error" else None)
        tab.goto(page.as_uri(), wait_until="load")
        tab.wait_for_timeout(1200)

        # A canvas that threw before drawing is a blank rectangle; sample its pixels.
        blank = tab.evaluate("""() => [...document.querySelectorAll('canvas')]
            .filter(c => c.width > 8 && c.height > 8)
            .filter(c => {
                const ctx = c.getContext('2d');
                const data = ctx.getImageData(0, 0, c.width, c.height).data;
                for (let i = 3; i < data.length; i += 4000) if (data[i] !== 0) return false;
                return true;                       // no alpha anywhere: nothing was drawn
            }).map(c => c.id || '(anonymous canvas)')""")
        for name in blank:
            problems.append(f"{name} is blank (the script did not draw)")
        browser.close()
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="execute the pages and report runtime errors")
    ap.add_argument("--page", action="append", default=None)
    args = ap.parse_args(argv)
    pages = [pathlib.Path(p).resolve() for p in args.page] if args.page else [
        ROOT / "site" / "index.html", ROOT / "site" / "dashboard.html"]

    findings: list[str] = []
    for page in pages:
        if not page.is_file():
            print(f"[FAIL] {page} has not been built")
            return 1
        found = audit(page)
        print(f"  {'PASS' if not found else 'FAIL'}  {page.name}: runs without errors")
        findings += [f"{page.name}: {f}" for f in found]

    if findings:
        for line in findings:
            print(f"[FAIL] {line}")
        return 1
    print("runtime clean: both pages execute, and every canvas has pixels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
