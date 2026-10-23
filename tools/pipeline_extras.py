"""Two panels the status page needs and the base renderer does not draw.

    timeline_panel   discrete states of every chain over time — the colour blocks
    coupling_matrix  which chain exercises which module, so shared modules are visible

Both are pure functions of recorded data, so they can be unit-tested without a browser.
"""

from __future__ import annotations

import html

ORDER = ["IDLE", "RUNNING", "PASS", "SKIP", "FAIL", "STALE"]

#: CSS class per state; the colour block is the whole point of the timeline.
CLASS = {"IDLE": "idle", "RUNNING": "run", "PASS": "pass", "SKIP": "skip",
         "FAIL": "fail", "STALE": "stale"}

LEGEND = ("<span class='tl-key'><i class='tl-cell idle'></i>idle</span>"
          "<span class='tl-key'><i class='tl-cell run'></i>running</span>"
          "<span class='tl-key'><i class='tl-cell pass'></i>pass</span>"
          "<span class='tl-key'><i class='tl-cell skip'></i>skip</span>"
          "<span class='tl-key'><i class='tl-cell fail'></i>fail</span>"
          "<span class='tl-key'><i class='tl-cell stale'></i>stale</span>")


def _short_module(name: str) -> str:
    return name.replace("framework.", "").replace("tools.", "")


def timeline_panel(status: dict, limit: int = 60) -> str:
    rows = (status.get("timeline") or [])[-limit:]
    if not rows:
        return ("<p class='detail'>no samples yet: the timeline fills as "
                "tools/watch_pipeline.py runs (or as the server samples).</p>")
    chains = sorted({name for row in rows for name in (row.get("states") or {})})
    start = str(rows[0].get("ts", ""))[11:19]
    end = str(rows[-1].get("ts", ""))[11:19]

    body = []
    for chain in chains:
        cells = []
        for row in rows:
            state = (row.get("states") or {}).get(chain, "IDLE")
            cells.append(f"<i class='tl-cell {CLASS.get(state, 'idle')}' "
                         f"title='{html.escape(str(row.get('ts', ''))[11:19])} "
                         f"{html.escape(state)}'></i>")
        current = (rows[-1].get("states") or {}).get(chain, "IDLE")
        body.append(
            f"<div class='tl-row'><span class='tl-name'>{html.escape(chain)}</span>"
            f"<span class='tl-cells' data-chain='{html.escape(chain)}'>{''.join(cells)}</span>"
            f"<span class='tl-now {CLASS.get(current, 'idle')}'>{current}</span></div>")
    axis = (f"<div class='tl-row'><span class='tl-name'></span>"
            f"<span class='tl-axis'><span>{start}</span><span>{end}</span></span>"
            f"<span class='tl-now'></span></div>")
    return ("<div class='tl' id='tl'>" + "".join(body) + axis + "</div>"
            f"<p class='detail' style='margin:8px 0 0'>Each column is one sample "
            f"({len(rows)} shown, 1 cell = one observation). A colour that persists is a "
            f"state that held; a break is a transition, and every break is also in the "
            f"alarm log above.</p><p class='tl-legend'>{LEGEND}</p>")


def coupling_matrix(chain_modules: dict[str, list[str]]) -> str:
    if not chain_modules:
        return "<p class='detail'>no chain-to-module mapping recorded</p>"
    chains = sorted(chain_modules)
    modules = sorted({m for mods in chain_modules.values() for m in mods})
    if not modules:
        return "<p class='detail'>no framework imports found inside the chains</p>"

    head = "".join(f"<th title='{html.escape(m)}'>{html.escape(_short_module(m))}</th>"
                   for m in modules)
    rows = []
    for chain in chains:
        cells = []
        for module in modules:
            hit = module in chain_modules[chain]
            cells.append(f"<td class='cm-cell'>{'<i class=cm-dot></i>' if hit else ''}</td>")
        rows.append(f"<tr><th class='cm-row'>{html.escape(chain)}</th>{''.join(cells)}</tr>")

    shared = {m: sum(1 for chain in chains if m in chain_modules[chain]) for m in modules}
    worst = sorted(shared.items(), key=lambda kv: -kv[1])[:3]
    note = ", ".join(f"<span class='mono'>{html.escape(_short_module(m))}</span> ×{n}"
                     for m, n in worst)
    return ("<table class='cm'><caption>Chain × module: a filled cell means the chain "
            "executes that module.</caption><thead><tr><th></th>" + head
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            f"<p class='detail' style='margin:8px 0 0'>Most shared: {note}. These are the "
            f"modules where a change can break several chains at once.</p>")


SCRIPT = """
<script>
(() => {
  const CLS = {IDLE:'idle', RUNNING:'run', PASS:'pass', SKIP:'skip', FAIL:'fail', STALE:'stale'};
  const paint = (timeline) => {
    const host = document.getElementById('tl');
    if (!host || !timeline || !timeline.length) return;
    const chains = [...new Set(timeline.flatMap(r => Object.keys(r.states || {})))].sort();
    host.innerHTML = chains.map(chain => {
      const cells = timeline.map(r => {
        const s = (r.states || {})[chain] || 'IDLE';
        return `<i class="tl-cell ${CLS[s] || 'idle'}" title="${(r.ts || '').slice(11,19)} ${s}"></i>`;
      }).join('');
      const now = (timeline[timeline.length - 1].states || {})[chain] || 'IDLE';
      return `<div class="tl-row"><span class="tl-name">${chain}</span>` +
             `<span class="tl-cells">${cells}</span>` +
             `<span class="tl-now ${CLS[now] || 'idle'}">${now}</span></div>`;
    }).join('');
  };
  window.__paintTimeline = paint;
})();
</script>
"""
