/* Presentation only: values, errors and qualification are measured by the Python producer.
   Native selectors inspect immutable evidence; there is no browser numerical kernel. */
(() => {
  "use strict";
  const DATA = JSON.parse(document.getElementById("demo-data").textContent);
  const el = id => document.getElementById(id);
  const mode = el("numerics-mode"), dtype = el("numerics-dtype"), choice = el("numerics-case");
  const number = value => value === null || value === undefined ? "undefined" : Number(value).toExponential(5);
  const parameter = row => mode.value === "collapse" ? row.margin : row.perturbation;
  const parameterText = row => mode.value === "collapse" ? String(row.margin) : number(row.perturbation);
  const rows = () => DATA[mode.value].filter(row => row.dtype === dtype.value);

  function cell(tag, text, numeric = false) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (numeric) node.className = "num";
    if (tag === "th") node.scope = "row";
    return node;
  }

  function errorText(row, key, compact = false) {
    if (row.stationary || row.reference_norm === 0) return compact ? "undefined" : "undefined at zero reference";
    if (row[key] !== null && row[key] !== undefined) return number(row[key]);
    return "undefined (see evidence)";
  }

  function renderGradients(row) {
    const body = el("numerics-gradients");
    body.replaceChildren();
    row.reference_gradient.forEach((reference, index) => {
      const tr = document.createElement("tr");
      const ref = cell("td", number(reference), true);
      ref.title = String(reference);
      tr.append(cell("th", `g${index}`), cell("td", number(row.standard_gradient[index]), true),
                cell("td", number(row.fixed_gradient[index]), true), ref);
      body.append(tr);
    });
    el("numerics-standard-error").textContent = errorText(row, "standard_error");
    el("numerics-fixed-error").textContent = errorText(row, "fixed_error");
  }

  function renderRegime(selected) {
    const checkpoints = new Set([0, 10, 16, 18, 20, 36, 40, 60, 80]);
    const regime = rows().filter(row => mode.value === "cancellation" || checkpoints.has(row.margin) || row === selected);
    const body = el("numerics-regime");
    body.replaceChildren();
    for (const row of regime) {
      const tr = document.createElement("tr");
      if (row === selected) tr.setAttribute("aria-current", "true");
      tr.append(cell("th", parameterText(row)), cell("td", errorText(row, "standard_error", true), true),
                cell("td", errorText(row, "fixed_error", true), true));
      body.append(tr);
    }
    const axis = mode.value === "collapse" ? "Logit gap" : "Requested perturbation";
    el("numerics-regime-axis").textContent = mode.value === "collapse" ? axis : "Requested Δ";
    el("numerics-regime-caption").textContent = `${axis} checkpoints · ${dtype.value} · relative L2 gradient error`;
  }

  function inspect() {
    const row = rows()[Number(choice.value)];
    if (!row) return;
    renderGradients(row);
    renderRegime(row);
    if (mode.value === "collapse") {
      el("numerics-case-label").textContent = "Logit gap";
      el("numerics-explanation").textContent = "One dominant target, two non-target classes. The fixed kernel sums non-target gradients before negating their sum at the target.";
      el("numerics-status").textContent = `${dtype.value} · logit gap ${row.margin} · target class 0`;
      el("numerics-details").textContent = `Loss: standard ${number(row.standard_loss)}; fixed ${number(row.fixed_loss)}. Absolute gradient sum: standard ${number(row.standard_residual)}; fixed ${number(row.fixed_residual)}.`;
      el("numerics-inputs").textContent = "";
    } else {
      el("numerics-case-label").textContent = "Requested perturbation";
      el("numerics-explanation").textContent = "Nearby student and teacher logits. The fixed kernel works with centered logit differences using log1p and expm1, rather than subtracting rounded probabilities.";
      const stationary = row.stationary || row.reference_norm === 0;
      el("numerics-status").textContent = `${dtype.value} · requested perturbation ${number(row.perturbation)}${stationary ? " · equal represented distributions" : ""}`;
      let detail = `Independent reference gradient norm: ${number(row.reference_norm)}.`;
      if (stationary) {
        detail += row.standard_gradient.some(value => value !== 0) ? " Standard gradient is nonzero at stationarity." : " Standard gradient is zero at stationarity in this case.";
        detail += " Relative error is undefined at zero reference.";
      }
      if (row.standard_absolute_error !== undefined) {
        detail += ` Absolute L2 error: standard ${number(row.standard_absolute_error)}; fixed ${number(row.fixed_absolute_error)}.`;
      }
      el("numerics-details").textContent = detail;
      el("numerics-inputs").textContent = `Student ${JSON.stringify(row.student)} · Teacher ${JSON.stringify(row.teacher)} · Represented Δ [${row.represented_delta.map(number).join(", ")}]`;
    }
  }

  function populate(preferred) {
    const figure = DATA.figures && DATA.figures[dtype.value];
    if (figure) {
      el("numerics-figure-svg").href = figure.svg;
      el("numerics-figure-pdf").href = figure.pdf;
    }
    const cases = rows();
    choice.replaceChildren();
    cases.forEach((row, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = parameterText(row);
      choice.append(option);
    });
    const wanted = preferred === undefined ? (mode.value === "collapse" ? 18 : 1e-7) : preferred;
    const index = cases.findIndex(row => parameter(row) === wanted);
    choice.value = String(index < 0 ? 0 : index);
    choice.disabled = cases.length === 0;
    if (cases.length === 0) el("numerics-status").textContent = "No filed cases for this selection; inspect the evidence downloads.";
    inspect();
  }

  mode.addEventListener("change", () => populate());
  dtype.addEventListener("change", () => populate());
  choice.addEventListener("change", inspect);
  populate();
})();
