"""The pipeline assembly: chains → modules → services, each node carrying its own state.

Rebuilt from memory of the version that was running before the source was lost to an
uncommitted checkout. What it draws, and why:

    chains (left, in execution order) → modules (middle) → services (right)

Every node is filled with the state it holds and stamped with its age, so "what is running,
what is stale, what is broken" is answered by looking. Below it, the same nodes over time:
one row per chain, one segment per interval, hatched where the watcher was silent.

    python tools/dashboard.py            # writes site/dashboard.html
"""

from __future__ import annotations

import datetime
import html
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import status_view  # noqa: E402  (the single verdict function, shared with the watcher)

STATUS = ROOT / "docs" / "status"
PIPELINE = ROOT / "docs" / "pipeline.json"
OUT = ROOT / "site" / "dashboard.html"
MAX_COLS = 80
HKT = datetime.timezone(datetime.timedelta(hours=8))

PALETTE = {
    "IDLE": "#2a2f36", "RUNNING": "#5b8def", "PASS": "#57ab5a",
    "SKIP": "#7d8590", "FAIL": "#e5534b", "STALE": "#d29922",
}
INK = {"IDLE": "#c9d1d9", "RUNNING": "#0b0e12", "PASS": "#0b0e12",
       "SKIP": "#0b0e12", "FAIL": "#ffffff", "STALE": "#141414"}
SEVERITY = {"FAIL": 5, "STALE": 4, "RUNNING": 3, "SKIP": 2, "PASS": 1, "IDLE": 0}

MODULE_SERVICE = {
    "framework.decision": "decision_service",
    "framework.inference": "runtime_18434",
    "framework.quarto_bridge": "quarto",
    "framework.tracking": "mlflow",
}
SERVICE_LABEL = {
    "decision_service": "decision · :8090",
    "runtime_18434": "llama.cpp · :18434",
    "quarto": "quarto",
    "dvc": "dvc",
    "mlflow": "mlflow",
}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def worst(states):
    return max(states, key=lambda s: SEVERITY.get(s, 0)) if states else "IDLE"


def hkt(ts: str) -> str:
    try:
        return (datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                .astimezone(HKT).strftime("%H:%M:%S"))
    except (ValueError, AttributeError):
        return "—"


def fmt_age(seconds: float) -> str:
    if seconds < 1:
        return "now"
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


