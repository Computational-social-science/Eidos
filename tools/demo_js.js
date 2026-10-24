const DATA = __DEMO__;
const ROWS = DATA.rows;
const W = 640, H = 360, PAD = {l: 52, r: 14, t: 14, b: 40};
const xOf = lam => PAD.l + (lam - 0.1) / 0.9 * (W - PAD.l - PAD.r);
const yOf = u => H - PAD.b - (u / 1.05) * (H - PAD.t - PAD.b);

function frame(ctx, w, h, pad, ymax, ylabel) {
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#232830"; ctx.beginPath();
  ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, h - pad.b); ctx.lineTo(w - pad.r, h - pad.b);
  ctx.stroke();
  ctx.fillStyle = "#98a2b3"; ctx.font = "10.5px -apple-system,Segoe UI,Arial";
  ctx.textAlign = "center";
  for (const t of [0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
    ctx.fillText(t.toFixed(1), pad.l + (t - 0.1) / 0.9 * (w - pad.l - pad.r), h - pad.b + 15);
  ctx.textAlign = "right";
  for (let v = 0; v <= ymax + 1e-9; v += ymax / 4) {
    const py = h - pad.b - (v / ymax) * (h - pad.t - pad.b);
    ctx.fillText(v.toFixed(2), pad.l - 7, py + 4);
    ctx.strokeStyle = "#1b1f26"; ctx.beginPath(); ctx.moveTo(pad.l, py);
    ctx.lineTo(w - pad.r, py); ctx.stroke();
  }
  ctx.save(); ctx.translate(14, (h + pad.t - pad.b) / 2); ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center"; ctx.fillStyle = "#98a2b3"; ctx.fillText(ylabel, 0, 0); ctx.restore();
}

function drawMain() {
  const ctx = document.getElementById("plot").getContext("2d");
  frame(ctx, W, H, PAD, 1.05, "u*");
  ctx.strokeStyle = "#5b8def"; ctx.lineWidth = 2; ctx.beginPath();
  ROWS.forEach((r, i) => i ? ctx.lineTo(xOf(r.lam), yOf(r.truth)) : ctx.moveTo(xOf(r.lam), yOf(r.truth)));
  ctx.stroke();
  ctx.fillStyle = "#e5534b";
  ROWS.forEach(r => { if (r.learned === null) return;
    ctx.beginPath(); ctx.arc(xOf(r.lam), yOf(r.learned), 2, 0, 7); ctx.fill(); });
  const sel = parseFloat(document.getElementById("lam").value);
  const near = ROWS.reduce((a, b) => Math.abs(b.lam - sel) < Math.abs(a.lam - sel) ? b : a);
  document.getElementById("lamval").textContent = sel.toFixed(2);
  document.getElementById("u_learned").textContent = near.learned === null ? "—" : near.learned.toFixed(4);
  const err = near.learned === null ? null : Math.abs(near.learned - near.truth) / near.truth;
  document.getElementById("err").textContent = err === null ? "—" : (100 * err).toExponential(1) + "%";
  document.getElementById("rho").textContent = near.rho === null ? "—" : near.rho.toFixed(3);
  ctx.strokeStyle = "#6b7480"; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(xOf(near.lam), PAD.t); ctx.lineTo(xOf(near.lam), H - PAD.b);
  ctx.stroke(); ctx.setLineDash([]);
}

function drawRho() {
  const ctx = document.getElementById("rho_plot").getContext("2d");
  const w = 420, h = 210, pad = {l: 44, r: 12, t: 12, b: 30};
  const top = Math.max(1.15, ...ROWS.map(r => r.rho || 0));
  frame(ctx, w, h, pad, top, "ρ");
  ctx.strokeStyle = "#5b8def"; ctx.lineWidth = 2; ctx.beginPath();
  ROWS.forEach((r, i) => { if (r.rho === null) return;
    const px = pad.l + (r.lam - 0.1) / 0.9 * (w - pad.l - pad.r);
    const py = h - pad.b - (r.rho / top) * (h - pad.t - pad.b);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.stroke();
  const py = h - pad.b - (1 / top) * (h - pad.t - pad.b);
  ctx.strokeStyle = "#e5534b"; ctx.setLineDash([5, 4]); ctx.lineWidth = 1;
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
  const w = svg.clientWidth || 380, h = 92;
  const ux = i => 14 + i / Math.max(1, pts.length - 1) * (w - 28);
  const uy = v => h - 12 - (v / 1.05) * (h - 24);
  svg.innerHTML = pts.map((v, i) =>
    `<circle cx="${ux(i)}" cy="${uy(v)}" r="3" fill="#5b8def" opacity="${(0.35 + 0.65 * i / pts.length).toFixed(2)}"/>`
  ).join("") + `<polyline fill="none" stroke="#5b8def" stroke-width="1.1" points="${pts.map((v, i) => `${ux(i)},${uy(v)}`).join(" ")}"/>`;
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

document.getElementById("lam").addEventListener("input", () => { drawMain(); drawTrace(); });
document.getElementById("replay").addEventListener("click", replay);
drawMain(); drawRho(); drawTrace(); fillTable();
window.addEventListener("resize", () => { drawRho(); drawTrace(); });