"""Does the page speak one visual language, or several?

Colour and type drift one component at a time: a grey added here, a 9.5 px label there, and after
a month the page has five near-identical greys and ten type sizes. Nobody decides that; it
accumulates. This audit states the scale and fails when a page leaves it.

    python tools/audit_visual.py              # both pages, built files
    python tools/audit_visual.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The declared scale. Four sizes for text plus one for a section title; anything else is drift.
SCALE = {10.0, 11.0, 12.0, 12.5, 15.0}
MIN_PX = 10.0
MAX_SIZES = 5
MAX_COLOURS = 6      # design colours; palette state colours are exempt (a FAIL is allowed to be red)
MAX_WEIGHTS = 3

PROBE = """() => {
  const sizes = {}, colours = {}, weights = {};
  document.querySelectorAll('*').forEach(e => {
    if (e.childElementCount) return;
    const text = (e.textContent || '').trim();
    if (!text) return;
    const s = getComputedStyle(e);
    if (s.visibility === 'hidden' || s.display === 'none') return;
    const size = Math.round(parseFloat(s.fontSize) * 10) / 10;
    sizes[size] = (sizes[size] || 0) + 1;
    colours[s.color] = (colours[s.color] || 0) + 1;
    weights[s.fontWeight] = (weights[s.fontWeight] || 0) + 1;
  });
  return {sizes, colours, weights};
}"""


def audit(page: Path) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        tab = browser.new_page(viewport={"width": 1440, "height": 1000})
        tab.goto(page.as_uri(), wait_until="load")
        tab.wait_for_timeout(900)
        data = tab.evaluate(PROBE)
        browser.close()
    return data


def _is_state_colour(colour: str) -> bool:
    """A palette colour used as text is a verdict, not a design decision.

    The six state colours may all appear at once when the sample has failures; counting them
    against the design budget would make the check fail on bad news rather than on drift.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dashboard as dash

    def rgb(value: str) -> str:
        value = value.strip().lstrip("#")
        return "rgb({}, {}, {})".format(*(int(value[i:i + 2], 16) for i in (0, 2, 4)))

    return str(colour).replace(" ", "") in {rgb(v).replace(" ", "") for v in dash.PALETTE.values()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    problems, warnings, report = [], [], {}
    # The monitor is the surface this scale was written for and it is enforced. The document has
    # its own typography history; it is reported, not enforced, until it is migrated.
    for name in ("dashboard.html", "index.html"):
        page = ROOT / "site" / name
        if not page.is_file():
            problems.append(f"{name} has not been built")
            continue
        data = audit(page)
        sizes = {float(k): v for k, v in data["sizes"].items()}
        colours = list(data["colours"])
        weights = list(data["weights"])
        report[name] = {"sizes": sorted(sizes), "colours": colours, "weights": weights}

        sink = problems if name == "dashboard.html" else warnings
        stray = sorted(s for s in sizes if s not in SCALE)
        if stray:
            sink.append(f"{name}: type sizes outside the scale {stray}")
        if len(sizes) > MAX_SIZES:
            sink.append(f"{name}: {len(sizes)} type sizes (max {MAX_SIZES})")
        small = sorted(s for s in sizes if s < MIN_PX)
        if small:
            sink.append(f"{name}: text below {MIN_PX}px {small}")
        design = [c for c in colours if not _is_state_colour(c)]
        if len(design) > MAX_COLOURS:
            sink.append(f"{name}: {len(design)} design text colours (max {MAX_COLOURS}): {design}")
        if len(weights) > MAX_WEIGHTS:
            sink.append(f"{name}: {len(weights)} font weights {weights}")

        print(f"{name}: sizes {sorted(sizes)} · {len(colours)} colours · {len(weights)} weights")

    if args.json:
        (ROOT / "docs" / "VISUAL.json").write_text(
            json.dumps({"report": report, "problems": problems,
                        "scale": sorted(SCALE), "warnings": warnings}, indent=2),
            encoding="utf-8")

    for line in warnings:
        print(f"[WARN] {line}")
    for line in problems:
        print(f"[FAIL] {line}")
    if not problems:
        tail = f"; {len(warnings)} warning(s) on the document" if warnings else ""
        print(f"[OK] the monitor holds one visual language: ≤{MAX_SIZES} sizes from the declared "
              f"scale, ≤{MAX_COLOURS} colours, ≤{MAX_WEIGHTS} weights{tail}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
