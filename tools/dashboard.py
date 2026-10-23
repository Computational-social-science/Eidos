"""A scientific monitoring dashboard for the Eidos pipeline.

One self-contained HTML file (site/dashboard.html), no external assets, no runtime
dependency beyond the JSON artefacts the watcher already writes. The three scientific
views it is built around:

    1. A state machine (FSM): the six states a chain can be in, and the transitions the
       monitor enforces. Every other view colours its output with this palette.
    2. A swimlane timeline: discrete states over wall-clock time, one lane per chain.
       A coloured segment is the state the chain held for that interval; a boundary is a
       transition, and every transition is also a row in the alarm log.
    3. A coupling graph: which chain executes which module, so a shared module — the point
       where one chain's change can break another — is visible.

It draws with SVG only, so a screenshot is a publication figure and the page is the same
whether opened from disk or served live (the poller is the only difference).

    python tools/dashboard.py            # writes site/dashboard.html
"""

from __future__ import annotations

import datetime
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = __import__("sys")
sys_path.path.insert(0, str(ROOT / "tools"))

import chain_states  # noqa: E402
import pipeline_view  # noqa: E402

STATUS = ROOT / "docs" / "status"
PIPELINE = ROOT / "docs" / "pipeline.json"
OUT = ROOT / "site" / "dashboard.html"

PALETTE = {
    "IDLE": "#eceff3", "RUNNING": "#4c72b0", "PASS": "#55a868",
    "SKIP": "#8a94a6", "FAIL": "#c44e52", "STALE": "#dd8452",
}
TEXT = {"IDLE": "#6b7683", "RUNNING": "#3a5a94", "PASS": "#2f6e44",
        "SKIP": "#5a6672", "FAIL": "#8e2f34", "STALE": "#9a5b1f"}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _epoch(ts: str) -> float:
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def legend() -> str:
    items = "".join(
        f"<span class='lg'><i style='background:{PALETTE[s]}'></i>{s}</span>"
        for s in chain_states.STATES)
    return f"<div class='legend'>{items}</div>"


def fsm_svg() -> str:
    """The state machine, drawn as states and the edges the monitor enforces."""
    pos = {
        "IDLE": (80, 130), "RUNNING": (250, 60), "PASS": (430, 60),
        "SKIP": (430, 130), "FAIL": (430, 200), "STALE": (250, 240),
    }
    edges = [
        ("IDLE", "RUNNING"), ("RUNNING", "PASS"), ("RUNNING", "SKIP"),
        ("RUNNING", "FAIL"), ("PASS", "RUNNING"), ("SKIP", "RUNNING"),
        ("FAIL", "RUNNING"), ("PASS", "STALE"), ("SKIP", "STALE"), ("FAIL", "STALE"),
        ("IDLE", "STALE"), ("STALE", "RUNNING"),
    ]
    parts = ["<svg viewBox='0 0 540 300' width='100%' role='img' aria-label='state machine'>"]
    parts.append("<defs><marker id='arr' viewBox='0 0 10 10' refX='9' refY='5' "
                 "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
                 "<path d='M0 0 L10 5 L0 10 z' fill='#7a8494'/></marker></defs>")
    for src, dst in edges:
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        parts.append(f"<path d='M{x1} {y1} C{(x1 + x2) / 2} {y1}, {(x1 + x2) / 2} {y2}, "
                     f"{x2} {y2}' fill='none' stroke='#7a8494' stroke-width='1.3' "
                     f"marker-end='url(#arr)'/>")
    for name, (x, y) in pos.items():
        fill = PALETTE[name] if name != "IDLE" else "#ffffff"
        stroke = PALETTE[name] if name != "IDLE" else "#c3c9d2"
        text_colour = "#ffffff" if name in ("RUNNING", "FAIL") else "#2b333d"
        parts.append(f"<rect x='{x - 46}' y='{y - 14}' width='92' height='28' rx='6' "
                     f"fill='{fill}' stroke='{stroke}' stroke-width='1.5'/>"
                     f"<text x='{x}' y='{y + 4}' text-anchor='middle' font-size='11.5' "
                     f"font-weight='600' fill='{text_colour}'>{name}</text>")
    parts.append("</svg>")
    return "".join(parts)


