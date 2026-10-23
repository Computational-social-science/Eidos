"""Render the pipeline section: structure, coupling, chain trace and the control loop.

Three views of the same system, kept separate on purpose:

    structure   the import graph as a layered DAG, edges typed (hard / soft / process)
    execution   the last chain audit as a trace waterfall, one bar per chain
    control     the loop that watches the pipeline: reference, measurement, error, alarms

The page is a snapshot when opened from disk and a live view when served by
tools/serve_site.py — the same markup, one `fetch` away.
"""

from __future__ import annotations

import html

PASS, SKIP, FAIL = "pass", "skip", "fail"
PILL = {"PASS": PASS, "SKIP": SKIP, "FAIL": FAIL, "ERROR": FAIL}


def _short(name: str) -> str:
    return name.replace("framework.", "f.").replace("tools.", "")[:18]


def dag_svg(coupling: dict, width: int = 720) -> str:
    nodes = coupling.get("nodes") or []
    edges = coupling.get("edges") or []
    levels = coupling.get("levels") or {}
    attrs = coupling.get("attrs") or {}
    if not nodes:
        return "<p class='detail'>no coupling data</p>"

    depth = max(levels.values(), default=0) + 1
    columns: dict[int, list[str]] = {}
    for node in nodes:
        columns.setdefault(levels.get(node, 0), []).append(node)
    for column in columns.values():
        column.sort()

    row_h, node_w, node_h = 30, 148, 20
    rows = max(len(c) for c in columns.values())
    height = rows * row_h + 40
    x_step = (width - node_w - 40) / max(depth - 1, 1)
    pos: dict[str, tuple[float, float]] = {}
    for level, column in columns.items():
        for index, node in enumerate(column):
            x = 20 + level * x_step
            y = 20 + index * row_h + (rows - len(column)) * row_h / 2
            pos[node] = (x, y)

    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
             f"aria-label='module import graph'>"]
    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source not in pos or target not in pos:
            continue
        x1, y1 = pos[source]
        x2, y2 = pos[target]
        colour = "#2f855a" if edge["kind"] == "hard" else "#8a94a6"
        dash = "" if edge["kind"] == "hard" else "stroke-dasharray='3 3'"
        parts.append(
            f"<path d='M{x1 + node_w} {y1 + node_h / 2} C{x1 + node_w + 30} "
            f"{y1 + node_h / 2}, {x2 - 30} {y2 + node_h / 2}, {x2} {y2 + node_h / 2}' "
            f"fill='none' stroke='{colour}' stroke-width='1.2' {dash}/>")
    for node in nodes:
        x, y = pos[node]
        attribute = attrs.get(node) or {}
        fan = attribute.get("fan_in", 0)
        stroke = "#2f855a" if fan >= 2 else "#d3d9e2"
        parts.append(
            f"<g><rect x='{x}' y='{y}' width='{node_w}' height='{node_h}' rx='5' "
            f"fill='#ffffff' stroke='{stroke}' stroke-width='{1.6 if fan >= 2 else 1}'/>"
            f"<text x='{x + 7}' y='{y + 14}' font-size='9.5' fill='#2b333d' "
            f"font-family='ui-monospace,SFMono-Regular,Menlo,monospace'>"
            f"{html.escape(_short(node))}</text></g>")
    parts.append("</svg>")
    legend = ("<p class='detail' style='margin:8px 0 0'>solid = module-scope import "
              "(failure propagates) · dashed = import inside a function (optional) · "
              "green border = imported by two or more modules</p>")
    return "".join(parts) + legend


