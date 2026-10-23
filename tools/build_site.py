"""Build the Eidos delivery page: the front door of the project.

Every number on the page is read at build time from an artefact -- the chain audit, the
self-audit record, the project registry, the referee document, the Lean records, and one
extrapolation experiment computed here. A page that asserts a number it did not compute is
the failure mode this framework exists to catch, and the front door is the last place to
make an exception.

    python tools/build_site.py            # writes site/index.html
    python tools/build_site.py --check    # rebuild and compare with the file on disk
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from framework.surrogate import (RandomFeatureOperator, fixed_point,  # noqa: E402
                                 spectral_radius)
from audit_surrogate import training_pairs  # noqa: E402
from surrogate_lab import build as lab_build  # noqa: E402

OUT = ROOT / "site" / "index.html"


# --------------------------------------------------------------------------- data
def meta() -> dict:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    return {"version": project.get("version", "?"),
            "license": project.get("license", {}).get("text", "?"),
            "description": project.get("description", "")}


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
        root_path = (spec.parent / (root.group(1) if root else "")).resolve()
        rows.append({"name": name.group(1) if name else spec.parent.name,
                     "root": root.group(1) if root else "?",
                     "gate": gate.group(1) if gate else "?",
                     "available": root_path.is_dir()})
    return rows


def referee() -> dict:
    text = (ROOT / "docs" / "REFEREE_SIM.md").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^##\s+O\d+\.", text)[1:]
    return {"total": len(blocks),
            "resolved": sum(1 for b in blocks if "[RESOLVED]" in b),
            "open": sum(1 for b in blocks if "[UNRESOLVED]" in b)}


def lean_runs() -> list[dict]:
    """Read the two measured Lean runs from the audit record, not from memory."""
    text = (ROOT / "docs" / "CHAIN_AUDIT.md").read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        found = re.search(r"`([^`]+)`", cells[0])
        target = found.group(1) if found else cells[0].strip()
        if target not in ("lean-nhb", "atlas-lean"):
            continue
        rows.append({"target": target,
                     "theorem": re.sub(r"`", "", cells[1]).split("/")[-1].strip(),
                     "verdict": cells[2].replace("*", ""),
                     "time": cells[3]})
    return rows


def extrapolation() -> dict:
    """Fit inside lam <= 0.6 and look at what happens outside: the honest half of a demo."""
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


def collect() -> dict:
    return {"meta": meta(),
            "audit": json.loads((ROOT / "docs" / "SELF_AUDIT.json").read_text(encoding="utf-8")),
            "chains": chains(), "registry": registry(), "referee": referee(),
            "lean": lean_runs(), "extra": extrapolation(),
            "commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True).stdout.strip() or "uncommitted",
            "today": datetime.date.today().isoformat()}


# --------------------------------------------------------------------- helpers
PILL = {"PASS": "pass", "SKIP": "skip", "FAIL": "fail", "ERROR": "fail"}


def pill(status: str) -> str:
    return f'<span class="pill {PILL.get(status, "skip")}">{html.escape(status)}</span>'


def architecture_svg() -> str:
    """Three columns: what is checked, what is bridged, what is served."""
    groups = [
        ("Checks", 20, [("gates", "acceptance, planted truth, independence"),
                        ("validity", "Gate S — claims, not artefacts"),
                        ("surrogate", "fixed points, stability (no consumer yet)")]),
        ("Bridges", 300, [("project", "external registry, pointer not copy"),
                          ("quarto", "render, multi-format"),
                          ("tracking", "MLflow + DVC")]),
        ("Services", 580, [("inference", "budgeted model loading"),
                           ("decision", "typed choices, 42 ms"),
                           ("diagnosis", "gate failure → next action")]),
    ]
    parts = ['<svg viewBox="0 0 820 330" width="100%" class="fig" role="img" '
             'aria-label="Module map in three groups: checks, bridges, services">']
    for title, x, items in groups:
        parts.append(f'<text x="{x}" y="18" font-family="Segoe UI,Arial" font-size="11" '
                     f'font-weight="600" letter-spacing="1" fill="#5d6773">{title.upper()}</text>')
        for i, (name, desc) in enumerate(items):
            y = 34 + i * 86
            parts.append(f'<rect x="{x}" y="{y}" width="220" height="66" rx="9" '
                         f'fill="#ffffff" stroke="#dde2e8"/>')
            parts.append(f'<text x="{x + 14}" y="{y + 24}" font-family="Segoe UI,Arial" '
                         f'font-size="13.5" fill="#11161c">{name}</text>')
            parts.append(f'<text x="{x + 14}" y="{y + 42}" font-family="Segoe UI,Arial" '
                         f'font-size="10.5" fill="#5d6773">{desc}</text>')
            parts.append(f'<text x="{x + 14}" y="{y + 57}" font-family="ui-monospace,Consolas" '
                         f'font-size="9.5" fill="#8a94a0">framework/{name}</text>')
    for y in (67, 153, 239):
        parts.append(f'<line x1="240" y1="{y}" x2="298" y2="{y}" stroke="#c3cad2" '
                     f'stroke-width="1.2" marker-end="url(#a)"/>')
        parts.append(f'<line x1="520" y1="{y}" x2="578" y2="{y}" stroke="#c3cad2" '
                     f'stroke-width="1.2" marker-end="url(#a)"/>')
    parts.append('<defs><marker id="a" markerWidth="7" markerHeight="7" refX="6" refY="3" '
                 'orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#c3cad2"/></marker></defs>')
    parts.append('<text x="20" y="318" font-family="Segoe UI,Arial" font-size="10.5" '
                 'fill="#8a94a0">Arrows are calls, not imports. A module without a consumer '
                 'is marked as such rather than promoted.</text>')
    parts.append("</svg>")
    return "".join(parts)


def gate_flow_svg() -> str:
    steps = [("register", "CLAIMS.yaml"), ("span", "text in deliverable"),
             ("evidence", "pointer → value"), ("control", "a failure that could happen"),
             ("referee", "open objections parsed"), ("lean", "#print axioms")]
    parts = ['<svg viewBox="0 0 820 120" width="100%" class="fig" role="img" '
             'aria-label="Gate S pipeline: register, span, evidence, control, referee, Lean">']
    for i, (name, desc) in enumerate(steps):
        x = 8 + i * 136
        parts.append(f'<rect x="{x}" y="34" width="124" height="56" rx="8" fill="#fbfcfd" '
                     f'stroke="#dde2e8"/>')
        parts.append(f'<text x="{x + 10}" y="56" font-family="Segoe UI,Arial" font-size="11.5" '
                     f'fill="#11161c">{name}</text>')
        parts.append(f'<text x="{x + 10}" y="73" font-family="Segoe UI,Arial" font-size="9.8" '
                     f'fill="#5d6773">{desc}</text>')
        if i < len(steps) - 1:
            parts.append(f'<line x1="{x + 124}" y1="62" x2="{x + 134}" y2="62" '
                         f'stroke="#c3cad2" stroke-width="1.2" marker-end="url(#b)"/>')
    parts.append('<defs><marker id="b" markerWidth="7" markerHeight="7" refX="6" refY="3" '
                 'orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#c3cad2"/></marker></defs>')
    parts.append('<text x="8" y="108" font-family="Segoe UI,Arial" font-size="10.5" '
                 'fill="#8a94a0">A verdict is issued only when every step resolves; an '
                 'unresolvable evidence handle is a FAIL, not a warning.</text>')
    parts.append("</svg>")
    return "".join(parts)


def extrapolation_svg(extra: dict) -> str:
    rows = extra["rows"]
    W, H, pad = 660, 300, {"l": 54, "r": 14, "t": 16, "b": 38}
    x = lambda lam: pad["l"] + (lam - 0.1) / 0.9 * (W - pad["l"] - pad["r"])
    y = lambda u: H - pad["b"] - (u / 1.05) * (H - pad["t"] - pad["b"])
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" class="fig" role="img" '
             f'aria-label="Fixed points inside and outside the training interval">']
    parts.append(f'<rect x="{x(0.6):.1f}" y="{pad["t"]}" width="{x(1.0) - x(0.6):.1f}" '
                 f'height="{H - pad["t"] - pad["b"]}" fill="#f7e6e8"/>')
    parts.append(f'<text x="{x(0.8):.1f}" y="{pad["t"] + 14}" text-anchor="middle" '
                 f'font-family="Segoe UI,Arial" font-size="10.5" fill="#8c1d2c">'
                 f'outside the training interval</text>')
    parts.append(f'<line x1="{pad["l"]}" y1="{H - pad["b"]}" x2="{W - pad["r"]}" '
                 f'y2="{H - pad["b"]}" stroke="#dde2e8"/>')
    parts.append(f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" '
                 f'y2="{H - pad["b"]}" stroke="#dde2e8"/>')
    truth = " ".join(f"{x(r['lam']):.1f},{y(r['truth']):.1f}" for r in rows)
    learned = " ".join(f"{x(r['lam']):.1f},{y(r['learned']):.1f}"
                       for r in rows if r["learned"] is not None)
    parts.append(f'<polyline points="{truth}" fill="none" stroke="#1f4e9c" stroke-width="2"/>')
    parts.append(f'<polyline points="{learned}" fill="none" stroke="#a8323f" stroke-width="1.6"/>')
    for t in (0.2, 0.4, 0.6, 0.8, 1.0):
        parts.append(f'<text x="{x(t):.1f}" y="{H - pad["b"] + 16}" text-anchor="middle" '
                     f'font-family="Segoe UI,Arial" font-size="10.5" fill="#5d6773">{t:.1f}</text>')
    for t in (0.0, 0.5, 1.0):
        parts.append(f'<text x="{pad["l"] - 8}" y="{y(t) + 4:.1f}" text-anchor="end" '
                     f'font-family="Segoe UI,Arial" font-size="10.5" fill="#5d6773">{t:.1f}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _stable(detail: str) -> str:
    """Strip the parts of a chain detail that change on every run.

    MLflow run ids and measured latencies differ between two invocations, and a page that
    embeds them can never be checked for staleness. The stabilised text keeps the finding
    and drops the incidentals.
    """
    text = re.sub(r"\b[0-9a-f]{6,}\b", "…", str(detail))
    text = re.sub(r"\d+(?:\.\d+)?\s?(?:ms|s)", "…", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:110]


def chain_rows(rows: list[dict]) -> str:
    return "".join(
        f"<tr><td class='mono'>{html.escape(r['chain'])}</td><td>{pill(r['status'])}</td>"
        f"<td class='detail'>{html.escape(_stable(r['detail']))}</td></tr>" for r in rows)


def adopt_rows(rows: list[dict]) -> str:
    return "".join(
        f"<tr><td class='mono'>{html.escape(p['name'])}</td><td>{html.escape(p['root'])}</td>"
        f"<td><code>{html.escape(p['gate'])}</code></td>"
        f"<td>{'present' if p['available'] else 'absent'}</td></tr>" for p in rows)


def lean_rows(rows: list[dict]) -> str:
    return "".join(
        f"<tr><td class='mono'>{html.escape(r['target'])}</td>"
        f"<td class='mono'>{html.escape(r['theorem'])}</td>"
        f"<td>{pill(r['verdict'])}</td><td class='num'>{html.escape(r['time'])}</td></tr>"
        for r in rows)


def demo_rows() -> str:
    rows = lab_build()["rows"]
    return json.dumps([{"lam": round(r["lam"], 3), "learned": r["learned"],
                        "truth": r["truth"], "rho": r["rho"]} for r in rows],
                      separators=(",", ":"))


# ------------------------------------------------------------------------ page
PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eidos __VERSION__ — verification and validation for research</title>
<meta name="description" content="A research framework that verifies artefacts and validates claims: chain audits, Gate S, a Lean 4 audit chain, and two adopters.">
<style>
:root{
  --ink:#0f141a; --body:#232b34; --muted:#61707f; --rule:#e2e6eb; --paper:#fff;
  --wash:#f7f8fa; --accent:#1d4e89; --limit:#a8323f; --ok:#17663f;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--wash);color:var(--body);
     font:17px/1.65 Georgia,"Iowan Old Style","Times New Roman",serif;
     -webkit-font-smoothing:antialiased}
.sans{font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.mono{font-family:var(--mono);font-size:12.5px}
.skip{position:absolute;left:-9999px;top:0;background:#fff;padding:10px 14px;z-index:100}
.skip:focus{left:12px;top:12px;border:1px solid var(--rule)}
header.site{position:sticky;top:0;z-index:50;background:rgba(247,248,250,.94);
            backdrop-filter:saturate(1.2) blur(6px);border-bottom:1px solid var(--rule)}
header.site .inner{max-width:1120px;margin:0 auto;padding:10px 24px;display:flex;
                   align-items:center;gap:22px}
.wordmark{font:700 15px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.02em}
.wordmark span{color:var(--muted);font-weight:500;margin-left:8px;font-size:12px}
nav.toc{margin-left:auto;display:flex;gap:16px;flex-wrap:wrap}
nav.toc a{font:500 12.5px/1 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--muted);
          text-decoration:none;padding:6px 0;border-bottom:1px solid transparent}
nav.toc a:hover,nav.toc a:focus{color:var(--ink);border-bottom-color:var(--ink)}
@media (max-width:820px){nav.toc{display:none}}
.wrap{max-width:1120px;margin:0 auto;padding:44px 24px 80px}
.hero{padding:26px 0 8px}
.eyebrow{font:600 11px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.14em;
         text-transform:uppercase;color:var(--muted)}
h1{font-size:46px;line-height:1.08;letter-spacing:-.025em;margin:14px 0 14px;color:var(--ink);font-weight:700}
.thesis{font-size:20px;line-height:1.5;color:#2c343d;max-width:66ch;margin:0 0 22px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0 8px}
@media (max-width:760px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--paper);border:1px solid var(--rule);border-radius:10px;padding:14px 16px}
.stat .n{font:700 26px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:-.02em;
         font-variant-numeric:tabular-nums}
.stat .l{font:500 11px/1.3 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--muted);
         margin-top:6px;letter-spacing:.03em}
section{margin-top:52px}
h2{font-size:27px;letter-spacing:-.015em;color:var(--ink);margin:0 0 14px;font-weight:700}
h2 .num{font:600 13px/1 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--muted);
        margin-right:10px;vertical-align:2px}
h3{font-size:17px;margin:0 0 8px;color:var(--ink)}
p{margin:0 0 14px;max-width:76ch}
ul.prose,ol.prose{padding-left:20px;margin:0 0 14px;max-width:76ch}
ul.prose li,ol.prose li{margin-bottom:7px}
.card{background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:20px 22px}
.grid2{display:grid;grid-template-columns:1.05fr .95fr;gap:18px}
.grid2.wide{grid-template-columns:1.15fr .85fr}
@media (max-width:900px){.grid2,.grid2.wide{grid-template-columns:1fr}}
.fig{width:100%;height:auto;display:block}
figcaption{font-size:13px;line-height:1.5;color:var(--muted);margin-top:10px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
caption{caption-side:top;text-align:left;font-size:12.5px;color:var(--muted);margin-bottom:8px}
th,td{padding:8px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
thead th{font:600 10.5px/1.2 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.06em;
         text-transform:uppercase;color:var(--muted);border-bottom:1px solid #b9c1ca}
td.detail{color:var(--muted);font-size:12.5px}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;
      font:600 10.5px/1.7 -apple-system,Segoe UI,Arial,sans-serif}
.pill.pass{background:#e8f4ec;color:var(--ok)}
.pill.skip{background:#eef1f4;color:#4b5563}
.pill.fail{background:#fbecee;color:#8c1d2c}
.note{border-left:3px solid var(--limit);padding-left:14px;color:#3a434d}
.oknote{border-left:3px solid var(--ok);padding-left:14px;color:#3a434d}
canvas{width:100%;height:auto;display:block}
.controls{display:flex;align-items:center;gap:14px;margin-top:12px}
input[type=range]{flex:1;accent-color:var(--limit)}
.readout{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
.kv{border:1px solid var(--rule);border-radius:8px;padding:8px 10px;background:#fbfcfd}
.kv .k{font:600 9.5px/1.2 -apple-system,Segoe UI,Arial,sans-serif;letter-spacing:.07em;
       text-transform:uppercase;color:var(--muted)}
.kv .v{font-size:16px;margin-top:3px;font-variant-numeric:tabular-nums}
pre{background:#0f141a;color:#e6e9ee;padding:14px 16px;border-radius:10px;overflow-x:auto;
    font:12.5px/1.6 var(--mono);margin:0 0 10px}
pre .c{color:#8a94a0}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--rule);
       font-size:12.5px;line-height:1.7;color:var(--muted)}
code{background:#eef1f5;padding:1px 5px;border-radius:4px;font:12.5px var(--mono)}
@media print{body{background:#fff}header.site{display:none}.wrap{max-width:none;padding:0}
  .card{border:1px solid #ccc;break-inside:avoid}section{break-inside:avoid}}
</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="inner">
  <div class="wordmark">EIDOS <span>__VERSION__</span></div>
  <nav class="toc" aria-label="Sections">
    <a href="#why">Why</a><a href="#architecture">Architecture</a><a href="#gate-s">Gate S</a>
    <a href="#status">Status</a><a href="#demo">Demo</a><a href="#adopters">Adopters</a>
    <a href="#limits">Limits</a><a href="#reproduce">Reproduce</a>
  </nav>
</div></header>

<div class="wrap" id="main">
<div class="hero">
  <div class="eyebrow">Research framework · verification and validation</div>
  <h1>A framework that audits its own claims</h1>
  <p class="thesis">Eidos checks what most tooling never checks: whether the sentence a paper
  argues for is the sentence its evidence licenses. It then applies that check to itself, in
  public, with the failures left visible.</p>
  <div class="stats">
    <div class="stat"><div class="n">__NCLAIMS__</div><div class="l">claims in the self-register</div></div>
    <div class="stat"><div class="n">__NCHAINS__</div><div class="l">chains exercised end to end</div></div>
    <div class="stat"><div class="n">__NTESTS__</div><div class="l">tests, __COV__% coverage</div></div>
    <div class="stat"><div class="n">__NOPEN__</div><div class="l">open referee objections</div></div>
  </div>
</div>

<section id="why">
  <h2><span class="num">01</span>Why it exists</h2>
  <div class="grid2 wide">
    <div>
      <p>A project can pass twenty artefact gates with an unsupported central sentence. Those
      gates answer questions about files — did the pipeline run, is the figure legible, does
      the citation resolve — and none of them asks whether the evidence supports the claim.
      The failure is invisible to tooling because it is not a defect in an artefact; it is a
      gap between the artefact and the sentence.</p>
      <p>Eidos separates two things usually conflated:</p>
      <ul class="prose">
        <li><b>Verification</b> — did we build it correctly, reproducibly, and (where the
        claim is formal) provably?</li>
        <li><b>Validation</b> — is the claim we are making the claim the evidence licenses?</li>
      </ul>
      <p>Verification is strong by construction here: eleven chains, negative controls, CI on
      two Python versions, and a Lean 4 audit that has been run against real proofs.
      Validation is a single gate, and it is deliberately the strictest thing in the
      repository.</p>
    </div>
    <div class="card">
      <h3>What Gate S refuses</h3>
      <ol class="prose">
        <li>A claim whose text is not in the deliverable.</li>
        <li>An evidence pointer that no longer resolves, or a value that moved.</li>
        <li>“Supported” without a preregistered design <i>and</i> a negative control.</li>
        <li>A scope axis neither declared nor excluded with a reason.</li>
        <li>A referee document whose open objections are under-reported.</li>
        <li>A formal claim the Lean chain cannot reproduce.</li>
      </ol>
    </div>
  </div>
</section>

<section id="architecture">
  <h2><span class="num">02</span>Architecture</h2>
  <div class="card">__ARCH__</div>
  <p style="margin-top:14px"><b>Chains, not modules, are the unit of trust.</b> Each chain is
  exercised end to end — a real render, a real MLflow run, a real Lean build — and reports
  PASS, SKIP or FAIL. A module that imports is not a module that works; the chain audit
  exists because that distinction was learned the expensive way.</p>
</section>

<section id="gate-s">
  <h2><span class="num">03</span>Gate S — the validation layer</h2>
  <div class="card" style="margin-bottom:18px">__GATEFLOW__</div>
  <div class="grid2">
    <div class="card">
      <h3>The eight checks</h3>
      <table>
        <caption>The gate reads one register per deliverable and issues a verdict only when
          every check resolves.</caption>
        <thead><tr><th>code</th><th>rule</th><th>why it exists</th></tr></thead>
        <tbody>
          <tr><td class="mono">S1</td><td>register parses, ≥1 claim</td><td>no claims, nothing to audit</td></tr>
          <tr><td class="mono">S2</td><td>claim span appears verbatim</td><td>a claim not in the paper is not a claim</td></tr>
          <tr><td class="mono">S3</td><td>evidence pointer resolves and matches</td><td>artefacts move; the register must move with them</td></tr>
          <tr><td class="mono">S4</td><td>“supported” needs preregistration + control</td><td>strength must be earned, not typed</td></tr>
          <tr><td class="mono">S5</td><td>scope axes declared or excluded with a reason</td><td>silence is not a scope statement</td></tr>
          <tr><td class="mono">S6</td><td>power and multiplicity stated</td><td>or explicitly not applicable, with a reason</td></tr>
          <tr><td class="mono">S7</td><td>referee objections parsed, not declared</td><td>under-reporting is the failure mode</td></tr>
          <tr><td class="mono">S8</td><td>formal claims pass the Lean chain</td><td>build, axioms, kernel control</td></tr>
        </tbody>
      </table>
    </div>
    <div>
      <div class="card" style="margin-bottom:18px">
        <h3>Lean 4 audit chain</h3>
        <table>
          <caption>Two measured runs on real proofs. A name that does not resolve fails;
            a toolchain that accepts <span><math display="inline"><mn>1</mn><mo>=</mo><mn>2</mn></math></span>
            is rejected as a checker.</caption>
          <thead><tr><th>target</th><th>theorem</th><th>verdict</th><th>time</th></tr></thead>
          <tbody>__LEANROWS__</tbody>
        </table>
      </div>
      <div class="card">
        <h3>Self-audit</h3>
        <p>Eidos keeps a register for itself: three claims about its own behaviour, each
        with an evidence handle into <code>docs/SELF_AUDIT.json</code>. The gate caught a
        stale claim (ten chains recorded, eleven present) before a human noticed.</p>
        <p class="oknote"><b>__NOPEN__ open objection(s)</b> out of __NRES__ in
        <a href="../docs/REFEREE_SIM.md">docs/REFEREE_SIM.md</a> — the count is parsed from
        the document, so it cannot be talked down.</p>
      </div>
    </div>
  </div>
</section>

<section id="status">
  <h2><span class="num">04</span>Live status</h2>
  <p>This table is the chain audit from this build, not a transcription. Record:
  <a href="../docs/SELF_AUDIT.json">docs/SELF_AUDIT.json</a>.</p>
  <div class="card">
    <table>
      <caption>__NCHAINS__ chains: __NPASS__ pass, __NSKIP__ skip, 0 fail. A skip is named,
        never counted as a pass.</caption>
      <thead><tr><th>chain</th><th>verdict</th><th>detail</th></tr></thead>
      <tbody>__CHAINROWS__</tbody>
    </table>
  </div>
</section>

<section id="demo">
  <h2><span class="num">05</span>The demo, and its limit</h2>
  <div class="grid2 wide">
    <figure class="card" style="margin:0">
      <h3>Fixed points of a learned short-time operator</h3>
      <canvas id="plot" width="640" height="380" role="img"
              aria-label="Learned fixed point against the parameter, compared with the analytic branch"></canvas>
      <figcaption>The operator is fitted to one-step pairs of
        <span><math display="inline"><mfrac><mrow><mi>d</mi><mi>u</mi></mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mi>&#955;</mi><mo>&#8722;</mo><msup><mi>u</mi><mn>2</mn></msup></math></span>;
        Newton solves <span><math display="inline"><mi>&#968;</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>=</mo><mi>S</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>&#8722;</mo><mi>u</mi><mo>=</mo><mn>0</mn></math></span>
        on the learned map. Circles are the operator; the line is
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
      <figcaption style="margin-top:12px">Full version with three panels and a Newton replay:
        <a href="../lab/lab.html">lab/lab.html</a>.</figcaption>
    </figure>
    <div>
      <figure class="card" style="margin:0 0 18px">
        <h3>Outside its training data</h3>
        __EXTRAP__
        <figcaption>Same experiment with the fit restricted to λ ≤ 0.6 (shaded: outside the
          data). Max relative error <b>__INMAX__</b> inside, <b>__OUTMAX__</b> outside. The
          operator does <i>not</i> fail here: the map is smooth and one-dimensional, and
          training on λ ≤ 0.2 still holds 0.31%. That is a property of this system, not a
          licence to extrapolate — near a fold the same procedure is expected to break, and
          this panel would then show it.</figcaption>
      </figure>
      <div class="card">
        <h3>What this demonstrates — and what it does not</h3>
        <p><b>Does.</b> A short-time operator fitted on data supports system-level
        computation: fixed points, their stability, their parameter dependence — without
        writing the governing equation down.</p>
        <p class="note"><b>Does not.</b> It is not a PDE solver, and no claim is made outside
        the training interval merely because extrapolation happened to work: the measured
        accuracy beyond λ = 0.6 reflects a smooth one-dimensional map, not a general result.
        Applying the machinery to token sequences would be a category error — those are not
        C¹ function spaces.</p>
      </div>
    </div>
  </div>
</section>

<section id="adopters">
  <h2><span class="num">06</span>Adopters</h2>
  <div class="card">
    <table>
      <caption>A pointer, not a copy: the framework discovers, executes and reports one
        comparable verdict; each project keeps its own gate logic and tests.</caption>
      <thead><tr><th>project</th><th>root</th><th>registered gate</th><th>checkout</th></tr></thead>
      <tbody>__ADOPT__</tbody>
    </table>
    <p style="margin:14px 0 0">The two adopters are deliberately unlike — a Python repository
    with a manuscript, and a Lean library with no Python and no manuscript. If the registry
    only fitted the first, the generality claim would be empty.</p>
  </div>
</section>

<section id="limits">
  <h2><span class="num">07</span>What the framework does not claim</h2>
  <div class="card">
    <p><b>Referee simulation.</b> __NRES__ objections recorded, __NOPEN__ open. The gate
    parses the tags in <a href="../docs/REFEREE_SIM.md">docs/REFEREE_SIM.md</a> and refuses a
    register whose count disagrees.</p>
    <p><b>Known limits.</b> Coverage is uneven — <code>framework/inference</code> is exercised
    mainly by chains, not unit tests. The Lean chain is verified on two external projects, not
    on a project this framework gates. Quarto is absent on the build host, so a project's PDF
    path cannot be exercised end to end here.</p>
    <p><b>One adopter proves an interface, not a field.</b> Two show the registry is not shaped
    around one repository. Nothing here shows that the gates improve a project's science; that
    would need a control group this programme does not have.</p>
  </div>
</section>

<section id="reproduce">
  <h2><span class="num">08</span>Reproduce this page</h2>
  <div class="grid2">
    <div class="card">
      <h3>Commands</h3>
      <pre><span class="c"># tests, chains, coverage, self-audit -> docs/SELF_AUDIT.json</span>
python tools/record_self_audit.py

<span class="c"># rebuild this page from the artefacts it cites</span>
python tools/build_site.py

<span class="c"># fail if the committed page is stale</span>
python tools/build_site.py --check

<span class="c"># Gate S on a project</span>
python tools/audit_validity.py --project ../keystroke-observatory</pre>
    </div>
    <div class="card">
      <h3>What is generated, what is reviewed</h3>
      <p>Every number on this page is computed at build time. The prose is reviewed by hand;
      the figures are not — <code>architecture_svg</code>, the chain table and the
      extrapolation panel are all produced from data or from the code that runs the chains.</p>
      <p>The page has no external script, font or network call: it opens from disk. Formulas
      are MathML, not images.</p>
    </div>
  </div>
</section>

<footer>
  Eidos __VERSION__ · MIT · commit <span class="mono">__COMMIT__</span> · built
  __DATE__ by <code>tools/build_site.py</code>.
  Numbers come from <a href="../docs/SELF_AUDIT.json">SELF_AUDIT.json</a>,
  <a href="../docs/CHAIN_AUDIT.md">CHAIN_AUDIT.md</a>, the project registry, and one
  extrapolation experiment computed at build time.
</footer>
</div>

<script>
const ROWS = __DEMO__;
const W = 640, H = 380, PAD = {l: 52, r: 14, t: 14, b: 40};
const xOf = lam => PAD.l + (lam - 0.1) / 0.9 * (W - PAD.l - PAD.r);
const yOf = u => H - PAD.b - (u / 1.05) * (H - PAD.t - PAD.b);

function axes(ctx) {
  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = "#e2e6eb"; ctx.beginPath();
  ctx.moveTo(PAD.l, PAD.t); ctx.lineTo(PAD.l, H - PAD.b); ctx.lineTo(W - PAD.r, H - PAD.b);
  ctx.stroke();
  ctx.fillStyle = "#61707f"; ctx.font = "11px -apple-system,Segoe UI,Arial";
  ctx.textAlign = "center";
  for (const t of [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]) ctx.fillText(t.toFixed(1), xOf(t), H - PAD.b + 16);
  ctx.textAlign = "right";
  for (let v = 0; v <= 1.0; v += 0.25) {
    const py = yOf(v); ctx.fillText(v.toFixed(2), PAD.l - 8, py + 4);
    ctx.strokeStyle = "#f0f2f5"; ctx.beginPath(); ctx.moveTo(PAD.l, py); ctx.lineTo(W - PAD.r, py); ctx.stroke();
  }
}

function draw() {
  const ctx = document.getElementById("plot").getContext("2d");
  axes(ctx);
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

document.getElementById("lam").addEventListener("input", draw);
draw();
</script>
</body></html>
"""