def gantt_svg(timeline: list[dict], width: int = 960, lane: int = 22) -> str:
    """Swimlane of discrete states over wall-clock time.

    Each lane is one chain. A run of identical state becomes one coloured segment, so a
    colour boundary is exactly a transition — the same boundary that appears in the alarm
    log. The x axis is real time, not a sample index.
    """
    rows = [r for r in timeline if r.get("ts")]
    if not rows:
        return "<p class='muted'>no timeline recorded yet</p>"
    chains = sorted({n for r in rows for n in (r.get("states") or {})})
    t0, t1 = _epoch(rows[0]["ts"]), _epoch(rows[-1]["ts"])
    span = max(t1 - t0, 1.0)
    left, right = 150, width - 20
    plot_w = right - left
    top, bottom = 8, 8 + len(chains) * lane

    def x(ts: str) -> float:
        return left + (_epoch(ts) - t0) / span * plot_w

    parts = [f"<svg viewBox='0 0 {width} {bottom + 30}' width='100%' "
             f"role='img' aria-label='chain state timeline'>"]

    # grid + time ticks
    for i in range(5):
        frac = i / 4
        xx = left + frac * plot_w
        tick = rows[min(int(frac * (len(rows) - 1)), len(rows) - 1)]["ts"]
        label = str(tick)[11:19]
        parts.append(f"<line x1='{xx}' y1='{top}' x2='{xx}' y2='{bottom}' "
                     f"stroke='#eef0f3' stroke-width='1'/>"
                     f"<text x='{xx}' y='{bottom + 16}' text-anchor='middle' "
                     f"font-size='10' fill='#7a8494'>{label}</text>")

    for index, chain in enumerate(chains):
        y = top + index * lane
        parts.append(f"<text x='{left - 10}' y='{y + lane - 6}' text-anchor='end' "
                     f"font-size='11' font-family='ui-monospace,Menlo,monospace' "
                     f"fill='#2b333d'>{html.escape(chain)}</text>")
        # segment runs of constant state
        seg_start = None
        seg_state = None
        for row in rows:
            state = (row.get("states") or {}).get(chain, "IDLE")
            if seg_state is None:
                seg_start, seg_state = row["ts"], state
                continue
            if state != seg_state:
                x1 = x(seg_start)
                x2 = x(row["ts"])
                parts.append(f"<rect x='{x1}' y='{y}' width='{max(x2 - x1, 1.0)}' "
                             f"height='{lane - 3}' rx='2' fill='{PALETTE[seg_state]}'>"
                             f"<title>{seg_start[11:19]} → {row['ts'][11:19]} "
                             f"{seg_state}</title></rect>")
                seg_start, seg_state = row["ts"], state
        x1 = x(seg_start)
        x2 = right
        parts.append(f"<rect x='{x1}' y='{y}' width='{max(x2 - x1, 1.0)}' "
                     f"height='{lane - 3}' rx='2' fill='{PALETTE[seg_state]}'>"
                     f"<title>{seg_start[11:19]} → {rows[-1]['ts'][11:19]} "
                     f"{seg_state}</title></rect>")
    parts.append("</svg>")
    return "".join(parts)


def coupling_panel(pipeline: dict) -> str:
    modules = pipeline.get("chain_modules") or {}
    if not modules:
        return "<p class='muted'>no chain→module mapping</p>"
    shared = {}
    for chain, mods in modules.items():
        for m in mods:
            shared[m] = shared.get(m, 0) + 1
    hub = max(shared, key=shared.get) if shared else None
    hub_note = (f"<p class='muted'>Coupling hub: "
                f"<span class='mono'>{html.escape(str(hub))}</span> is executed by "
                f"{shared[hub]} chains — a change there breaks several chains at once.</p>"
                if hub and shared[hub] > 1 else
                "<p class='muted'>No module is shared by more than one chain: the chains "
                "are the coupling units, and shared modules are absent.</p>")
    return pipeline_view.dag_svg(pipeline.get("coupling") or {}) + hub_note


def signals_table(status: dict) -> str:
    return pipeline_view.control_table(status)


def alarms_table(alarms: list[dict]) -> str:
    return pipeline_view.alarms_table(alarms)


PALETTE_JS = json.dumps(PALETTE)