def waterfall(spans: list[dict]) -> str:
    if not spans:
        return "<p class='detail'>no trace recorded: run tools/audit_chains.py --spans</p>"
    start = min(s["start_ts"] for s in spans)
    end = max(s["end_ts"] for s in spans)
    total = max(end - start, 0.001)
    rows = []
    for span in sorted(spans, key=lambda s: s["start_ts"]):
        left = (span["start_ts"] - start) / total * 100
        width = max(span["duration_ms"] / 1000.0 / total * 100, 0.4)
        pill = PILL.get(span["status"], SKIP)
        rows.append(
            f"<div class='wf-row' title='{html.escape(span['attributes']['detail'])}'>"
            f"<span class='wf-name'>{html.escape(span['name'])}</span>"
            f"<span class='wf-track'><i class='wf-bar {pill}' "
            f"style='left:{left:.2f}%;width:{width:.2f}%'></i></span>"
            f"<span class='wf-ms'>{span['duration_ms']:.0f} ms</span>"
            f"<span class='pill {pill}'>{span['status']}</span></div>")
    return "".join(rows)


def spark(values: list[float], width: int = 90, height: int = 18) -> str:
    clean = [float(v) for v in values if isinstance(v, (int, float))]
    if len(clean) < 2:
        return "<span class='detail'>—</span>"
    low, high = min(clean), max(clean)
    span = (high - low) or 1.0
    points = " ".join(
        f"{i * width / (len(clean) - 1):.1f},{height - (v - low) / span * (height - 2) - 1:.1f}"
        for i, v in enumerate(clean))
    return (f"<svg width='{width}' height='{height}' aria-hidden='true'>"
            f"<polyline points='{points}' fill='none' stroke='#2f855a' "
            f"stroke-width='1.2'/></svg>")


def control_table(status: dict) -> str:
    signals = (status.get("signals") or {})
    if not signals:
        return "<p class='detail'>no sample yet: run tools/watch_pipeline.py</p>"
    history = status.get("history") or []
    rows = []
    for name, row in signals.items():
        state = row.get("state", "UNOBSERVABLE")
        pill = {"OK": PASS, "ALARM": FAIL}.get(state, SKIP)
        series = [s.get("values", {}).get(name) for s in history
                  if isinstance(s.get("values"), dict)]
        err_text = "" if row.get("error") is None else format(row["error"], "+.1f")
        rows.append(
            f"<tr><td class='mono'>{html.escape(name)}</td>"
            f"<td>{html.escape(str(row.get('reference')))}</td>"
            f"<td><b>{html.escape(str(row.get('value')))}</b> "
            f"<span class='detail'>{html.escape(str(row.get('unit') or ''))}</span></td>"
            f"<td>{err_text}</td>"
            f"<td><span class='pill {pill}'>{state}</span></td>"
            f"<td>{spark([v for v in series if v is not None])}</td></tr>")
    return ("<table class='ctl'><caption>The loop: each signal against its reference.</caption>"
            "<thead><tr><th>signal</th><th>reference</th>"
            "<th>measured</th><th>error</th><th>state</th><th>last 40</th></tr></thead>"
            "<tbody id='ctl-rows'>" + "".join(rows) + "</tbody></table>")


def alarms_table(alarms: list[dict]) -> str:
    if not alarms:
        return "<p class='detail'>no transitions recorded</p>"
    rows = "".join(
        f"<tr><td class='mono'>{html.escape(str(a.get('ts', ''))[11:19])}</td>"
        f"<td class='mono'>{html.escape(str(a.get('signal')))}</td>"
        f"<td>{html.escape(str(a.get('from')))} → <b>{html.escape(str(a.get('to')))}</b></td>"
        f"<td class='detail'>{html.escape(str(a.get('source', '')))}</td></tr>"
        for a in reversed(alarms[-8:]))
    return ("<table class='ctl'><caption>Edge-triggered transitions, newest first.</caption>"
            "<thead><tr><th>time</th><th>signal</th><th>transition</th>"
            "<th>source</th></tr></thead><tbody>" + rows + "</tbody></table>")


def chain_table(chains: list[dict]) -> str:
    if not chains:
        return "<p class='detail'>no chains recorded</p>"
    rows = "".join(
        f"<tr><td class='mono'>{html.escape(c['name'])}</td>"
        f"<td><span class='pill {PILL.get(c['status'], SKIP)}'>{c['status']}</span></td>"
        f"<td>{c['ms']:.0f} ms</td>"
        f"<td class='detail'>{html.escape(c['detail'][:110])}</td></tr>"
        for c in chains)
    return ("<table class='ctl'><caption>One row per chain, in run order.</caption>"
            "<thead><tr><th>chain</th><th>status</th><th>time</th>"
            "<th>what it exercised</th></tr></thead><tbody>" + rows + "</tbody></table>")


