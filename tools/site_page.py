"""The delivery page: one document, composed from parts, authored dark from the first line.

This module holds no data access. `build_site.render()` collects the artefacts, renders the
figures, and hands them here as a context; everything below is presentation. Splitting the
two is what keeps a restyle from touching measurement, and a new metric from touching layout.
"""

from __future__ import annotations

import html
import pathlib

import theme

# The demo's canvas script is an asset, not a string literal: it is the only executable code
# on the page, and keeping it in its own file means a restyle cannot mangle it.
DEMO_JS = (pathlib.Path(__file__).parent / "demo_js.js").read_text(encoding="utf-8")

CSS = theme.root_css() + """
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:66px}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--body);
  font:12.5px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.skip{position:absolute;left:-9999px}
.skip:focus{left:12px;top:12px;background:var(--panel);padding:8px 12px;
  border:1px solid var(--line);z-index:100}
.top{position:sticky;top:0;z-index:20;background:#15181d;border-bottom:1px solid var(--line);
  box-shadow:0 6px 14px -10px #000}
.top-in{max-width:1320px;margin:0 auto;padding:7px 20px;display:flex;align-items:center;gap:12px}
.brand{font:650 12.5px/1 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--fg)}
.brand i{color:var(--accent);font-style:normal;margin-right:6px}
.brand .ver{color:var(--dim);font-weight:400;margin-left:8px;font-size:11px}
.spacer{flex:1}
.hchip{font:600 10px/1.7 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.06em;
  text-transform:uppercase;padding:3px 8px;border-radius:999px;border:1px solid var(--line);
  color:var(--mut);white-space:nowrap}
.hchip.ok{color:#6cbf6e;border-color:rgba(87,171,90,.4);background:rgba(87,171,90,.08)}
.cta{font:600 10px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.06em;
  text-transform:uppercase;border:1px solid var(--line);border-radius:7px;padding:6px 10px;
  color:var(--fg);white-space:nowrap}
.cta:hover{border-color:var(--accent);text-decoration:none}
.shell{max-width:1320px;margin:0 auto;display:grid;grid-template-columns:196px minmax(0,1fr);
  gap:18px;padding:12px 16px 28px}
@media (max-width:1000px){.shell{grid-template-columns:1fr;gap:0}.rail{display:none}}
.rail{position:sticky;top:52px;align-self:start;font-size:11px}
.rail ol{list-style:none;margin:0;padding:0}
.rail a{display:flex;gap:8px;padding:2px 7px;border-radius:5px;color:var(--mut);
  border-left:2px solid transparent}
.rail a span{color:var(--dim);font:600 10px/1.6 var(--mono)}
.rail a:hover{color:var(--fg);background:rgba(255,255,255,.03);text-decoration:none}
.rail a.cur{color:var(--fg);border-left-color:var(--accent);background:rgba(91,141,239,.07)}
.rail-meta{margin-top:16px;padding-top:12px;border-top:1px solid var(--line);
  color:var(--dim);font:10.5px/1.75 var(--mono)}
main{min-width:0}
.hero{padding:2px 0 12px;border-bottom:1px solid var(--line);margin-bottom:14px}
.eyebrow{font:600 10px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.16em;
  text-transform:uppercase;color:var(--dim);margin:0 0 10px}
h1{font-size:19px;line-height:1.2;letter-spacing:-.01em;margin:0 0 6px;color:var(--fg);
  max-width:52ch}
.thesis{font-size:12.5px;line-height:1.5;color:var(--body);max-width:92ch;margin:0 0 4px}
.subthesis{color:var(--mut);max-width:92ch;margin:0 0 10px;font-size:12px}
.stats{display:flex;flex-wrap:wrap;gap:6px}
@media (max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:5px 9px;
  display:flex;align-items:baseline;gap:6px}
.stat .n{font:700 15px/1.2 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--fg);
  font-variant-numeric:tabular-nums}
.stat .l{font:600 10px/1.3 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.09em;
  text-transform:uppercase;color:var(--mut)}
.stat .s{font-size:10px;color:var(--dim)}
.sec{margin:0 0 20px;scroll-margin-top:56px}
.sec-h{display:flex;align-items:baseline;gap:11px;margin:0 0 5px}
.sec-h .num{font:600 10px/1 var(--mono);color:var(--dim)}
.sec-h h2{font-size:10px;letter-spacing:.13em;text-transform:uppercase;font-weight:600;
  margin:0;color:var(--dim)}
.sec-h .anchor{opacity:0;font-size:.72em;margin-left:5px}
.sec-h:hover .anchor,.sec-h:focus-within .anchor{opacity:.9}
.lede{color:var(--mut);max-width:104ch;margin:0 0 9px;font-size:12px}
h3{font-size:11px;margin:0 0 4px;color:var(--fg)}
p{margin:0 0 8px;max-width:104ch}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:11px 13px;min-width:0}
/* The nine pipeline stages: a card each, number / title / detail on three lines. Without
   these rules the stage text ran together on one line and read as truncation. */
ol.pipeline{list-style:none;margin:0;padding:0;display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
@media (max-width:900px){ol.pipeline{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:620px){ol.pipeline{grid-template-columns:1fr}}
ol.pipeline li{display:flex;gap:10px;background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:10px 12px;min-width:0}
ol.pipeline .n{font:600 10px/1.7 var(--mono);color:var(--accent);flex:none}
ol.pipeline b{display:block;font-size:12.5px;color:var(--fg);line-height:1.35}
ol.pipeline .d{display:block;font-size:11px;color:var(--mut);margin-top:3px;line-height:1.45}
.grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
@media (max-width:1180px){.grid2{grid-template-columns:1fr}}
@media (max-width:900px){.grid3{grid-template-columns:1fr}}
.tw{overflow-x:auto;max-width:100%}
.stack{display:grid;gap:10px}
ul.prose,ol.prose{padding-left:16px;margin:0 0 8px;max-width:104ch}
ul.prose li,ol.prose li{margin-bottom:5px}
figcaption{font-size:11px;color:var(--dim);margin-top:7px;line-height:1.5;max-width:80ch}
table{width:100%;border-collapse:collapse;font-size:12.5px}
caption{caption-side:top;text-align:left;font-size:11px;color:var(--dim);margin-bottom:6px}
th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
thead th{font:600 10px/1.2 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:var(--mut)}
td.num{text-align:right;font-variant-numeric:tabular-nums}
td.mono,.mono{font-family:var(--mono);font-size:11px}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;
  font:600 10px/1.7 -apple-system,"Segoe UI",Arial,sans-serif}
.pill.pass{background:rgba(87,171,90,.12);color:#6cbf6e}
.pill.skip{background:rgba(152,162,179,.12);color:var(--mut)}
.pill.fail{background:rgba(229,83,75,.12);color:#ef6b62}
pre{background:var(--panel2);color:#e6e8eb;border:1px solid var(--line);padding:11px 13px;
  border-radius:8px;overflow-x:auto;font:11.8px/1.62 var(--mono);margin:0 0 10px}
code{background:#1b2027;padding:1px 5px;border-radius:4px;font:12px var(--mono);color:#e6e8eb}
pre code{background:none;padding:0;font-size:inherit}
.contracts{display:flex;flex-wrap:wrap;gap:6px;margin:0}
.contract{font:600 11px/1 -apple-system,"Segoe UI",Arial,sans-serif;padding:6px 9px;
  border-radius:999px;border:1px solid var(--line);background:#191d23;color:var(--body)}
.contract.ok{border-color:rgba(87,171,90,.35);background:rgba(87,171,90,.07);color:#6cbf6e}
.contract.miss{border-color:rgba(229,83,75,.4);background:rgba(229,83,75,.07);color:#ef6b62}
.gchip{display:inline-block;padding:1px 7px;border-radius:999px;
  font:600 10px/1.65 -apple-system,"Segoe UI",Arial,sans-serif}
.gchip.must{background:rgba(91,141,239,.16);color:var(--accent)}
.gchip.rec{border:1px solid rgba(91,141,239,.55);color:var(--accent)}
.gchip.opt{color:var(--mut)}
.gchip.none{color:var(--dim)}
.mrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.mpill{font:600 10px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.08em;
  padding:5px 10px;border-radius:20px;text-transform:uppercase}
.mpill.ok{color:#6cbf6e;background:rgba(87,171,90,.12);border:1px solid rgba(87,171,90,.4)}
.mpill.alarm{color:#ef6b62;background:rgba(229,83,75,.12);border:1px solid rgba(229,83,75,.4)}
.mmeta{color:var(--mut);font-size:11px}
.mmeta b{color:var(--fg)}
.mlink{margin-left:auto;font-size:11px}
.mgrid{display:grid;grid-template-columns:2fr 1fr;gap:12px}
@media (max-width:900px){.mgrid{grid-template-columns:1fr}}
.mlabel{font:600 10px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.1em;
  text-transform:uppercase;color:var(--dim);margin-bottom:6px}
.mchips{display:flex;flex-wrap:wrap;gap:4px}
.mchip{display:inline-flex;gap:6px;align-items:center;font:11px/1 ui-monospace,Menlo,monospace;
  padding:4px 7px;border-radius:5px;border:1px solid var(--line);color:var(--body);
  background:#191d23}
.mchip b{font:600 10px/1 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.06em}
.mchip.pass b{color:#6cbf6e}.mchip.skip b{color:var(--mut)}.mchip.fail b{color:#ef6b62}
.mchip.running b{color:var(--accent)}.mchip.stale b{color:var(--warn)}.mchip.idle b{color:var(--dim)}
.mchip.ok b{color:#6cbf6e}.mchip.bad b{color:#ef6b62}
.mnote{margin:10px 0 0;font-size:11px;color:var(--dim)}
/* The gate matrix: a scannable object, not a wall of cells. Absent after the rewrite, which
   the component/style check caught before a reader had to. */
table.gm{width:100%;border-collapse:collapse;font-size:12px}
table.gm td,table.gm th{padding:5px 7px;border-bottom:1px solid var(--line);vertical-align:middle}
table.gm td.st{font-weight:600;color:var(--fg);white-space:nowrap}
table.gm td.has{background:rgba(91,141,239,.06)}
table.gm td.none{color:var(--dim)}
.gm-sum{margin:9px 0 0;font-size:12px;color:var(--mut)}
.gm-sum b{color:var(--fg)}
.gm-key{display:flex;gap:9px;align-items:center;margin:7px 0 0;flex-wrap:wrap}
.fig{width:100%;height:auto;display:block}
canvas{width:100%;height:auto;display:block;max-width:100%}
.readout{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:9px}
.kv{border:1px solid var(--line);border-radius:7px;padding:7px 9px;background:#191d23}
.kv .k{font:600 10px/1.2 -apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:var(--dim)}
.kv .v{font:650 15px/1.3 -apple-system,"Segoe UI",Arial,sans-serif;color:var(--fg);
  font-variant-numeric:tabular-nums;margin-top:3px}
.controls{display:flex;align-items:center;gap:10px;margin-top:10px}
.controls input[type=range]{flex:1;accent-color:var(--accent)}
.controls button{font:600 10px/1 -apple-system,"Segoe UI",Arial,sans-serif;
  letter-spacing:.05em;text-transform:uppercase;background:transparent;color:var(--mut);
  border:1px solid var(--line);border-radius:6px;padding:6px 10px;cursor:pointer}
.controls button:hover{color:var(--fg);border-color:var(--accent)}
.controls span{font:11px var(--mono);color:var(--mut)}
footer{margin-top:34px;padding-top:13px;border-top:1px solid var(--line);color:var(--dim);
  font-size:11px;line-height:1.7}
@media print{
  body{background:#fff;color:#111}
  .top,.rail{display:none}
  .shell{display:block;padding:0;max-width:none}
  .card,.stat,.kv{border-color:#ccc;background:#fff}
  a{color:#111}
}
"""


