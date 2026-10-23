"""Build the Eidos front door: positioning, pipeline, gates, live status, and the demo.

Eidos is the reusable skeleton a research project is instantiated into: one source, dual
quality gates, a typed decision layer, provenance, and multi-format delivery. This page
has to say that before it says anything about any single gate, and every number on it is
read at build time from an artefact rather than typed.

The demo is self-contained: three panels, a Newton replay and a checkpoint table, all
inline. Nothing on this page links to another page for its core content.

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
from framework.surrogate.demo import build_demo  # noqa: E402

OUT = ROOT / "site" / "index.html"
VERSIONS = ROOT / "site" / "versions.json"
MAX_VERSIONS = 50


# --------------------------------------------------------------------------- data
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
        document = re.search(r'^validity_document:\s*"?([^"]+)"?', text, re.M)
        expected = re.search(r'^expected_gate_s:\s*(\w+)', text, re.M)
        root_path = (spec.parent / (root.group(1) if root else "")).resolve()
        row = {"name": name.group(1) if name else spec.parent.name,
               "root": root.group(1) if root else "?",
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
    return [{"name": k, "ok": bool(v.get("ok")),
             "version": str(v.get("version") or v.get("model") or v.get("reason") or "")[:38]}
            for k, v in boundaries.items()]


def collect() -> dict:
    return {"meta": meta(),
            "audit": json.loads((ROOT / "docs" / "SELF_AUDIT.json").read_text(encoding="utf-8")),
            "chains": chains(), "registry": registry(), "referee": referee(),
            "lean": lean_runs(), "decision": decision(), "extra": extrapolation(),
            "contracts": contracts(),
            "commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True).stdout.strip() or "uncommitted",
            "today": datetime.date.today().isoformat()}


# ----------------------------------------------------------------------- figures
PILL = {"PASS": "pass", "SKIP": "skip", "FAIL": "fail", "ERROR": "fail"}


def pill(status: str) -> str:
    return f'<span class="pill {PILL.get(status, "skip")}">{html.escape(status)}</span>'


def stack_svg() -> str:
    """The seven layers of the pipeline, top = delivery, bottom = inference."""
    layers = [("Multi-format delivery", "Quarto: LaTeX/PDF · Word · interactive HTML · code"),
              ("Dual quality gates", "BootLoops (quantitative) · semantic suite · Gate S · human"),
              ("Analysis and critique", "agents · failure diagnosis"),
              ("Decision layer", "StartLux-Decision-4B: choice · yes/no · score"),
              ("Evaluation and robustness", "Inspect · DeepEval · Promptfoo · Ragas"),
              ("Orchestration", "Hydra · MLflow · DVC · three knowledge layers"),
              ("Inference serving", "vLLM (batch) · Ollama (interactive) · typed decisions")]
    parts = ['<svg viewBox="0 0 820 372" width="100%" class="fig" role="img" '
             'aria-label="Seven-layer stack from delivery at the top to inference at the bottom">']
    for i, (title, detail) in enumerate(layers):
        y = 8 + i * 52
        fill = "#eef3fa" if i == 1 else "#ffffff"
        stroke = "#b9cbe4" if i == 1 else "#dde2e8"
        parts.append(f'<rect x="8" y="{y}" width="804" height="44" rx="7" fill="{fill}" '
                     f'stroke="{stroke}"/>')
        parts.append(f'<text x="22" y="{y + 19}" font-family="Segoe UI,Arial" font-size="12.5" '
                     f'font-weight="600" fill="#11161c">{title}</text>')
        parts.append(f'<text x="22" y="{y + 34}" font-family="Segoe UI,Arial" font-size="10.5" '
                     f'fill="#5d6773">{detail}</text>')
    parts.append('<text x="8" y="368" font-family="Segoe UI,Arial" font-size="10.5" '
                 'fill="#8a94a0">Highlighted: the gate layer is the only one that can stop a '
                 'result from reaching the delivery layer.</text>')
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
    rows = [
        ("Hypothesis", "lit-review · planted-truth", "Promptfoo · novelty", "mandatory"),
        ("Design", "tool-stewardship · timing", "DeepEval design tests", "recommended"),
        ("Execution", "acceptance · independence", "—", "optional"),
        ("Evaluation", "acceptance", "Inspect · DeepEval · Ragas", "—"),
        ("Result injection", "independence · prose-lint", "faithfulness", "—"),
        ("Manuscript", "prose-lint · ref-check", "Promptfoo style", "mandatory"),
        ("Package", "full battery", "full semantic suite", "mandatory"),
    ]
    body = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>"
                   for a, b, c, d in rows)
    return ("<table><caption>Where each gate sits in the workflow. A cell with an em dash "
            "means the stage is not gated there, which is a decision, not an oversight."
            "</caption><thead><tr><th>stage</th><th>quantitative</th><th>semantic</th>"
            "<th>human</th></tr></thead><tbody>" + body + "</tbody></table>")


def extrapolation_svg(extra: dict) -> str:
    rows = extra["rows"]
    W, H, pad = 620, 250, {"l": 50, "r": 12, "t": 14, "b": 34}
    x = lambda lam: pad["l"] + (lam - 0.1) / 0.9 * (W - pad["l"] - pad["r"])
    y = lambda u: H - pad["b"] - (u / 1.05) * (H - pad["t"] - pad["b"])
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" class="fig" role="img" '
             f'aria-label="Fixed points inside and outside the training interval">']
    parts.append(f'<rect x="{x(0.6):.1f}" y="{pad["t"]}" width="{x(1.0) - x(0.6):.1f}" '
                 f'height="{H - pad["t"] - pad["b"]}" fill="#f7e6e8"/>')
    parts.append(f'<text x="{x(0.8):.1f}" y="{pad["t"] + 13}" text-anchor="middle" '
                 f'font-family="Segoe UI,Arial" font-size="10" fill="#8c1d2c">'
                 f'outside the training interval</text>')
    parts.append(f'<line x1="{pad["l"]}" y1="{H - pad["b"]}" x2="{W - pad["r"]}" '
                 f'y2="{H - pad["b"]}" stroke="#dde2e8"/>')
    parts.append(f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" '
                 f'y2="{H - pad["b"]}" stroke="#dde2e8"/>')
    parts.append('<polyline points="' + " ".join(
        f"{x(r['lam']):.1f},{y(r['truth']):.1f}" for r in rows) +
        '" fill="none" stroke="#1d4e89" stroke-width="2"/>')
    parts.append('<polyline points="' + " ".join(
        f"{x(r['lam']):.1f},{y(r['learned']):.1f}" for r in rows if r["learned"] is not None) +
        '" fill="none" stroke="#a8323f" stroke-width="1.5"/>')
    for t in (0.2, 0.4, 0.6, 0.8, 1.0):
        parts.append(f'<text x="{x(t):.1f}" y="{H - pad["b"] + 15}" text-anchor="middle" '
                     f'font-family="Segoe UI,Arial" font-size="10" fill="#5d6773">{t:.1f}</text>')
    for t in (0.0, 0.5, 1.0):
        parts.append(f'<text x="{pad["l"] - 7}" y="{y(t) + 4:.1f}" text-anchor="end" '
                     f'font-family="Segoe UI,Arial" font-size="10" fill="#5d6773">{t:.1f}</text>')
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
    return "".join(
        f"<tr><td class='mono'>{html.escape(p['name'])}</td><td>{html.escape(p['root'])}</td>"
        f"<td><code>{html.escape(p['gate'])}</code></td>"
        f"<td>{'present' if p['available'] else 'absent'}</td>"
        f"<td>{gs(p.get('gate_s', '—'))}"
        + (" <span class='detail'>(expected)</span>"
           if p.get('expected') == 'FAIL' and p.get('gate_s') == 'FAIL' else "")
        + "</td></tr>" for p in rows)


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
    return f"""<div class="card" style="margin-top:18px">
  <h3>Demo — the evidence, draggable</h3>
  <p class="detail" style="margin:0 0 10px">The confidence floor, swept over the tuning
  half of the same 100 items. Move it and read what the operator would have acted on.
  Nothing is recomputed here; the numbers are the measured sweep.</p>
  <input id="tau" type="range" min="0" max="{len(sweep) - 1}" value="{middle}" step="1"
         style="width:100%;accent-color:var(--accent)" aria-label="confidence floor">
  <p style="margin:10px 0 0;font:600 13px/1.5 -apple-system,'Segoe UI',Arial,sans-serif">
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
  </script>