def fault_ranking(hours: int = 24, gap_minutes: int = 10):
    path = STATUS / "faults.jsonl"
    if not path.is_file():
        return []
    cutoff = time.time() - hours * 3600
    episodes: dict[str, list[float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            when = datetime.datetime.fromisoformat(
                str(row.get("ts", "")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if when < cutoff:
            continue
        episodes.setdefault(row.get("signal") or "?", []).append(when)
    out = []
    for node, times in episodes.items():
        times.sort()
        count = 1
        for earlier, later in zip(times, times[1:]):
            if later - earlier > gap_minutes * 60:
                count += 1
        out.append((node, count, hkt(datetime.datetime.fromtimestamp(times[-1], HKT).isoformat())))
    return sorted(out, key=lambda kv: -kv[1])[:6]


def freshness() -> str:
    parts = []
    render = load(ROOT / "docs" / "RENDER_CHECK.json", {}) or {}
    evidence = load(ROOT / "reference" / "operator_calibration" / "docs"
                    / "evidence.json", {}) or {}
    for label, stamp, limit_h in (("render", render.get("generated"), 24),
                                  ("operator evidence", evidence.get("generated"), 168)):
        age = None
        if stamp:
            try:
                then = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                age = (datetime.datetime.now(datetime.timezone.utc) - then).total_seconds() / 3600
            except ValueError:
                age = None
        if age is None:
            parts.append(f"{label}: no timestamp")
            continue
        tone = "#d29922" if age > limit_h else "#7d8899"
        parts.append(f"<span style='color:{tone}'>{label} {age:.1f} h (limit {limit_h} h)</span>")
    return "<div class='fresh'>" + " · ".join(parts) + "</div>" if parts else ""


def strip(timeline, max_cols=MAX_COLS):
    """History with a real time axis: a block's width is the interval it covers."""
    rows = [r for r in timeline if r.get("ts")][-max_cols:]
    if len(rows) < 2:
        return ""
    times = []
    for r in rows:
        try:
            times.append(datetime.datetime.fromisoformat(
                str(r["ts"]).replace("Z", "+00:00")).timestamp())
        except ValueError:
            times.append(0.0)
    deltas = [max(times[i + 1] - times[i], 1.0) for i in range(len(times) - 1)]
    deltas.append(deltas[-1] if deltas else 1.0)
    ordered = sorted(deltas)
    median = ordered[len(ordered) // 2] or 1.0
    total = sum(deltas) or 1.0

    raw = []
    for delta in deltas:
        share = delta / total * 100
        if delta > 5 * median and delta > 60:
            state_share = median / total * 100
            raw.append([max(state_share, 0.05), max(share - state_share, 0.05)])
        else:
            raw.append([max(share, 0.05)])
    scale = 100.0 / (sum(sum(p) for p in raw) or 1.0)
    raw = [[v * scale for v in pair] for pair in raw]

    chains = sorted({n for r in rows for n in (r.get("states") or {})})
    out = []
    for chain in chains:
        cells = []
        for i, row in enumerate(rows):
            state = (row.get("states") or {}).get(chain, "IDLE")
            widths = raw[i]
            if len(widths) == 2:
                cells.append(f"<i class='sc' style='width:{widths[0]:.3f}%;"
                             f"background:{PALETTE[state]}' "
                             f"title='{hkt(row['ts'])} · {state}'></i>")
                cells.append(f"<i class='sc gap' style='width:{widths[1]:.3f}%' "
                             f"title='no samples for {deltas[i] / 60:.0f} min'></i>")
            else:
                cells.append(f"<i class='sc' style='width:{widths[0]:.3f}%;"
                             f"background:{PALETTE[state]}' "
                             f"title='{hkt(row['ts'])} · {state}'></i>")
        out.append(f"<div class='srow'><span class='sname'>{html.escape(chain)}</span>"
                   f"<span class='scells'>{''.join(cells)}</span></div>")

    gaps = [d for d in deltas if d > 5 * median and d > 60]
    summary = ("<div class='gapsum'>no gaps in this window</div>" if not gaps else
               f"<div class='gapsum'>{len(gaps)} gap{'s' if len(gaps) > 1 else ''} · "
               f"longest {max(gaps) / 60:.0f} min without a sample</div>")
    axis = (f"<div class='sax'><span>{hkt(rows[0]['ts'])}</span>"
            f"<span>{hkt(rows[-1]['ts'])}</span><span>HKT</span></div>")
    return f"<div class='srows'>{''.join(out)}</div>" + axis + summary


def ranking_table(rows) -> str:
    if not rows:
        return "<div class='empty'>no faults in the last 24 hours</div>"
    body = "".join(
        f"<tr><td class='mono'>{html.escape(str(node))}</td>"
        f"<td class='num'>{count}×</td><td class='num'>{last}</td></tr>"
        for node, count, last in rows)
    return ("<table class='rank'><thead><tr><th>node</th><th>incidents</th><th>last</th>"
            "</tr></thead><tbody>" + body + "</tbody></table>")


def topology(pipeline, chain_now, durations, signals, trace_ts):
    """The assembly. `signals` is passed in so a caller can hand it a fixture."""
    chain_modules = pipeline.get("chain_modules") or {}
    chains = list(chain_modules)
    if not chains:
        return "<div class='empty'>no chains recorded</div>", [], {}

    module_users: dict[str, list[str]] = {}
    for chain, mods in chain_modules.items():
        for module in mods or []:
            module_users.setdefault(module, []).append(chain)
    modules = sorted(module_users)
    services = [s for s in ("decision_service", "runtime_18434", "quarto", "dvc", "mlflow")
                if s in signals]

    c_x, c_w, c_h, c_gap = 18, 330, 24, 8
    m_x, m_w, m_h = 408, 300, 22
    s_x, s_w, s_h = 768, 300, 24
    top = 8
    chain_y = {c: top + i * (c_h + c_gap) for i, c in enumerate(chains)}
    rows = len(chains) * (c_h + c_gap)
    mod_gap = max(5, rows // max(len(modules), 1) - m_h)
    mod_y = {m: top + i * (m_h + mod_gap) for i, m in enumerate(modules)}
    s_gap = max(14, rows // max(len(services), 1) - s_h)
    svc_y = {s: top + i * (s_h + s_gap) for i, s in enumerate(services)}
    height = max(max(chain_y.values()) + c_h,
                 max(mod_y.values(), default=0) + m_h,
                 (max(svc_y.values()) + s_h) if svc_y else 0) + 12
    width = s_x + s_w + 10
    age = max(0.0, time.time() - trace_ts) if trace_ts else None

    svg = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
           f"aria-label='pipeline assembly with status'>",
           "<defs><marker id='ah' viewBox='0 0 10 10' refX='8.5' refY='5' markerWidth='4.6' "
           "markerHeight='4.6' orient='auto'><path d='M0 1 L9 5 L0 9 z' "
           "fill='context-stroke'/></marker></defs>"]

    drawn = 0
    for chain in chains:
        state = chain_now.get(chain, "IDLE")
        y = chain_y[chain]
        svg.append(
            f"<g class='node chain' data-chain='{html.escape(chain)}' tabindex='0' role='button'>"
            f"<title>{html.escape(chain)} · {state} · click for detail</title>"
            f"<rect x='{c_x}' y='{y}' width='{c_w}' height='{c_h}' rx='5' "
            f"fill='{PALETTE.get(state, PALETTE['IDLE'])}' stroke='#0a0c0f'/>"
            f"<text x='{c_x + 10}' y='{y + c_h / 2 + 3.7}' font-size='10.5' font-weight='600' "
            f"fill='{INK.get(state, '#c9d1d9')}'>"
            f"{html.escape(chain[:34] + ('…' if len(chain) > 34 else ''))}</text>"
            f"<text class='age' x='{c_x + c_w - 10}' y='{y + c_h / 2 + 3.4}' text-anchor='end' "
            f"font-size='9' fill='{INK.get(state, '#c9d1d9')}' opacity='0.92'>"
            f"{fmt_age(age) if age is not None else '—'}</text></g>")
        for module in chain_modules.get(chain) or []:
            if module not in mod_y:
                continue
            x1, y1 = c_x + c_w, y + c_h / 2
            x2, y2 = m_x, mod_y[module] + m_h / 2
            dx = max(36, (x2 - x1) * 0.42)
            drawn += 1
            flow = ""
            svg.append(f"<path class='edge' data-from='{html.escape(chain)}' "
                       f"d='M{x1} {y1} C{x1 + dx} {y1}, {x2 - dx} {y2}, {x2} {y2}' "
                       f"style='stroke-dashoffset:{(drawn * 2.7) % 7:.1f}' fill='none' "
                       f"stroke='{PALETTE.get(state, PALETTE['IDLE'])}' stroke-width='1.1' "
                       f"opacity='0.55' stroke-dasharray='4 3' marker-end='url(#ah)'/>")

    for module in modules:
        users = module_users[module]
        state = worst([chain_now.get(u, "IDLE") for u in users])
        y = mod_y[module]
        name = module.replace("framework.", "").replace("tools.", "")
        svg.append(
            f"<g class='node module' data-module='{html.escape(module)}' tabindex='0' "
            f"role='button'><title>{html.escape(module)} · {state} · used by "
            f"{len(users)} chains</title>"
            f"<rect x='{m_x}' y='{y}' width='{m_w}' height='{m_h}' rx='4' "
            f"fill='{PALETTE.get(state, PALETTE['IDLE'])}' stroke='#0a0c0f'/>"
            f"<text x='{m_x + 10}' y='{y + m_h / 2 + 3.4}' font-size='10' "
            f"fill='{INK.get(state, '#c9d1d9')}'>"
            f"{html.escape(name[:36] + ('…' if len(name) > 36 else ''))}</text>"
            f"<text x='{m_x + m_w - 8}' y='{y + m_h / 2 + 3.4}' text-anchor='end' font-size='9' "
            f"fill='{INK.get(state, '#c9d1d9')}' opacity='0.92'>{len(users)}×</text></g>")
        service = MODULE_SERVICE.get(module)
        if service and service in svc_y:
            x1, y1 = m_x + m_w, y + m_h / 2
            x2, y2 = s_x, svc_y[service] + s_h / 2
            dx = max(36, (x2 - x1) * 0.42)
            up = (signals.get(service) or {}).get("state") not in ("ALARM", "UNOBSERVABLE")
            drawn += 1

            svg.append(f"<path class='edge svc{flow}' d='M{x1} {y1} C{x1 + dx} {y1}, "
                       f"{x2 - dx} {y2}, {x2} {y2}' "
                       f"style='stroke-dashoffset:{(drawn * 2.7) % 7:.1f}' fill='none' "
                       f"stroke='{PALETTE['PASS' if up else 'FAIL']}' stroke-width='1.1' "
                       f"opacity='0.55' stroke-dasharray='4 3' marker-end='url(#ah)'/>")

    for service in services:
        sig = signals.get(service) or {}
        ok = sig.get("state") not in ("ALARM", "UNOBSERVABLE")
        state = "PASS" if ok else "FAIL"
        y = svc_y[service]
        label = SERVICE_LABEL.get(service, service)
        svg.append(
            f"<g class='node service' data-service='{html.escape(service)}' tabindex='0' "
            f"role='button'><title>{html.escape(label)} · {sig.get('state', '?')}</title>"
            f"<rect x='{s_x}' y='{y}' width='{s_w}' height='{s_h}' rx='4' "
            f"fill='{PALETTE[state]}' stroke='#0a0c0f'/>"
            f"<text x='{s_x + 10}' y='{y + s_h / 2 + 3.4}' font-size='10' "
            f"fill='{INK[state]}'>{html.escape(label)}</text>"
            f"<text x='{s_x + s_w - 8}' y='{y + s_h / 2 + 3.4}' text-anchor='end' font-size='9' "
            f"fill='{INK[state]}' opacity='0.92'>"
            f"{html.escape(str(sig.get('note') or 'now'))}</text></g>")

    svg.append("</svg>")

    faults = [f"{c} = {s}" for c, s in chain_now.items() if s in ("FAIL", "STALE")]
    for module, users in module_users.items():
        st = worst([chain_now.get(u, "IDLE") for u in users])
        if st in ("FAIL", "STALE"):
            faults.append(f"{module} = {st}")
    for service in services:
        if (signals.get(service) or {}).get("state") in ("ALARM", "UNOBSERVABLE"):
            faults.append(f"{service} = DOWN")
    return "".join(svg), faults, module_users


CSS = """
:root{--bg:#0e1013;--panel:#15181d;--line:#232830;--fg:#e6e8eb;--mut:#98a2b3;--dim:#7d8899;
  --accent:#5b8def;--ok:#57ab5a;--warn:#d29922;--bad:#e5534b}
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased}
body{margin:0;font:12.5px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--fg);background:var(--bg);letter-spacing:.005em}
header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:7px 18px;
  border-bottom:1px solid var(--line);background:#15181d;position:sticky;top:0;
  box-shadow:0 6px 14px -10px #000;z-index:5}
.brand{font-weight:650;font-size:12.5px;letter-spacing:.02em}
.brand i{color:var(--accent);font-style:normal;margin-right:6px}
.pill{font:600 10.5px/1 inherit;letter-spacing:.08em;padding:5px 10px;border-radius:20px;
  border:1px solid var(--line);text-transform:uppercase}
.pill.OK{color:#57ab5a;background:rgba(87,171,90,.1);border-color:rgba(87,171,90,.35)}
.pill.ALARM{color:#ef6b62;background:rgba(229,83,75,.1);border-color:rgba(229,83,75,.35)}
.spacer{flex:1}
.act{font:600 10.5px/1 inherit;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);
  background:transparent;border:1px solid var(--line);border-radius:6px;padding:5px 9px;
  cursor:pointer;transition:color .2s,border-color .2s}
.act:hover{color:var(--fg);border-color:#3a4048}
.meta{color:var(--dim);font-size:11px;letter-spacing:.02em}
.meta b{color:var(--mut);font-weight:600}
#live{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:#7d8899;
  display:inline-flex;align-items:center}
#live.on{color:#57ab5a}#live.off{color:#d29922}
.live{width:7px;height:7px;border-radius:50%;background:#3fb950;display:inline-block;
  margin-right:7px;animation:beat 2.4s ease-in-out infinite;will-change:opacity}
@keyframes beat{0%,100%{opacity:.35}50%{opacity:1}}
main{max-width:1320px;margin:0 auto;padding:12px 18px 24px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:11px 13px;margin-bottom:9px}
.card h2{margin:0 0 8px;font-size:10px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--dim);font-weight:600}
.grid{display:grid;grid-template-columns:1.9fr 1fr;gap:9px;align-items:start}
.grid.one{grid-template-columns:1fr}
@media (max-width:1000px){.grid{grid-template-columns:1fr}}
.faults{font-size:11.5px;color:#d29922;margin-top:8px}
.faults b{color:#e5534b;letter-spacing:.1em;font-size:10.5px;margin-right:6px}
svg text{font-variant-numeric:tabular-nums}
svg .node{cursor:pointer}
svg .node rect{transition:fill .4s ease,stroke .4s ease}
svg .node:hover rect{stroke:#fff;stroke-opacity:.45}
svg .node:focus{outline:none}
svg .edge{transition:stroke .4s ease}
.key{display:flex;gap:11px;font-size:9.5px;color:var(--dim);margin:0 0 7px;flex-wrap:wrap;
  letter-spacing:.04em;text-transform:uppercase}
.key i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px}
.key i.dotkey{width:0;height:0;border-left:7px solid #5b8def;border-top:4px solid transparent;
  border-bottom:4px solid transparent;background:none;border-radius:0;margin:0 6px 0 8px}
.srow{display:flex;align-items:center;gap:14px;margin:1px 0}
.sname{width:122px;flex:none;text-align:right;padding-right:8px;
  font:9px/1.35 ui-monospace,Menlo,monospace;color:var(--dim);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.scells{flex:1;display:flex;gap:0;min-width:0;overflow:hidden}
.sc{height:7px;display:inline-block;flex:0 0 auto;box-shadow:inset -1px 0 0 rgba(14,16,19,.85)}
.sc.gap{background:repeating-linear-gradient(45deg,#15181d,#15181d 2px,#20242b 2px,#20242b 4px)}
.sax{display:flex;justify-content:space-between;font:9px ui-monospace;color:#7d8899;
  margin:4px 0 0 136px}
.gapsum{margin-top:4px;font:9.5px/1.4 ui-monospace,Menlo,monospace;color:#7d8899}
.fresh{margin-top:5px;font:9.5px/1.4 ui-monospace,Menlo,monospace;color:var(--dim)}
.empty{color:#7d8899;font-style:italic;font-size:11.5px}
table.rank{width:100%;border-collapse:collapse;font-size:10.5px}
table.rank th{text-align:left;font:9.5px/1 -apple-system,sans-serif;letter-spacing:.06em;
  text-transform:uppercase;color:#7d8899;padding:0 0 5px;font-weight:600}
table.rank td{padding:3px 0;border-bottom:1px solid var(--line)}
table.rank td.num{text-align:right;font-variant-numeric:tabular-nums}
#pop{position:fixed;z-index:30;width:360px;max-height:60vh;overflow:auto;display:none;
  background:#191d23;border:1px solid var(--line);border-radius:8px;padding:12px 14px;
  box-shadow:0 18px 40px -18px #000}
#pop.on{display:block}
#pop .t{font-weight:650;font-size:12.5px;margin-bottom:4px}
#pop .d{color:var(--mut);font-size:11px;line-height:1.5}
#pop .m{color:var(--dim);font-size:10.5px;margin-top:5px;font-family:ui-monospace,Menlo,monospace}
#pop .x{float:right;cursor:pointer;color:var(--dim);font-size:15px;line-height:1}
@media (prefers-reduced-motion:reduce){
  .live{animation:none}
  svg .node rect{transition:none}
}
"""

JS = """
const PALETTE = __PALETTE__;
const POLL_MS = 10000;
const popEl = () => document.getElementById('pop');

function openPop(html, ev) {
  const box = popEl(); if (!box) return;
  box.innerHTML = '<span class="x" id="popx">×</span>' + html;
  box.className = 'on';
  let x = (ev ? ev.clientX : window.innerWidth / 2) + 14;
  let y = (ev ? ev.clientY : 140) + 14;
  x = Math.max(12, Math.min(x, window.innerWidth - 372));
  y = Math.max(12, Math.min(y, window.innerHeight - 240));
  box.style.left = x + 'px'; box.style.top = y + 'px';
  const close = document.getElementById('popx');
  if (close) close.onclick = () => { box.className = ''; };
}
function dismiss() { const b = popEl(); if (b) b.className = ''; }
document.addEventListener('keydown', e => { if (e.key === 'Escape') dismiss(); });
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-restart]');
  if (!btn) return;
  const service = btn.dataset.restart;
  openPop('<div class="t">restarting ' + service + '…</div>', e);
  fetch('/api/restart/' + service, {method: 'POST'})
    .then(r => r.json())
    .then(j => openPop('<div class="t">' + (j.ok ? 'spawned pid ' + j.pid : 'refused') +
      '</div><div class="d">' + (j.error || j.description || 'the watcher confirms within one sample') +
      '</div>', e))
    .catch(err => openPop('<div class="t">failed</div><div class="d">' + err + '</div>', e));
});
document.addEventListener('click', e => {
  if (!e.target.closest('#pop')) dismiss();
  const node = e.target.closest('g.node');
  if (!node) return;
  const kind = node.dataset.chain ? 'chain' : node.dataset.module ? 'module' : 'service';
  const name = node.dataset.chain || node.dataset.module || node.dataset.service;
  const t = node.querySelector('title');
  let html = '<div class="t">' + name + '</div><div class="d">' + kind + ' · ' +
             (t ? t.textContent : name) + '</div>';
  if (kind === 'service') {
    html += '<div class="m">diagnosis: the probe is the measurement; a state other than OK ' +
            'means the boundary did not answer.</div>';
    html += '<div class="m">recovery: <button class="act" data-restart="' + name + '">' +
            'restart</button></div>';
  }
  html += '<div class="m">state from the last sample · click elsewhere to close</div>';
  openPop(html, e);
});

function hkt(ts) {
  try {
    return new Date(ts).toLocaleTimeString('en-GB', {hour12: false, timeZone: 'Asia/Hong_Kong'});
  } catch (e) { return '—'; }
}

async function poll() {
  try {
    const r = await fetch('/api/status', {cache: 'no-store'});
    const d = await r.json();
    const overall = (d.derived || {}).overall || d.overall || '—';
    const pill = document.getElementById('ov');
    if (pill) {
      pill.textContent = overall;
      pill.className = 'pill ' + (overall === 'OK' ? 'OK' : 'ALARM');
    }
    const meta = document.getElementById('meta');
    if (meta && d.ts) {
      meta.innerHTML = 'sampled <b>' + hkt(d.ts) + '</b> HKT · <b>' + (d.samples || 0) +
        '</b> samples · run <b>' + (d.live_run ? 'in progress' : 'idle') + '</b>';
    }
    const fl = document.getElementById('faults');
    if (fl && d.derived) {
      const faults = d.derived.faults || [];
      if (faults.length) {
        fl.innerHTML = '<b>FAULT</b>' + faults.map(f => ' · ' + f).join('');
        fl.style.display = '';
      } else { fl.textContent = ''; fl.style.display = 'none'; }
    }
    const chains = d.chains || {};
    document.querySelectorAll('g.node.chain').forEach(g => {
      const st = chains[g.dataset.chain] || 'IDLE';
      const rect = g.querySelector('rect');
      if (rect) rect.setAttribute('fill', PALETTE[st] || PALETTE.IDLE);
    });
    document.querySelectorAll('.edge').forEach(p => {
      const st = chains[p.dataset.from];
      if (st) p.setAttribute('stroke', PALETTE[st] || PALETTE.IDLE);
    });
    const stripEl = document.getElementById('strip');
    if (stripEl && d.strip_html && stripEl.dataset.sig !== d.strip_html) {
      stripEl.innerHTML = d.strip_html;
      stripEl.dataset.sig = d.strip_html;
    }
    const live = document.getElementById('live');
    if (live) {
      const txt = document.getElementById('livetext');
      if (txt) txt.textContent = d.stale ? 'snapshot' : 'live';
      live.className = d.stale ? 'off' : 'on';
    }
  } catch (err) { /* keep the last sample on screen */ }
}

if (location.protocol.startsWith('http')) {
  poll();
  let timer = null;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(async () => { await poll(); schedule(); },
                       document.hidden ? 60000 : POLL_MS);
  };
  schedule();
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); schedule(); });
}
"""


def build() -> str:
    pipeline = load(PIPELINE, {}) or {}
    status = load(STATUS / "current.json", {}) or {}
    timeline = load(STATUS / "timeline.json", []) or []
    if isinstance(status.get("timeline"), list) and status["timeline"]:
        timeline = status["timeline"]

    chain_now = status.get("chains") or {}
    signals = status.get("signals") or {}
    module_users: dict[str, list[str]] = {}
    for chain, mods in (pipeline.get("chain_modules") or {}).items():
        for module in mods or []:
            module_users.setdefault(module, []).append(chain)
    derived = status.get("derived") or status_view.derive(signals, chain_now, module_users)
    overall = derived.get("overall") or status.get("overall") or "—"
    traces = load(ROOT / "docs" / "traces" / "latest.json", {}) or {}
    try:
        trace_ts = datetime.datetime.fromisoformat(
            str(traces.get("ts", "")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        trace_ts = 0.0

    svg, faults, _ = topology(pipeline, chain_now, {}, signals, trace_ts)
    faults = derived.get("faults") or faults
    ranking = fault_ranking()
    stamp = hkt(status.get("ts", "")) if status.get("ts") else "—"

    key = "".join(f"<span><i style='background:{PALETTE[s]}'></i>{s}</span>"
                  for s in ("PASS", "SKIP", "RUNNING", "STALE", "FAIL", "IDLE"))
    key += "<span><i class='dotkey'></i>arrowhead = the direction the signal flows</span>"

    fault_line = ("<div class='faults' id='faults' style='display:none'></div>" if not faults else
                  "<div class='faults' id='faults'><b>FAULT</b>" + " · ".join(faults) + "</div>")

    if ranking:
        grid_class, fault_card = "grid", (
            "<section class='card'><h2>Faults — last 24 hours</h2>" +
            ranking_table(ranking) + "</section>")
    else:
        grid_class, fault_card = "grid one", ""

    script = JS.replace("__PALETTE__", json.dumps(PALETTE))
    ok = overall == "OK"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Eidos pipeline — assembly and status</title>
<style>{CSS}</style></head>
<body>
<header>
  <span class="brand"><i>●</i>Eidos pipeline</span>
  <span class="pill {'OK' if ok else 'ALARM'}" id="ov">{html.escape(str(overall))}</span>
  <span class="spacer"></span>
  <span class="meta" id="meta">sampled <b>{stamp}</b> HKT · <b>{status.get('samples', 0)}</b>
    samples · run <b>{'in progress' if status.get('live_run') else 'idle'}</b></span>
  <span id="live" class="{'on' if ok else 'off'}"><i class="live"></i>
    <span id="livetext">{'live' if ok else 'snapshot'}</span></span>
  <button class="act" onclick="location.reload()">refresh</button>
</header>
<main>
  <section class="card">
    <h2>Assembly — chains (run order) → modules → services</h2>
    <div class="key">{key}</div>
    {svg}
    {fault_line}
  </section>
  <div class="{grid_class}">
    <section class="card">
      <h2>History — the same nodes over the last {MAX_COLS} samples</h2>
      <div id="strip">{strip(timeline)}</div>
      {freshness()}
    </section>{fault_card}
  </div>
</main>
<div id="pop" role="dialog" aria-live="polite"></div>
<script>{script}</script>
</body></html>"""


def main(argv=None) -> int:
    import argparse
    import re

    ap = argparse.ArgumentParser(description="build the monitor page")
    ap.add_argument("--check", action="store_true",
                    help="verify the built page is structurally complete and fresh")
    ap.add_argument("--no-age", action="store_true", help="structure only, skip freshness")
    ap.add_argument("--max-age", type=float, default=300.0)
    args = ap.parse_args(argv)

    if args.check:
        if not OUT.is_file():
            print(f"[FAIL] {OUT} has not been built")
            return 1
        page = OUT.read_text(encoding="utf-8")
        required = ['id="ov"', "data-chain=", "data-module=", "data-service=",
                    "id='faults'", 'id="strip"']
        missing = [m for m in required if m not in page]
        if missing:
            print(f"[FAIL] page is missing {missing}")
            return 1
        if args.no_age:
            print("dashboard structure is complete (age not checked)")
            return 0
        stamp = re.search(r"sampled <b>(\d\d:\d\d:\d\d)</b>", page)
        if not stamp:
            print("[FAIL] page carries no sample timestamp")
            return 1
        now = datetime.datetime.now(HKT)
        then = datetime.datetime.combine(now.date(),
                                         datetime.time.fromisoformat(stamp.group(1)), tzinfo=HKT)
        age = (now - then).total_seconds()
        if age > args.max_age or age < -60:
            print(f"[FAIL] page is {age:.0f}s old (limit {args.max_age:.0f}s)")
            return 1
        print(f"dashboard is current ({age:.0f}s old)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    page = build()
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT}: {len(page) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