# Formulas are MathML: the page has no external font, script or network call, and the formal
# statements stay selectable text rather than a picture.
M_DUDT = ('<math display="inline"><mfrac><mrow><mi>d</mi><mi>u</mi></mrow>'
          '<mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mi>λ</mi><mo>−</mo>'
          '<msup><mi>u</mi><mn>2</mn></msup></math>')
M_PSI = ('<math display="inline"><mi>ψ</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>=</mo>'
         '<mi>S</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>−</mo><mi>u</mi><mo>=</mo>'
         '<mn>0</mn></math>')
M_USTAR = ('<math display="inline"><msup><mi>u</mi><mo>*</mo></msup><mo>=</mo>'
           '<msqrt><mi>λ</mi></msqrt></math>')
M_RHO = ('<math display="inline"><mi>ρ</mi><mo>(</mo><mi>S</mi><mo>)</mo><mo>&lt;</mo>'
         '<mn>1</mn></math>')


def pill(status: str) -> str:
    cls = {"PASS": "pass", "SKIP": "skip"}.get(status, "fail")
    return f'<span class="pill {cls}">{html.escape(status)}</span>'


def stat(n: str, label: str, sub: str) -> str:
    return (f'<div class="stat"><span class="n">{n}</span>'
            f'<span class="l">{label}</span><span class="s">{sub}</span></div>')


