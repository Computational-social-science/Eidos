"""Interactive lab for the local-operator layer -- the demonstrative consumer.

Runs the planted system ``du/dt = lam - u^2`` end to end -- fit the short-time operator on
data, solve for its fixed point by Newton, measure stability -- and writes a self-contained
HTML page where a reader can move ``lam`` and watch the learned fixed point track the
analytic one.

Why a page and not a notebook: the point of this consumer is *demonstration*. A reader who
can drag a slider and see the learned curve sit on the analytic curve, with the error and
the spectral radius updating, understands in ten seconds what a table of numbers takes ten
minutes to convey. It is also the cheapest possible consumer: one file, no server, no
network, no dependencies.

The page embeds its data at build time (``file://`` forbids ``fetch``), and every number on
it is recomputed here from the operator, not typed.

    python tools/surrogate_lab.py            # writes lab/lab.html
    python tools/surrogate_lab.py --check    # rebuild and compare with the file on disk
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from framework.surrogate import RandomFeatureOperator, fixed_point, rk4_step, spectral_radius  # noqa: E402
from audit_surrogate import DT, RHS, training_pairs  # noqa: E402

OUT = ROOT / "lab" / "lab.html"
GRID = 91


def _newton_trace(op, lam: float, u0: float, steps: int = 6) -> list[float]:
    u = np.array([u0], dtype=float)
    trace = [float(u[0])]
    for _ in range(steps):
        u, info = fixed_point(op.step, lam, u, tol=1e-10, max_iter=1)
        trace.append(float(u[0]))
        if info["converged"]:
            break
    # finish properly so the last point is the answer, not a partial step
    u, _ = fixed_point(op.step, lam, np.array([u0], dtype=float), tol=1e-10, max_iter=80)
    trace.append(float(u[0]))
    return trace


def build() -> dict:
    u, u_next, lam = training_pairs()
    op = RandomFeatureOperator(n_features=256, seed=0).fit(u, u_next, lam)

    lams = np.linspace(0.1, 1.0, GRID)
    rows = []
    for value in lams:
        u_star, info = fixed_point(op.step, float(value), np.array([1.0]), tol=1e-9)
        truth = float(np.sqrt(value))
        rho = spectral_radius(op.step, u_star, float(value)) if info["converged"] else None
        rows.append({"lam": round(float(value), 4),
                     "learned": round(float(u_star[0]), 6) if info["converged"] else None,
                     "truth": round(truth, 6),
                     "rho": round(float(rho), 5) if rho is not None else None,
                     "rel_error": round(abs(float(u_star[0]) - truth) / truth, 6)
                     if info["converged"] else None})

    errors = [r["rel_error"] for r in rows if r["rel_error"] is not None]
    return {
        "system": "du/dt = lam - u^2",
        "truth": "u* = sqrt(lam)",
        "dt": DT,
        "features": 256,
        "train_rows": int(len(u)),
        "rows": rows,
        "max_rel_error": max(errors) if errors else None,
        "median_rel_error": float(np.median(errors)) if errors else None,
        "traces": {str(lam0): _newton_trace(op, lam0, 1.0)
                   for lam0 in (0.2, 0.5, 0.9)},
    }


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local neural operator — fixed points on demand</title>
<style>
:root {{ --ink:#12161c; --muted:#5b6673; --rule:#d9dee5; --true:#1f6feb; --learned:#d1495b; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#f6f7f9; color:var(--ink);
        font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:28px 22px 48px; }}
h1 {{ font-size:20px; margin:0 0 4px; letter-spacing:-0.01em; }}
.sub {{ color:var(--muted); font-size:13px; margin-bottom:20px; }}
.grid {{ display:grid; grid-template-columns:1.35fr 1fr; gap:18px; }}
@media (max-width:860px) {{ .grid {{ grid-template-columns:1fr; }} }}
.card {{ background:#fff; border:1px solid var(--rule); border-radius:10px; padding:14px 16px; }}
.card h2 {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em;
            color:var(--muted); margin:0 0 10px; font-weight:700; }}
canvas {{ width:100%; height:auto; display:block; }}
.controls {{ display:flex; align-items:center; gap:12px; margin:10px 0 4px; }}
input[type=range] {{ flex:1; accent-color:var(--learned); }}
.readout {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:10px; }}
.kv {{ background:#fbfcfd; border:1px solid var(--rule); border-radius:8px; padding:8px 10px; }}
.kv .k {{ font-size:11px; color:var(--muted); }}
.kv .v {{ font-size:16px; font-variant-numeric:tabular-nums; margin-top:2px; }}
.badge {{ display:inline-block; font-size:12px; padding:3px 9px; border-radius:999px;
          background:#e8f5ee; color:#17663a; border:1px solid #bfe3cc; }}
.badge.bad {{ background:#fdecee; color:#8c1d2c; border-color:#f3c3ca; }}
.legend {{ display:flex; gap:16px; font-size:12px; color:var(--muted); margin-top:6px; }}
.dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }}
button {{ font:inherit; font-size:13px; padding:6px 12px; border-radius:7px;
          border:1px solid var(--rule); background:#fff; cursor:pointer; }}
button:hover {{ border-color:#b6bfca; }}
footer {{ margin-top:22px; color:var(--muted); font-size:12px; line-height:1.6; }}
code {{ background:#eef1f5; padding:1px 5px; border-radius:4px; font-size:12px; }}
</style></head>
<body><div class="wrap">
  <h1>Local neural operator — fixed points on demand</h1>
  <div class="sub">A short-time operator is fitted to data from <code>{system}</code>, then
    Newton solves <code>S(u) = u</code>. Drag λ: the red learned curve should sit on the
    blue analytic one.</div>

  <div class="grid">
    <div class="card">
      <h2>Fixed point u*(λ)</h2>
      <canvas id="plot" width="640" height="360"></canvas>
      <div class="legend">
        <span><span class="dot" style="background:var(--true)"></span>analytic √λ</span>
        <span><span class="dot" style="background:var(--learned)"></span>learned operator</span>
      </div>
      <div class="controls">
        <span style="font-size:13px;color:var(--muted)">λ</span>
        <input id="lam" type="range" min="0.10" max="1.00" step="0.01" value="0.50">
        <span id="lamval" style="font-size:14px;font-variant-numeric:tabular-nums;width:3.2em"></span>
      </div>
      <div class="readout">
        <div class="kv"><div class="k">learned u*</div><div class="v" id="u_learned">—</div></div>
        <div class="kv"><div class="k">relative error</div><div class="v" id="err">—</div></div>
        <div class="kv"><div class="k">spectral radius</div><div class="v" id="rho">—</div></div>
      </div>
      <div style="margin-top:10px" id="verdict"></div>
    </div>

    <div class="card">
      <h2>Stability ρ(λ) — below 1 is attracting</h2>
      <canvas id="rho_plot" width="420" height="220"></canvas>
      <h2 style="margin-top:16px">Newton, step by step</h2>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px">
        start u₀ = 1.0 at λ = <span id="trace_lam">0.50</span></div>
      <svg id="trace" width="100%" height="110"></svg>
      <div style="margin-top:8px"><button id="replay">Replay Newton</button></div>
    </div>
  </div>

  <footer>
    Fitted on {train_rows} short-step pairs, {features} random features, Δt = {dt}.
    Max relative error over the grid: <b>{max_err}</b>; median <b>{median_err}</b>.
    Every number is written by <code>tools/surrogate_lab.py</code>; the page embeds its data
    so it works from <code>file://</code> without a network.
  </footer>
</div>
<script>
const DATA = {data};

const W = 640, H = 360, PAD = {{l: 52, r: 14, t: 14, b: 38}};
const rows = DATA.rows;
const x = lam => PAD.l + (lam - 0.1) / 0.9 * (W - PAD.l - PAD.r);
const y = u => H - PAD.b - (u / 1.05) * (H - PAD.t - PAD.b);

function axes(ctx, w, h, pad, ymax, ylabel) {{
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#d9dee5"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, h - pad.b);
  ctx.lineTo(w - pad.r, h - pad.b); ctx.stroke();
  ctx.fillStyle = "#5b6673"; ctx.font = "11px -apple-system,Segoe UI,Arial";
  ctx.textAlign = "center";
  for (const t of [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]) {{
    const px = pad.l + (t - 0.1) / 0.9 * (w - pad.l - pad.r);
    ctx.fillText(t.toFixed(1), px, h - pad.b + 15);
  }}
  ctx.textAlign = "right";
  for (let v = 0; v <= ymax + 1e-9; v += ymax / 4) {{
    const py = h - pad.b - (v / ymax) * (h - pad.t - pad.b);
    ctx.fillText(v.toFixed(1), pad.l - 8, py + 4);
    ctx.strokeStyle = "#eef1f5"; ctx.beginPath(); ctx.moveTo(pad.l, py);
    ctx.lineTo(w - pad.r, py); ctx.stroke();
  }}
  ctx.save(); ctx.translate(14, (h + pad.t - pad.b) / 2); ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center"; ctx.fillText(ylabel, 0, 0); ctx.restore();
}}

function draw() {{
  const c = document.getElementById("plot"), ctx = c.getContext("2d");
  axes(ctx, W, H, PAD, 1.05, "u*");
  ctx.strokeStyle = "#1f6feb"; ctx.lineWidth = 2; ctx.beginPath();
  rows.forEach((r, i) => {{ const px = x(r.lam), py = y(r.truth);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }});
  ctx.stroke();
  ctx.fillStyle = "#d1495b";
  rows.forEach(r => {{ if (r.learned === null) return;
    ctx.beginPath(); ctx.arc(x(r.lam), y(r.learned), 2.2, 0, 7); ctx.fill(); }});

  const sel = +document.getElementById("lam").value;
  const near = rows.reduce((a, b) => Math.abs(b.lam - sel) < Math.abs(a.lam - sel) ? b : a);
  document.getElementById("lamval").textContent = sel.toFixed(2);
  document.getElementById("u_learned").textContent = near.learned === null ? "—" : near.learned.toFixed(3);
  document.getElementById("err").textContent = near.rel_error === null ? "—" : (100 * near.rel_error).toFixed(2) + "%";
  document.getElementById("rho").textContent = near.rho === null ? "—" : near.rho.toFixed(3);
  const ok = near.rel_error !== null && near.rel_error < 0.05;
  const v = document.getElementById("verdict");
  v.innerHTML = ok ? '<span class="badge">within 5% of the analytic fixed point</span>'
                   : '<span class="badge bad">outside the 5% tolerance</span>';
  ctx.strokeStyle = "#9aa4b1"; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(x(near.lam), PAD.t); ctx.lineTo(x(near.lam), H - PAD.b); ctx.stroke();
  ctx.setLineDash([]);
}}

function drawRho() {{
  const c = document.getElementById("rho_plot"), ctx = c.getContext("2d");
  const w = 420, h = 220, pad = {{l: 42, r: 12, t: 12, b: 30}};
  const max = Math.max(1.2, ...rows.map(r => r.rho || 0));
  axes(ctx, w, h, pad, max, "ρ");
  ctx.strokeStyle = "#1f6feb"; ctx.lineWidth = 2; ctx.beginPath();
  rows.forEach((r, i) => {{ if (r.rho === null) return;
    const px = pad.l + (r.lam - 0.1) / 0.9 * (w - pad.l - pad.r);
    const py = h - pad.b - (r.rho / max) * (h - pad.t - pad.b);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }});
  ctx.stroke();
  const py = h - pad.b - (1 / max) * (h - pad.t - pad.b);
  ctx.strokeStyle = "#d1495b"; ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.moveTo(pad.l, py); ctx.lineTo(w - pad.r, py); ctx.stroke();
  ctx.setLineDash([]);
}}

let timer = null;
function drawTrace() {{
  const sel = +document.getElementById("lam").value;
  const key = Object.keys(DATA.traces).reduce((a, b) =>
    Math.abs(+b - sel) < Math.abs(+a - sel) ? b : a);
  document.getElementById("trace_lam").textContent = (+key).toFixed(2);
  const pts = DATA.traces[key];
  const svg = document.getElementById("trace");
  const w = svg.clientWidth || 380, h = 110;
  const ux = i => 18 + (i / Math.max(1, pts.length - 1)) * (w - 36);
  const uy = v => h - 16 - (v / 1.05) * (h - 28);
  svg.innerHTML = pts.map((v, i) =>
    `<circle cx="${{ux(i)}}" cy="${{uy(v)}}" r="3.2" fill="#1f6feb" opacity="${{0.35 + 0.65 * i / pts.length}}"/>`
  ).join("") + `<polyline fill="none" stroke="#1f6feb" stroke-width="1.2"
     points="${{pts.map((v, i) => `${{ux(i)}},${{uy(v)}}`).join(" ")}}"/>`;
}}

document.getElementById("lam").addEventListener("input", draw);
document.getElementById("replay").addEventListener("click", () => {{
  const svg = document.getElementById("trace");
  const pts = svg.querySelectorAll("circle");
  if (timer) clearInterval(timer);
  pts.forEach(p => p.style.opacity = 0.05);
  let i = 0;
  timer = setInterval(() => {{
    if (i >= pts.length) {{ clearInterval(timer); timer = null; return; }}
    pts[i].style.opacity = 1; i++;
  }}, 220);
}});
draw(); drawRho(); drawTrace();
window.addEventListener("resize", () => {{ drawRho(); drawTrace(); }});
</script>
</body></html>
"""


def render(data: dict) -> str:
    return PAGE.format(system=data["system"], train_rows=data["train_rows"],
                       features=data["features"], dt=data["dt"],
                       max_err=f"{100 * data['max_rel_error']:.4f}%",
                       median_err=f"{100 * data['median_rel_error']:.4f}%",
                       data=json.dumps(data, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    data = build()
    page = render(data)
    if args.json:
        print(json.dumps({k: data[k] for k in ("max_rel_error", "median_rel_error")}))
    if args.check:
        if not OUT.is_file():
            print(f"[FAIL] {OUT} has not been built")
            return 1
        if OUT.read_text(encoding="utf-8") != page:
            print("[FAIL] lab/lab.html is stale; rebuild with tools/surrogate_lab.py")
            return 1
        print(f"lab is current; max relative error {100 * data['max_rel_error']:.4f}%")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(page) // 1024} KB; "
          f"max relative error {100 * data['max_rel_error']:.4f}%, "
          f"median {100 * data['median_rel_error']:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
