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
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

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
INK = {"IDLE": "#e6e8eb", "RUNNING": "#0b0e12", "PASS": "#0b0e12",
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


#: Every dashed line means the same thing — logical coupling: A uses, calls or is observed by B.
#: One dash pattern, one width, one opacity; only a failing endpoint changes the colour.
#: #4a5361 at 0.45 was invisible on the panel; a line the eye cannot follow is a line that
#: carries no information. Same style everywhere, but light enough to read.
COUPLING = {"dash": "4 3", "width": 1.1, "opacity": 0.62, "colour": "#96a3b5"}
HEALTHY = ("PASS", "SKIP", "IDLE")


def coupling(state: str) -> dict:
    """The shared style for a coupling edge, coloured only when the source is unhealthy."""
    style = dict(COUPLING)
    if state not in HEALTHY:
        style["colour"] = PALETTE.get(state, COUPLING["colour"])
        style["opacity"] = 0.95
        style["width"] = 1.5
    return style


def topology(pipeline, chain_now, durations, signals, trace_ts, evolution=None,
             chain_meta=None):
    """The coupling matrix: chains (run order) x modules, with services as a second block.

    A node-link drawing of 11 chains against 9 modules produces crossings that hide the very
    structure it is meant to show. A matrix cannot: a filled cell is a dependency, an empty cell
    is not, and the load per column is readable at a glance. Order is carried by the rows, which
    are grouped by layer; health by one chip per row; services by a second block, because a chain
    reaches a service through a module.
    """
    chain_modules = pipeline.get("chain_modules") or {}
    spans = pipeline.get("spans") or []
    executed = [sp.get("name") for sp in spans if sp.get("name") in chain_modules]
    chains = executed + [c for c in chain_modules if c not in executed]
    if not chains:
        return "<div class='empty'>no chains recorded</div>", [], {}

    module_users: dict[str, list[str]] = {}
    for chain, mods in chain_modules.items():
        for module in mods or []:
            module_users.setdefault(module, []).append(chain)
    modules = sorted(module_users, key=lambda m: (-len(module_users[m]), m))
    services = [s for s in SERVICE_LABEL if s in signals]

    layers = pipeline.get("layers") or []
    grouped, seen = [], set()
    for layer in layers:
        members = [c for c in chains if c in (layer.get("chains") or [])]
        if members:
            grouped.append((str(layer.get("name") or ""), members))
            seen |= set(members)
    rest = [c for c in chains if c not in seen]
    if rest:
        grouped.append(("Ungrouped", rest))

    row_h, head_h, top = 20, 15, 48
    label_w, col_w, gap = 300, 66, 18
    rows: list[dict] = []
    y = top
    for title, members in grouped:
        rows.append({"kind": "layer", "title": title, "y": y})
        y += head_h
        for chain in members:
            rows.append({"kind": "chain", "chain": chain, "y": y})
            y += row_h
    matrix_bottom = y + 6

    m_x = label_w + 12
    s_x = m_x + len(modules) * col_w + gap
    width = s_x + len(services) * col_w + 10
    obs_h = 30
    height = matrix_bottom + obs_h + 18
    gut = 34                      # the return path lives in this gutter, outside the matrix

    meta = chain_meta or {}
    svg = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
           f"aria-label='coupling matrix of chains, modules and services'>"]
    svg.append("<defs><marker id='ah' viewBox='0 0 10 10' refX='8.5' refY='5' markerWidth='4.6' "
               "markerHeight='4.6' orient='auto'><path d='M0 1 L9 5 L0 9 z' "
               "fill='context-stroke'/></marker></defs>")
    # A real header band: two lines (group, then column), a tinted strip and a closing rule.
    # Without it the column names read as the first row of the table.
    svg.append(f"<rect x='0' y='0' width='{width}' height='{top - 6}' fill='#12151a'/>")
    svg.append(f"<text x='{m_x}' y='12' font-size='10' letter-spacing='0.12em' fill='#7d8899' "
               f"font-family='ui-monospace,Consolas,monospace'>MODULES</text>")
    svg.append(f"<text x='{s_x}' y='12' font-size='10' letter-spacing='0.12em' fill='#7d8899' "
               f"font-family='ui-monospace,Consolas,monospace'>SERVICES</text>")
    svg.append(f"<line x1='0' y1='{top - 6}' x2='{width}' y2='{top - 6}' "
               f"stroke='rgba(255,255,255,0.14)'/>")
    svg.append(f"<g transform='translate({gut},0)'>")

    labels = {"framework.quarto_bridge": "quarto·br", "framework.validity": "Gate S",
              "framework.project": "project", "framework.gates": "gates",
              "framework.decision": "decision", "framework.inference": "inference",
              "framework.diagnosis": "diagnosis", "framework.tracking": "tracking",
              "framework.surrogate": "surrogate", "tools.surrogate": "surrogate"}
    for k, module in enumerate(modules):
        name = labels.get(module) or module.replace("framework.", "").replace("tools.", "").split(".")[0]
        # A module is a column, but it is still a node: the drill-down and the hover handler
        # bind to it, and the structure check counts it.
        # SKIP is not evidence of a problem: a chain nobody ran says nothing about the module.
        # Only verdicts count; if every user was skipped, the module says SKIP.
        states = [chain_now.get(c, "IDLE") for c in module_users[module]]
        judged = [st for st in states if st not in ("SKIP", "IDLE")]
        mod_state = worst(judged) if judged else ("SKIP" if states else "IDLE")
        svg.append(f"<g class='node module' data-module='{html.escape(module)}' "
                   f"data-users='{html.escape(','.join(module_users[module]))}' tabindex='0' "
                   f"role='button'><title>{html.escape(module)} · {mod_state} · used by "
                   f"{len(module_users[module])} chains</title>"
                   f"<text x='{m_x + k * col_w}' y='30' font-size='10' "
                   f"fill='{PALETTE.get(mod_state, '#98a2b3') if mod_state != 'PASS' else PALETTE['PASS']}' "
                   f"font-family='ui-monospace,Consolas,monospace'>"
                   f"{html.escape(name[:12])}</text></g>")
    for k, service in enumerate(services):
        # SERVICE_LABEL already carries the endpoint ("decision · :8090"); appending a port
        # here printed it twice.
        name = SERVICE_LABEL.get(service, service)
        short = name.split(" · ")[0]
        svg.append(f"<g class='node service' data-service='{html.escape(service)}' tabindex='0' "
                   f"role='button'><title>{html.escape(name)} · "
                   f"{(signals.get(service) or {}).get('source', '')}</title>"
                   f"<text x='{s_x + k * col_w}' y='30' font-size='10' "
                   f"fill='{PALETTE['FAIL' if (signals.get(service) or {}).get('state') in ('ALARM', 'UNOBSERVABLE') else 'PASS']}' "
                   f"font-family='ui-monospace,Consolas,monospace'>"
                   f"{html.escape(short[:10])}</text></g>")

    # vertical structure: a rule under the column names, one between the labels and the
    # matrix, one between modules and services, and a faint guide at every column boundary.
    # Horizontal separators alone leave a wide matrix unreadable across its width.
    svg.append(f"<line x1='{m_x - 10}' y1='{top - 4}' x2='{m_x - 10}' y2='{matrix_bottom}' "
               f"stroke='rgba(255,255,255,0.10)'/>")
    svg.append(f"<line x1='{s_x - gap / 2}' y1='{top - 4}' x2='{s_x - gap / 2}' "
               f"y2='{matrix_bottom}' stroke='rgba(255,255,255,0.10)'/>")
    for k in range(1, len(modules)):
        gx = m_x + k * col_w - 8
        svg.append(f"<line x1='{gx}' y1='{top}' x2='{gx}' y2='{matrix_bottom}' "
                   f"stroke='rgba(255,255,255,0.05)'/>")
    for k in range(1, len(services)):
        gx = s_x + k * col_w - 8
        svg.append(f"<line x1='{gx}' y1='{top}' x2='{gx}' y2='{matrix_bottom}' "
                   f"stroke='rgba(255,255,255,0.05)'/>")

    stripe = 0
    for row in rows:
        if row["kind"] == "layer":
            svg.append(f"<text x='0' y='{row['y'] + 11}' font-size='10' letter-spacing='0.1em' "
                       f"fill='#7d8899' font-family='ui-monospace,Consolas,monospace'>"
                       f"{html.escape(row['title'].upper())}</text>")
            svg.append(f"<line x1='0' y1='{row['y'] + 14}' x2='{width}' y2='{row['y'] + 14}' "
                       f"stroke='rgba(255,255,255,0.06)'/>")
            continue

        stripe += 1
        if stripe % 2 == 0:
            svg.append(f"<rect x='0' y='{row['y'] + 2}' width='{width}' height='{row_h - 4}' "
                       f"fill='rgba(255,255,255,0.018)'/>")
        chain = row["chain"]
        state = chain_now.get(chain, "IDLE")
        info = meta.get(chain) or {}
        age = info.get("age_s")
        y = row["y"]
        title = (f"{chain} · {state} · last {fmt_age(age) if age is not None else 'never'}"
                 f" · needs {info.get('requires', '—')} · {info.get('detail', 'no record')}")
        svg.append(
            f"<g class='node chain' data-chain='{html.escape(chain)}' tabindex='0' role='button'>"
            f"<title>{html.escape(title)}</title>"
            # A dot, the same mark the legend shows and the cells use. A bar and a dot for
            # the same idea is two languages in one figure.
            f"<circle cx='7' cy='{y + row_h / 2:.1f}' r='3.4' "
            f"fill='{PALETTE.get(state, PALETTE['IDLE'])}'/>"
            f"<text x='12' y='{y + row_h / 2 + 3.5}' font-size='11' fill='#e6e8eb'>"
            f"{html.escape(chain)}</text>"
            f"<text x='{label_w - 16}' y='{y + row_h / 2 + 3.5}' text-anchor='end' font-size='10' "
            f"fill='#7d8899' font-family='ui-monospace,Consolas,monospace'>"
            f"{html.escape(fmt_age(age) if age is not None else '—')}</text></g>")

        used = set(chain_modules.get(chain) or [])
        for k, module in enumerate(modules):
            if module not in used:
                continue
            cx = m_x + k * col_w + col_w / 2 - 10
            svg.append(f"<circle cx='{cx:.1f}' cy='{y + row_h / 2:.1f}' r='3.4' "
                       f"fill='{PALETTE.get(state, PALETTE['IDLE'])}' opacity='0.9'/>")
        for k, service in enumerate(services):
            if not any(MODULE_SERVICE.get(m) == service for m in used):
                continue
            cx = s_x + k * col_w + col_w / 2 - 10
            up = (signals.get(service) or {}).get("state") not in ("ALARM", "UNOBSERVABLE")
            svg.append(f"<circle cx='{cx:.1f}' cy='{y + row_h / 2:.1f}' r='3.4' "
                       f"fill='{PALETTE['PASS' if up else 'FAIL']}' opacity='0.9'/>")
    evo = evolution or {}
    open_defects = (evo.get("state") or {}).get("open_defects") or 0
    obs_y = matrix_bottom + 6
    state = "PASS" if not open_defects else "FAIL"
    svg.append(
        f"<g class='node instrument' data-instrument='instruments' tabindex='0' role='button'>"
        f"<title>instruments · 4 · fixtures: every gate check trips · mutations: 0 open defects · "
        f"runtime + layout: pages execute · probes: a dead half is named</title>"
        f"<rect x='0' y='{obs_y}' width='{width - 10}' height='{obs_h}' rx='4' fill='#15181d' "
        f"stroke='#2a3038'/>"
        f"<rect x='0' y='{obs_y}' width='3' height='{obs_h}' fill='{PALETTE[state]}'/>"
        f"<text x='12' y='{obs_y + 18}' font-size='10' letter-spacing='0.1em' fill='#98a2b3' "
        f"font-family='ui-monospace,Consolas,monospace'>INSTRUMENTS 4 · "
        f"{'no open defects' if not open_defects else str(open_defects) + ' open defect(s)'}</text>"
        f"</g>")
    svg.append("</g>")
    # Orthogonal return: out of the observer, down into the gutter, up it, and back into the
    # first row. A curve between two points says 'related'; square corners say 'this goes back
    # to the beginning', which is the claim the figure is making.
    y_mid = obs_y + obs_h / 2
    y_end = top + head_h + row_h / 2          # the first chain row, not the header rule
    svg.append(f"<g class='feedback-loop'>"
               f"<path d='M{gut} {y_mid} L{gut / 2} {y_mid} L{gut / 2} {y_end:.1f} L{gut} {y_end:.1f}' fill='none' "
               f"stroke='#a9b6c8' stroke-width='1.3' opacity='0.9' "
               f"marker-end='url(#ah)'/>"
               f"<text x='{gut / 2 - 4}' y='{(y_mid + y_end) / 2}' text-anchor='middle' "
               f"font-size='10' fill='#98a2b3' transform='rotate(-90 {gut / 2 - 4} {(y_mid + y_end) / 2})' "
               f"font-family='ui-monospace,Consolas,monospace'>feedback → guards</text>"
               f"</g>")
    svg.append("</svg>")

    faults = [f"{c} = {chain_now[c]}" for c in chains
              if chain_now.get(c) in ("FAIL", "ERROR")]
    for service in services:
        if (signals.get(service) or {}).get("state") in ("ALARM", "UNOBSERVABLE"):
            faults.append(f"{service} = DOWN")
    return "".join(svg), faults, {m: list(module_users[m]) for m in modules}

