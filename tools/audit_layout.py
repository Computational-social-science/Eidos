"""Layout audit: find text that collides with text and boxes that escape their card.

The monitor is a single dense page; "it looks crowded" is not actionable. This script makes
the claim checkable: it opens the built page at several widths and reports (a) pairs of text
bounding boxes that intersect, and (b) any scrollable element whose content is wider than its
own box. Exit code 1 when either is found, so a regression cannot be dismissed as taste.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "dashboard.html"

PROBE = """() => {
  const visible = el => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  // Inline elements can wrap around an earlier label. Their union bounding box
  // includes empty space and can falsely intersect that label. Measure actual
  // line fragments, including direct text in parents that also contain markup.
  const fragments = [];
  let owner = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, el = node.parentElement;
    const text = (node.textContent || '').trim();
    if (!el || !text || el.closest('svg,script,style,noscript,template') || !visible(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const id = ++owner;
    for (const rect of range.getClientRects()) {
      if (rect.width > 1 && rect.height > 1) fragments.push({el, rect, text, owner: id});
    }
  }
  const texts = [...document.querySelectorAll('svg text')].filter(el =>
    visible(el) && (el.textContent || '').trim()).map(el => {
    const r = el.getBoundingClientRect();
    return {t: (el.textContent || '').trim().slice(0, 26), x: r.x, y: r.y, w: r.width, h: r.height};
  });
  for (const {rect: r, text, owner} of fragments)
    texts.push({t: text.slice(0, 26), x: r.x, y: r.y, w: r.width, h: r.height, owner});
  const over = [];
  document.querySelectorAll('body *').forEach(el => {
    const st = getComputedStyle(el);
    // An element that is *meant* to scroll (code blocks, long commands) is not overflowing.
    if (st.overflowX === 'auto' || st.overflowX === 'scroll') return;
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 && el.children.length) {
      over.push({el: (el.className || el.tagName).toString().slice(0, 30),
                 scroll: el.scrollWidth, client: el.clientWidth});
    }
  });
  const cardEls = [...document.querySelectorAll('.card')].filter(visible);
  const cards = cardEls.map(c => {
    const r = c.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height};
  });
  const nested = [];
  cardEls.forEach((a, i) => cardEls.forEach((b, j) => {
    if (i !== j && a.contains(b)) nested.push(i + ':' + j);   // a card inside a card is not a collision
  }));
  // Paint order matters: an opaque rect drawn after a label hides it, and a bounding-box
  // intersection test cannot see that. Same for text that falls outside its own viewBox and is
  // clipped by the svg.
  const svgKids = [...document.querySelectorAll('svg *')];
  const order = new Map(svgKids.map((el, i) => [el, i]));
  const covered = [];
  document.querySelectorAll('svg text').forEach(t => {
    const txt = (t.textContent || '').trim();
    if (!txt || !visible(t)) return;
    const r = t.getBoundingClientRect();
    const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
    const ti = order.get(t);
    for (const [el, i] of order) {
      if (i <= ti || el.tagName !== 'rect') continue;
      const st = getComputedStyle(el);
      if (!st.fill || st.fill === 'none' || st.fill === 'transparent') continue;
      if (+st.opacity < 0.9) continue;
      const b = el.getBoundingClientRect();
      if (cx > b.x && cx < b.x + b.width && cy > b.y && cy < b.y + b.height) {
        covered.push({t: txt.slice(0, 26), by: (el.getAttribute('fill') || '').slice(0, 12)});
        break;
      }
    }
  });
  // HTML occlusion: absolute panels, negative margins and overlays cover text without any
  // bounding-box intersection. Hit-test each text fragment, not empty space in
  // a wrapped element's union rectangle.
  const obscured = [];
  const alphaCache = new Map();
  const colorProbe = document.createElement('canvas');
  colorProbe.width = colorProbe.height = 1;
  const colors = colorProbe.getContext('2d', {willReadFrequently: true});
  const canPaintOverText = (el, st) => {
    if (+st.opacity < 0.9) return false;
    // Replaced media can paint without a CSS background. Retain conservative
    // rectangle-based detection; this is not a per-pixel media alpha oracle.
    if (['IMG','VIDEO','CANVAS','IFRAME','OBJECT','EMBED','SVG'].includes(el.tagName.toUpperCase())) return true;
    if (st.backgroundImage !== 'none') return true;
    if (!colors) throw new Error('Cannot inspect background opacity');
    if (!alphaCache.has(st.backgroundColor)) {
      colors.clearRect(0, 0, 1, 1);
      colors.fillStyle = st.backgroundColor;
      colors.fillRect(0, 0, 1, 1);
      alphaCache.set(st.backgroundColor, colors.getImageData(0, 0, 1, 1).data[3] / 255);
    }
    return alphaCache.get(st.backgroundColor) >= 0.9;
  };
  fragments.forEach(({el, rect: r, text}) => {
    // Off-screen text (a skip link parked at left:-9999px) is not covered by anything; clamping
    // its centre into the viewport would invent an overlay that is not there.
    if (r.right < 1 || r.left > window.innerWidth - 1 || r.bottom < 1 || r.top > window.innerHeight - 1)
      return;
    const cx = Math.min(Math.max(r.x + r.width / 2, 1), window.innerWidth - 2);
    const cy = Math.min(Math.max(r.y + r.height / 2, 1), window.innerHeight - 2);
    // A transparent hit-test layer can sit above a genuinely painted cover.
    // Inspect front-to-back until reaching this text's own paint context.
    for (const top of document.elementsFromPoint(cx, cy)) {
      if (top === el || top.contains(el)) break;
      const st = getComputedStyle(top);
      if (st.visibility === 'hidden' || st.display === 'none') continue;
      if (!canPaintOverText(top, st)) continue;
      // A mark smaller than the text it sits beside is an icon, not a cover.
      const tr = top.getBoundingClientRect();
      if (tr.width * tr.height < r.width * r.height) continue;
      obscured.push({t: text.slice(0, 26),
                     by: (top.tagName + (top.className ? '.' + top.className : '')).slice(0, 30)});
      break;
    }
  });
  const clipped = [];
  document.querySelectorAll('svg text').forEach(t => {
    const txt = (t.textContent || '').trim();
    if (!txt || !t.ownerSVGElement) return;
    const r = t.getBoundingClientRect(), s = t.ownerSVGElement.getBoundingClientRect();
    if (r.left < s.left - 1 || r.right > s.right + 1 || r.top < s.top - 1 || r.bottom > s.bottom + 1)
      clipped.push({t: txt.slice(0, 26)});
  });
  return {texts, over, cards, nested, covered, clipped, obscured,
          body: document.body.scrollWidth, win: window.innerWidth};
}"""


def audit(width: int) -> list[str]:
    from playwright.sync_api import sync_playwright
    from browser import launch as browser_launch


    findings: list[str] = []
    with sync_playwright() as p:
        browser = browser_launch(p)
        page = browser.new_page(viewport={"width": width, "height": 1000})
        page.goto(PAGE.as_uri(), wait_until="load")
        # Entrance animations start at opacity 0; measuring during them would report a
        # page with no visible text and therefore no collisions. Let them settle.
        page.wait_for_timeout(1500)
        data = page.evaluate(PROBE)
        browser.close()

    boxes = data["texts"]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            # Range rectangles include font leading. Tight lines of the same
            # text node can intersect without colliding glyphs. As before, this
            # guard checks collisions between distinct text owners, not internal
            # glyph/line layout within a single text node.
            if a.get("owner") is not None and a["owner"] == b.get("owner"):
                continue
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                findings.append(f"{width}px: text overlap {a['t']!r} / {b['t']!r}")
    cards = data["cards"]
    nested = set(data.get("nested") or [])
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            if f"{i}:{j}" in nested or f"{j}:{i}" in nested:
                continue
            a, b = cards[i], cards[j]
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                findings.append(f"{width}px: two cards overlap")
    for item in data.get("covered") or []:
        findings.append(f"{width}px: text {item['t']!r} is painted over by a rect "
                        f"({item['by']})")
    for item in data.get("obscured") or []:
        findings.append(f"{width}px: html text {item['t']!r} is covered by {item['by']!r}")
    for item in data.get("clipped") or []:
        findings.append(f"{width}px: svg text {item['t']!r} falls outside its viewBox")
    for item in data["over"]:
        findings.append(f"{width}px: {item['el']} overflows "
                        f"({item['scroll']} > {item['client']} px)")
    if data["body"] > data["win"] + 1:
        findings.append(f"{width}px: page scrolls horizontally "
                        f"({data['body']} > {data['win']} px)")
    return findings


def main(argv: list[str] | None = None) -> int:
    global PAGE
    ap = argparse.ArgumentParser(description="audit the monitor layout")
    ap.add_argument("--widths", default="1024,1280,1440")
    ap.add_argument("--page", default=str(PAGE))
    args = ap.parse_args(argv)
    page = pathlib.Path(args.page).resolve()
    if not page.is_file():
        print(f"[FAIL] {page} has not been built")
        return 1
    PAGE = page
    findings: list[str] = []
    for width in (int(w) for w in args.widths.split(",")):
        findings += audit(width)
    if findings:
        for line in findings:
            print(f"[FAIL] {line}")
        return 1
    print(f"layout clean at {args.widths} px: no text collisions, no overflowing boxes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
