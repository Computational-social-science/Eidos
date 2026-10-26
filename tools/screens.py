"""Regenerate the README screenshots, and refuse to let them go stale.

The five images in `docs/screens/` are the README's evidence. Nothing regenerated them, so after
a layout change the README kept showing the previous release — a picture that claims to show the
monitor, showing something else.

    python tools/screens.py --update     # recapture from the built pages
    python tools/screens.py --check      # fail if a page changed after its picture was taken

`--check` compares the *source page hashes* recorded in `docs/SCREENS.json` with the pages on
disk. That is machine-independent: it does not care that a Linux box antialiases text differently,
only that the page changed and the picture did not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "docs" / "screens"
WEB = SCREENS / "web"
RECORD = ROOT / "docs" / "SCREENS.json"
PAGES = {"dashboard.html": SCREENS / ".." / ".." / "site" / "dashboard.html",
         "index.html": SCREENS / ".." / ".." / "site" / "index.html"}

VIEWPORT = {"width": 1440, "height": 1000}
SCALE = 2

#: name -> (page, selector anchor, padding, crop mode)
SHOTS = [
    ("dashboard-top", "dashboard.html", None, 0, "viewport"),
    ("dashboard-operator", "dashboard.html", "h3:Operators", 10, "wrap"),
    ("dashboard-consumers", "dashboard.html", "h3:Consumers", 10, "wrap"),
    ("dashboard-history", "dashboard.html", ".grid", 6, "grid"),
    ("index-top", "index.html", None, 0, "viewport"),
    ("index-deps", "index.html", "h3=Dependency versions", 10, "card"),
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page_path(name: str) -> Path:
    return (ROOT / "site" / name).resolve()


def capture(out_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright
    from browser import launch as browser_launch


    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    with sync_playwright() as p:
        browser = browser_launch(p)
        for page_name in ("dashboard.html", "index.html"):
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
            page.goto(_page_path(page_name).as_uri(), wait_until="load")
            page.wait_for_timeout(1200)
            for name, target, anchor, pad, mode in SHOTS:
                if target != page_name:
                    continue
                if mode == "viewport":
                    box = {"x": 0, "y": 0, "w": VIEWPORT["width"], "h": VIEWPORT["height"]}
                else:
                    box = page.evaluate(
                        """([anchor, mode, pad]) => {
                            const h3 = [...document.querySelectorAll('h3')].find(e =>
                              anchor.startsWith('h3:') ? e.textContent.trim().startsWith(anchor.slice(3))
                                                       : e.textContent.trim() === anchor.split('=')[1]);
                            const el = mode === 'grid' ? document.querySelector(anchor)
                                                       : (mode === 'card' ? h3.closest('.card')
                                                                          : (h3.closest('.opwrap') || h3.parentElement));
                            const r = el.getBoundingClientRect();
                            return {x: Math.max(0, r.x - pad), y: Math.max(0, r.y + window.scrollY - pad),
                                    w: Math.min(window.innerWidth - Math.max(0, r.x - pad), r.width + 2 * pad),
                                    h: r.height + 2 * pad};
                        }""", [anchor, mode, pad])
                page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True, clip={
                    "x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]})
                written[name] = _sha(out_dir / f"{name}.png")
            page.close()
        browser.close()
    return written


def web_copies(images: dict) -> dict:
    """Smaller versions for the README: a page that opens with 800 KB of PNG is a slow first look."""
    from PIL import Image
    WEB.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in images:
        source = SCREENS / f"{name}.png"
        target = WEB / f"{name}.webp"
        # Text-heavy dark UI: WebP at 86 is about a third smaller than the PNG and stays legible,
        # while JPEG of the same picture came out larger than the PNG.
        Image.open(source).convert("RGB").save(target, "WEBP", quality=86, method=6)
        out[name] = {"sha256": _sha(target), "bytes": target.stat().st_size}
    return out


def record(images: dict) -> None:
    RECORD.write_text(json.dumps({
        "viewport": VIEWPORT, "scale": SCALE,
        "sources": {name: _sha(ROOT / "site" / name) for name in ("dashboard.html", "index.html")},
        "images": {name: {"sha256": digest,
                          "bytes": (SCREENS / f"{name}.png").stat().st_size}
                   for name, digest in images.items()},
        "web": web_copies(images),
    }, indent=2) + "\n", encoding="utf-8")


def check() -> int:
    if not RECORD.is_file():
        print("screens: no docs/SCREENS.json — run tools/screens.py --update")
        return 1
    saved = json.loads(RECORD.read_text(encoding="utf-8"))
    problems = []
    for name, digest in (saved.get("sources") or {}).items():
        page = ROOT / "site" / name
        if not page.is_file():
            problems.append(f"site/{name} is missing")
        elif _sha(page) != digest:
            problems.append(f"site/{name} changed after the screenshots were taken")
    for name, meta in (saved.get("images") or {}).items():
        path = SCREENS / f"{name}.png"
        if not path.is_file():
            problems.append(f"docs/screens/{name}.png is missing")
        elif _sha(path) != meta.get("sha256"):
            problems.append(f"docs/screens/{name}.png was edited by hand")
    if problems:
        for line in problems:
            print(f"[FAIL] {line}")
        print("regenerate with: python tools/screens.py --update")
        return 1
    print(f"screens current: {len(saved.get('images') or {})} images match their pages")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true", help="recapture every image and rewrite the record")
    ap.add_argument("--check", action="store_true", help="fail if a page changed since capture")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    if not args.update:
        ap.print_help()
        return 2
    images = capture(SCREENS)
    record(images)
    total = sum((SCREENS / f"{n}.png").stat().st_size for n in images)
    web = sum((WEB / f"{n}.webp").stat().st_size for n in images)
    print(f"wrote {len(images)} screenshots: {total / 1024:.0f} KB PNG, "
          f"{web / 1024:.0f} KB WebP for the README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