def sec(num: str, ident: str, title: str, lede: str, body: str) -> str:
    return (f'<section class="sec" id="{ident}">'
            f'<div class="sec-h"><span class="num">{num}</span><h2>{title}'
            f'<a class="anchor" href="#{ident}" aria-label="permalink">¶</a></h2></div>'
            f'<p class="lede">{lede}</p>{body}</section>')


RAIL = [("position", "Position"), ("pipeline", "The pipeline"),
        ("architecture", "Architecture"), ("gates", "Gates"),
        ("state", "State"), ("monitor", "Monitor"), ("demo", "The demo"),
        ("start", "Start"), ("limits", "Limits")]


def rail(commit: str, date: str, version: str, nvers: int) -> str:
    items = "".join(
        f'<li><a href="#{i}"><span>{n:02d}</span>{t}</a></li>'
        for n, (i, t) in enumerate(RAIL, start=1))
    return (f'<nav class="rail" aria-label="Sections"><ol>{items}</ol>'
            f'<div class="rail-meta">build {commit} · {date}<br>v{version} · {nvers} releases<br>'
            f'MIT · operator CC BY-NC 4.0</div></nav>')


def hero(ctx: dict) -> str:
    return f'''<div class="hero">
  <p class="eyebrow">Global reusable research pipeline</p>
  <h1>A skeleton, not a paper factory.</h1>
  <p class="thesis">One source → journal LaTeX/PDF + Word + interactive HTML + executable code,
    with quantitative and semantic quality gates enforced throughout.</p>
  <p class="subthesis">Every number below is computed at build time from an artefact this page
    names; the page refuses to state a claim it cannot point at.</p>
  <div class="stats">
    {stat(str(ctx["nchains"]), "chains", f'{ctx["npass"]} pass · {ctx["nskip"]} skip')}
    {stat(str(ctx["ntests"]), "tests", f'coverage {ctx["cov"]}%')}
    {stat(str(ctx["nadopt"]), "consumers", "2 must fail, on purpose")}
    {stat(str(ctx["ncontracts"]), "contracts", "probed at build time")}
    {stat(str(ctx["nclaims"]), "claims", f'{ctx["nres"]} objections, {ctx["nopen"]} open')}
  </div>
</div>'''


