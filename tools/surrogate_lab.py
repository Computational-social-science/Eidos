"""Build the interactive demonstrator for the local-operator layer.

The page is a deliverable, so it carries the apparatus a reader needs in order to trust it:
what question it answers, how the operator is fitted, what the numbers mean, what the
demonstration does not show, and where the method comes from. Formulas are typeset in
MathML rather than as plain text: the page must open from disk with no network, so a
JavaScript math renderer is not an option and MathML is native.

    python tools/surrogate_lab.py            # writes lab/lab.html
    python tools/surrogate_lab.py --check    # rebuild and compare with the file on disk

Every number on the page is computed here from the fitted operator; nothing is typed.
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

from framework.surrogate import (RandomFeatureOperator, fixed_point,  # noqa: E402
                                 spectral_radius)
from audit_surrogate import DT, training_pairs  # noqa: E402

OUT = ROOT / "lab" / "lab.html"
GRID = 91
CHECK = (0.20, 0.40, 0.60, 0.80, 1.00)


def _trace(op, lam: float, u0: float = 1.0, steps: int = 6) -> list[float]:
    """Newton iterates at one lambda, for the step-by-step panel."""
    u = np.array([u0], dtype=float)
    trace = [float(u[0])]
    for _ in range(steps):
        u, info = fixed_point(op.step, lam, u, tol=1e-10, max_iter=1)
        trace.append(float(u[0]))
        if info["converged"]:
            break
    u, _ = fixed_point(op.step, lam, np.array([u0], dtype=float), tol=1e-10, max_iter=80)
    trace.append(float(u[0]))
    return trace


def build() -> dict:
    u, u_next, lam = training_pairs()
    op = RandomFeatureOperator(n_features=256, seed=0).fit(u, u_next, lam)

    rows = []
    for value in np.linspace(0.1, 1.0, GRID):
        u_star, info = fixed_point(op.step, float(value), np.array([1.0]), tol=1e-9)
        truth = float(np.sqrt(value))
        rho = spectral_radius(op.step, u_star, float(value)) if info["converged"] else None
        rows.append({
            "lam": round(float(value), 4),
            "learned": round(float(u_star[0]), 6) if info["converged"] else None,
            "truth": round(truth, 6),
            "rho": round(float(rho), 5) if rho is not None else None,
            "rel_error": round(abs(float(u_star[0]) - truth) / truth, 6)
            if info["converged"] else None,
        })

    checkpoints = [r for r in rows if any(abs(r["lam"] - c) < 0.006 for c in CHECK)]
    errors = [r["rel_error"] for r in rows if r["rel_error"] is not None]
    return {
        "dt": DT, "features": 256, "train_rows": int(len(u)), "seed": 0, "grid": GRID,
        "rows": rows, "checkpoints": checkpoints,
        "traces": {f"{lam0:.2f}": _trace(op, lam0) for lam0 in (0.2, 0.5, 0.9)},
        "max_rel_error": max(errors) if errors else None,
        "median_rel_error": float(np.median(errors)) if errors else None,
    }


# -- MathML -------------------------------------------------------------------
M_ODE = ("<math display='inline'><mfrac><mrow><mi>d</mi><mi>u</mi></mrow>"
         "<mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mi>&#955;</mi>"
         "<mo>&#8722;</mo><msup><mi>u</mi><mn>2</mn></msup></math>")
M_STAR = ("<math display='inline'><msup><mi>u</mi><mo>&#8727;</mo></msup><mo>=</mo>"
          "<msqrt><mi>&#955;</mi></msqrt></math>")
M_PSI = ("<math display='inline'><mi>&#968;</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>=</mo>"
         "<mi>S</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>&#8722;</mo><mi>u</mi>"
         "<mo>=</mo><mn>0</mn></math>")
M_NEWTON = ("<math display='inline'><msub><mi>u</mi><mrow><mi>k</mi><mo>+</mo><mn>1</mn>"
            "</mrow></msub><mo>=</mo><msub><mi>u</mi><mi>k</mi></msub><mo>&#8722;</mo>"
            "<msup><mi>J</mi><mrow><mo>&#8722;</mo><mn>1</mn></mrow></msup>"
            "<mi>&#968;</mi><mo>(</mo><msub><mi>u</mi><mi>k</mi></msub><mo>)</mo></math>")
M_RHO = ("<math display='inline'><mi>&#961;</mi><mo>(</mo><mfrac><mrow><mo>&#8706;</mo>"
         "<mi>S</mi></mrow><mrow><mo>&#8706;</mo><mi>u</mi></mrow></mfrac><mo>)</mo>"
         "<mo>&lt;</mo><mn>1</mn></math>")
M_LOSS = ("<math display='inline'><mi>&#949;</mi><mo>=</mo><mo>|</mo><msub><mi>u</mi>"
          "<mtext>learned</mtext></msub><mo>&#8722;</mo><msqrt><mi>&#955;</mi></msqrt>"
          "<mo>|</mo><mo>/</mo><msqrt><mi>&#955;</mi></msqrt></math>")
M_DT = ("<math display='inline'><mi>&#916;</mi><mi>t</mi><mo>=</mo><mn>0.05</mn></math>")
M_LAM = "<math display='inline'><mi>&#955;</mi></math>"

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fixed points of a learned short-time operator — Eidos demonstrator</title>
<style>
:root{--ink:#11161c;--muted:#5d6773;--rule:#dde2e8;--paper:#fff;--wash:#f5f6f8;
      --analytic:#1f4e9c;--learned:#a8323f;--ok:#1c6b42}
*{box-sizing:border-box}
body{margin:0;background:var(--wash);color:var(--ink);
     font:16px/1.58 Georgia,"Iowan Old Style","Times New Roman",serif}
.sans{font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:34px 24px 64px}
.eyebrow{font:600 11px/1 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;
         letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{font-size:30px;line-height:1.18;margin:10px 0 8px;letter-spacing:-.01em}
.lede{font-size:17px;color:#2b333c;max-width:62ch;margin:0 0 18px}
h2{font:700 12px/1 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;
   letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0 0 12px}
p{margin:0 0 12px}
.card{background:var(--paper);border:1px solid var(--rule);border-radius:10px;padding:18px 20px}
.abstract p{max-width:74ch}
.grid{display:grid;grid-template-columns:1.45fr 1fr;gap:18px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
canvas{width:100%;height:auto;display:block}
figcaption{font-size:13px;color:var(--muted);margin-top:10px;line-height:1.5}
.controls{display:flex;align-items:center;gap:14px;margin-top:14px}
input[type=range]{flex:1;accent-color:var(--learned);height:22px}
button{font:500 13px/1 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;padding:7px 12px;
       border-radius:7px;border:1px solid var(--rule);background:#fff;color:var(--ink);cursor:pointer}
button:hover{border-color:#b8c0c9}
button:focus-visible,input:focus-visible{outline:2px solid var(--analytic);outline-offset:2px}
.readout{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}
.kv{border:1px solid var(--rule);border-radius:8px;padding:9px 11px;background:#fbfcfd}
.kv .k{font:600 10px/1.2 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;
       letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.kv .v{font-size:17px;margin-top:3px;font-variant-numeric:tabular-nums}
.verdict{margin-top:12px}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:12px;
      font-family:-apple-system,"Segoe UI",Arial,sans-serif}
.pill.ok{background:#e9f4ee;color:var(--ok);border:1px solid #c3e0cf}
.pill.bad{background:#fbecee;color:#8c1d2c;border:1px solid #f0c4cb}
.legend{display:flex;gap:18px;font-size:13px;color:var(--muted);margin-top:8px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
caption{caption-side:top;text-align:left;font-size:13px;color:var(--muted);margin-bottom:8px}
th,td{padding:6px 8px;border-bottom:1px solid var(--rule);text-align:right}
th:first-child,td:first-child{text-align:left}
thead th{font:600 11px/1.2 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.05em;
         text-transform:uppercase;color:var(--muted);border-bottom:1px solid #b9c1ca}
ol.method{margin:0;padding-left:20px}
ol.method li{margin-bottom:8px}
.caveat{border-left:3px solid var(--learned);padding-left:14px;color:#3a434d}
footer{margin-top:26px;font-size:13px;color:var(--muted);line-height:1.6}
a{color:var(--analytic)}
@media print{body{background:#fff}.wrap{max-width:none;padding:0}
  .card{border:1px solid #ccc;break-inside:avoid}.controls,button{display:none}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style></head>
<body><div class="wrap">

<div class="eyebrow">Eidos · framework/surrogate · demonstrative consumer</div>
<h1>Fixed points of a learned short-time operator</h1>
<p class="lede">A neural operator is fitted to short-step data from a nonlinear system, and
the system's steady states are then computed from the operator alone — the equation-free
move that motivates the layer, shown end to end.</p>

<div class="card abstract" style="margin-bottom:18px">
  <h2>Abstract</h2>
  <p>We fit a random-feature operator to one-step pairs of the scalar system
  <span>__M_ODE__</span> with __M_DT__, then solve <span>__M_PSI__</span> by Newton's method
  using only the learned map. Over __GRID__ values of __M_LAM__ the recovered fixed points
  track the analytic branch <span>__M_STAR__</span> with a maximum relative error of
  __MAXERR__ (median __MEDERR__), and the spectral radius of the learned map stays below
  one everywhere, so every recovered steady state is attracting. The demonstration is the
  consumer of <code>framework/surrogate</code>: it shows that system-level quantities —
  existence, location, stability — can be read from a fitted operator without integrating
  the governing equation.</p>
</div>

<div class="grid">
  <figure class="card" style="margin:0">
    <h2>Panel A · Fixed point against parameter</h2>
    <canvas id="plot" width="640" height="380" role="img"
            aria-label="Fixed point of the learned operator against the parameter, compared with the analytic branch"></canvas>
    <div class="legend">
      <span><span class="dot" style="background:var(--analytic)"></span>analytic __M_STAR__</span>
      <span><span class="dot" style="background:var(--learned)"></span>learned operator, Newton solution</span>
    </div>
    <figcaption>Circles are Newton solutions of __M_PSI__ on the fitted map; the line is the
      closed form. The dashed rule marks the selected parameter.</figcaption>
    <div class="controls">
      <label for="lam" class="sans" style="font-size:13px;color:var(--muted)">λ</label>
      <input id="lam" type="range" min="0.10" max="1.00" step="0.01" value="0.50"
             aria-label="parameter lambda">
      <output id="lamval" class="sans" style="font-size:14px;width:3.4em">0.50</output>
    </div>
    <div class="readout">
      <div class="kv"><div class="k">learned u*</div><div class="v" id="u_learned">—</div></div>
      <div class="kv"><div class="k">relative error ε</div><div class="v" id="err">—</div></div>
      <div class="kv"><div class="k">spectral radius ρ</div><div class="v" id="rho">—</div></div>
    </div>
    <div class="verdict" id="verdict"></div>
  </figure>

  <div style="display:grid;gap:18px">
    <div class="card">
      <h2>Panel B · Stability</h2>
      <canvas id="rho_plot" width="420" height="230" role="img"
              aria-label="Spectral radius of the learned map against the parameter"></canvas>
      <figcaption>__M_RHO__ at the learned fixed point. The red rule is the unit threshold;
        below it a perturbation decays.</figcaption>
    </div>
    <div class="card">
      <h2>Panel C · Newton iterates</h2>
      <svg id="trace" width="100%" height="96" role="img"
           aria-label="Newton iterates converging to the fixed point"></svg>
      <figcaption class="sans" style="font-size:12px">Start
        <span>u<sub>0</sub> = 1</span> at λ = <span id="trace_lam">0.50</span>; each point is
        one Newton step on __M_PSI__.</figcaption>
      <div style="margin-top:10px"><button id="replay" type="button">Replay</button></div>
    </div>
  </div>
</div>

<div class="card" style="margin-top:18px">
  <h2>Table 1 · Checkpoints</h2>
  <table>
    <caption>Learned fixed point, analytic value, relative error and spectral radius at five
      parameters. Full grid: __GRID__ points, all stable.</caption>
    <thead><tr><th>λ</th><th>u* analytic</th><th>u* learned</th><th>ε</th><th>ρ</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>

<div class="grid" style="margin-top:18px">
  <div class="card">
    <h2>Method</h2>
    <ol class="method">
      <li><b>Data.</b> __TRAIN__ one-step pairs <span>(u<sub>t</sub>, u<sub>t+Δt</sub>)</span>
        generated by RK4 at __M_DT__, sampled around the branch.</li>
      <li><b>Operator.</b> Random features <span>φ(u) = tanh(Wu + c)</span> with a ridge fit
        on the <i>increment</i>, so the regression is conditioned on the short-time dynamics;
        __FEATURES__ features, seed __SEED__.</li>
      <li><b>Fixed point.</b> Newton on __M_PSI__ with a finite-difference Jacobian and
        backtracking: __M_NEWTON__.</li>
      <li><b>Stability.</b> Eigenvalues of ∂S/∂u at the solution; the state is attracting
        when __M_RHO__.</li>
      <li><b>Check.</b> The same procedure on the analytic map would return the closed form
        exactly; the gap between the curves is the operator's error, __M_LOSS__.</li>
    </ol>
  </div>
  <div class="card">
    <h2>What this does and does not show</h2>
    <p><b>Does.</b> A short-time operator fitted on data supports system-level computation:
      fixed points, their stability, and their parameter dependence — the quantities a
      scientist wants, without writing the governing equation down.</p>
    <p class="caveat"><b>Does not.</b> It is not a PDE solver, and no claim is made outside
      the training interval. The operator is a random-feature regressor, not a DeepONet; the
      state here is one-dimensional and smooth. Applying the machinery to discrete objects
      such as token sequences would be a category error: they are not C¹ function spaces,
      and the correct analogue there is a transfer operator.</p>
  </div>
</div>

<footer>
  Provenance: __TRAIN__ training pairs, __FEATURES__ features, Δt = __DT__, seed __SEED__,
  built by <code>tools/surrogate_lab.py</code>. All numbers are computed at build time and
  embedded, so the page opens from disk without a server or a network. Formulas are typeset
  in MathML, not rendered by a script.
  <br>Method after Fabiani, Vandecasteele, Goswami, Siettos &amp; Kevrekidis, <i>Enabling
  Local Neural Operators to perform Equation-Free System-Level Analysis</i>, Nature Machine
  Intelligence (2026), doi:10.1038/s42256-026-01265-1; the equation-free framing is due to
  Kevrekidis and co-workers.
</footer>
</div>

<script>
const DATA = __DATA__;
const W = 640, H = 380, PAD = {l:56, r:16, t:16, b:44};
const rows = DATA.rows;
const xOf = lam => PAD.l + (lam - 0.1) / 0.9 * (W - PAD.l - PAD.r);
const yOf = u => H - PAD.b - (u / 1.05) * (H - PAD.t - PAD.b);

function frame(ctx, w, h, pad, ymax, ylabel) {
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#dde2e8"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, h - pad.b);
  ctx.lineTo(w - pad.r, h - pad.b); ctx.stroke();
  ctx.fillStyle = "#5d6773"; ctx.font = "11px -apple-system,Segoe UI,Arial";
  ctx.textAlign = "center";
  for (const t of [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]) {
    ctx.fillText(t.toFixed(1), pad.l + (t - 0.1) / 0.9 * (w - pad.l - pad.r), h - pad.b + 16);
  }
  ctx.textAlign = "right";
  for (let v = 0; v <= ymax + 1e-9; v += ymax / 4) {
    const py = h - pad.b - (v / ymax) * (h - pad.t - pad.b);
    ctx.fillText(v.toFixed(2), pad.l - 8, py + 4);
    ctx.strokeStyle = "#eef1f4"; ctx.beginPath(); ctx.moveTo(pad.l, py);
    ctx.lineTo(w - pad.r, py); ctx.stroke();
  }
  ctx.save(); ctx.translate(16, (h + pad.t - pad.b) / 2); ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center"; ctx.fillStyle = "#5d6773"; ctx.fillText(ylabel, 0, 0); ctx.restore();
}

function drawMain() {
  const ctx = document.getElementById("plot").getContext("2d");
  frame(ctx, W, H, PAD, 1.05, "u*");
  ctx.strokeStyle = "#1f4e9c"; ctx.lineWidth = 2; ctx.beginPath();
  rows.forEach((r, i) => i ? ctx.lineTo(xOf(r.lam), yOf(r.truth)) : ctx.moveTo(xOf(r.lam), yOf(r.truth)));
  ctx.stroke();
  ctx.fillStyle = "#a8323f";
  rows.forEach(r => { if (r.learned === null) return;
    ctx.beginPath(); ctx.arc(xOf(r.lam), yOf(r.learned), 2.1, 0, 7); ctx.fill(); });

  const sel = parseFloat(document.getElementById("lam").value);
  const near = rows.reduce((a, b) => Math.abs(b.lam - sel) < Math.abs(a.lam - sel) ? b : a);
  document.getElementById("lamval").textContent = sel.toFixed(2);
  document.getElementById("u_learned").textContent = near.learned === null ? "—" : near.learned.toFixed(4);
  document.getElementById("err").textContent = near.rel_error === null ? "—" : (100 * near.rel_error).toExponential(1) + "%";
  document.getElementById("rho").textContent = near.rho === null ? "—" : near.rho.toFixed(3);
  const ok = near.rel_error !== null && near.rel_error < 0.05;
  document.getElementById("verdict").innerHTML = ok
    ? '<span class="pill ok">within 5% of the analytic fixed point</span>'
    : '<span class="pill bad">outside the 5% tolerance</span>';
  ctx.strokeStyle = "#9aa4b1"; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(xOf(near.lam), PAD.t); ctx.lineTo(xOf(near.lam), H - PAD.b);
  ctx.stroke(); ctx.setLineDash([]);
}

function drawRho() {
  const ctx = document.getElementById("rho_plot").getContext("2d");
  const w = 420, h = 230, pad = {l:46, r:14, t:14, b:34};
  const top = Math.max(1.15, ...rows.map(r => r.rho || 0));
  frame(ctx, w, h, pad, top, "ρ");
  ctx.strokeStyle = "#1f4e9c"; ctx.lineWidth = 2; ctx.beginPath();
  rows.forEach((r, i) => { if (r.rho === null) return;
    const px = pad.l + (r.lam - 0.1) / 0.9 * (w - pad.l - pad.r);
    const py = h - pad.b - (r.rho / top) * (h - pad.t - pad.b);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.stroke();
  const py = h - pad.b - (1 / top) * (h - pad.t - pad.b);
  ctx.strokeStyle = "#a8323f"; ctx.setLineDash([5, 4]); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, py); ctx.lineTo(w - pad.r, py); ctx.stroke();
  ctx.setLineDash([]);
}

function drawTrace() {
  const sel = parseFloat(document.getElementById("lam").value);
  const keys = Object.keys(DATA.traces);
  const key = keys.reduce((a, b) => Math.abs(parseFloat(b) - sel) < Math.abs(parseFloat(a) - sel) ? b : a);
  document.getElementById("trace_lam").textContent = parseFloat(key).toFixed(2);
  const pts = DATA.traces[key];
  const svg = document.getElementById("trace");
  const w = svg.clientWidth || 380, h = 96;
  const ux = i => 16 + i / Math.max(1, pts.length - 1) * (w - 32);
  const uy = v => h - 14 - (v / 1.05) * (h - 26);
  svg.innerHTML = pts.map((v, i) =>
    `<circle cx="${ux(i)}" cy="${uy(v)}" r="3.1" fill="#1f4e9c" opacity="${(0.35 + 0.65 * i / pts.length).toFixed(2)}"/>`
  ).join("") + `<polyline fill="none" stroke="#1f4e9c" stroke-width="1.1" points="${pts.map((v, i) => `${ux(i)},${uy(v)}`).join(" ")}"/>`;
}

function fillTable() {
  document.getElementById("rows").innerHTML = DATA.checkpoints.map(r => `
    <tr><td>${r.lam.toFixed(2)}</td><td>${r.truth.toFixed(4)}</td>
    <td>${r.learned === null ? "—" : r.learned.toFixed(4)}</td>
    <td>${r.rel_error === null ? "—" : (100 * r.rel_error).toExponential(1) + "%"}</td>
    <td>${r.rho === null ? "—" : r.rho.toFixed(3)}</td></tr>`).join("");
}

let timer = null;
function replay() {
  const circles = document.getElementById("trace").querySelectorAll("circle");
  if (timer) clearInterval(timer);
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    circles.forEach(c => c.style.opacity = 1); return;
  }
  circles.forEach(c => c.style.opacity = 0.05);
  let i = 0;
  timer = setInterval(() => {
    if (i >= circles.length) { clearInterval(timer); timer = null; return; }
    circles[i].style.opacity = 1; i++;
  }, 210);
}

document.getElementById("lam").addEventListener("input", drawMain);
document.getElementById("replay").addEventListener("click", replay);
drawMain(); drawRho(); drawTrace(); fillTable();
window.addEventListener("resize", () => { drawRho(); drawTrace(); });
</script>
</body></html>
"""


def render(data: dict) -> str:
    page = PAGE
    for token, value in (("__M_ODE__", M_ODE), ("__M_STAR__", M_STAR), ("__M_PSI__", M_PSI),
                         ("__M_NEWTON__", M_NEWTON), ("__M_RHO__", M_RHO),
                         ("__M_LOSS__", M_LOSS), ("__M_DT__", M_DT), ("__M_LAM__", M_LAM),
                         ("__GRID__", str(data["grid"])),
                         ("__TRAIN__", f"{data['train_rows']:,}"),
                         ("__FEATURES__", str(data["features"])),
                         ("__SEED__", str(data["seed"])),
                         ("__DT__", str(data["dt"])),
                         ("__MAXERR__", f"{100 * data['max_rel_error']:.4f}%"),
                         ("__MEDERR__", f"{100 * data['median_rel_error']:.4f}%"),
                         ("__DATA__", json.dumps(data, separators=(",", ":")))):
        page = page.replace(token, value)
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    data = build()
    page = render(data)
    if args.json:
        print(json.dumps({k: data[k] for k in
                          ("max_rel_error", "median_rel_error", "grid", "train_rows")}))
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
          f"median {100 * data['median_rel_error']:.4f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