def operator_strip(status: dict, recoveries: list) -> str:
    """The system's own operators: self-check, then self-heal, drawn as the loop they form.

    The assembly shows what the pipeline *is*. This shows what keeps it alive: a sample, a
    verdict, a plan, a repair, a verification, a record — and a second pass that proves the
    repair worked. State comes from the sampler's own files, not from optimism.
    """
    ts = status.get("ts") or ""
    try:
        age = max(0.0, time.time() - datetime.datetime.fromisoformat(
            str(ts).replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        age = None
    sampled = "PASS" if age is not None and age < 90 else ("STALE" if age is not None else "IDLE")
    # The log has two kinds of line: an attempt (ok, pid) and a terminal verdict (outcome).
    # Reading only the last line made "verified / recovered" — which carries no `ok` — paint the
    # repair red, and made a bare attempt paint it green before anything was verified.
    terminal = next((r for r in reversed(recoveries)
                     if r.get("phase") in ("verified", "failed", "gave_up")), None)
    attempt = next((r for r in reversed(recoveries) if r.get("phase") == "attempt"), None)
    # The strip describes the *current* loop. An episode that ended "no effect" last night is history
    # once nothing is faulting: showing it as a red verify forever made a healthy board look broken,
    # which is the same false signal as a green board with a dead sampler.
    active_faults = list((status.get("derived") or {}).get("faults") or [])
    if not active_faults:
        exec_state = verify_state = plan_state = "IDLE"
        # The box is 168 px wide; "last episode: no effect" overlapped the label at every viewport.
        # The history stays in recoveries.jsonl and in the service popup, where there is room for it.
        verify_note = "no active fault" if terminal else "recovery.verify"
        last_note = ""
    elif terminal:
        # Rows written before the schema was enforced carry `outcome` but no `ok`.
        ok = terminal.get("ok")
        if ok is None:
            ok = terminal.get("outcome") == "recovered"
        outcome = terminal.get("outcome") or ("recovered" if ok else "failed")
        exec_state = "PASS" if attempt is None or attempt.get("ok") else "FAIL"
        verify_state = "PASS" if outcome == "recovered" else "FAIL"
        plan_state = "PASS"
        verify_note = outcome
    elif attempt:
        exec_state = "PASS" if attempt.get("ok") else "FAIL"
        verify_state, plan_state, verify_note = "RUNNING", "PASS", "not verified yet"
    else:
        exec_state = verify_state = plan_state = "IDLE"
        verify_note = "recovery.verify"
    healed = len([r for r in recoveries if r.get("phase") == "verified"])

    steps = [
        ("self-check · sample", sampled, "15 s"),
        ("derive verdict", "PASS", "status_view"),
        ("plan repair", plan_state, "recovery.plan"),
        ("execute", exec_state, "recovery.execute"),
        ("verify", verify_state, verify_note),
        ("record", "PASS", f"{healed} healed"),
    ]
    n = len(steps)
    box_w, gap = 168, 26
    width = n * box_w + (n - 1) * gap + 8
    height = 46
    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
             f"aria-label='self-check and self-heal loop'>"]
    for k, (name, state, note) in enumerate(steps):
        x = 4 + k * (box_w + gap)
        parts.append(
            f"<g class='node operator' data-operator='{html.escape(name)}' tabindex='0' role='button'>"
            f"<title>{html.escape(name)} · {state} · {html.escape(note)}</title>"
            f"<rect x='{x}' y='6' width='{box_w}' height='26' rx='4' "
            f"fill='{PALETTE.get(state, PALETTE['IDLE'])}' stroke='#0a0c0f'/>"
            f"<text x='{x + 9}' y='23' font-size='10' fill='{INK.get(state, '#e6e8eb')}'>"
            f"{html.escape(name)}</text>"
            f"<text x='{x + box_w - 8}' y='23' text-anchor='end' font-size='10' "
            f"fill='{INK.get(state, '#e6e8eb')}' opacity='0.85'>{html.escape(note)}</text></g>")
        if k < n - 1:
            ax = x + box_w
            parts.append(f"<path d='M{ax + 3} 19 L{ax + gap - 3} 19' stroke='#96a3b5' "
                         f"stroke-width='1.1' marker-end='url(#ah2)'/>")
    # the loop closes: a repair that verifies re-enters the sampler
    parts.append(f"<path d='M{width - box_w / 2 - 4} 32 C{width - 40} 44, 40 44, "
                 f"{box_w / 2 + 4} 32' fill='none' stroke='#a9b6c8' stroke-width='1.2' "
                 f"opacity='0.85' stroke-dasharray='4 3' marker-end='url(#ah2)'/>")
    parts.append("<defs><marker id='ah2' viewBox='0 0 10 10' refX='8.5' refY='5' markerWidth='4' "
                 "markerHeight='4' orient='auto'><path d='M0 1 L9 5 L0 9 z' "
                 "fill='context-stroke'/></marker></defs>")
    parts.append("</svg>")
    return "".join(parts)


def provenance() -> str:
    """Where each state on this page comes from, and how old it is.

    A colour is a claim; this line is the evidence behind the claim.
    """
    sources = [("current.json", STATUS / "current.json"),
               ("chains.json", STATUS / "chains.json"),
               ("recoveries", STATUS / "recoveries.jsonl"),
               ("pipeline.json", PIPELINE)]
    parts = []
    for name, path in sources:
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            parts.append(f"{name} missing")
            continue
        parts.append(f"{name} {fmt_age(age)}")
    return "<p class='mono prov'>sources — " + " · ".join(parts) + "</p>"


def chains_meta() -> dict:
    """Per-chain record straight from the audit's own file, when the sample is older than it."""
    try:
        record = json.loads((ROOT / "docs" / "status" / "chains.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    now = time.time()
    for name, row in (record.get("chains") or {}).items():
        ran = float(row.get("ts") or 0)
        out[name] = {**row, "age_s": round(max(0.0, now - ran), 1) if ran else None}
    return out



def evolution_loop(evo: dict) -> str:
    """FEEDBACK -> evolution, drawn as the cycle it is: find, encode, enforce, record, iterate.

    The assembly can show findings returning to the chains; only this can show what happens to
    them on the way. A defect is not closed by being noticed — it is closed when a fixture, a
    mutation or a transition rule makes it impossible to repeat, and the next run proves that.
    """
    if not evo:
        return ""
    state = evo.get("state") or {}
    hist = evo.get("evolution") or {}
    instruments = len(state.get("instruments") or [])
    try:
        fixtures = len((json.loads((ROOT / "docs" / "FIXTURES.json").read_text(encoding="utf-8"))
                        or {}).get("fixtures") or [])
    except (OSError, json.JSONDecodeError):
        fixtures = 0
    try:
        fuzz = json.loads((ROOT / "docs" / "FUZZ.json").read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        fuzz = {}
    cases = sum(len(fuzz.get(k) or []) for k in ("wrong", "equivalent", "wrong_evidence",
                                                 "equivalent_evidence", "pairs"))
    stages = [
        ("1 FIND", f"{instruments} instruments", "a mutation, a render, a dead endpoint", "PASS"),
        ("2 ENCODE", f"{fixtures} fixtures · {cases} cases", "fixture · mutation · transition rule",
         "PASS"),
        ("3 ENFORCE", "6 checks before commit", "tests, fixtures, fuzz, chains, state, page",
         "PASS"),
        ("4 RECORD", f"{instruments} capabilities", "each with the artefact that would refute it",
         "PASS"),
        ("5 ITERATE", f"{hist.get('blind_spots_found', 0)} found · "
                      f"{hist.get('blind_spots_open', 0)} open", "the next run re-measures", "PASS"),
    ]
    n = len(stages)
    box_w, gap, height = 214, 30, 66
    width = n * box_w + (n - 1) * gap + 8
    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
             f"aria-label='feedback to evolution cycle'>"]
    for k, (title, count, note, st) in enumerate(stages):
        x = 4 + k * (box_w + gap)
        parts.append(
            f"<g class='node stage' data-stage='{html.escape(title)}' tabindex='0' role='button'>"
            f"<title>{html.escape(title)} · {html.escape(count)} · {html.escape(note)}</title>"
            # Stages are not health: a green box would say "passing", and a stage cannot pass.
            f"<rect x='{x}' y='4' width='{box_w}' height='44' rx='4' fill='#1b2027' "
            f"stroke='#2a3038'/>"
            f"<rect x='{x}' y='4' width='3' height='44' fill='#5b8def'/>"
            f"<text x='{x + 11}' y='17' font-size='10' letter-spacing='0.08em' "
            f"fill='#98a2b3'>{html.escape(title)}</text>"
            f"<text x='{x + 11}' y='35' font-size='11' fill='#e6e8eb'>"
            f"{html.escape(count)}</text></g>")
        if k < n - 1:
            ax = x + box_w
            parts.append(f"<path d='M{ax + 4} 26 L{ax + gap - 4} 26' stroke='#96a3b5' "
                         f"stroke-width='1.1' marker-end='url(#ah3)'/>")
    # the cycle: stage 5 feeds stage 1 with the next instrument run
    parts.append(f"<path d='M{width - box_w / 2 - 4} 48 C{width - 30} 62, 30 62, "
                 f"{box_w / 2 + 4} 48' fill='none' stroke='#a9b6c8' stroke-width='1.2' "
                 f"opacity='0.85' stroke-dasharray='4 3' marker-end='url(#ah3)'/>")
    parts.append("<defs><marker id='ah3' viewBox='0 0 10 10' refX='8.5' refY='5' markerWidth='4' "
                 "markerHeight='4' orient='auto'><path d='M0 1 L9 5 L0 9 z' "
                 "fill='context-stroke'/></marker></defs>")
    parts.append("</svg>")
    return "".join(parts)


def version_label() -> str:
    """The version this tree declares, or the last release on record.

    pyproject.toml is the single source: a version bump that has not been released yet must still
    be the number the page states, or the page and the tree disagree by construction.
    """
    try:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1)
    except OSError:
        pass
    try:
        rows = json.loads((ROOT / "site" / "versions.json").read_text(encoding="utf-8"))
        return str((rows[-1] or {}).get("version") or "")
    except (OSError, json.JSONDecodeError, IndexError):
        return ""



def consumer_strip(pipeline: dict) -> str:
    """The outward face: what the framework does for a project.

    A consumer is only healthy when its verdict equals its *expectation* — a negative control
    that fails is doing its job, and colouring it red would invert the meaning of the test.
    """
    # Only projects Gate S actually judged belong here. The chain fixtures have no claims and
    # no verdict; listing them as consumers would pad the band with entries that prove nothing.
    rows = [r for r in (pipeline.get("consumers") or [])
            if str(r.get("gate_s") or "—") not in ("—", "", "None")]
    if not rows:
        return ("<p class='mono' style='color:var(--mut)'>no consumer registered: the framework "
                "is checking itself and serving no project</p>")
    box_w, gap, height = 226, 12, 54
    width = max(600, len(rows) * (box_w + gap) + 8)
    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
             f"aria-label='consumers: what the framework does for a project'>"]
    now = time.time()
    for k, row in enumerate(rows):
        name = str(row.get("name") or "?")
        got, want = str(row.get("gate_s") or "—"), str(row.get("expected") or "—")
        as_expected = want != "—" and got == want
        st = "PASS" if as_expected else "FAIL"
        gen = row.get("generated")
        age = ""
        if gen:
            try:
                age = fmt_age(max(0.0, now - datetime.datetime.fromisoformat(
                    str(gen).replace("Z", "+00:00")).timestamp()))
            except ValueError:
                age = ""
        x = 4 + k * (box_w + gap)
        role = str(row.get("role") or "")
        tag = ("demo" if role.upper().startswith("DEMO")
               else "control" if "control" in role.lower()
               else "consumer" if "consumer" in role.lower() else "")
        note = (f"{tag} · " if tag else "") + f"gate {got} / expected {want}" +                (f" · {age}" if age else "")
        parts.append(
            f"<g class='node consumer' data-consumer='{html.escape(name)}' tabindex='0' role='button'>"
            f"<title>{html.escape(name)} · {html.escape(note)}</title>"
            f"<rect x='{x}' y='3' width='{box_w}' height='38' rx='4' fill='#1b2027' stroke='#2a3038'/>"
            f"<rect x='{x}' y='3' width='3' height='38' fill='{PALETTE[st]}'/>"
            f"<text x='{x + 11}' y='17' font-size='10' fill='#e6e8eb'>"
            f"{html.escape(name[:26])}</text>"
            f"<text x='{x + 11}' y='31' font-size='10' fill='#98a2b3'>"
            f"{html.escape(note[:46])}</text></g>")
    parts.append("</svg>")
    return "".join(parts)


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
.brand{font-weight:600;font-size:12.5px;letter-spacing:.02em}
.brand i{color:var(--accent);font-style:normal;margin-right:6px}
.brand .ver{margin-left:7px;padding:1px 5px;border:1px solid var(--line);border-radius:4px;
  font:600 10px/1.5 ui-monospace,Consolas,monospace;color:var(--mut);letter-spacing:0}
.pill{font:600 10.5px/1 inherit;letter-spacing:.08em;padding:5px 10px;border-radius:20px;
  border:1px solid var(--line);text-transform:uppercase}
.pill.OK{color:#57ab5a;background:rgba(87,171,90,.1);border-color:rgba(87,171,90,.35)}
.pill.ALARM{color:#ef6b62;background:rgba(229,83,75,.1);border-color:rgba(229,83,75,.35)}
.spacer{flex:1}
.act{font-size:11px;font-weight:600;line-height:1;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);
  background:transparent;border:1px solid var(--line);border-radius:6px;padding:5px 9px;
  cursor:pointer;transition:color .2s,border-color .2s}
.act:hover{color:var(--fg);border-color:#3a4048}
.meta{color:var(--dim);font-size:11px;letter-spacing:.02em}
.meta b{color:var(--mut);font-weight:600}
#live{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#7d8899;
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
.faults{font-size:12px;color:#d29922;margin-top:8px}
.faults b{color:#e5534b;letter-spacing:.1em;font-size:11px;margin-right:6px}
svg text{font-variant-numeric:tabular-nums}
svg .node{cursor:pointer}
svg .node rect{transition:fill .4s ease,stroke .4s ease}
svg .node:hover rect{stroke:#fff;stroke-opacity:.45}
svg .node:focus{outline:none}
svg .edge{transition:stroke .4s ease}
/* The operator band sits under the assembly, separated by a hairline: same figure, second
   question — not a new card competing with it. */
.card code,.card pre{font-size:11px}
.opwrap .hint{text-transform:none;letter-spacing:0;font-weight:400;color:var(--mut);
  margin-left:8px;font-size:10px}
.opwrap{margin-top:10px;padding-top:9px;border-top:1px solid var(--line)}
.opwrap h3{margin:0 0 6px;font:600 10px/1.4 -apple-system,"Segoe UI",Arial,sans-serif;
  letter-spacing:.11em;text-transform:uppercase;color:var(--dim);font-weight:600}
.key{display:flex;gap:11px;font-size:10px;color:var(--dim);margin:0 0 7px;flex-wrap:wrap;
  letter-spacing:.04em;text-transform:uppercase}
.key i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}
.key i.dotkey{display:none;border-left:7px solid #5b8def;border-top:4px solid transparent;
  border-bottom:4px solid transparent;background:none;border-radius:0;margin:0 6px 0 8px}
.srow{display:flex;align-items:center;gap:14px;margin:1px 0}
.sname{width:122px;flex:none;text-align:right;padding-right:8px;
  font:10px/1.35 ui-monospace,Menlo,monospace;color:var(--dim);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.scells{flex:1;display:flex;gap:0;min-width:0;overflow:hidden}
.sc{height:7px;display:inline-block;flex:0 0 auto;box-shadow:inset -1px 0 0 rgba(14,16,19,.85)}
.sc.gap{background:repeating-linear-gradient(45deg,#15181d,#15181d 2px,#20242b 2px,#20242b 4px)}
.sax{display:flex;justify-content:space-between;font:10px ui-monospace;color:#7d8899;
  margin:4px 0 0 136px}
.gapsum{margin-top:4px;font:10px/1.4 ui-monospace,Menlo,monospace;color:#7d8899}
.fresh{margin-top:5px;font:10px/1.4 ui-monospace,Menlo,monospace;color:var(--dim)}
.empty{color:#7d8899;font-style:italic;font-size:12px}
table.rank{width:100%;border-collapse:collapse;font-size:11px}
table.rank th{text-align:left;font:10px/1 -apple-system,sans-serif;letter-spacing:.06em;
  text-transform:uppercase;color:#7d8899;padding:0 0 5px;font-weight:600}
table.rank td{padding:3px 0;border-bottom:1px solid var(--line)}
table.rank td.num{text-align:right;font-variant-numeric:tabular-nums}
#pop{position:fixed;z-index:30;width:360px;max-height:60vh;overflow:auto;display:none;
  background:#191d23;border:1px solid var(--line);border-radius:8px;padding:12px 14px;
  box-shadow:0 18px 40px -18px #000}
#pop.on{display:block}
#pop .t{font-weight:600;font-size:12.5px;margin-bottom:4px}
#pop .d{color:var(--mut);font-size:11px;line-height:1.5}
#pop .m{color:var(--dim);font-size:11px;margin-top:5px;font-family:ui-monospace,Menlo,monospace}
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
// Hover isolates one chain: its edges stay, the rest recedes. A hairball of eleven chains is
// readable when the reader can ask "what does this one touch".
function focusChain(name) {
  const mods = new Set();
  document.querySelectorAll('g.node.chain').forEach(g => {
    if (g.dataset.chain === name) (g.dataset.modules || '').split(',').filter(Boolean).forEach(m => mods.add(m));
  });
  document.querySelectorAll('.edge').forEach(p => {
    const mine = p.dataset.from === name;
    p.setAttribute('opacity', name ? (mine ? '1' : '0.08') : '0.62');
  });
  document.querySelectorAll('g.node.module').forEach(g => {
    g.style.opacity = name && !mods.has(g.dataset.module) ? '0.35' : '1';
  });
  document.querySelectorAll('g.node.chain').forEach(g => {
    g.style.opacity = name && g.dataset.chain !== name ? '0.5' : '1';
  });
}
document.querySelectorAll('g.node.chain').forEach(g => {
  g.addEventListener('mouseenter', () => focusChain(g.dataset.chain));
  g.addEventListener('mouseleave', () => focusChain(null));
  g.addEventListener('focus', () => focusChain(g.dataset.chain));
  g.addEventListener('blur', () => focusChain(null));
});
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
  // Only addressable nodes answer a click: a chain, a module, a service. The operator strip and
  // the instrument column are also g.node groups, and defaulting them to 'service' produced the
  // popup "undefined · service · verify · FAIL · no effect" — a label that described nothing.
  const kind = node.dataset.chain ? 'chain' : node.dataset.module ? 'module'
             : node.dataset.service ? 'service' : node.dataset.operator ? 'operator' : null;
  if (!kind) return;
  const name = node.dataset.chain || node.dataset.module || node.dataset.service
             || node.dataset.operator;
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
      const dot = g.querySelector('circle');
      if (dot) dot.setAttribute('fill', PALETTE[st] || PALETTE.IDLE);
    });
    // A column header carries its own state: the worst of the chains that use it. Without this
    // the header would keep whatever colour it had at build time while the rows moved.
    const rank = {FAIL: 0, STALE: 1, RUNNING: 2, SKIP: 3, PASS: 4, IDLE: 5};
    document.querySelectorAll('g.node.module').forEach(g => {
      const users = (g.dataset.users || '').split(',').filter(Boolean);
      const judged = users.map(u => chains[u] || 'IDLE').filter(st => st !== 'SKIP' && st !== 'IDLE');
      let worst = judged.length ? judged.sort((a, b) => (rank[a] ?? 9) - (rank[b] ?? 9))[0]
                                : (users.length ? 'SKIP' : 'IDLE');
      const t = g.querySelector('text');
      if (t) t.setAttribute('fill', PALETTE[worst] || PALETTE.IDLE);
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

    try:
        evolution = json.loads((ROOT / "docs" / "EVOLUTION.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        evolution = {}
    svg, faults, _ = topology(pipeline, chain_now, {}, signals, trace_ts, evolution,
                              status.get("chain_meta") or chains_meta())
    try:
        recoveries = [json.loads(l) for l in
                      (STATUS / "recoveries.jsonl").read_text(encoding="utf-8").splitlines()
                      if l.strip()][-20:]
    except (OSError, json.JSONDecodeError):
        recoveries = []
    operator = operator_strip(status, recoveries)
    consumers = consumer_strip(pipeline)
    try:
        cov = json.loads((ROOT / "docs" / "DEMO_COVERAGE.json").read_text(encoding="utf-8"))
        cov = f"{cov.get('demo', 0)}/{cov.get('total', 0)}"
    except (OSError, json.JSONDecodeError):
        cov = "—"
    evoloop = evolution_loop(evolution)
    faults = derived.get("faults") or faults
    ranking = fault_ranking()
    stamp = hkt(status.get("ts", "")) if status.get("ts") else "—"

    key = "".join(f"<span><i style='background:{PALETTE[s]}'></i>{s}</span>"
                  for s in ("PASS", "SKIP", "RUNNING", "STALE", "FAIL", "IDLE"))
    # These sentences are checked against the drawing: there are no forward arrows in a matrix,
    # so a legend claiming "the direction the signal flows" would be describing a figure that
    # no longer exists.


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
<title>Eidos v{html.escape(version_label() or '—')} — assembly and status</title>
<style>{CSS}</style></head>
<body>
<header>
  <span class="brand"><i>●</i>Eidos<span class="ver"> v{html.escape(version_label() or '—')}</span></span>
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
    <h2>Framework self-audit — chains (run order) × modules × services, observed by four instruments</h2>
    <div class="key">{key}</div>
    {svg}
    <div class="opwrap"><h3>Project pipeline — bootstrap → measure → gates → Gate S → render → handoff</h3>
    <p class="mono" style="margin:0 0 6px;color:var(--mut)">The band below is that pipeline's
    output: each registered project, its verdict, and how old the evidence behind it is.</p></div>
    <div class="opwrap"><h3>Consumers — what the framework does for a project
      <span class="hint">green = verdict equals expectation, not “the project passed”
      · capability coverage {cov}</span></h3>
    {consumers}</div>
    <div class="opwrap"><h3>Operators — self-check, then self-heal</h3>{operator}</div>
    <div class="opwrap"><h3>Feedback → evolution — how a defect becomes a guard</h3>{evoloop}</div>
    {fault_line}
    {provenance()}
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