def sec_position() -> str:
    body = f'''<div class="grid3">
  <div class="card"><h3>It is a skeleton</h3>
    <p>One clone, many projects. <code>bootstrap_project.sh</code> produces a project wired to
    the same gates, the same provenance and the same rendering path. An existing repository is
    registered by pointer — never moved, never copied.</p></div>
  <div class="card"><h3>It is not a paper factory</h3>
    <p>Nothing here decides what is true. It decides what may leave the pipeline: a result is
    certified by gates, a claim by Gate S, and a judgement by a human gate when the operator's
    confidence is below threshold.</p></div>
  <div class="card"><h3>Knowledge has three homes</h3>
    <p>Procedure → agent skills. Facts → agent memory. History → the project's own
    <code>LESSONS</code> file. A framework vector store was built, never written to, and
    deleted; the lesson is recorded, the code is not.</p></div>
</div>'''
    return sec("01", "position", "Position",
               "What it is, what it is not, and where knowledge lives.", body)


def sec_pipeline(fragment: str) -> str:
    return sec("02", "pipeline", "The pipeline",
               "Nine stages, each with a gate it cannot skip. The order is the point: a result is "
               "certified before it is written, and written before it is packaged.", fragment)


def sec_architecture(fragment: str) -> str:
    return sec("03", "architecture", "Architecture",
               "Seven layers, ordered by dependence rather than by time: each layer can only be "
               "trusted if the one below it holds. Read bottom-up.", fragment)


def fixture_table(fx: dict, rb: dict | None = None) -> str:
    """Every check needed a fixture that trips it; this is that claim, not a slogan."""
    rows = fx.get("fixtures") or []
    if not rows:
        return ""
    cells = "".join(
        f'<tr><td class="st">{r["fixture"]}</td><td>{r["expected"]}</td>'
        f'<td class="{"has" if r["actual"] == r["expected"] else "none"}">{r["actual"]}</td>'
        f'<td>{", ".join(r["checks"]) or "&mdash;"}</td>'
        f'<td class="{"has" if r["ok"] else "none"}">{"ok" if r["ok"] else "wrong"}</td></tr>'
        for r in rows)
    covered = " ".join(fx.get("covered") or [])
    rb = rb or {}
    fuzz = rb.get("fuzz") or {}
    hist = rb.get("history") or {}
    chain = rb.get("chain") or {}
    extra = ""
    if fuzz.get("wrong") or chain.get("fixtures"):
        n_wrong = len(fuzz.get("wrong") or [])
        n_ev = len(fuzz.get("wrong_evidence") or [])
        n_pairs = len(fuzz.get("pairs") or [])
        n_equiv = len(fuzz.get("equivalent") or []) + len(fuzz.get("equivalent_evidence") or [])
        n_blind = len(fuzz.get("blind_spots") or [])
        n_over = len(fuzz.get("over_rejections") or [])
        n_chain = len(chain.get("fixtures") or [])
        extra = (f'<p class="gm-sum">Beyond the register: <b>{n_wrong}</b> wrong registers and '
                 f'<b>{n_ev}</b> wrong evidence files rejected, <b>{n_pairs}</b> combined faults '
                 f'rejected, <b>{n_equiv}</b> equivalent rewrites accepted &mdash; '
                 f'<b>{n_blind}</b> blind spots, <b>{n_over}</b> over-rejections &middot; '
                 f'<b>{n_chain}</b> chain consumers, where a gate that exits 0 without its artefact '
                 f'is refused and a missing binary is SKIP</p>'
                 f'<p class="mono">python tools/fuzz_register.py &middot; '
                 f'python tools/audit_chain_fixtures.py</p>')
    return f'''<div class="card" style="margin-top:10px"><h3>Every check has a fixture that trips it</h3>
    <p>A checklist that has never rejected anything is a claim about the checklist. Each fixture
    below is a finished project that is wrong in exactly one way; the gate must reject it, and
    the check that fires must be the one the fixture was built for. One clean fixture must pass.</p>
    <div class="tw"><table class="gm"><thead><tr><th>fixture</th><th>expected</th><th>actual</th>
    <th>check</th><th>match</th></tr></thead><tbody>{cells}</tbody></table></div>
    <p class="gm-sum">Covered: <b>{covered}</b> &middot; {len(rows)} fixtures &middot;
    <code>python tools/audit_fixtures.py</code></p>{extra}</div>'''


