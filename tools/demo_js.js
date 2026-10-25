const DATA = __DEMO__;
const ROWS = DATA.rows.filter(r => r.learned !== null);
const LAM0 = 0.1, LAM1 = 1.0;

/* One axis, drawn once, used by both panels: hairline grid, no box, tabular ticks. Two panels
   with two visual languages is how a figure starts looking assembled rather than designed. */
const INK = { line: "#6b7480", grid: "rgba(255,255,255,0.055)", text: "#8b95a5",
              accent: "#5b8def", warm: "#d29922", bad: "#e5534b" };

function prepare(canvas) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const cssW = canvas.clientWidth || canvas.width;
  const cssH = Math.round(cssW * 0.52);
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  return { ctx, w: cssW, h: cssH };
}

function axis(ctx, w, h, pad, ydomain, ylabel, xticks) {
  const X = lam => pad.l + (lam - LAM0) / (LAM1 - LAM0) * (w - pad.l - pad.r);
  const Y = v => h - pad.b - (v - ydomain[0]) / (ydomain[1] - ydomain[0]) * (h - pad.t - pad.b);
  ctx.font = "9.5px ui-monospace,SFMono-Regular,Consolas,monospace";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 4; i++) {
    const v = ydomain[0] + (ydomain[1] - ydomain[0]) * i / 4, y = Y(v);
    ctx.strokeStyle = INK.grid; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.l, y + 0.5); ctx.lineTo(w - pad.r, y + 0.5); ctx.stroke();
    ctx.fillStyle = INK.text; ctx.textAlign = "right";
    ctx.fillText(v.toFixed(2), pad.l - 6, y);
  }
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (const t of xticks) {
    const x = X(t);
    ctx.strokeStyle = INK.grid; ctx.beginPath();
    ctx.moveTo(x + 0.5, pad.t); ctx.lineTo(x + 0.5, h - pad.b); ctx.stroke();
    ctx.fillStyle = INK.text; ctx.fillText(t.toFixed(1), x, h - pad.b + 6);
  }
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#7d8797"; ctx.font = "9.5px ui-monospace,Consolas,monospace";
  ctx.fillText(ylabel.toUpperCase(), pad.l, pad.t - 4);
  return { X, Y };
}

function dot(ctx, x, y, r, fill, ring) {
  if (ring) {
    ctx.beginPath(); ctx.arc(x, y, r + 3.4, 0, 7);
    ctx.strokeStyle = ring; ctx.lineWidth = 1; ctx.stroke();
  }
  ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = fill; ctx.fill();
}

function drawMain() {
  const { ctx, w, h } = prepare(document.getElementById("plot"));
  const pad = { l: 40, r: 12, t: 18, b: 22 };
  const { X, Y } = axis(ctx, w, h, pad, [0, 1.05], "u* (fixed point)",
                        [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]);

  // analytic curve first, then a fill beneath it so the learned dots sit inside a shape
  ctx.beginPath();
  DATA.rows.forEach((r, i) => i ? ctx.lineTo(X(r.lam), Y(r.truth)) : ctx.moveTo(X(r.lam), Y(r.truth)));
  const grad = ctx.createLinearGradient(0, pad.t, 0, h - pad.b);
  grad.addColorStop(0, "rgba(91,141,239,0.16)");
  grad.addColorStop(1, "rgba(91,141,239,0.00)");
  ctx.save();
  ctx.lineTo(X(DATA.rows[DATA.rows.length - 1].lam), h - pad.b);
  ctx.lineTo(X(DATA.rows[0].lam), h - pad.b);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
  ctx.restore();

  ctx.beginPath();
  DATA.rows.forEach((r, i) => i ? ctx.lineTo(X(r.lam), Y(r.truth)) : ctx.moveTo(X(r.lam), Y(r.truth)));
  ctx.strokeStyle = INK.accent; ctx.lineWidth = 1.6; ctx.lineJoin = "round"; ctx.stroke();

  for (const r of ROWS) dot(ctx, X(r.lam), Y(r.learned), 2.4, INK.warm);

  const sel = parseFloat(document.getElementById("lam").value);
  const near = ROWS.reduce((a, b) => Math.abs(b.lam - sel) < Math.abs(a.lam - sel) ? b : a);

  ctx.strokeStyle = "rgba(210,153,34,0.45)"; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
  ctx.beginPath(); ctx.moveTo(X(near.lam), pad.t); ctx.lineTo(X(near.lam), h - pad.b); ctx.stroke();
  ctx.setLineDash([]);
  dot(ctx, X(near.lam), Y(near.learned), 3.1, INK.warm, "rgba(210,153,34,0.55)");

  // the reading belongs next to the point, not only in a panel three inches away
  ctx.font = "9.5px ui-monospace,Consolas,monospace"; ctx.textAlign = "left";
  ctx.fillStyle = "#c8d0da";
  const lx = Math.min(w - pad.r - 62, X(near.lam) + 8);
  const ly = Math.max(pad.t + 8, Y(near.learned) - 12);
  ctx.fillText(`u* ${near.learned.toFixed(4)}`, lx, ly);

  document.getElementById("lamval").textContent = sel.toFixed(2);
  document.getElementById("u_learned").textContent = near.learned.toFixed(4);
  const err = Math.abs(near.learned - near.truth) / near.truth;
  document.getElementById("err").textContent = (100 * err).toExponential(1) + "%";
  document.getElementById("rho").textContent = near.rho === null ? "—" : near.rho.toFixed(3);
}

