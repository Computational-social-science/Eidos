/* Evidence views only. Axes transform recorded values; no softmax is evaluated here. */
(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("demo-data").textContent);
  const el = id => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const colors = {standard: "#f29a70", fixed: "#6ebcff", reference: "#bdc4ce"};
  const fmt = n => n === null || !Number.isFinite(Number(n)) ? "undefined" :
    Number(n) === 0 ? "0" : Number(n).toExponential(3);
  function node(parent, tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) n.setAttribute(key, String(value));
    if (text !== undefined) n.textContent = String(text);
    parent.append(n);
    return n;
  }
  function frame(svg, title) {
    const width = Math.max(260, svg.getBoundingClientRect().width);
    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} 300`);
    node(svg, "title", {}, title);
    return {svg, width, left: 66, right: width - 20, top: 25, bottom: 222};
  }
  function line(f, x1, y1, x2, y2, attrs = {}) {
    return node(f.svg, "line", {x1, y1, x2, y2, stroke: "#39414e", ...attrs});
  }
  function text(f, x, y, value, attrs = {}) {
    return node(f.svg, "text", {x, y, fill: "#b6c0cf", "font-size": 12, ...attrs}, value);
  }
  function axes(f, x, y, xticks, yticks, xformat, yformat) {
    for (const v of yticks) {
      line(f, f.left, y(v), f.right, y(v), {"stroke-opacity": .55});
      text(f, f.left - 8, y(v) + 4, yformat(v), {"text-anchor": "end"});
    }
    line(f, f.left, f.top, f.left, f.bottom);
    line(f, f.left, f.bottom, f.right, f.bottom);
    for (const v of xticks) {
      line(f, x(v), f.bottom, x(v), f.bottom + 5);
      text(f, x(v), f.bottom + 21, xformat(v), {"text-anchor": "middle"});
    }
  }
  function path(f, points, color, dashed, attrs = {}) {
    let active = false, d = "";
    for (const p of points) {
      if (!p || !p.every(Number.isFinite)) { active = false; continue; }
      d += `${active ? "L" : "M"}${p[0].toFixed(3)},${p[1].toFixed(3)} `;
      active = true;
    }
    return node(f.svg, "path", {d, fill: "none", stroke: color, "stroke-width": 1.8,
      "stroke-dasharray": dashed ? "6 4" : "none", ...attrs});
  }
  function marker(f, x, y, color, title, reference = false) {
    const n = node(f.svg, reference ? "rect" : "circle", reference ?
      {x: x - 3, y: y - 3, width: 6, height: 6, fill: "#1b2027", stroke: color} :
      {cx: x, cy: y, r: 3, fill: color});
    node(n, "title", {}, title);
  }
  function gradients(row) {
    const f = frame(el("numerics-gradient-chart"), "Selected gradient: standard, fixed and independent Decimal");
    const series = ["standard", "fixed", "reference"];
    const values = series.flatMap(name => row[`${name}_gradient`].map(Number));
    const bound = Math.max(...values.map(Math.abs));
    const limit = bound === 0 ? 1 : bound * 1.18;
    const x = i => f.left + (i + .5) * (f.right - f.left) / 3;
    const y = v => f.bottom - (v + limit) / (2 * limit) * (f.bottom - f.top);
    axes(f, x, y, [0, 1, 2], [-bound, 0, bound].filter((v,i,a) => a.indexOf(v) === i),
      i => `g${i}`, fmt);
    line(f, f.left, y(0), f.right, y(0), {stroke: "#8b97a8"});
    const bar = Math.min(16, (f.right - f.left) / 15);
    series.forEach((name, s) => row[`${name}_gradient`].forEach((value, i) => {
      const v = Number(value), cx = x(i) + (s - 1) * (bar + 2);
      const rect = node(f.svg, "rect", {x: cx - bar / 2, y: Math.min(y(v), y(0)),
        width: bar, height: Math.abs(y(v) - y(0)), fill: colors[name], "fill-opacity": name === "reference" ? .35 : .9,
        stroke: colors[name], "stroke-dasharray": name === "standard" ? "3 2" : "none"});
      node(rect, "title", {}, `${name} g${i}: ${value}`);
      if (v === 0) marker(f, cx, y(0), colors[name], `${name} g${i}: exact zero`);
    }));
    text(f, f.left, 281, "Signed gradient · local scale per selected case");
  }
  function sweep(rows, row, mode) {
    const collapse = mode === "collapse", key = collapse ? "margin" : "perturbation";
    const error = collapse ? "error" : "absolute_error";
    const points = rows.filter(r => collapse || r[key] > 0);
    const f = frame(el("numerics-sweep-chart"), "Recorded gradient error across measured inputs");
    f.bottom = 200;
    const xs = points.map(r => collapse ? r[key] : Math.log10(r[key]));
    const xmin = Math.min(...xs), xmax = Math.max(...xs);
    const positive = points.flatMap(r => [r[`standard_${error}`], r[`fixed_${error}`]])
      .filter(v => v !== null && Number.isFinite(v) && v > 0);
    const lo = positive.length ? Math.floor(Math.log10(Math.min(...positive))) : -1;
    const hi = positive.length ? Math.max(lo + 1, Math.ceil(Math.log10(Math.max(...positive)))) : 0;
    const x = v => f.left + ((collapse ? v : Math.log10(v)) - xmin) / (xmax - xmin || 1) * (f.right - f.left);
    const y = v => f.bottom - (Math.log10(v) - lo) / (hi - lo) * (f.bottom - f.top);
    const xticks = points.filter((_, i) => i % Math.max(1, Math.ceil((points.length - 1) / 4)) === 0).map(r => r[key]);
    const powers = Array.from({length: 5}, (_, i) => 10 ** (lo + i * (hi - lo) / 4));
    axes(f, x, y, xticks, powers, v => collapse ? String(v) : v.toExponential(0), v => v.toExponential(0));
    const zeroY = 254;
    line(f, f.left, zeroY, f.right, zeroY, {"stroke-dasharray": "2 4"});
    text(f, f.left - 8, zeroY + 4, "0", {"text-anchor": "end"});
    for (const name of ["standard", "fixed"]) {
      path(f, points.map(r => r[`${name}_${error}`] > 0 ? [x(r[key]), y(r[`${name}_${error}`])] : null), colors[name], name === "standard",
        {"data-series": name});
      for (const r of points) {
        const value = r[`${name}_${error}`];
        if (value === null || !Number.isFinite(value)) continue;
        marker(f, x(r[key]), value === 0 ? zeroY : y(value), colors[name], `${name}, ${r[key]}: ${fmt(value)}`);
      }
    }
    if (collapse || row[key] > 0) {
      line(f, x(row[key]), f.top, x(row[key]), zeroY + 5, {stroke: "#e5ebf3", "stroke-opacity": .6, "stroke-dasharray": "2 3", "data-cursor": "selected"});
    }
    text(f, f.left, 283, collapse ? "Logit gap · exact-zero rail below log axis" : "Requested Δ (log) · exact-zero rail below");
    el("numerics-sweep-title").textContent = `b · ${collapse ? "Relative" : "Absolute"} L2 gradient error`;
  }
  function numerical() {
    const mode = el("numerics-mode").value, dtype = el("numerics-dtype").value;
    const rows = data[mode].filter(r => r.dtype === dtype), index = Number(el("numerics-case").value), row = rows[index];
    if (!row) return;
    const slider = el("numerics-scrub");
    slider.max = String(rows.length - 1); slider.value = String(index);
    const value = mode === "collapse" ? `Gap ${row.margin}` : `Δ ${fmt(row.perturbation)}`;
    el("numerics-scrub-value").textContent = value;
    gradients(row); sweep(rows, row, mode);
    el("numerics-chart-readout").textContent = `${dtype} · ${value} · target g₀: standard ${fmt(row.standard_gradient[0])} → fixed ${fmt(row.fixed_gradient[0])} · Decimal ${fmt(row.reference_gradient[0])}` +
      (mode === "cancellation" && row.perturbation === 0 ? " · Exact equality: see the selected gradient and absolute errors below; Δ=0 has no logarithmic x coordinate." : "");
  }
  function training() {
    if (!el("training-chart")) return;
    const seed = el("training-seed").value, metric = el("training-metric").value;
    const symmetric = el("training-scale").value === "symlog", step = Number(el("training-step").value);
    const all = data.training.trajectories || [];
    const series = all.filter(s => (seed === "all" || String(s.seed) === seed) && el(`training-${s.variant}`).checked);
    const f = frame(el("training-chart"), "Measured optimizer trajectories; full curves and selected step");
    const transform = v => symmetric ? Math.sign(v) * Math.log10(1 + Math.abs(v) / 1e-12) : v;
    const inverse = v => symmetric ? Math.sign(v) * (10 ** Math.abs(v) - 1) * 1e-12 : v;
    const vals = series.flatMap(s => s.checkpoints.map(p => transform(p[metric])));
    const low = Math.min(0, ...vals), high = Math.max(0, ...vals);
    const span = high - low || 1, ymin = low - .08 * span, ymax = high + .08 * span;
    const x = v => f.left + v / data.training.steps * (f.right - f.left);
    const y = v => f.bottom - (transform(v) - ymin) / (ymax - ymin) * (f.bottom - f.top);
    axes(f, x, y, [0, .25, .5, .75, 1].map(v => v * data.training.steps),
      high === low ? [inverse(low)] : [0, .25, .5, .75, 1].map(v => inverse(low + v * (high - low))), String, fmt);
    line(f, f.left, y(0), f.right, y(0), {stroke: "#8b97a8"});
    const readouts = [];
    series.forEach(s => {
      path(f, s.checkpoints.map(p => [x(p.step), y(p[metric])]), colors[s.variant], s.variant === "standard",
        {"data-series": `${s.variant}-${s.seed}`, "stroke-opacity": .55 + .2 * Number(s.seed)});
      const p = s.checkpoints.find(p => p.step === step);
      if (p) {
        marker(f, x(p.step), y(p[metric]), colors[s.variant], `Seed ${s.seed} ${s.variant}: ${fmt(p[metric])}`, Number(s.seed) === 1);
        readouts.push({seed: s.seed, text: `${s.variant}: ${fmt(p[metric])}`});
      }
    });
    line(f, x(step), f.top, x(step), f.bottom, {stroke: "#e5ebf3", "stroke-dasharray": "2 3", "data-cursor": "step"});
    text(f, f.left, 281, "Full-batch Adam step · measured checkpoints");
    el("training-step-value").textContent = String(step);
    el("training-chart-title").textContent = metric === "parameter_displacement_l2" ? "Parameter displacement · L2" : "Held-out KL · float64 evaluation";
    const output = el("training-readout");
    output.replaceChildren();
    for (const seed of new Set(readouts.map(r => r.seed))) {
      const span = document.createElement("span");
      span.textContent = `seed ${seed} ` + readouts.filter(r => r.seed === seed).map(r => r.text).join(" → ");
      output.append(span);
    }
    if (!series.length) output.textContent = "Select a repair variant to display its measured trajectory.";
    const checkpoints = all[0]?.checkpoints || [];
    if (checkpoints.length > 1) el("training-step").step = String(checkpoints[1].step - checkpoints[0].step);
  }
  for (const id of ["numerics-mode", "numerics-dtype", "numerics-case"]) el(id).addEventListener("change", numerical);
  el("numerics-scrub").addEventListener("input", () => {
    el("numerics-case").value = el("numerics-scrub").value;
    el("numerics-case").dispatchEvent(new Event("change"));
  });
  for (const id of ["training-seed", "training-metric", "training-scale", "training-standard", "training-fixed"])
    el(id)?.addEventListener("change", training);
  el("training-step")?.addEventListener("input", training);
  const observer = new ResizeObserver(() => { numerical(); training(); });
  observer.observe(el("numerics-figure"));
  numerical(); training();
})();