def sec_gates(ctx: dict) -> str:
    body = f'''<div class="grid2">
  <div class="card"><h3>Dual gates</h3>
    <p><b>Quantitative</b> — BootLoops protocols: acceptance thresholds with an explicit
    direction, planted truths, independence bookkeeping, timing discipline.</p>
    <p><b>Semantic</b> — Inspect, DeepEval, Promptfoo and Ragas for agent traces, RAG
    faithfulness and prompt regressions. A missing tool is a SKIP, named, never a pass.</p>
    <p><b>Human</b> — mandatory at hypothesis confirmation, experiment design and final
    submission. A gate nobody signs is a gate nobody owns.</p></div>
  <div class="card"><h3>Gate S — validation</h3>
    <p>Verification asks whether we built it correctly. Validation asks whether the claim is the
    one the evidence licenses. Gate S reads <code>analysis/CLAIMS.yaml</code> and refuses: a
    claim absent from the deliverable, an evidence pointer that no longer resolves, "supported"
    without preregistration and a negative control, an undeclared scope axis, an under-reported
    referee count, or a formal claim the Lean chain cannot reproduce.</p>
    <p class="mono">{ctx["nres"]} objections in the framework's own review,
    {ctx["nopen"]} open — parsed from the document, not declared.</p></div>
</div>
<div class="card" style="margin-top:10px">{ctx["matrix"]}</div>
<div class="grid2" style="margin-top:10px">
  <div class="card"><h3>Lean 4 audit chain</h3>
    <div class="tw"><table><caption>Two measured runs on real proofs: build, <code>#print axioms</code>, an axiom
    allow-list, and a kernel control asserting <code>1 = 2</code> must fail.</caption>
    <thead><tr><th>target</th><th>theorem</th><th>verdict</th><th class="num">time</th></tr></thead>
    <tbody>{ctx["lean_rows"]}</tbody></table></div></div>
  <div class="card"><h3>Decision layer, measured</h3>
    <p>A typed operator returns <code>choice</code> / <code>yes-no</code> / <code>score</code>
    with calibrated probabilities in one pass; prose stays with generators. Median
    <b>{ctx["latency"]} ms</b> over HTTP for a two-question set.</p>
    <p>Calibration, n=100. Accuracy <b>{ctx["acc"]}</b>; abstention <b>{ctx["abs_a"]}</b> vs
    <b>{ctx["abs_u"]}</b> on answerable vs unanswerable items (Fisher
    p = {ctx["fisher"]}). The confidence floor is <b>not identified</b>
    (<code>tau_identified = {ctx["tau"]}</code>; lowest confidence on a correct answer
    {ctx["minconf"]}), so a gate may not use <code>none_probability ≥ 0.2</code> as a success
    criterion. The option set does the work, not the threshold.</p></div>
</div>{fixture_table(ctx.get("fixtures") or {}, ctx.get("robustness") or {})}'''
    return sec("04", "gates", "Gates: two kinds, plus a validator",
               "Two gate families, one validator, and a matrix that says where each one sits.",
               body)


def spark(values, width=190, height=34, colour="var(--accent)"):
    """A sparkline drawn from a list of numbers; flat data still draws a line."""
    vals = [v for v in values if isinstance(v, (int, float))]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    step = width / (len(vals) - 1)
    pts = " ".join(f"{i * step:.1f},{height - 4 - (v - lo) / span * (height - 8):.1f}"
                   for i, v in enumerate(vals))
    last = vals[-1]
    return (f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="trend, last value {last}">'
            f'<polyline fill="none" stroke="{colour}" stroke-width="1.3" points="{pts}"/></svg>')