SCRIPT = """
<script>
(() => {
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
  const badge = document.getElementById('live-badge');
  const paint = (d) => {
    set('ov', d.overall || '—');
    set('stamp', (d.ts || '').replace('T', ' ').slice(0, 19));
    const tbody = document.getElementById('ctl-rows');
    if (tbody && d.signals) {
      tbody.innerHTML = Object.entries(d.signals).map(([name, r]) => {
        const cls = r.state === 'OK' ? 'pass' : (r.state === 'ALARM' ? 'fail' : 'skip');
        const err = (r.error === null || r.error === undefined) ? '' : (r.error > 0 ? '+' : '') + r.error;
        return `<tr><td class="mono">${name}</td><td>${r.reference}</td>` +
               `<td><b>${r.value}</b> <span class="detail">${r.unit || ''}</span></td>` +
               `<td>${err}</td><td><span class="pill ${cls}">${r.state}</span></td><td></td></tr>`;
      }).join('');
    }
    if (badge) { badge.textContent = d.stale ? 'stale' : 'live'; badge.className = 'pill ' + (d.stale ? 'skip' : 'pass'); }
  };
  const poll = async () => {
    try {
      const r = await fetch('/api/status', {cache: 'no-store'});
      if (!r.ok) throw new Error('http ' + r.status);
      paint(await r.json());
    } catch (e) {
      if (badge) { badge.textContent = 'snapshot'; badge.className = 'pill skip'; }
    }
  };
  if (location.protocol.startsWith('http')) { poll(); setInterval(poll, 3000); }
})();
</script>
"""


def render(pipeline: dict, status: dict) -> str:
    coupling = pipeline.get("coupling") or {}
    trace = pipeline.get("trace") or {}
    overall = status.get("overall", "—")
    badge = {"OK": PASS, "ALARM": FAIL}.get(overall, SKIP)
    html_out = f"""
<div class="card" style="margin-top:18px">
  <h3 style="display:flex;justify-content:space-between;align-items:baseline">
    Control loop
    <span><span class="pill {badge}" id="ov">{html.escape(str(overall))}</span>
    <span class="pill skip" id="live-badge">snapshot</span></span>
  </h3>
  <p class="detail" style="margin:0 0 10px">Every signal has a reference; the error is
  what the loop acts on. Sampled {html.escape(str(status.get('ts', 'never'))[:19])}
  ({status.get('samples', 0)} samples). Served over http, this table repaints itself
  every 3 s; opened from disk it is the last snapshot and says so.</p>
  {control_table(status)}
  <h4 style="margin:16px 0 6px;font-size:12px">Transitions (edge-triggered)</h4>
  {alarms_table(status.get('alarms') or [])}
</div>

<div class="card" style="margin-top:18px">
  <h3>Structure — what depends on what</h3>
  <p class="detail" style="margin:0 0 6px">{len(coupling.get('nodes') or [])} modules,
  {len(coupling.get('edges') or [])} import edges, {coupling.get('cycles', 0)} cycles.
  Layered by dependency depth: a module sits one column right of everything it imports.</p>
  {dag_svg(coupling)}
</div>

<div class="card" style="margin-top:18px">
  <h3>Execution — the last chain audit as a trace</h3>
  <p class="detail" style="margin:0 0 10px">Trace
  <span class="mono">{html.escape(str(trace.get('id', '—'))[:12])}</span>,
  {trace.get('duration_ms', 0):,.0f} ms wall, status
  <b>{html.escape(str(trace.get('status', '—')))}</b>. The order below is the order the
  chains ran; overlapping bars would mean the chains could run in parallel, which they
  cannot.</p>
  {chain_table(pipeline.get('chains') or [])}
  <div style="margin-top:12px">{waterfall(pipeline.get('spans') or [])}</div>
</div>
{SCRIPT}"""
    return html_out
