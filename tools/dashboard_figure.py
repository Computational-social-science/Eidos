"""Publication-quality monitoring figure for the Eidos pipeline.

Rendered with matplotlib + scienceplots (the ``nature`` style), this is the scientific
surface for the pipeline: three panels drawn as a single figure —

    1. State machine — the six states and the transitions the monitor enforces.
    2. Swimlane — discrete state over wall-clock time, one lane per chain, coloured
       blocks per state (broken_barh), with a real time axis.
    3. Coupling — the import structure layered by dependency depth, arrows typed by
       module-scope (solid) vs in-function (dashed) import.

No JavaScript, no chart library, no network. The figure is regenerated from the watcher's
artefacts, so "near real-time" means: regenerate the PNG and it is current.

    python tools/dashboard_figure.py   # writes site/dashboard.png and site/dashboard.html
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import numpy as np  # noqa: E402
import scienceplots  # noqa: E402, F401  — registers the "science"/"nature" styles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import chain_states  # noqa: E402

STATUS = ROOT / "docs" / "status"
PIPELINE = ROOT / "docs" / "pipeline.json"
PNG = ROOT / "site" / "dashboard.png"
HTML = ROOT / "site" / "dashboard.html"

PALETTE = {
    "IDLE": "#ECECEC", "RUNNING": "#4C72B0", "PASS": "#55A868",
    "SKIP": "#8C8C8C", "FAIL": "#C44E52", "STALE": "#DD8452",
}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def epoch(ts: str) -> float:
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def draw_fsm(ax) -> None:
    pos = {"IDLE": (0, 1), "RUNNING": (1.6, 1.6), "PASS": (3.2, 1.6),
           "SKIP": (3.2, 1.0), "FAIL": (3.2, 0.4), "STALE": (1.6, 0.0)}
    edges = [("IDLE", "RUNNING"), ("RUNNING", "PASS"), ("RUNNING", "SKIP"),
             ("RUNNING", "FAIL"), ("PASS", "RUNNING"), ("SKIP", "RUNNING"),
             ("FAIL", "RUNNING"), ("PASS", "STALE"), ("SKIP", "STALE"),
             ("FAIL", "STALE"), ("IDLE", "STALE"), ("STALE", "RUNNING")]
    for src, dst in edges:
        ax.annotate("", xy=pos[dst], xytext=pos[src],
                    arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#444444",
                                    shrinkA=14, shrinkB=14,
                                    connectionstyle="arc3,rad=0.12"))
    for name, (x, y) in pos.items():
        fc = PALETTE[name] if name != "IDLE" else "#FFFFFF"
        ec = PALETTE[name] if name != "IDLE" else "#BBBBBB"
        ax.add_patch(mpatches.Circle((x, y), 0.34, fc=fc, ec=ec, lw=1.2, zorder=3))
        ax.text(x, y, name, ha="center", va="center", fontsize=6.5,
                color="#222222", zorder=4, weight="bold")
    ax.set_xlim(-0.6, 3.9)
    ax.set_ylim(-0.6, 2.2)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("State machine — transitions the monitor enforces", loc="left",
                 fontsize=9, pad=6)


def draw_swimlane(ax, timeline) -> None:
    rows = [r for r in timeline if r.get("ts")]
    if not rows:
        ax.text(0.5, 0.5, "no timeline recorded yet", ha="center", va="center")
        ax.set_xticks([]), ax.set_yticks([])
        return
    chains = sorted({n for r in rows for n in (r.get("states") or {})})
    t0 = epoch(rows[0]["ts"])
    t1 = epoch(rows[-1]["ts"])
    span = max(t1 - t0, 1.0)

    for index, chain in enumerate(chains):
        y = len(chains) - 1 - index
        # collapse runs of constant state into (start, duration)
        seg_start, seg_state = None, None
        for row in rows:
            state = (row.get("states") or {}).get(chain, "IDLE")
            ts = epoch(row["ts"])
            if seg_state is None:
                seg_start, seg_state = ts, state
            elif state != seg_state:
                ax.broken_barh([(seg_start, ts - seg_start)], (y - 0.4, 0.8),
                               facecolors=PALETTE[seg_state], edgecolor="none")
                seg_start, seg_state = ts, state
        ax.broken_barh([(seg_start, t1 - seg_start)], (y - 0.4, 0.8),
                       facecolors=PALETTE[seg_state], edgecolor="none")

    ax.set_yticks(range(len(chains)))
    ax.set_yticklabels(chains[::-1], fontsize=6.5, fontfamily="monospace")
    # x axis in wall-clock time
    ticks = np.linspace(t0, t1, 6)
    labels = [datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
              .strftime("%H:%M:%S") for t in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=6.5, rotation=0)
    ax.set_xlim(t0 - 0.02 * span, t1 + 0.02 * span)
    ax.set_title("Discrete state over time — one lane per chain", loc="left",
                 fontsize=9, pad=6)
    # legend
    handles = [mpatches.Rectangle((0, 0), 1, 1, color=PALETTE[s]) for s in chain_states.STATES]
    ax.legend(handles, list(chain_states.STATES), loc="upper right", fontsize=6,
              ncol=6, frameon=False, handlelength=1.0, handleheight=0.9)


def draw_coupling(ax, pipeline) -> None:
    coupling = pipeline.get("coupling") or {}
    nodes = coupling.get("nodes") or []
    edges = coupling.get("edges") or []
    levels = coupling.get("levels") or {}
    if not nodes:
        ax.text(0.5, 0.5, "no coupling data", ha="center", va="center")
        ax.set_xticks([]), ax.set_yticks([])
        return
    columns = {}
    for node in nodes:
        columns.setdefault(levels.get(node, 0), []).append(node)
    for column in columns.values():
        column.sort()
    rows = max(len(c) for c in columns.values())
    pos = {}
    for level, column in columns.items():
        for index, node in enumerate(column):
            pos[node] = (level, rows - 1 - index - (rows - len(column)) / 2)
    for edge in edges:
        if edge["source"] in pos and edge["target"] in pos:
            (x1, y1), (x2, y2) = pos[edge["source"]], pos[edge["target"]]
            style = dict(arrowstyle="-|>", lw=0.7, color="#2F855A", shrinkA=5, shrinkB=5,
                         connectionstyle="arc3,rad=0.1")
            if edge["kind"] == "soft":
                style.update(linestyle="--", color="#8C8C8C")
            ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=style)
    for node, (x, y) in pos.items():
        ax.scatter([x], [y], s=26, c="#FFFFFF", edgecolors="#333333", lw=0.7, zorder=3)
        label = node.replace("framework.", "").replace("tools.", "")
        ax.text(x, y - 0.25, label, ha="center", va="top", fontsize=5.2,
                fontfamily="monospace")
    ax.set_xticks(sorted(columns))
    ax.set_xticklabels([f"layer {c}" for c in sorted(columns)], fontsize=6.5)
    ax.set_yticks([])
    ax.set_xlim(-0.6, max(columns) + 0.6)
    ax.set_title("Coupling — import structure layered by dependency depth", loc="left",
                 fontsize=9, pad=6)


def build_figure() -> None:
    status = load(STATUS / "current.json", {}) or {}
    timeline = load(STATUS / "timeline.json", []) or []
    pipeline = load(PIPELINE, {}) or {}

    plt.style.use(["science", "nature"])
    # The nature style enables usetex; we have no LaTeX on PATH (only TinyTeX's pdflatex).
    # No formula in this figure needs TeX, so mathtext is enough and keeps the same serif.
    plt.rcParams["text.usetex"] = False
    fig = plt.figure(figsize=(7.16, 8.2), dpi=400)
    gs = fig.add_gridspec(3, 1, height_ratios=[0.9, 1.7, 1.0], hspace=0.5)

    overall = status.get("overall", "—")
    sampled = str(status.get("ts", ""))[:19].replace("T", " ")
    fig.suptitle("Eidos pipeline — monitor", x=0.02, ha="left", fontsize=13, weight="bold")
    fig.text(0.02, 0.965, f"overall: {overall}    ·    sampled {sampled}    ·    "
             f"{status.get('samples', 0)} samples    ·    "
             f"{'run in progress' if status.get('live_run') else 'idle'}",
             fontsize=7, color="#555555")

    draw_fsm(fig.add_subplot(gs[0]))
    draw_swimlane(fig.add_subplot(gs[1]), timeline)
    draw_coupling(fig.add_subplot(gs[2]), pipeline)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=400, facecolor="white")
    plt.close(fig)


def html_shell() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Eidos pipeline — monitor</title>
<style>
:root{color-scheme:light}
body{margin:0;background:#ffffff;display:flex;justify-content:center;font-family:serif}
img{max-width:100%;height:auto}
</style></head>
<body><img src="/dashboard.png" alt="Eidos pipeline monitor"></body></html>
"""


def main() -> int:
    build_figure()
    HTML.write_text(html_shell(), encoding="utf-8")
    print(f"wrote {PNG} ({PNG.stat().st_size // 1024} KB) and {HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