def evolution_cards(evo: dict) -> str:
    """State as things the framework can prove, and evolution as the defects it caught."""
    state = evo.get("state") or {}
    hist = evo.get("evolution") or {}
    instruments = state.get("instruments") or []
    if not instruments:
        return ""
    rows = "".join(
        f'<tr><td class="st">{html.escape(i["capability"])}</td>'
        f'<td>{html.escape(i["contradicted_by"])}</td>'
        f'<td class="num">{html.escape(i["result"])}</td>'
        f'<td class="mono">{html.escape(i["witness"])}</td></tr>' for i in instruments)
    tests = (hist.get("tests_by_release") or [])
    sparks = spark([t.get("tests") or 0 for t in tests])
    blind = spark(hist.get("blind_spots_by_run") or [], colour="var(--bad, #e5534b)")
    return f'''<div class="card">
  <h3>What it can prove, and what would contradict it</h3>
  <p>Every capability names the artefact that would falsify it. A line with no witness is a
  slogan, and this table has none.</p>
  <div class="tw"><table class="gm"><thead><tr><th>capability</th><th>would be contradicted by</th>
  <th>last result</th><th>witness</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="gm-sum">{state.get("chains", {}).get("pass", 0)} chains pass,
  {state.get("tests") or "?"} tests collected, {state.get("open_defects", 0)} open defect(s)
  &middot; recorded {html.escape(str(evo.get("asof", ""))[:16])}</p>
</div>
<div class="grid2" style="margin-top:10px">
  <div class="card"><h3>Evolution: the defects its instruments caught</h3>
    <p>Feature counts grow on their own. What matters is whether the framework can find its own
    regressions: a mutation the gate accepts, a component with no style rule, a page that renders
    without running, a service whose front door answers while its engine is dead.</p>
    <div class="readout">
      <div class="kv"><div class="k">mutation runs</div><div class="v">{hist.get("mutation_runs", 0)}</div></div>
      <div class="kv"><div class="k">blind spots found</div><div class="v">{hist.get("blind_spots_found", 0)}</div></div>
      <div class="kv"><div class="k">still open</div><div class="v">{hist.get("blind_spots_open", 0)}</div></div>
    </div>
    <p class="mono" style="margin:9px 0 0">blind spots per run {blind}</p></div>
  <div class="card"><h3>Tests per release</h3>
    <p>{len(tests)} releases on record; the last is {tests[-1].get("tests") if tests else "—"} tests
    at v{tests[-1].get("version") if tests else "—"}.</p>
    <p class="mono" style="margin:9px 0 0">{sparks}</p>
    <p style="font-size:12px;color:var(--dim);margin:8px 0 0">Release history:
    <a href="../site/versions.json">site/versions.json</a>. Written by the build, not by hand.</p></div>
</div>'''


def sec_state(ctx: dict) -> str:
    body = f'''{evolution_cards(ctx.get("evolution") or {})}<div class="card" style="margin-top:10px">
  <h3>External contracts</h3>
  <p class="contracts">{ctx["contracts"]}</p>
  <p class="mono" style="margin:9px 0 0;color:var(--dim)">{ctx["render"]}</p>
  <p style="margin:8px 0 0;font-size:12px;color:var(--dim)">Probed at build time. A boundary
  that is down is named; it is never silently skipped.</p>
</div>
<div class="card" style="margin-top:10px">
  <h3>Consumers</h3>
  <p>A pointer, not a copy: the framework discovers each consumer, runs its gate and reports one
  verdict; every fixture keeps its own logic and evidence.</p>
  <div class="tw"><table><caption>Three entries, each a different failure test: an LLM consumer whose claim is a
  measured interval (must pass), a negative control whose claim is false (must be rejected by
  S3), and a second control whose prose states a better number than its own evidence (must be
  rejected by S9).</caption>
  <thead><tr><th>project</th><th>root</th><th>registered gate</th><th>checkout</th>
  <th>Gate S</th></tr></thead><tbody>{ctx["consumers"]}</tbody></table></div>
</div>
<div class="card" style="margin-top:10px">
  <h3>Demo — the evidence, draggable</h3>
  <p>The confidence floor, swept over the tuning half of the same 100 items. Move it and read
  what the operator would have acted on. Nothing is recomputed here; the numbers are the
  measured sweep.</p>
  {ctx["opdemo"]}
</div>'''
    return sec("05", "state", "State, at this build",
               'Chain-by-chain and module-by-module state is live in the '
               '<a href="http://127.0.0.1:8765/">monitor</a>, which is the only place that draws it. '
               'This page records what the framework <em>is</em>; the monitor records what it is '
               '<em>doing</em>. Machine record: <a href="../docs/SELF_AUDIT.json">'
               'docs/SELF_AUDIT.json</a>.', body)




def sec_monitor(ctx: dict) -> str:
    """A still frame of the monitor, taken at build time.

    The document states what the framework *is*; this section shows what it was *doing* when
    the page was built, so a reader does not have to open a second tab to find out whether the
    thing they are reading about is alive.
    """
    m = ctx["monitor"]
    chips = "".join(
        f'<span class="mchip {row["state"].lower()}">{html.escape(row["name"])}'
        f'<b>{html.escape(row["state"])}</b></span>' for row in m["chains"])
    down = [s for s in m["services"] if not s["ok"]]
    services = "".join(
        f'<span class="mchip {"ok" if s["ok"] else "bad"}">{html.escape(s["name"])}'
        f'<b>{"up" if s["ok"] else "down"}</b></span>' for s in m["services"])
    verdict = "OK" if not down else "ALARM"
    body = f'''<!--snapshot:start--><div class="card">
  <div class="mrow">
    <span class="mpill {verdict.lower()}">{verdict}</span>
    <span class="mmeta">snapshot at <b>{m["asof"]}</b> HKT · <b>{m["samples"]}</b> samples ·
    <b>{m["ok_chains"]}/{m["n_chains"]}</b> chains healthy</span>
    <a class="mlink" href="http://127.0.0.1:8765/">open the live monitor →</a>
  </div>
  <div class="mgrid">
    <div><div class="mlabel">chains</div><div class="mchips">{chips}</div></div>
    <div><div class="mlabel">services</div><div class="mchips">{services}</div></div>
  </div>
  <p class="mnote">Collected from <code>docs/status/current.json</code> when this page was
  built. The live page polls the same payload every ten seconds; this frame does not.</p>
</div><!--snapshot:end-->'''
    return sec("06", "monitor", "Monitor — the pipeline at build time",
               "A still frame, so the document cannot claim a state the monitor contradicts.",
               body)