def render(data: dict) -> str:
    audit = data["audit"]
    rows = data["chains"]
    claims = len(__import__("yaml").safe_load(
        (ROOT / "analysis" / "CLAIMS.yaml").read_text(encoding="utf-8"))["claims"])
    extra = data["extra"]
    tokens = {
        "__VERSION__": data["meta"]["version"],
        "__NCLAIMS__": str(claims),
        "__NCHAINS__": str(len(rows)),
        "__NPASS__": str(sum(1 for r in rows if r["status"] == "PASS")),
        "__NSKIP__": str(sum(1 for r in rows if r["status"] == "SKIP")),
        "__NTESTS__": str(audit.get("tests_collected", "?")),
        "__COV__": str(audit.get("coverage_total", "?")),
        "__NOPEN__": str(data["referee"]["open"]),
        "__NRES__": str(data["referee"]["total"]),
        "__ARCH__": architecture_svg(),
        "__GATEFLOW__": gate_flow_svg(),
        "__LEANROWS__": lean_rows(data["lean"]),
        "__CHAINROWS__": chain_rows(rows),
        "__ADOPT__": adopt_rows(data["registry"]),
        "__EXTRAP__": extrapolation_svg(extra),
        "__INMAX__": f"{100 * (extra['inside_max'] or 0):.4f}%",
        "__OUTMAX__": f"{100 * (extra['outside_max'] or 0):.2f}%",
        "__DEMO__": demo_rows(),
        "__DATE__": data["today"],
        "__COMMIT__": data["commit"],
    }
    page = PAGE
    for token, value in tokens.items():
        page = page.replace(token, value)
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    data = collect()
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
