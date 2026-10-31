"""Build the Eidos front door: positioning, pipeline, gates, live status, and the demo.

Eidos is the reusable skeleton a research project is instantiated into: one source, dual
quality gates, a typed decision layer, provenance, and multi-format delivery. This page
has to say that before it says anything about any single gate, and every number on it is
read at build time from an artefact rather than typed.

The scientific case selects recorded Softmax Collapse/Cancellation measurements;
the report and reproduction bundle are built from the same evidence.

    python tools/build_site.py            # writes site/index.html
    python tools/build_site.py --check    # rebuild and compare with the file on disk
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from framework.surrogate import (RandomFeatureOperator, fixed_point,  # noqa: E402
                                 spectral_radius)
from audit_surrogate import training_pairs  # noqa: E402
from framework.surrogate.demo import build_demo
from numerics_case import build_case, export_case

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_view  # noqa: E402  # noqa: E402

OUT = ROOT / "site" / "index.html"
VERSIONS = ROOT / "site" / "versions.json"
MAX_VERSIONS = 50


# --------------------------------------------------------------------------- data
def bump(kind: str) -> str:
    """Raise the one version number that matters, in the one place it lives."""
    path = ROOT / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    current = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not current:
        raise SystemExit("pyproject.toml has no [project] version")
    major, minor, patch = (int(x) for x in current.group(1).split(".")[:3])
    if kind == "major":
        major, minor, patch = major + 1, 0, 0
    elif kind == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = f"{major}.{minor}.{patch}"
    path.write_text(text.replace(current.group(0), f'version = "{new}"', 1), encoding="utf-8")
    return new


def meta() -> dict:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {"version": project.get("version", "?"),
            "license": project.get("license", {}).get("text", "?")}


def chains() -> list[dict]:
    run = subprocess.run([sys.executable, "tools/audit_chains.py", "--json", "--ci"],
                         cwd=ROOT, capture_output=True, text=True, timeout=900)
    return json.loads(run.stdout)


def registry() -> list[dict]:
    rows = []
    for spec in sorted((ROOT / "projects").glob("*/project.yaml")):
        text = spec.read_text(encoding="utf-8")
        name = re.search(r"^name:\s*(\S+)", text, re.M)
        root = re.search(r"^root:\s*(\S+)", text, re.M)
        gate = re.search(r"^gate_command:\s*(\[.*\])", text, re.M)
        register = re.search(r"^validity_register:\s*(\S+)", text, re.M)
        document = re.search(r'^validity_document:\s*"?([^"\n]+)"?', text, re.M)
        expected = re.search(r'^expected_gate_s:\s*(\w+)', text, re.M)
        root_path = (spec.parent / (root.group(1) if root else "")).resolve()
        row = {"name": name.group(1) if name else spec.parent.name,
               "root": root.group(1) if root else "?",
               "root_path": str(root_path),
               "gate": gate.group(1) if gate else "?",
               "available": root_path.is_dir(),
               "register": register.group(1) if register else None,
               "document": document.group(1) if document else None,
               "gate_s": "—",
               "expected": expected.group(1).upper() if expected else None}
        if row["available"] and row["register"] and row["document"]:
            docs = [d.strip() for d in str(row["document"]).split(",") if d.strip()]
            args = [sys.executable, "tools/audit_validity.py", "--project", str(root_path),
                    "--register", row["register"]]
            for doc in docs:
                args += ["--document", doc]
            run = subprocess.run(args + ["--json"], cwd=ROOT, capture_output=True,
                                 text=True, timeout=900)
            try:
                row["gate_s"] = json.loads(run.stdout).get("status", "ERROR")
            except json.JSONDecodeError:
                row["gate_s"] = "ERROR"
        rows.append(row)
    return rows


def referee() -> dict:
    text = (ROOT / "docs" / "REFEREE_SIM.md").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^##\s+O\d+\.", text)[1:]
    return {"total": len(blocks),
            "resolved": sum(1 for b in blocks if "[RESOLVED]" in b),
            "open": sum(1 for b in blocks if "[UNRESOLVED]" in b)}


def lean_runs() -> list[dict]:
    text = (ROOT / "docs" / "CHAIN_AUDIT.md").read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        found = re.search(r"`([^`]+)`", cells[0])
        target = found.group(1) if found else ""
        if target not in ("lean-nhb", "atlas-lean"):
            continue
        rows.append({"target": target,
                     "theorem": re.sub(r"`", "", cells[1]).split("/")[-1].strip(),
                     "verdict": cells[2].replace("*", ""), "time": cells[3]})
    return rows


def decision() -> dict:
    """Latency from the chain audit, calibration from the probe artefact."""
    audit = (ROOT / "docs" / "CHAIN_AUDIT.md").read_text(encoding="utf-8")
    m = re.search(r"median\s+(\d+)\s*ms", audit)
    calib = json.loads((ROOT / "artifacts" / "decision_calibration_100.json")
                       .read_text(encoding="utf-8"))
    return {"latency_ms": int(m.group(1)) if m else None,
            "accuracy": calib.get("accuracy"),
            "abstain_answerable": calib.get("abstain_answerable"),
            "abstain_unanswerable": calib.get("abstain_unanswerable"),
            "fisher_p": calib.get("fisher_p"),
            "tau_identified": calib.get("tau_identified"),
            "min_conf": calib.get("min_confidence_correct")}


def extrapolation() -> dict:
    u, u_next, lam = training_pairs()
    inside = lam <= 0.6
    op = RandomFeatureOperator(n_features=256, seed=0).fit(u[inside], u_next[inside], lam[inside])
    rows = []
    for value in np.linspace(0.1, 1.0, 91):
        u_star, info = fixed_point(op.step, float(value), np.array([1.0]), tol=1e-9)
        truth = float(np.sqrt(value))
        err = abs(float(u_star[0]) - truth) / truth if info["converged"] else float("inf")
        rows.append({"lam": float(value),
                     "learned": float(u_star[0]) if info["converged"] else None,
                     "truth": truth, "err": err, "inside": bool(value <= 0.6)})
    inside_err = [r["err"] for r in rows if r["inside"] and np.isfinite(r["err"])]
    outside_err = [r["err"] for r in rows if not r["inside"] and np.isfinite(r["err"])]
    return {"rows": rows,
            "inside_max": max(inside_err) if inside_err else None,
            "outside_max": max(outside_err) if outside_err else None}



def contracts() -> list[dict]:
    """Probe the six external boundaries, with the sibling Quarto install if present."""
    env = os.environ.copy()
    if not env.get("QUARTO_BIN"):
        candidate = ROOT.parent / "tools" / "quarto" / "bin" / "quarto.exe"
        if candidate.is_file():
            env["QUARTO_BIN"] = str(candidate)
    run = subprocess.run([sys.executable, "tools/contract_snapshot.py", "--check",
                          "--allow-missing", "--json"], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=300)
    try:
        boundaries = json.loads(run.stdout)["boundaries"]
    except (json.JSONDecodeError, KeyError):
        return []
    # Identity strings are data: truncating one to 38 characters is how the decision service
    # appeared as "...AutoThink-GG" on the page. Keep the value whole; the chip wraps.
    return [{"name": k, "ok": bool(v.get("ok")),
             "version": str(v.get("version") or v.get("model") or v.get("reason") or "")}
            for k, v in boundaries.items()]


def evolution_record() -> dict:
    """What the framework can prove about itself, and how that has changed."""
    try:
        return json.loads((ROOT / "docs" / "EVOLUTION.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def fuzz_history() -> dict:
    """How many mutation runs are on record, and when the last one was."""
    path = ROOT / "docs" / "status" / "fuzz_history.jsonl"
    try:
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        last = json.loads(lines[-1]) if lines else {}
    except (OSError, json.JSONDecodeError):
        return {"runs": 0, "last": "", "clean_runs": 0}
    clean = sum(1 for l in lines if json.loads(l).get("ok"))
    return {"runs": len(lines), "clean_runs": clean, "last": last.get("ts", "")}


def robustness() -> dict:
    """Counts from the three audits that ask whether the chain can say no."""
    out = {"history": fuzz_history()}
    for key in ("fuzz", "chain"):
        try:
            out[key] = json.loads((ROOT / "docs" / f"{key.upper()}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out[key] = {}
    return out


def fixtures() -> dict:
    """The fixture audit's machine record: which check each fixture trips."""
    try:
        return json.loads((ROOT / "docs" / "FIXTURES.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"fixtures": [], "covered": [], "ok": False}


def collect() -> dict:
    return {"meta": meta(),
            "audit": json.loads((ROOT / "docs" / "SELF_AUDIT.json").read_text(encoding="utf-8")),
            "chains": chains(), "registry": registry(), "referee": referee(), "fixtures": fixtures(),
            "robustness": robustness(), "evolution": evolution_record(),
            "lean": lean_runs(), "decision": decision(), "extra": extrapolation(),
            "contracts": contracts(),
            "commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True).stdout.strip() or "uncommitted",
            "today": datetime.date.today().isoformat()}


# ----------------------------------------------------------------------- figures
PILL = {"PASS": "pass", "SKIP": "skip", "FAIL": "fail", "ERROR": "fail", "STALE": "skip"}


def pill(status: str) -> str:
    return f'<span class="pill {PILL.get(status, "skip")}">{html.escape(status)}</span>'


def layer_chains() -> dict[str, list[str]]:
    """Read the layer grouping from the pipeline document; never keep a second copy."""
    path = ROOT / "docs" / "pipeline.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        layers = doc.get("layers") or []
        return {row["name"]: list(row["chains"]) for row in layers if row.get("name")}
    except (OSError, json.JSONDecodeError):
        return {}


def stack_svg() -> str:
    """The seven layers of the pipeline, top = delivery, bottom = inference.

    Three things the previous version got wrong: the note collided with the last layer (it
    sat at y=357 inside a rect ending at 364), the "highlight" was two greys apart on a dark
    page so nothing was actually highlighted, and nothing showed the direction a result
    travels. All three are geometry, so all three are fixed in geometry.
    """
    layers = [("Multi-format delivery", "Quarto: LaTeX/PDF · Word · interactive HTML · code", False),
              ("Dual quality gates", "BootLoops (quantitative) · semantic suite · Gate S · human", True),
              ("Analysis and critique", "agents · failure diagnosis", False),
              ("Decision layer", "StartLux-Decision-4B: choice · yes/no · score", False),
              ("Evaluation and robustness", "Inspect · DeepEval · Promptfoo · Ragas", False),
              ("Orchestration", "Hydra · MLflow · DVC · three knowledge layers", False),
              ("Inference serving", "vLLM (batch) · Ollama (interactive) · typed decisions", False)]

    global LAYER_INDEX
    LAYER_INDEX = layer_chains()
    top, step, height = 8, 56, 48
    bottom = top + (len(layers) - 1) * step + height          # 320 + 44 = 364
    note_y = bottom + 30                                        # baseline, not glyph top
    width, box_h = 860, note_y + 12

    parts = [f'<svg viewBox="0 0 {width} {box_h}" width="100%" class="fig" role="img" '
             'aria-label="Seven-layer stack: delivery at the top, inference at the bottom; '
             'the gate layer is the only one that can stop a result from rising">',
             '<defs><marker id="up" viewBox="0 0 10 10" refX="5" refY="9" markerWidth="6" '
             'markerHeight="6" orient="auto"><path d="M1 9 L5 1 L9 9 z" '
             'style="fill:var(--accent)"/></marker></defs>']

    for i, (title, detail, is_gate) in enumerate(layers):
        y = top + i * step
        chains = "|".join(LAYER_INDEX.get(title, []))
        fill = "rgba(91,141,239,.10)" if is_gate else "rgba(255,255,255,.018)"
        stroke = "rgba(91,141,239,.60)" if is_gate else "var(--rule)"
        gate_attr = " data-gate='1'" if is_gate else ""
        parts.append(f'<g class="layer" data-chains="{chains}"{gate_attr}>')
        parts.append(f'<rect x="8" y="{y}" width="804" height="{height}" rx="7" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="{1.4 if is_gate else 1}"/>')
        parts.append(f'<circle class="lstate" cx="704" cy="{y + 24}" r="4.5" '
                     f'fill="#3a4048" stroke="rgba(0,0,0,.35)"/>')
        parts.append(f'<text x="22" y="{y + 19}" font-family="Segoe UI,Arial" font-size="12" '
                     f'font-weight="600" style="fill:var(--fg)">{title}</text>')
        parts.append(f'<text x="22" y="{y + 36}" font-family="Segoe UI,Arial" font-size="10" '
                     f'style="fill:var(--mut)">{detail}</text>')
        if is_gate:
            parts.append(f'<rect x="726" y="{y + 15}" width="72" height="18" rx="9" '
                         f'fill="rgba(91,141,239,.18)" stroke="rgba(91,141,239,.55)"/>')
            parts.append(f'<text x="762" y="{y + 28}" text-anchor="middle" '
                         f'font-family="Segoe UI,Arial" font-size="9.5" letter-spacing="1.1" '
                         f'style="fill:var(--accent)">GATE</text>')
        parts.append("</g>")

    # A result rises from inference to delivery; the gate is the choke point on that path.
    parts.append(f'<line x1="830" y1="{bottom - 6}" x2="830" y2="{top + 10}" '
                 f'stroke="rgba(91,141,239,.45)" stroke-width="1.4" stroke-dasharray="3 4" '
                 f'marker-end="url(#up)"/>')
    parts.append(f'<text x="830" y="{bottom + 12}" text-anchor="middle" font-size="9.5" '
                 f'font-family="Segoe UI,Arial" style="fill:var(--dim)">result</text>')

    parts.append(f'<text x="8" y="{note_y}" font-family="Segoe UI,Arial" font-size="10.5" '
                 'style="fill:var(--dim)">Remove the gate layer and every layer above it loses its warrant.'
                 '</text>')
    parts.append("</svg>")
    return "".join(parts)


def pipeline_html() -> str:
    steps = [
        ("01", "Instantiate", "bootstrap_project.sh · inherited gates and Quarto"),
        ("02", "Hypothesis", "lit-review · Promptfoo · human sign-off"),
        ("03", "Design & run", "Hydra · MLflow/DVC · acceptance · timing discipline"),
        ("04", "Evaluate", "BootLoops battery · Inspect · DeepEval · Ragas"),
        ("05", "Diagnose", "typed classification of the failure, with its probability"),
        ("06", "Certify", "only certified results enter the Quarto source"),
        ("07", "Draft", "dual gates on prose · human sign-off before submission"),
        ("08", "Deliver", "LaTeX/PDF · Word · HTML · executable package"),
        ("09", "Record", "skills for procedure · memory for facts · LESSONS for history"),
    ]
    items = "".join(
        f'<li><span class="n">{n}</span><div><b>{html.escape(t)}</b>'
        f'<span class="d">{html.escape(d)}</span></div></li>' for n, t, d in steps)
    return f'<ol class="pipeline">{items}</ol>'


def gate_matrix() -> str:
    """The gate matrix as a scannable object, not a wall of cells.

    The information was already right; the shape made it unreadable. Strength is carried by
    a chip (mandatory / recommended / optional), presence by a tint, and absence by a dash
    that is visibly nothing. The totals under the table are computed from the rows, so the
    sentence cannot drift from the cells.
    """
    rows = [
        ("Hypothesis", "lit-review · planted-truth", "Promptfoo · novelty", "mandatory"),
        ("Design", "tool-stewardship · timing", "DeepEval design tests", "recommended"),
        ("Execution", "acceptance · independence", "—", "optional"),
        ("Evaluation", "acceptance", "Inspect · DeepEval · Ragas", "—"),
        ("Result injection", "independence · prose-lint", "faithfulness", "—"),
        ("Manuscript", "prose-lint · ref-check", "Promptfoo style", "mandatory"),
        ("Package", "full battery", "full semantic suite", "mandatory"),
    ]
    chip = {"mandatory": "must", "recommended": "rec", "optional": "opt", "—": "none"}
    body = []
    for stage, q, sem, human in rows:
        qc = "none" if q == "—" else "has"
        sc = "none" if sem == "—" else "has"
        hc = chip[human]
        htext = "—" if human == "—" else human
        body.append(f'<tr><td class="st">{stage}</td><td class="{qc}">{q}</td>'
                    f'<td class="{sc}">{sem}</td>'
                    f'<td><span class="chip {hc}">{htext}</span></td></tr>')
    must = sum(1 for r in rows if r[3] == "mandatory")
    ungated = sum(1 for r in rows if r[2] == "—")
    return (
        '<table class="gm"><caption>Where each gate sits in the workflow. A dash is a '
        'decision that the stage is not gated there, not an oversight.</caption>'
        '<thead><tr><th>stage</th><th>quantitative</th><th>semantic</th><th>human</th></tr>'
        '</thead><tbody>' + "".join(body) + '</tbody></table>'
        f'<p class="gm-sum"><b>{must}</b> of {len(rows)} stages require a human signature · '
        f'<b>{ungated}</b> stage{"s" if ungated != 1 else ""} '
        f'{"carry" if ungated != 1 else "carries"} no semantic gate</p>'
        '<p class="gm-key"><span class="chip must">mandatory</span>'
        '<span class="chip rec">recommended</span><span class="chip opt">optional</span>'
        '<span class="chip none">not gated</span></p>')


def extrapolation_svg(extra: dict) -> str:
    rows = extra["rows"]
    W, H, pad = 620, 250, {"l": 50, "r": 12, "t": 14, "b": 34}
    x = lambda lam: pad["l"] + (lam - 0.1) / 0.9 * (W - pad["l"] - pad["r"])
    y = lambda u: H - pad["b"] - (u / 1.05) * (H - pad["t"] - pad["b"])
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" class="fig" role="img" '
             f'aria-label="Fixed points inside and outside the training interval">']
    parts.append(f'<rect x="{x(0.6):.1f}" y="{pad["t"]}" width="{x(1.0) - x(0.6):.1f}" '
                 f'height="{H - pad["t"] - pad["b"]}" fill="rgba(229,83,75,.10)"/>')
    parts.append(f'<text x="{x(0.8):.1f}" y="{pad["t"] + 13}" text-anchor="middle" '
                 f'font-family="Segoe UI,Arial" font-size="10" fill="#ef6b62">'
                 f'outside the training interval</text>')
    parts.append(f'<line x1="{pad["l"]}" y1="{H - pad["b"]}" x2="{W - pad["r"]}" '
                 f'y2="{H - pad["b"]}" stroke="#2a3038"/>')
    parts.append(f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" '
                 f'y2="{H - pad["b"]}" stroke="#2a3038"/>')
    parts.append('<polyline points="' + " ".join(
        f"{x(r['lam']):.1f},{y(r['truth']):.1f}" for r in rows) +
        '" fill="none" stroke="#5b8def" stroke-width="2"/>')
    parts.append('<polyline points="' + " ".join(
        f"{x(r['lam']):.1f},{y(r['learned']):.1f}" for r in rows if r["learned"] is not None) +
        '" fill="none" stroke="#e5534b" stroke-width="1.5"/>')
    for t in (0.2, 0.4, 0.6, 0.8, 1.0):
        parts.append(f'<text x="{x(t):.1f}" y="{H - pad["b"] + 15}" text-anchor="middle" '
                     f'font-family="Segoe UI,Arial" font-size="10" fill="#8b97a6">{t:.1f}</text>')
    for t in (0.0, 0.5, 1.0):
        parts.append(f'<text x="{pad["l"] - 7}" y="{y(t) + 4:.1f}" text-anchor="end" '
                     f'font-family="Segoe UI,Arial" font-size="10" fill="#8b97a6">{t:.1f}</text>')
    parts.append("</svg>")
    return "".join(parts)


def chain_rows(rows: list[dict]) -> str:
    def stable(detail: str) -> str:
        text = re.sub(r"\b[0-9a-f]{6,}\b", "…", str(detail))
        text = re.sub(r"\d+(?:\.\d+)?\s?(?:ms|s)\b", "…", text)
        return re.sub(r"\s+", " ", text).strip()[:104]
    return "".join(
        f"<tr><td class='mono'>{html.escape(r['chain'])}</td><td>{pill(r['status'])}</td>"
        f"<td class='detail'>{html.escape(stable(r['detail']))}</td></tr>" for r in rows)


def adopt_rows(rows: list[dict]) -> str:
    def gs(value: str) -> str:
        return pill(value) if value in PILL else f"<span class='detail'>{value}</span>"

    from framework.project import evidence_age_hours

    out = []
    for p in rows:
        verdict = p.get("gate_s", "—")
        note = ""
        # A cached verdict is not a current one. Past 24 h the row shows STALE and the age, because
        # "PASS" on its own claims a measurement that may be a week old.
        age_h = evidence_age_hours(p.get("root_path") or p.get("root") or "")             if verdict in ("PASS", "FAIL") else None
        if age_h is not None and age_h > 24.0:
            verdict = "STALE"
            note = f" <span class='detail'>(was {p.get('gate_s')}) · evidence {age_h:.0f} h old</span>"
        elif p.get("expected") == "FAIL" and p.get("gate_s") == "FAIL":
            note = " <span class='detail'>(expected)</span>"
        out.append(
            f"<tr><td class='mono'>{html.escape(p['name'])}</td><td>{html.escape(p['root'])}</td>"
            f"<td><code>{html.escape(p['gate'])}</code></td>"
            f"<td>{'present' if p['available'] else 'absent'}</td>"
            f"<td>{gs(verdict)}{note}</td></tr>")
    return "".join(out)


def lean_rows(rows: list[dict]) -> str:
    return "".join(
        f"<tr><td class='mono'>{html.escape(r['target'])}</td>"
        f"<td class='mono'>{html.escape(r['theorem'])}</td><td>{pill(r['verdict'])}</td>"
        f"<td class='num'>{html.escape(r['time'])}</td></tr>" for r in rows)


def operator_demo() -> str:
    """Interactive panel over the consumer's evidence: the sweep is the deliverable."""
    path = ROOT / "reference" / "operator_calibration" / "docs" / "evidence.json"
    if not path.exists():
        return '<p class="detail">operator evidence not built</p>'
    ev = json.loads(path.read_text(encoding="utf-8"))
    sweep = ev["sweep"]
    middle = len(sweep) // 2
    rows = json.dumps(sweep)
    return f"""<input id="tau" type="range" min="0" max="{len(sweep) - 1}" value="{middle}"
  step="1" style="width:100%;accent-color:var(--accent)" aria-label="confidence floor">
  <p style="margin:9px 0 0;font:600 12.5px/1.5 -apple-system,'Segoe UI',Arial,sans-serif">
    floor <b id="tau-v">-</b> &nbsp;·&nbsp; acted <b id="acted">-</b> &nbsp;·&nbsp;
    precision <b id="prec">-</b> &nbsp;·&nbsp; coverage <b id="cov">-</b></p>
  <script>
  (() => {{
    const S = {rows};
    const el = document.getElementById('tau');
    const v = document.getElementById('tau-v'), a = document.getElementById('acted');
    const p = document.getElementById('prec'), c = document.getElementById('cov');
    const draw = () => {{
      const r = S[Number(el.value)];
      v.textContent = r.tau.toFixed(2);
      a.textContent = r.n_acted + '/50';
      p.textContent = (r.precision * 100).toFixed(0) + '%';
      c.textContent = (r.coverage * 100).toFixed(0) + '%';
    }};
    el.addEventListener('input', draw); draw();
  }})();
  </script>"""


def render_strip() -> str:
    path = ROOT / "docs" / "RENDER_CHECK.json"
    if not path.exists():
        return '<span class="contract miss">render chain not checked</span>'
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for fmt, row in data.get("formats", {}).items():
        cls = "ok" if row.get("ok") else "miss"
        size = f"{row['bytes'] / 1024:.0f} KB" if row.get("bytes") else "no output"
        out.append(f'<span class="contract {cls}">{fmt} <b>{size}</b></span>')
    verdict = "ok" if data.get("ok") else "miss"
    out.append(f'<span class="contract {verdict}">chain <b>{"passes" if data.get("ok") else "fails"}</b></span>')
    stamp = data.get("generated", "")[:16].replace("T", " ")
    if stamp:
        # The evidence is from one machine at one time; say so instead of implying it is
        # continuously verified. CI runs this check without a LaTeX install, so it skips.
        out.append(f'<span class="contract">checked <b>{stamp}</b> on this host</span>')
    return "".join(out)


def contract_strip(rows: list[dict]) -> str:
    if not rows:
        return '<span class="contract miss">no contract probe available</span>'
    return "".join(
        f'<span class="contract {"ok" if r["ok"] else "miss"}">'
        f'{html.escape(r["name"])} <b>{html.escape(r["version"] or ("up" if r["ok"] else "down"))}</b></span>'
        for r in rows)


def demo_payload() -> str:
    data = build_case()
    export_case(ROOT / "site/reports/numerics", data)
    return json.dumps(data, allow_nan=False, separators=(",", ":"))




# -------------------------------------------------------------------------- page
def monitor_snapshot(data: dict) -> dict:
    """The monitor's state at build time, for the document's still frame."""
    try:
        status = json.loads((ROOT / "docs" / "status" / "current.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status = {}
    try:
        pipeline = json.loads((ROOT / "docs" / "pipeline.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pipeline = {}
    chains_now = status.get("chains") or {}
    signals = status.get("signals") or {}

    def stamp(ts: str) -> str:
        try:
            return (datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    .astimezone(datetime.timezone(datetime.timedelta(hours=8)))
                    .strftime("%Y-%m-%d %H:%M:%S"))
        except (ValueError, AttributeError):
            return "—"

    order = list(pipeline.get("chain_modules") or {})
    rows = [{"name": c, "state": chains_now.get(c, "IDLE")} for c in order]
    services = [{"name": name, "ok": (row or {}).get("state") == "OK"}
                for name, row in signals.items()
                if name in ("decision_service", "runtime_18434", "quarto", "dvc", "mlflow")]
    return {"asof": stamp(status.get("ts", "")), "samples": status.get("samples", 0),
            "chains": rows, "services": services, "n_chains": len(rows),
            "ok_chains": sum(1 for r in rows if r["state"] in ("PASS", "SKIP"))}


def _stamp_hkt(iso: str | None) -> str:
    """A document records when it was checked, as a date — not "9 minutes ago", which is only
    true for the minute it was rendered and makes the page look stale on every rebuild."""
    if not iso:
        return "never"
    try:
        when = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    return when.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M HKT")


def deps_table() -> str:
    """Dependency pins, on the page that documents the framework rather than the one that runs it."""
    try:
        sense = json.loads((ROOT / "docs" / "status" / "updates.json").read_text(encoding="utf-8"))
        lock = json.loads((ROOT / "lock" / "versions.lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "<p class='mono'>not sensed yet</p>"
    labels = {"decision_model": "decision model"}
    sys.path.insert(0, str(ROOT))
    from framework import updates as upd

    rows = []
    for name, item in (sense.get("items") or {}).items():
        pin = ((lock.get("pins") or {}).get(name) or {}).get("version") or item.get("pinned") or "—"
        # Measured now, not remembered from the last sense: a snapshot's `installed` goes stale the
        # moment anything is installed, and a table that repeats it will claim a divergence exists
        # or hide one that does.
        # No `installed` column: a committed page cannot claim what one machine has installed,
        # and rebuilding it elsewhere would make the page differ from the file for that reason
        # alone. The host is measured by `update_operator.py status`, which runs on the host.
        upstream_state = item.get("state") or "unknown"
        offer = item.get("available")
        state = upstream_state
        cls = {"behind": "warn", "unknown": "warn", "unmonitored": "dim"}.get(state, "")
        upstream = (f"<b>{offer}</b>" if upstream_state == "behind" and offer
                    else {"unmonitored": "no upstream", "unknown": "unreachable"}.get(
                        upstream_state, "—"))
        rows.append(f"<tr><td class='mono'>{html.escape(labels.get(name, name))}</td>"
                    f"<td class='mono'>{html.escape(str(pin))}</td>"
                    f"<td class='{cls}'>{upstream}</td>"
                    f"<td class='mono {cls}'>{html.escape(state)}</td></tr>")
    checked = _stamp_hkt(sense.get("ts"))
    return ("<div class='tw'><table><caption>Pins are the contract; the upstream column is what "
            "sensing found. A promotion needs a passing try, and <code>apply</code> is the only "
            "command that installs. What a particular host has installed is reported by "
            "<code>update_operator.py status</code>, not recorded here.</caption>"
            "<thead><tr><th>dependency</th><th>pinned</th>"
            "<th>upstream</th><th>state</th></tr></thead><tbody>"
            + "".join(rows) +
            f"</tbody></table></div><p class='mono' style='margin:6px 0 0;color:var(--dim)'>"
            f"sensed {html.escape(checked)}</p>")


def render(data: dict) -> str:
    """Assemble the page. Measurement stays here; layout lives in site_page."""
    import site_page

    audit = data["audit"]
    rows = data["chains"]
    claims = yaml.safe_load((ROOT / "analysis" / "CLAIMS.yaml").read_text(encoding="utf-8"))
    extra, dec = data["extra"], data["decision"]
    lab = build_demo()
    contracts = data.get("contracts", [])
    version = data["meta"]["version"]
    nvers = data.get("versions", 0)

    ctx = {
        "version": version,
        "commit": data["commit"],
        "date": data["today"],
        "nvers": nvers,
        "nchains": len(rows),
        "npass": sum(1 for r in rows if r["status"] == "PASS"),
        "nskip": sum(1 for r in rows if r["status"] == "SKIP"),
        "ntests": audit.get("tests_collected", "?"),
        "cov": audit.get("coverage_total", "?"),
        "nclaims": len(claims["claims"]),
        "nopen": data["referee"]["open"],
        "nres": data["referee"]["total"],
        "nadopt": len(data["registry"]),
        "ncontracts": len(contracts),
        "fixtures": data.get("fixtures") or {"fixtures": [], "covered": [], "ok": False},
        "robustness": data.get("robustness") or {},
        "evolution": data.get("evolution") or {},
        "latency": dec["latency_ms"] or "—",
        "acc": f"{100 * dec['accuracy']:.1f}%" if dec["accuracy"] is not None else "—",
        "abs_a": (f"{100 * dec['abstain_answerable']:.0f}%"
                  if dec["abstain_answerable"] is not None else "—"),
        "abs_u": (f"{100 * dec['abstain_unanswerable']:.0f}%"
                  if dec["abstain_unanswerable"] is not None else "—"),
        "fisher": f"{dec['fisher_p']:.1e}" if dec["fisher_p"] else "—",
        "tau": dec["tau_identified"],
        "minconf": f"{dec['min_conf']:.2f}" if dec["min_conf"] is not None else "—",
        "pipeline": pipeline_html(),
        "stack": stack_svg(),
        "matrix": gate_matrix(),
        "lean_rows": lean_rows(data["lean"]),
        "consumers": adopt_rows(data["registry"]),
        "contracts": contract_strip(contracts),
        "render": render_strip(),
        "opdemo": operator_demo(),
        "extrap": extrapolation_svg(extra),
        "inmax": f"{100 * (extra['inside_max'] or 0):.4f}%",
        "outmax": f"{100 * (extra['outside_max'] or 0):.2f}%",
        "grid": len(lab["rows"]),
        "demo": demo_payload(),
        "rail": site_page.rail(data["commit"], data["today"], version, nvers),
        "deps": deps_table(),
        "monitor": monitor_snapshot(data),
    }
    return site_page.render(ctx)


def versions() -> list[dict]:
    if not VERSIONS.is_file():
        return []
    try:
        return json.loads(VERSIONS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def record_release(data: dict) -> list[dict]:
    """Append this build to the release history.

    Only called with --release: a build on every save would make the history noise, and
    an entry that changes on every run is not a release.
    """
    audit = data["audit"]
    entry = {"version": data["meta"]["version"], "date": data["today"],
             "commit": data["commit"],
             "metrics": {"tests": audit.get("tests_collected"),
                         "coverage": audit.get("coverage_total"),
                         "chains": len(data["chains"]),
                         "open_objections": data["referee"]["open"],
                         "decision_ms": data["decision"]["latency_ms"],
                         # Self-evolution is a capability, so it belongs in the release record:
                         # how many defects the instruments have caught, and how many remain.
                         "blind_spots_found": ((data.get("evolution") or {}).get("evolution") or {}
                                               ).get("blind_spots_found"),
                         "blind_spots_open": ((data.get("evolution") or {}).get("evolution") or {}
                                              ).get("blind_spots_open"),
                         "instruments": len(((data.get("evolution") or {}).get("state") or {}
                                             ).get("instruments") or [])}}
    rehearsal = subprocess.run([sys.executable, "tools/release_gate.py"], cwd=ROOT,
                               capture_output=True, text=True, timeout=1800)
    print(rehearsal.stdout.strip()[-1200:])
    if rehearsal.returncode != 0:
        print("[FAIL] release refused: the framework could not onboard a new project", file=sys.stderr)
        raise SystemExit(1)

    history = versions()
    if history and history[-1].get("commit") == entry["commit"]:
        history[-1] = entry          # same commit rebuilt: replace, do not duplicate
    else:
        history.append(entry)
    history = history[-MAX_VERSIONS:]
    VERSIONS.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return history


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--bump", choices=("major", "minor", "patch"), default="",
                    help="raise the version in pyproject.toml before building")
    ap.add_argument("--release", action="store_true",
                    help="append this build to site/versions.json")
    args = ap.parse_args(argv)
    if args.bump:
        print(f"version -> {bump(args.bump)}")

    data = collect()
    if args.release:
        data["versions"] = len(record_release(data))
    else:
        data["versions"] = len(versions())
    page = render(data)
    if args.check:
        if not OUT.is_file():
            print(f"[FAIL] {OUT} has not been built")
            return 1
        # The page names the commit it was built from; committing the rebuilt page changes
        # that name, so a byte comparison would report "stale" every time. Normalise the two
        # fields that depend on HEAD itself, and compare the rest.
        # Two kinds of volatile text: the commit the page names (changes when this page is
        # committed) and the monitor snapshot (a still frame of a live system). Comparing
        # either byte-for-byte would report "stale" for reasons that are not staleness.
        volatile = re.compile(
            r"<!--snapshot:start-->.*?<!--snapshot:end-->|build [0-9a-f]{7,40}"
            r"|\d+ recorded builds?|from <code>[0-9a-f]{7,40}</code>", re.S)
        # The control block carries a sampling timestamp and run counts; comparing it byte
        # for byte would report "stale" on every rebuild. Structure is compared, the live
        # numbers are not.
        if volatile.sub("", OUT.read_text(encoding="utf-8")) != volatile.sub("", page):
            print("[FAIL] site/index.html is stale; rebuild with tools/build_site.py")
            return 1
        print("site is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(page) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