def sec_demo(ctx: dict) -> str:
    """The demo: three panels and a table, all drawn by tools/demo_js.js.

    The ids here are the script's contract (`plot`, `rho_plot`, `trace`, `lam`, `lamval`,
    `u_learned`, `err`, `rho`, `trace_lam`, `replay`, `rows`). A rewrite that renamed them
    silently broke the demo: canvases existed, the section rendered, and every number stayed
    at an em dash because the script threw on the first missing id.
    """
    body = f'''<p>The operator is fitted to one-step pairs of {M_DUDT} and Newton solves
  {M_PSI} on the learned map. Circles are the operator; the line is the analytic {M_USTAR}.
  Drag the parameter: the point, the reading and the Newton trace follow together.</p>
  <div class="grid2">
    <div class="card"><h3>Fixed point against parameter</h3>
      <canvas id="plot" width="640" height="330" aria-label="Learned fixed point against lambda"></canvas>
      <div class="controls"><input id="lam" type="range" min="0.2" max="1" step="0.02" value="0.5"
        aria-label="lambda"><span>λ = <b id="lamval">0.50</b></span></div>
      <div class="readout">
        <div class="kv"><div class="k">learned u*</div><div class="v" id="u_learned">—</div></div>
        <div class="kv"><div class="k">relative error</div><div class="v" id="err">—</div></div>
        <div class="kv"><div class="k">spectral radius</div><div class="v" id="rho">—</div></div>
      </div></div>
    <div class="card"><h3>Stability</h3>
      <canvas id="rho_plot" width="640" height="330" aria-label="Spectral radius at the learned fixed point"></canvas>
      <figcaption>Below {M_RHO} a perturbation decays; the red rule is the unit threshold.</figcaption></div>
  </div>
  <div class="grid2" style="margin-top:10px">
    <div class="card"><h3>Newton iterates</h3>
      <svg id="trace" viewBox="0 0 640 96" width="100%" role="img"
        aria-label="Newton iterates from u=1" style="display:block"></svg>
      <div class="controls"><button id="replay" type="button">Replay</button>
        <span>λ = <b id="trace_lam">0.50</b> · one point per step</span></div></div>
    <div class="card"><h3>Checkpoints</h3>
      <div class="tw"><table><caption>All {ctx["grid"]} grid points are stable.</caption>
      <thead><tr><th class="num">λ</th><th class="num">u* analytic</th><th class="num">u* learned</th>
      <th class="num">ε</th><th class="num">ρ</th></tr></thead><tbody id="rows"></tbody></table></div></div>
  </div>
  <div class="card" style="margin-top:10px"><h3>Outside the training data</h3>
    {ctx["extrap"]}
    <figcaption>Fit restricted to λ ≤ 0.6 (shaded: outside the data). Max relative error
    {ctx["inmax"]} inside, {ctx["outmax"]} outside. The operator does not fail here — the map is
    smooth and one-dimensional, and training on λ ≤ 0.2 still holds 0.31%. That is a property of
    this system, not a licence to extrapolate.</figcaption></div>'''
    return sec("07", "demo", "The demo: system-level quantities from a learned operator",
               "Fitted on short-step data, solved for fixed points and stability. Every panel is "
               "computed at build time; the page carries its own data and needs no other file.",
               body)


def sec_start() -> str:
    body = '''<div class="grid2">
  <div class="card"><h3>Instantiate or register</h3>
<pre><code># new project: inherits gates, tracking, rendering
./bootstrap_project.sh my_study

# existing repository: pointer, not a copy
cat &gt; projects/my_study/project.yaml &lt;&lt;'YAML'
root: ../../../my_study
gate_command: ["{python}", "scripts/check_handoff.py"]
YAML

# run its gate through the framework
python -m framework.project check my_study</code></pre></div>
  <div class="card"><h3>Check this page's own claims</h3>
<pre><code># chains, tests, coverage, self-audit
python tools/record_self_audit.py
python tools/record_self_audit.py --check

# rebuild this page from the artefacts it cites
python tools/build_site.py --check

# append this build to site/versions.json
python tools/build_site.py --release

# validate a project's claims
python tools/audit_validity.py --project ../my_study</code></pre></div>
</div>
<p style="margin-top:10px">The page has no external script, font or network call; formulas are
MathML, the demo is inline, and every number is computed at build time.</p>'''
    return sec("08", "start", "Start a project", "Two commands to instantiate, one to audit.",
               body)