function drawRho() {
  const { ctx, w, h } = prepare(document.getElementById("rho_plot"));
  const pad = { l: 40, r: 12, t: 18, b: 22 };
  const top = Math.max(1.15, ...ROWS.map(r => r.rho || 0));
  const { X, Y } = axis(ctx, w, h, pad, [0, top], "rho (spectral radius)", [0.1, 0.5, 0.9, 1.0]);

  ctx.beginPath();
  ROWS.forEach((r, i) => i ? ctx.lineTo(X(r.lam), Y(r.rho)) : ctx.moveTo(X(r.lam), Y(r.rho)));
  ctx.lineTo(X(ROWS[ROWS.length - 1].lam), h - pad.b); ctx.lineTo(X(ROWS[0].lam), h - pad.b);
  ctx.closePath(); ctx.fillStyle = "rgba(91,141,239,0.13)"; ctx.fill();

  ctx.beginPath();
  ROWS.forEach((r, i) => i ? ctx.lineTo(X(r.lam), Y(r.rho)) : ctx.moveTo(X(r.lam), Y(r.rho)));
  ctx.strokeStyle = INK.accent; ctx.lineWidth = 1.6; ctx.stroke();

  // the only line in this panel that means something on its own
  const y1 = Y(1);
  ctx.strokeStyle = "rgba(229,83,75,0.75)"; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, y1); ctx.lineTo(w - pad.r, y1); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = "#e5534b"; ctx.font = "9.5px ui-monospace,Consolas,monospace";
  ctx.textAlign = "right"; ctx.fillText("1.00 — unstable above", w - pad.r - 2, y1 - 8);
}

function drawTrace() {
  const sel = parseFloat(document.getElementById("lam").value);
  const keys = Object.keys(DATA.traces);
  const key = keys.reduce((a, b) => Math.abs(parseFloat(b) - sel) < Math.abs(parseFloat(a) - sel) ? b : a);
  document.getElementById("trace_lam").textContent = parseFloat(key).toFixed(2);
  const pts = DATA.traces[key];
  const svg = document.getElementById("trace");
  const w = svg.clientWidth || 380, h = 96, pad = 16;
  // The viewBox follows the measured width. A fixed 640 viewBox with coordinates in CSS pixels
  // draws the trace into the left three quarters of its own frame.
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const X = i => pad + i / Math.max(1, pts.length - 1) * (w - 2 * pad);
  const Y = v => h - 14 - (v / 1.05) * (h - 30);

  const line = pts.map((v, i) => `${X(i)},${Y(v)}`).join(" ");
  const steps = pts.map((v, i) => {
    const r = 2.2 + 2.4 * (i / Math.max(1, pts.length - 1));
    return `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="${r.toFixed(1)}"` +
           ` fill="#5b8def" fill-opacity="${(0.45 + 0.55 * i / pts.length).toFixed(2)}"/>`;
  }).join("");
  // convergence drawn as a visible target line, not something to infer from the last dot
  const yEnd = Y(pts[pts.length - 1]).toFixed(1);
  svg.innerHTML =
    `<line x1="${pad}" y1="${yEnd}" x2="${w - pad}" y2="${yEnd}"` +
    ` stroke="rgba(255,255,255,0.10)" stroke-dasharray="3 3"/>` +
    `<polyline fill="none" stroke="rgba(91,141,239,0.55)" stroke-width="1.1" points="${line}"/>` +
    steps +
    `<text x="${pad}" y="10" fill="#7d8797" font-size="9.5"` +
    ` font-family="ui-monospace,Consolas,monospace">${pts.length} newton steps</text>`;
}

function fillTable() {
  document.getElementById("rows").innerHTML = DATA.checkpoints.map(r => `
    <tr><td class="num">${r.lam.toFixed(2)}</td><td class="num">${r.truth.toFixed(4)}</td>
    <td class="num">${r.learned === null ? "—" : r.learned.toFixed(4)}</td>
    <td class="num">${r.rel_error === null ? "—" : (100 * r.rel_error).toExponential(1) + "%"}</td>
    <td class="num">${r.rho === null ? "—" : r.rho.toFixed(3)}</td></tr>`).join("");
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
  }, 190);
}

document.getElementById("lam").addEventListener("input", () => { drawMain(); drawTrace(); });
document.getElementById("replay").addEventListener("click", replay);
drawMain(); drawRho(); drawTrace(); fillTable();
window.addEventListener("resize", () => { drawMain(); drawRho(); });