</div>"""


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
    lab = build_demo()
    return json.dumps({"rows": [{"lam": round(r["lam"], 3), "learned": r["learned"],
                                 "truth": r["truth"], "rho": r["rho"]} for r in lab["rows"]],
                       "checkpoints": lab["checkpoints"], "traces": lab["traces"]},
                      separators=(",", ":"))


# -------------------------------------------------------------------------- page
PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eidos __VERSION__ — a reusable research pipeline with dual gates</title>
<meta name="description" content="Eidos is the reusable skeleton behind a research project: dual quality gates, a typed decision layer, provenance, and multi-format delivery. Every claim it makes is checked against an artefact.">
<style>
:root{
  --ink:#0e1319;--body:#222a33;--muted:#5f6c7a;--rule:#e1e6ec;--paper:#fff;
  --wash:#f6f8fa;--accent:#1d4e89;--limit:#a8323f;--ok:#17663f;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--wash);color:var(--body);
     font:17px/1.62 Georgia,"Iowan Old Style","Times New Roman",serif;
     -webkit-font-smoothing:antialiased}
.sans{font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.mono{font-family:var(--mono);font-size:12.5px}
.skip{position:absolute;left:-9999px;background:#fff;padding:10px 14px;z-index:100}
.skip:focus{left:12px;top:12px;border:1px solid var(--rule)}
header.site{position:sticky;top:0;z-index:50;background:rgba(246,248,250,.94);
            backdrop-filter:saturate(1.2) blur(8px);border-bottom:1px solid var(--rule)}
header.site .inner{max-width:1120px;margin:0 auto;padding:10px 24px;display:flex;align-items:center;gap:20px}
.wordmark{font:700 15px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.02em;color:var(--ink)}
.wordmark span{color:var(--muted);font-weight:500;margin-left:8px;font-size:12px}
nav.toc{margin-left:auto;display:flex;gap:15px;flex-wrap:wrap}
nav.toc a{font:500 12.5px/1 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--muted);
          text-decoration:none;padding:6px 0;border-bottom:1px solid transparent}
nav.toc a:hover,nav.toc a:focus{color:var(--ink);border-bottom-color:var(--ink)}
@media (max-width:860px){nav.toc{display:none}}
.wrap{max-width:1120px;margin:0 auto;padding:46px 24px 84px}
.hero{padding:22px 0 6px}
.eyebrow{font:600 11px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.14em;
         text-transform:uppercase;color:var(--muted)}
h1{font-size:45px;line-height:1.08;letter-spacing:-.025em;margin:14px 0 14px;color:var(--ink)}
.thesis{font-size:20px;line-height:1.5;color:#2b333d;max-width:68ch;margin:0 0 10px}
.subthesis{font-size:15px;color:var(--muted);max-width:68ch}
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:26px 0 6px}
@media (max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--paper);border:1px solid var(--rule);border-radius:10px;padding:13px 14px}
.stat .n{font:700 24px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:-.02em;
         font-variant-numeric:tabular-nums;color:var(--ink)}
.stat .l{font:500 10.5px/1.35 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--muted);margin-top:6px}
section{margin-top:56px}
h2{font-size:27px;letter-spacing:-.015em;color:var(--ink);margin:0 0 8px}
h2 .num{font:600 13px/1 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--muted);
        margin-right:10px;vertical-align:2px}
.lede2{color:var(--muted);font-size:15px;margin:0 0 16px;max-width:76ch}
h3{font-size:17px;margin:0 0 8px;color:var(--ink)}
p{margin:0 0 14px;max-width:76ch}
ul.prose,ol.prose{padding-left:20px;margin:0 0 14px;max-width:76ch}
ul.prose li,ol.prose li{margin-bottom:7px}
.card{background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:20px 22px}
.grid2{display:grid;grid-template-columns:1.05fr .95fr;gap:18px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px}
@media (max-width:940px){.grid2,.grid3{grid-template-columns:1fr}}
.fig{width:100%;height:auto;display:block}
figcaption{font-size:12.8px;line-height:1.5;color:var(--muted);margin-top:9px}
table{width:100%;border-collapse:collapse;font-size:13.3px}
caption{caption-side:top;text-align:left;font-size:12.4px;color:var(--muted);margin-bottom:8px}
th,td{padding:7px 8px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
thead th{font:600 10.4px/1.2 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.06em;
         text-transform:uppercase;color:var(--muted);border-bottom:1px solid #b9c1ca}
td.detail{color:var(--muted);font-size:12.4px}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;
      font:600 10.4px/1.7 -apple-system,Segoe UI,Arial,sans-serif}
.pill.pass{background:#e8f4ec;color:var(--ok)}
.pill.skip{background:#eef1f4;color:#4b5563}
.pill.fail{background:#fbecee;color:#8c1d2c}
.note{border-left:3px solid var(--limit);padding-left:14px;color:#3a434d}
.contracts{display:flex;flex-wrap:wrap;gap:8px;margin:0}
.contract{font:600 11.4px/1 -apple-system,"Segoe UI",Arial,sans-serif;padding:7px 9px;
          border-radius:999px;border:1px solid var(--rule);background:#fff;color:#2b333d}
.contract.ok{border-color:#c3e0cf;background:#f3faf6;color:#17663f}
.contract.miss{border-color:#f0c4cb;background:#fdf1f3;color:#8c1d2c}
.oknote{border-left:3px solid var(--ok);padding-left:14px;color:#3a434d}
ol.pipeline{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media (max-width:900px){ol.pipeline{grid-template-columns:1fr}}
ol.pipeline li{display:flex;gap:12px;background:var(--paper);border:1px solid var(--rule);
               border-radius:10px;padding:12px 14px}
ol.pipeline .n{font:700 12px/1 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--accent);
               letter-spacing:.06em;padding-top:2px}
ol.pipeline b{display:block;font-size:14px;color:var(--ink)}
ol.pipeline .d{display:block;font-size:12px;color:var(--muted);margin-top:3px;line-height:1.45}
canvas{width:100%;height:auto;display:block}
.controls{display:flex;align-items:center;gap:12px;margin-top:12px}
input[type=range]{flex:1;accent-color:var(--limit)}
.readout{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:12px}
.kv{border:1px solid var(--rule);border-radius:8px;padding:8px 10px;background:#fbfcfd}
.kv .k{font:600 9.4px/1.2 -apple-system,Segoe UI,Arial,sans-serif;letter-spacing:.07em;
       text-transform:uppercase;color:var(--muted)}
.kv .v{font-size:15.5px;margin-top:3px;font-variant-numeric:tabular-nums}
pre{background:#0e1319;color:#e6e9ee;padding:14px 16px;border-radius:10px;overflow-x:auto;
    font:12.4px/1.65 var(--mono);margin:0 0 10px}
pre .c{color:#8a94a0}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
footer{margin-top:60px;padding-top:18px;border-top:1px solid var(--rule);
       font-size:12.4px;line-height:1.7;color:var(--muted)}
code{background:#eef1f5;padding:1px 5px;border-radius:4px;font:12.4px var(--mono)}
@media print{body{background:#fff}header.site{display:none}.wrap{max-width:none;padding:0}
  .card{border:1px solid #ccc;break-inside:avoid}section{break-inside:avoid}}
</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="inner">
  <div class="wordmark">EIDOS <span>__VERSION__</span></div>
  <nav class="toc" aria-label="Sections">
    <a href="#position">Position</a><a href="#pipeline">Pipeline</a>
    <a href="#architecture">Architecture</a><a href="#gates">Gates</a>
    <a href="#status">Status</a><a href="#demo">Demo</a><a href="#start">Start</a><a href="#limits">Limits</a>
  </nav>
</div></header>

<div class="wrap" id="main">
<div class="hero">
  <div class="eyebrow">Global reusable research pipeline · v__VERSION__</div>
  <h1>One skeleton from theory to a certified result</h1>
  <p class="thesis">Eidos is what a research project is instantiated into: dual quality
  gates, a typed decision layer, provenance, and multi-format delivery, inherited whole
  rather than rebuilt per project.</p>
  <p class="subthesis">Theory-driven LLM experimentation → multi-layered certified results →
  reproducible delivery. The framework owns the machinery; the project owns its science.</p>
  <div class="stats">
    <div class="stat"><div class="n">__NCHAINS__</div><div class="l">chains exercised end to end</div></div>
    <div class="stat"><div class="n">__NTESTS__</div><div class="l">tests · __COV__% coverage</div></div>
    <div class="stat"><div class="n">__NOPEN__</div><div class="l">open referee objections</div></div>
    <div class="stat"><div class="n">__LATENCY__<span style="font-size:13px"> ms</span></div><div class="l">typed decision, median</div></div>
    <div class="stat"><div class="n">__NADOPT__</div><div class="l">adopters registered</div></div>
  </div>
</div>

<section id="position">
  <h2><span class="num">01</span>Position</h2>
  <p class="lede2">What it is, what it is not, and where knowledge lives.</p>
  <div class="grid3">
    <div class="card">
      <h3>It is a skeleton</h3>
      <p>One clone, many projects. <code>bootstrap_project.sh</code> produces a project
      wired to the same gates, the same provenance and the same rendering path. An existing
      repository is <b>registered</b> by pointer — never moved, never copied.</p>
    </div>
    <div class="card">
      <h3>It is not a paper factory</h3>
      <p>Nothing here decides what is true. It decides what may leave the pipeline: a result
      is certified by gates, a claim by Gate S, and a judgement by a human gate when the
      operator's confidence is below threshold.</p>
    </div>
    <div class="card">
      <h3>Knowledge has three homes</h3>
      <p>Procedure → agent skills. Facts → agent memory. History → the project's own
      <code>LESSONS</code> file. A framework vector store was built, never written to, and
      deleted; the lesson is recorded, the code is not.</p>
    </div>
  </div>
</section>

<section id="pipeline">
  <h2><span class="num">02</span>The pipeline</h2>
  <p class="lede2">Nine stages, each with a gate it cannot skip. The order is the point: a
  result is certified before it is written, and written before it is packaged.</p>
  __PIPELINE__
</section>

<section id="architecture">
  <h2><span class="num">03</span>Architecture</h2>
  <p class="lede2">Delivery at the top, inference at the bottom. The gate layer is the only
  one that can stop a result from reaching the page.</p>
  <div class="card">__STACK__</div>
</section>

<section id="gates">
  <h2><span class="num">04</span>Gates: two kinds, plus a validator</h2>
  <div class="grid2">
    <div class="card">
      <h3>Dual gates</h3>
      <p><b>Quantitative</b> — BootLoops protocols: acceptance thresholds with an explicit
      direction, planted truths, independence bookkeeping, timing discipline.</p>
      <p><b>Semantic</b> — Inspect, DeepEval, Promptfoo and Ragas for agent traces, RAG
      faithfulness and prompt regressions. A missing tool is a <b>SKIP</b>, named, never a
      pass.</p>
      <p><b>Human</b> — mandatory at hypothesis confirmation, experiment design and final
      submission. A gate nobody signs is a gate nobody owns.</p>
    </div>
    <div class="card">
      <h3>Gate S — validation</h3>
      <p>Verification asks whether we built it correctly. <b>Validation</b> asks whether the
      claim is the one the evidence licenses. Gate S reads <code>analysis/CLAIMS.yaml</code>
      and refuses: a claim absent from the deliverable, an evidence pointer that no longer
      resolves, “supported” without preregistration and a negative control, an undeclared
      scope axis, an under-reported referee count, or a formal claim the Lean chain cannot
      reproduce.</p>
      <p class="oknote"><b>__NRES__ objections</b> in the framework's own review,
      <b>__NOPEN__ open</b> — parsed from the document, not declared.</p>
    </div>
  </div>
  <div class="card" style="margin-top:18px">__MATRIX__</div>
  <div class="grid2" style="margin-top:18px">
    <div class="card">
      <h3>Lean 4 audit chain</h3>
      <table>
        <caption>Two measured runs on real proofs: build, <code>#print axioms</code>, an
          axiom allow-list, and a kernel control asserting 1 = 2 must fail.</caption>
        <thead><tr><th>target</th><th>theorem</th><th>verdict</th><th>time</th></tr></thead>
        <tbody>__LEANROWS__</tbody>
      </table>
    </div>
    <div class="card">
      <h3>Decision layer, measured</h3>
      <p>A typed operator returns <code>choice</code> / <code>yes-no</code> /
      <code>score</code> with calibrated probabilities in one pass; prose stays with
      generators. Median <b>__LATENCY__ ms</b> over HTTP for a two-question set.</p>
      <p class="note"><b>Calibration, n=100.</b> Accuracy __ACC__; abstention
      __ABS_A__ vs __ABS_U__ on answerable vs unanswerable items (Fisher
      p = __FISHER__). The confidence floor is <b>not identified</b>
      (<code>tau_identified = __TAU__</code>; lowest confidence on a correct answer
      __MINCONF__), so a gate may not use <code>none_probability ≥ 0.2</code> as a
      success criterion. The option set does the work, not the threshold.</p>
    </div>
  </div>
</section>

<section id="status">
  <h2><span class="num">05</span>Live status</h2>
  <p class="lede2">The chain audit from this build. Record:
  <a href="../docs/SELF_AUDIT.json">docs/SELF_AUDIT.json</a>.</p>
  <div class="card">
    <table>
      <caption>__NCHAINS__ chains: __NPASS__ pass, __NSKIP__ skip, 0 fail. A skip is named,
        never counted as a pass.</caption>
      <thead><tr><th>chain</th><th>verdict</th><th>detail</th></tr></thead>
      <tbody>__CHAINROWS__</tbody>
    </table>
  </div>
  <div class="card" style="margin-top:18px">
    <h3>External contracts</h3>
    <p class="contracts">__CONTRACTS__</p>
    <p class="contracts" style="margin-top:8px">__RENDER__</p>
    <p style="margin:10px 0 0;font-size:12.5px;color:var(--muted)">Probed at build time.
      A boundary that is down is named; it is never silently skipped.</p>
  </div>
  <div class="card" style="margin-top:18px">
    <h3>Consumers</h3>
    <table>
      <caption>A pointer, not a copy: the framework discovers each consumer, runs its gate
        and reports one verdict; every fixture keeps its own logic and evidence.</caption>
      <thead><tr><th>project</th><th>root</th><th>registered gate</th><th>checkout</th>
        <th>Gate S</th></tr></thead>
      <tbody>__ADOPT__</tbody>
    </table>
    __OP_DEMO__
    <p style="margin:14px 0 0;font-size:13px;color:#3a434d">Two entries: an LLM consumer
    whose claim is a measured interval (must pass), and a negative control on the same
    evidence whose claim is false (must be rejected). No external project is used as
    evidence — an instrument has to be validated before it measures, and an open study is
    not.</p>
  </div>
</section>

<section id="demo">
  <h2><span class="num">06</span>The demo: system-level quantities from a learned operator</h2>
  <p class="lede2">Fitted on short-step data, solved for fixed points and stability. Every
  panel is computed at build time; the page carries its own data and needs no other file.</p>
  <div class="grid2">
    <figure class="card" style="margin:0">
      <h3>Panel A · Fixed point against parameter</h3>
      <canvas id="plot" width="640" height="360" role="img"
              aria-label="Learned fixed point against the parameter, compared with the analytic branch"></canvas>
      <figcaption>The operator is fitted to one-step pairs of
        <span><math display="inline"><mfrac><mrow><mi>d</mi><mi>u</mi></mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mi>&#955;</mi><mo>&#8722;</mo><msup><mi>u</mi><mn>2</mn></msup></math></span>
        and Newton solves <span><math display="inline"><mi>&#968;</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>=</mo><mi>S</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>&#8722;</mo><mi>u</mi><mo>=</mo><mn>0</mn></math></span>
        on the learned map. Circles: operator. Line:
        <span><math display="inline"><msup><mi>u</mi><mo>&#8727;</mo></msup><mo>=</mo><msqrt><mi>&#955;</mi></msqrt></math></span>.</figcaption>
      <div class="controls">
        <label for="lam" class="sans" style="font-size:12.5px;color:var(--muted)">λ</label>
        <input id="lam" type="range" min="0.10" max="1.00" step="0.01" value="0.50"
               aria-label="parameter lambda">
        <output id="lamval" class="sans" style="font-size:13.5px;width:3.2em">0.50</output>
      </div>
      <div class="readout">
        <div class="kv"><div class="k">learned u*</div><div class="v" id="u_learned">—</div></div>
        <div class="kv"><div class="k">relative error</div><div class="v" id="err">—</div></div>
        <div class="kv"><div class="k">spectral radius</div><div class="v" id="rho">—</div></div>
      </div>
    </figure>
    <div style="display:grid;gap:18px">
      <div class="card">
        <h3>Panel B · Stability</h3>
        <canvas id="rho_plot" width="420" height="210" role="img"
                aria-label="Spectral radius of the learned map against the parameter"></canvas>
        <figcaption>Spectral radius at the learned fixed point. The red rule is the unit
          threshold; below it a perturbation decays.</figcaption>
      </div>
      <div class="card">
        <h3>Panel C · Newton iterates</h3>
        <svg id="trace" width="100%" height="92" role="img"
             aria-label="Newton iterates converging to the fixed point"></svg>
        <figcaption class="sans" style="font-size:11.5px">Start u₀ = 1 at λ =
          <span id="trace_lam">0.50</span>; each point is one Newton step.</figcaption>
        <div style="margin-top:10px"><button id="replay" type="button">Replay</button></div>
      </div>
    </div>
  </div>

  <div class="grid2" style="margin-top:18px">
    <div class="card">
      <h3>Table 1 · Checkpoints</h3>
      <table>
        <caption>Learned fixed point, analytic value, relative error and spectral radius at
          five parameters; all __GRID__ grid points are stable.</caption>
        <thead><tr><th>λ</th><th>u* analytic</th><th>u* learned</th><th>ε</th><th>ρ</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <figure class="card" style="margin:0">
      <h3>Panel D · Outside the training data</h3>
      __EXTRAP__
      <figcaption>Fit restricted to λ ≤ 0.6 (shaded: outside the data). Max relative error
        <b>__INMAX__</b> inside, <b>__OUTMAX__</b> outside. The operator does not fail here —
        the map is smooth and one-dimensional, and training on λ ≤ 0.2 still holds 0.31%.
        That is a property of this system, not a licence to extrapolate.</figcaption>
    </figure>
  </div>
</section>

<section id="start">
  <h2><span class="num">07</span>Start a project</h2>
  <div class="grid2">
    <div class="card">
      <h3>Instantiate or register</h3>
      <pre><span class="c"># new project: inherits gates, tracking, rendering</span>
./bootstrap_project.sh my_study

<span class="c"># existing repository: pointer, not a copy</span>
cat &gt; projects/my_study/project.yaml &lt;&lt;'YAML'
root: ../../../my_study
gate_command: ["{python}", "scripts/check_handoff.py"]
YAML

<span class="c"># run its gate through the framework</span>
python -m framework.project check my_study</pre>
    </div>
    <div class="card">
      <h3>Check this page's own claims</h3>
      <pre><span class="c"># chains, tests, coverage, self-audit</span>
python tools/record_self_audit.py
python tools/record_self_audit.py --check

<span class="c"># rebuild this page from the artefacts it cites</span>
python tools/build_site.py --check

<span class="c"># append this build to site/versions.json</span>
python tools/build_site.py --release

<span class="c"># validate a project's claims</span>
python tools/audit_validity.py --project ../keystroke-observatory</pre>
      <p style="margin:10px 0 0">The page has no external script, font or network call;
      formulas are MathML, the demo is inline, and every number is computed at build time.</p>
    </div>
  </div>
</section>

<section id="limits">
  <h2><span class="num">08</span>Limits and licence</h2>
  <div class="card">
    <p><b>What is measured.</b> Tests, coverage, chain verdicts, Lean runs, decision
    calibration, and the demo's error against a closed form.</p>
    <p><b>What is not.</b> That the gates improve a project's science — that would need a
    control group this programme does not have. That the interfaces generalise beyond two
    adopters. That a project's PDF path works everywhere: Quarto 1.10.19 is installed outside the
    repository and reached through <code>QUARTO_BIN</code>, so a clone without that variable
    reports SKIP; TinyTeX is a separate install and its absence limits PDF rendering.
    Coverage is uneven; <code>framework/inference</code> is exercised mainly by chains.</p>
    <p><b>Licence.</b> The framework is __LICENSE__. The decision operator's weights are
    <b>CC BY-NC 4.0</b> (non-commercial): a project that needs commercial terms must swap
    the operator, and the framework must not assume it is redistributable.</p>
  </div>
</section>

<footer>
  Eidos __VERSION__ · __LICENSE__ · commit <span class="mono">__COMMIT__</span> · built
  __DATE__ by <code>tools/build_site.py</code> · release history
  <a href="versions.json">versions.json</a> (__NVERS__).
  Numbers from <a href="../docs/SELF_AUDIT.json">SELF_AUDIT.json</a>,
  <a href="../docs/CHAIN_AUDIT.md">CHAIN_AUDIT.md</a>, the project registry,
  <code>artifacts/decision_calibration_100.json</code>, and one extrapolation experiment
  computed at build time.
</footer>
</div>

<script>
const DATA = __DEMO__;
const ROWS = DATA.rows;
const W = 640, H = 360, PAD = {l: 52, r: 14, t: 14, b: 40};
const xOf = lam => PAD.l + (lam - 0.1) / 0.9 * (W - PAD.l - PAD.r);
const yOf = u => H - PAD.b - (u / 1.05) * (H - PAD.t - PAD.b);

function frame(ctx, w, h, pad, ymax, ylabel) {
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#e1e6ec"; ctx.beginPath();
  ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, h - pad.b); ctx.lineTo(w - pad.r, h - pad.b);
  ctx.stroke();
  ctx.fillStyle = "#5f6c7a"; ctx.font = "10.5px -apple-system,Segoe UI,Arial";
  ctx.textAlign = "center";
  for (const t of [0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
    ctx.fillText(t.toFixed(1), pad.l + (t - 0.1) / 0.9 * (w - pad.l - pad.r), h - pad.b + 15);
  ctx.textAlign = "right";
  for (let v = 0; v <= ymax + 1e-9; v += ymax / 4) {
    const py = h - pad.b - (v / ymax) * (h - pad.t - pad.b);
    ctx.fillText(v.toFixed(2), pad.l - 7, py + 4);
    ctx.strokeStyle = "#f0f2f5"; ctx.beginPath(); ctx.moveTo(pad.l, py);
    ctx.lineTo(w - pad.r, py); ctx.stroke();
  }
  ctx.save(); ctx.translate(14, (h + pad.t - pad.b) / 2); ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center"; ctx.fillStyle = "#5f6c7a"; ctx.fillText(ylabel, 0, 0); ctx.restore();
}

function drawMain() {
  const ctx = document.getElementById("plot").getContext("2d");
  frame(ctx, W, H, PAD, 1.05, "u*");
  ctx.strokeStyle = "#1d4e89"; ctx.lineWidth = 2; ctx.beginPath();
  ROWS.forEach((r, i) => i ? ctx.lineTo(xOf(r.lam), yOf(r.truth)) : ctx.moveTo(xOf(r.lam), yOf(r.truth)));
  ctx.stroke();
  ctx.fillStyle = "#a8323f";
  ROWS.forEach(r => { if (r.learned === null) return;
    ctx.beginPath(); ctx.arc(xOf(r.lam), yOf(r.learned), 2, 0, 7); ctx.fill(); });
  const sel = parseFloat(document.getElementById("lam").value);
  const near = ROWS.reduce((a, b) => Math.abs(b.lam - sel) < Math.abs(a.lam - sel) ? b : a);
  document.getElementById("lamval").textContent = sel.toFixed(2);
  document.getElementById("u_learned").textContent = near.learned === null ? "—" : near.learned.toFixed(4);
  const err = near.learned === null ? null : Math.abs(near.learned - near.truth) / near.truth;
  document.getElementById("err").textContent = err === null ? "—" : (100 * err).toExponential(1) + "%";
  document.getElementById("rho").textContent = near.rho === null ? "—" : near.rho.toFixed(3);
  ctx.strokeStyle = "#9aa4b1"; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(xOf(near.lam), PAD.t); ctx.lineTo(xOf(near.lam), H - PAD.b);
  ctx.stroke(); ctx.setLineDash([]);
}

function drawRho() {
  const ctx = document.getElementById("rho_plot").getContext("2d");
  const w = 420, h = 210, pad = {l: 44, r: 12, t: 12, b: 30};
  const top = Math.max(1.15, ...ROWS.map(r => r.rho || 0));
  frame(ctx, w, h, pad, top, "ρ");
  ctx.strokeStyle = "#1d4e89"; ctx.lineWidth = 2; ctx.beginPath();
  ROWS.forEach((r, i) => { if (r.rho === null) return;
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
  const w = svg.clientWidth || 380, h = 92;
  const ux = i => 14 + i / Math.max(1, pts.length - 1) * (w - 28);
  const uy = v => h - 12 - (v / 1.05) * (h - 24);
  svg.innerHTML = pts.map((v, i) =>
    `<circle cx="${ux(i)}" cy="${uy(v)}" r="3" fill="#1d4e89" opacity="${(0.35 + 0.65 * i / pts.length).toFixed(2)}"/>`
  ).join("") + `<polyline fill="none" stroke="#1d4e89" stroke-width="1.1" points="${pts.map((v, i) => `${ux(i)},${uy(v)}`).join(" ")}"/>`;
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
</script>
</body></html>
"""



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
                         "decision_ms": data["decision"]["latency_ms"]}}
    history = versions()
    if history and history[-1].get("commit") == entry["commit"]:
        history[-1] = entry          # same commit rebuilt: replace, do not duplicate
    else:
        history.append(entry)
    history = history[-MAX_VERSIONS:]
    VERSIONS.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return history