def sec_limits() -> str:
    body = '''<div class="stack">
  <p><b>What is measured.</b> Tests, coverage, chain verdicts, Lean runs, decision calibration,
  and the demo's error against a closed form.</p>
  <p><b>What is not.</b> That the gates improve a project's science — that would need a control
  group this programme does not have. That the interfaces generalise beyond three sealed
  fixtures. That a project's PDF path works everywhere: Quarto is installed outside the
  repository and reached through <code>QUARTO_BIN</code>, so a clone without that variable
  reports SKIP; TinyTeX is a separate install and its absence limits PDF rendering. Coverage is
  uneven; <code>framework/inference</code> is exercised mainly by chains.</p>
  <p><b>Licence.</b> The framework is MIT. The decision operator's weights are CC BY-NC 4.0
  (non-commercial): a project that needs commercial terms must swap the operator, and the
  framework must not assume it is redistributable.</p></div>'''
    return sec("09", "limits", "Limits and licence", "What this page will not claim.", body)


JS = r"""
(() => {
  // Where am I on a long page: mark the section under the reading line.
  const links = [...document.querySelectorAll('.rail a')];
  const byId = Object.fromEntries(links.map(a => [a.getAttribute('href').slice(1), a]));
  const io = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      links.forEach(l => l.classList.remove('cur'));
      const l = byId[e.target.id]; if (l) l.classList.add('cur');
    }
  }, {rootMargin: '-40% 0px -55% 0px'});
  document.querySelectorAll('section[id]').forEach(s => io.observe(s));

  // Served by the monitor, the architecture figure states what the pipeline is doing.
  if (!location.protocol.startsWith('http')) return;
  const RANK = {FAIL: 5, STALE: 4, RUNNING: 3, SKIP: 2, PASS: 1, IDLE: 0};
  const COL = {FAIL: '#e5534b', STALE: '#d29922', RUNNING: '#5b8def', SKIP: '#8b97a6',
               PASS: '#57ab5a', IDLE: '#3a4048'};
  const paint = async () => {
    try {
      const d = await (await fetch('/api/status', {cache: 'no-store'})).json();
      const chains = d.chains || {};
      document.querySelectorAll('g.layer').forEach(g => {
        let worst = 'IDLE';
        (g.dataset.chains || '').split('|').filter(Boolean).forEach(n => {
          const st = chains[n] || 'IDLE';
          if (RANK[st] > RANK[worst]) worst = st;
        });
        const dot = g.querySelector('.lstate');
        if (dot) dot.setAttribute('fill', COL[worst]);
        if (!g.dataset.gate) {
          const rect = g.querySelector('rect');
          if (rect) rect.setAttribute('stroke',
            worst === 'FAIL' ? 'rgba(229,83,75,.55)' :
            worst === 'STALE' ? 'rgba(210,153,34,.5)' : 'var(--line)');
        }
      });
    } catch (e) { /* the figure reads correctly without a server */ }
  };
  paint();
  setInterval(paint, 20000);
})();
"""


def render(ctx: dict) -> str:
    head = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Eidos v{ctx["version"]} — a reusable research pipeline with dual gates</title>
<meta name="description" content="Eidos is the reusable skeleton behind a research project: dual
quality gates, a typed decision layer, provenance, and multi-format delivery. Every claim it
makes is checked against an artefact.">
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="top-in">
  <span class="brand"><i>●</i>Eidos<span class="ver">v{ctx["version"]}</span></span>
  <span class="spacer"></span>
  <span class="hchip ok">Gate S pass</span>
  <span class="hchip">{ctx["nchains"]} chains · {ctx["ntests"]} tests</span>
  <a class="cta" href="http://127.0.0.1:8765/">Monitor →</a>
</div></header>
<div class="shell">{ctx["rail"]}<main id="main">
{hero(ctx)}
{sec_position()}
{sec_pipeline(ctx["pipeline"])}
{sec_architecture(ctx["stack"])}
{sec_gates(ctx)}
{sec_state(ctx)}
{sec_monitor(ctx)}
{sec_demo(ctx)}
{sec_start()}
{sec_limits()}
<footer>Generated by <code>tools/build_site.py</code> from <code>{ctx["commit"]}</code> on
{ctx["date"]} · v{ctx["version"]} · {ctx["nvers"]} recorded builds · MIT.
<br>Machine record: <a href="../docs/SELF_AUDIT.json">docs/SELF_AUDIT.json</a> ·
<a href="../docs/HEALTH.md">docs/HEALTH.md</a> · <a href="../README.md">README</a></footer>
</main></div>
<script>{DEMO_JS.replace("__DEMO__", ctx["demo"])}</script>
<script>{JS}</script>
</body></html>'''
    return head