SCRIPT = """
<script>
const PALETTE = __PALETTE__;
const __timeline = __TIMELINE__;
const chains = () => { const s = new Set(); for (const r of __timeline) for (const k in (r.states||{})) s.add(k); return [...s].sort(); };
function epoch(ts){ return new Date(ts).getTime()/1000 || 0; }
function segments(timeline, chain){ const out=[]; let start=null, state=null;
  for (const r of timeline){ if(!r.ts) continue; const cur=(r.states||{})[chain]||'IDLE';
    if(start===null){start=r.ts;state=cur;} else if(cur!==state){out.push([start,r.ts,state]);start=r.ts;state=cur;} }
  if(start!==null && timeline.length) out.push([start, timeline[timeline.length-1].ts||start, state]); return out; }
function drawTimeline(timeline){ const host=document.getElementById('gantt'); if(!host||!timeline.length) return;
  const cs=chains(); const W=960, L=22, left=150, right=W-20;
  const t0=epoch(timeline[0].ts), t1=epoch(timeline[timeline.length-1].ts), span=Math.max(t1-t0,1);
  const bottom=8+cs.length*L; const xAt=t=>left+(epoch(t)-t0)/span*(right-left);
  let s='<svg viewBox="0 0 '+W+' '+(bottom+30)+'" width="100%">';
  for(let i=0;i<5;i++){const f=i/4, xx=left+f*(right-left);
    const idx=Math.min(Math.round(f*(timeline.length-1)),timeline.length-1);
    const lab=(timeline[idx].ts||'').slice(11,19);
    s+='<line x1="'+xx+'" y1="6" x2="'+xx+'" y2="'+bottom+'" stroke="#eef0f3"/>'+
       '<text x="'+xx+'" y="'+(bottom+16)+'" text-anchor="middle" font-size="10" fill="#7a8494">'+lab+'</text>';}
  cs.forEach((chain,idx)=>{const y=8+idx*L;
    s+='<text x="'+(left-10)+'" y="'+(y+L-6)+'" text-anchor="end" font-size="11" font-family="ui-monospace,Menlo,monospace">'+chain+'</text>';
    for(const [a,b,st] of segments(timeline,chain)){ const x1=xAt(a), x2=(b&&b!==a)?xAt(b):right;
      s+='<rect x="'+x1.toFixed(1)+'" y="'+y+'" width="'+Math.max(x2-x1,1).toFixed(1)+'" height="'+(L-3)+'" rx="2" fill="'+(PALETTE[st]||PALETTE.IDLE)+'"><title>'+(a||'').slice(11,19)+' \u2192 '+(b||'').slice(11,19)+' '+st+'</title></rect>'; }});
  s+='</svg>'; host.innerHTML=s; }
function drawSignals(d){ const tb=document.getElementById('ctl-rows');
  if(!tb||!d.signals) return;
  tb.innerHTML=Object.entries(d.signals).map(function(e){const n=e[0], r=e[1];
    const cls=r.state==='OK'?'pass':(r.state==='ALARM'?'fail':'skip');
    const err=(r.error===null||r.error===undefined)?'':((r.error>0?'+':'')+r.error);
    return '<tr><td class="mono">'+n+'</td><td>'+r.reference+'</td><td><b>'+r.value+'</b> <span class="muted">'+(r.unit||'')+'</span></td><td>'+err+'</td><td><span class="pill '+cls+'">'+r.state+'</span></td></tr>';}).join(''); }
const badge=document.getElementById('live-badge');
function paint(d){ if(badge){badge.textContent=d.stale?'stale':'live';badge.style.color=d.stale?'var(--warn)':'var(--ok)';}
  if(d.overall){const p=document.querySelector('header .pill');p.textContent=d.overall;p.className='pill '+(d.overall==='OK'?'pass':(d.overall==='ALARM'?'fail':'skip'));}
  drawSignals(d); if(d.timeline) drawTimeline(d.timeline); }
const poll=async()=>{try{const r=await fetch('/api/status',{cache:'no-store'});if(r.ok)paint(await r.json());}
  catch(e){if(badge){badge.textContent='snapshot';badge.style.color='var(--mut)';}}};
if(location.protocol.startsWith('http')){poll();setInterval(poll,3000);}
</script>
"""