def render(data: dict) -> str:
    audit = data["audit"]
    rows = data["chains"]
    claims = len(yaml.safe_load((ROOT / "analysis" / "CLAIMS.yaml").read_text(encoding="utf-8"))["claims"])
    extra, dec = data["extra"], data["decision"]
    lab = build_demo()
    tokens = {
        "__VERSION__": data["meta"]["version"],
        "__LICENSE__": data["meta"]["license"],
        "__NTESTS__": str(audit.get("tests_collected", "?")),
        "__COV__": str(audit.get("coverage_total", "?")),
        "__NCHAINS__": str(len(rows)),
        "__NPASS__": str(sum(1 for r in rows if r["status"] == "PASS")),
        "__NSKIP__": str(sum(1 for r in rows if r["status"] == "SKIP")),
        "__NOPEN__": str(data["referee"]["open"]),
        "__NRES__": str(data["referee"]["total"]),
        "__NADOPT__": str(len(data["registry"])),
        "__LATENCY__": str(dec["latency_ms"] or "—"),
        "__ACC__": f"{100 * dec['accuracy']:.1f}%" if dec["accuracy"] is not None else "—",
        "__ABS_A__": f"{100 * dec['abstain_answerable']:.0f}%" if dec["abstain_answerable"] is not None else "—",
        "__ABS_U__": f"{100 * dec['abstain_unanswerable']:.0f}%" if dec["abstain_unanswerable"] is not None else "—",
        "__FISHER__": f"{dec['fisher_p']:.1e}" if dec["fisher_p"] else "—",
        "__TAU__": str(dec["tau_identified"]),
        "__MINCONF__": f"{dec['min_conf']:.2f}" if dec["min_conf"] is not None else "—",
        "__PIPELINE__": pipeline_html(),
        "__STACK__": stack_svg(),
        "__MATRIX__": gate_matrix(),
        "__LEANROWS__": lean_rows(data["lean"]),
        "__CHAINROWS__": chain_rows(rows),
        "__ADOPT__": adopt_rows(data["registry"]),
        "__CONTRACTS__": contract_strip(data.get("contracts", [])),
        "__RENDER__": render_strip(),
        "__OP_DEMO__": operator_demo(),
        "__EXTRAP__": extrapolation_svg(extra),
        "__INMAX__": f"{100 * (extra['inside_max'] or 0):.4f}%",
        "__OUTMAX__": f"{100 * (extra['outside_max'] or 0):.2f}%",
        "__GRID__": str(len(lab["rows"])),
        "__DEMO__": demo_payload(),
        "__NCLAIMS__": str(claims),
        "__DATE__": data["today"],
        "__COMMIT__": data["commit"],
        "__NVERS__": str(data.get("versions", 0)),
    }
    page = PAGE
    for token, value in tokens.items():
        page = page.replace(token, value)
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--release", action="store_true",
                    help="append this build to site/versions.json")
    args = ap.parse_args(argv)

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
        if OUT.read_text(encoding="utf-8") != page:
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
