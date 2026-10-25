"""Contrast audit: WCAG AA against the *composited* background, not the declared colour.

A translucent panel over a dark page is not `rgb(87,171,90)` with an alpha someone forgot; it
is that colour mixed with what is behind it. Reading the raw rgba triple double-counts the
background and reports false failures, which is how a real violation gets ignored. This tool
composites the stack, then measures.

    python tools/audit_contrast.py                    # both pages
    python tools/audit_contrast.py --page site/index.html --width 1280
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

PROBE = r"""() => {
  const parse = c => {
    const m = c.match(/[\d.]+/g); if (!m) return null;
    const [r, g, b] = m.slice(0, 3).map(Number);
    const a = m.length > 3 ? Number(m[3]) : 1;
    return {r, g, b, a};
  };
  const over = (top, under) => ({
    r: top.r * top.a + under.r * (1 - top.a),
    g: top.g * top.a + under.g * (1 - top.a),
    b: top.b * top.a + under.b * (1 - top.a), a: 1});
  const bgOf = el => {
    const stack = [];
    for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0) stack.push(c);
    }
    let base = {r: 14, g: 16, b: 19, a: 1};
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
    return base;
  };
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const x = lum(a), y = lum(b), hi = Math.max(x, y), lo = Math.min(x, y);
    return (hi + 0.05) / (lo + 0.05);
  };
  const out = [];
  let n = 0;
  document.querySelectorAll('body *').forEach(el => {
    if (el.closest('svg') || el.children.length) return;
    const text = (el.textContent || '').trim(); if (!text) return;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return;
    const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return;
    n++;
    const fg = parse(s.color); if (!fg) return;
    const bg = bgOf(el);
    const size = parseFloat(s.fontSize);
    const weight = parseInt(s.fontWeight, 10) || 400;
    const floor = (size >= 18.66 || (size >= 14 && weight >= 700)) ? 3.0 : 4.5;
    const cr = ratio(fg, bg);
    if (cr < floor) out.push({text: text.slice(0, 40), cr: +cr.toFixed(2), floor,
                              size: +size.toFixed(1), cls: (el.className || '').toString().slice(0, 24)});
  });
  const svg = [];
  document.querySelectorAll('svg text').forEach(t => {
    const s = getComputedStyle(t);
    const fg = parse(s.fill); if (!fg || s.fill === 'none') return;
    // A label sits on the node it belongs to: composite over a rect in the *same* <g>.
    // Taking the first rect in the svg instead made a column header inherit a chain node's
    // green and report 1.12:1 against a background it never touches.
    let bg = {r: 14, g: 16, b: 19, a: 1};
    const parent = t.parentElement;
    const shape = parent && parent.tagName.toLowerCase() === 'g' ? parent.querySelector('rect') : null;
    if (shape) { const f = parse(getComputedStyle(shape).fill); if (f) bg = over(f, bg); }
    const alpha = (parseFloat(s.opacity) || 1) * fg.a;
    const shown = over({r: fg.r, g: fg.g, b: fg.b, a: alpha}, bg);
    const cr = ratio(shown, bg);
    if (cr < 3) svg.push({text: t.textContent.slice(0, 30), cr: +cr.toFixed(2)});
  });
  // Lines are information too. WCAG asks 3:1 for graphical objects, and a coupling edge at
  // 2.4:1 is a line the reader cannot follow — which is how "the diagram looks empty" happens.
  const lines = [];
  const panel = {r: 21, g: 24, b: 29, a: 1};
  document.querySelectorAll('svg path').forEach(p => {
    const s = getComputedStyle(p);
    const stroke = parse(s.stroke);
    if (!stroke || s.stroke === 'none' || s.display === 'none') return;
    const alpha = (parseFloat(s.opacity) || 1) * stroke.a;
    if (alpha < 0.05) return;                    // intentionally hidden (hover mode)
    const shown = over({r: stroke.r, g: stroke.g, b: stroke.b, a: alpha}, panel);
    const cr = ratio(shown, panel);
    if (cr < 3) lines.push({cls: (p.getAttribute('class') || 'path').slice(0, 20),
                            cr: +cr.toFixed(2)});
  });
  return {checked: n, violations: out, svg, lines};
}"""


def audit(page: pathlib.Path, width: int) -> list[str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        tab = browser.new_page(viewport={"width": width, "height": 900})
        tab.goto(page.as_uri(), wait_until="load")
        tab.wait_for_timeout(900)
        data = tab.evaluate(PROBE)
        browser.close()

    findings = [f"{page.name} {width}px: line {v['cr']}:1 < 3 ({v['cls']})"
                for v in data.get("lines") or []]
    findings += [f"{page.name} {width}px: text {v['cr']}:1 < {v['floor']} "
                f"({v['size']}px {v['cls']}) {v['text']!r}"
                for v in data["violations"]]
    findings += [f"{page.name} {width}px: svg text {v['cr']}:1 {v['text']!r}"
                 for v in data["svg"]]
    print(f"  {page.name}: {data['checked']} text nodes, "
          f"{len(data['violations'])} below AA, {len(data['svg'])} svg labels below 3:1")
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WCAG AA contrast audit")
    ap.add_argument("--page", action="append", default=None)
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args(argv)
    pages = [pathlib.Path(p).resolve() for p in args.page] if args.page else [
        ROOT / "site" / "index.html", ROOT / "site" / "dashboard.html"]
    findings: list[str] = []
    for page in pages:
        if not page.is_file():
            print(f"[FAIL] {page} has not been built")
            return 1
        findings += audit(page, args.width)
    if findings:
        for line in findings:
            print(f"[FAIL] {line}")
        return 1
    print("contrast clean: every text node meets WCAG AA and every drawn line meets 3:1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