def build() -> str:
    status = _load(STATUS / "current.json", {}) or {}
    timeline = _load(STATUS / "timeline.json", []) or []
    pipeline = _load(PIPELINE, {}) or {}

    overall = status.get("overall", "—")
    badge = {"OK": "pass", "ALARM": "fail"}.get(overall, "skip")
    sampled = str(status.get("ts", ""))[:19].replace("T", " ")
    live = status.get("live_run", False)

    script = SCRIPT.replace("__PALETTE__", PALETTE_JS).replace(
        "__TIMELINE__", json.dumps(timeline[-200:]))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eidos pipeline — monitor</title>
<style>
:root{{--fg:#1c2530;--mut:#6b7683;--rule:#e4e8ee;--card:#ffffff;--bg:#f5f7fa;
  --acc:#4c72b0;--ok:#55a868;--bad:#c44e52;--warn:#dd8452}}
*{{box-sizing:border-box}}
body{{margin:0;font:14px/1.55 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  color:var(--fg);background:var(--bg)}}
header{{background:var(--card);border-bottom:1px solid var(--rule);padding:14px 22px;
  position:sticky;top:0;z-index:5;display:flex;align-items:baseline;gap:18px;flex-wrap:wrap}}
header h1{{font-size:17px;margin:0;font-weight:650;letter-spacing:.01em}}
header .sub{{color:var(--mut);font-size:12.5px}}
.pill{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;
  font-weight:600;letter-spacing:.05em}}
.pill.pass{{background:#e5f3e9;color:#2f6e44}}.pill.fail{{background:#fbe9ea;color:#8e2f34}}
.pill.skip{{background:#eef0f3;color:#5a6672}}
main{{display:grid;grid-template-columns:repeat(12,1fr);gap:16px;padding:18px 22px;max-width:1280px;margin:0 auto}}
.card{{background:var(--card);border:1px solid var(--rule);border-radius:10px;
  padding:16px 18px;box-shadow:0 1px 2px rgba(16,24,40,.04)}}
.card h2{{font-size:13px;margin:0 0 10px;font-weight:650;letter-spacing:.04em;
  text-transform:uppercase;color:var(--mut)}}
.w12{{grid-column:span 12}}.w8{{grid-column:span 8}}.w4{{grid-column:span 4}}
.w6{{grid-column:span 6}}
.muted{{color:var(--mut);font-size:12px}}
.mono{{font-family:ui-monospace,Menlo,monospace;font-size:12px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--mut);
  margin:10px 0 0}}
.lg{{display:flex;align-items:center;gap:6px}}
.lg i{{width:12px;height:12px;border-radius:2px;display:inline-block}}
table.ctl{{width:100%;border-collapse:collapse;font-size:12.5px}}
table.ctl th{{text-align:left;font-size:10.5px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--mut);padding:5px 8px;border-bottom:1px solid var(--rule)}}
table.ctl td{{padding:6px 8px;border-bottom:1px solid var(--rule)}}
@media (max-width:980px){{.w8,.w4,.w6{{grid-column:span 12}}}}
</style></head>
<body>
<header>
  <h1>Eidos pipeline</h1>
  <span class="pill {badge}">{html.escape(overall)}</span>
  <span class="sub">sampled {sampled} · {status.get('samples', 0)} samples · {'run in progress' if live else 'idle'}</span>
  <span class="sub" id="live-badge">snapshot</span>
</header>
<main>
  <section class="card w4"><h2>State machine</h2>{fsm_svg()}
    <p class="muted">The monitor enforces these edges: a chain cannot jump from FAIL to
    PASS without passing through RUNNING, and any unrefreshed state decays to STALE.</p></section>
  <section class="card w8"><h2>Chain timeline — discrete states over time</h2>
    <div id="gantt">{gantt_svg(timeline)}</div>{legend()}</section>
  <section class="card w8"><h2>Coupling — structure</h2>{coupling_panel(pipeline)}</section>
  <section class="card w4"><h2>Control loop</h2>{signals_table(status)}</section>
  <section class="card w12"><h2>Transitions (edge-triggered)</h2>{alarms_table(status.get('alarms') or [])}</section>
</main>
{script}
</body></html>"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}: {len(build()) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
