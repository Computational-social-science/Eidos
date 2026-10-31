"""The delivery page: one document, composed from parts, authored dark from the first line.

This module holds no data access. `build_site.render()` collects the artefacts, renders the
figures, and hands them here as a context; everything below is presentation. Splitting the
two is what keeps a restyle from touching measurement, and a new metric from touching layout.
"""

from __future__ import annotations

import html
import json
import pathlib

import theme

# Evidence selection is an asset; numerical measurements remain in the Python producer.
DEMO_JS = "\n".join((pathlib.Path(__file__).parent / name).read_text(encoding="utf-8")
                    for name in ("demo_js.js", "demo_charts.js"))

CSS = theme.root_css() + """
:root{--mono:ui-monospace,SFMono-Regular,Consolas,monospace}
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
.decision-measurements code,.decision-measurements b{display:inline-block;max-width:100%;overflow-wrap:anywhere}
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
.numerics-intro{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}
.numerics-intro p{flex:1;min-width:220px}.numerics-intro .pill{flex:none}
.numerics-controls{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0}
.numerics-controls>div{display:grid;gap:4px;min-width:130px}
.numerics-controls label{color:var(--mut);font-size:11px}
.numerics-controls select{min-height:36px;width:100%;min-width:0;max-width:100%;padding:6px 30px 6px 9px;
  border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg);
  font:12px var(--mono)}
#demo :focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.numerics-panels{align-items:start}.numerics-table{font-size:11.5px}
.numerics-table th:first-child{white-space:nowrap}.numerics-table td{font-family:var(--mono);white-space:nowrap}
.numerics-table th.numerics-standard{color:var(--warn)}
.numerics-table th.numerics-fixed{color:var(--accent)}
.numerics-table tr[aria-current=true]{background:rgba(91,141,239,.08)}
.numerics-errors{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0}
.numerics-errors dt{color:var(--mut);font-size:10.5px}.numerics-errors dd{margin:3px 0 0;
  color:var(--fg);font:13px var(--mono)}
.numerics-note{font-size:11px;color:var(--dim);margin:8px 0;overflow-wrap:anywhere}
.numerics-inputs{font:10.5px/1.7 var(--mono);color:var(--mut);overflow-wrap:anywhere}
.numerics-scope{max-width:110ch;margin-top:12px}
.numerics-links{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:11px}
.numerics-publication{margin:18px 0 22px;min-width:0}
.numerics-plot{min-width:0;max-width:100%;background:var(--panel);border:1px solid var(--line);border-radius:6px}
.numerics-plot svg{display:block;width:100%;height:300px;overflow:hidden;color:var(--body);font:12px Arial,sans-serif}
.numerics-chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;min-width:0}
.numerics-chart-title{font-size:12px;font-weight:500;color:var(--fg);margin:14px 16px 0}
.numerics-legend{display:flex;flex-wrap:wrap;gap:8px 20px;color:var(--mut);font-size:12px;margin:12px 0}
.numerics-legend span:before{content:"";display:inline-block;width:22px;border-top:2px solid #6ebcff;margin:0 7px 3px 0}
.numerics-legend .standard:before{border-color:#f29a70;border-top-style:dashed}
.numerics-legend .reference:before{border-color:#bdc4ce;border-top-style:dotted}
.numerics-readout{font:12px/1.8 var(--mono);color:var(--body);min-height:2em;overflow-wrap:anywhere}
#training-readout{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:4px 16px}
.numerics-scrubber{display:grid;grid-template-columns:auto minmax(70px,1fr) auto;align-items:center;gap:12px;margin:14px 0;color:var(--mut);font-size:12px}
.numerics-scrubber input{width:100%;min-width:0;accent-color:var(--accent);min-height:30px}
.numerics-controls fieldset{border:0;padding:0;display:flex;gap:14px;align-items:center;min-width:0}
.numerics-controls legend{color:var(--mut);font-size:11px;margin-bottom:7px}
.numerics-controls fieldset label{font-size:12px;color:var(--body)}
.numerics-publication figcaption{margin-top:10px;color:var(--body);font-size:11px;line-height:1.65;max-width:95ch}
.numerics-figure-downloads{display:flex;gap:16px;margin-top:7px;flex-wrap:wrap}
@media(max-width:800px){.numerics-chart-grid{grid-template-columns:1fr}}
.numerics-repair,.numerics-training{margin:24px 0;padding-top:18px;border-top:1px solid var(--rule)}
.numerics-remedies h4{font-size:12px;margin:12px 0 7px}
.numerics-remedies p,.numerics-training>p{font-size:12px;color:var(--body);line-height:1.7}
.numerics-method,.numerics-usage{margin:12px 0;color:var(--mut);font-size:11px}
.numerics-method:not([open])>:not(summary),.numerics-usage:not([open])>:not(summary){display:none}
.numerics-method summary,.numerics-usage summary{cursor:pointer;color:var(--body);padding:4px 0}
.numerics-method .tw{margin:7px 0;color:var(--fg);font-size:14px}
@media(max-width:620px){.numerics-controls{display:grid;grid-template-columns:1fr 1fr}
  .numerics-controls>div:first-child{grid-column:1/-1}.numerics-controls>div{min-width:0}
  .numerics-intro p{min-width:0;flex-basis:100%}}
/* Research brief: the scientific argument leads; implementation details remain inspectable. */
.hero{padding:20px 0 24px;margin-bottom:28px}
.hero-layout{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(230px,.85fr);gap:30px;align-items:start}
.hero h1{font-size:clamp(26px,3.1vw,38px);line-height:1.13;letter-spacing:-.025em;max-width:24ch;margin:12px 0 16px}
.hero .thesis{font-size:14px;line-height:1.75;max-width:67ch}
.hero .subthesis{font-size:12px;line-height:1.75;margin-top:10px}
.hero-actions{display:flex;flex-wrap:wrap;gap:9px;margin:18px 0}
.hero-actions a{padding:8px 12px;border:1px solid var(--line);border-radius:4px;font-size:12px;color:var(--fg)}
.hero-actions a:first-child{border-color:#4265a1;background:#18243a}
.hero-evidence{border-left:2px solid #9b7e4d;padding:4px 0 4px 18px;margin-top:9px;min-width:0}
.hero-evidence .eyebrow{color:var(--mut);line-height:1.7}
.hero-evidence h3{font-size:15px;line-height:1.5;margin:8px 0 14px}
.hero-evidence dl{margin:0;display:grid;gap:9px}
.hero-evidence dt{font-size:11px;color:var(--mut)}
.hero-evidence dd{margin:1px 0 8px;font:600 23px/1.5 var(--mono);overflow-wrap:anywhere;color:var(--fg)}
.hero-evidence dd.fixed-value{color:#7facff}
.hero-evidence p{font-size:11px;color:var(--mut);margin-top:12px}
.academic-proposition{font-size:15px;line-height:1.8;max-width:85ch;color:var(--body);margin-bottom:18px}
.scientific-chain{list-style:none;padding:0;margin:18px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--line)}
.scientific-chain li{padding:14px 16px 14px 0;min-width:0}
.scientific-chain span{font:11px var(--mono);color:var(--dim);display:block;margin-bottom:8px}
.scientific-chain strong{font-size:13px;color:var(--fg)}
.scientific-chain p{font-size:12px;line-height:1.75;color:var(--mut);margin:7px 0}
.evidence-ledger{border-top:1px solid var(--line);margin:18px 0}
.evidence-row{display:grid;grid-template-columns:38px minmax(0,1fr) minmax(0,1.05fr);gap:15px;padding:20px 0;border-bottom:1px solid var(--line)}
.evidence-level{font:11px var(--mono);color:var(--dim)}
.evidence-row h3{font-size:14px;margin-bottom:8px}
.evidence-row p{font-size:12px;line-height:1.8}
.evidence-measure{color:var(--fg);font-size:18px;line-height:1.7;font-variant-numeric:tabular-nums;display:block;margin:1px 0 8px}
.evidence-scope{color:var(--mut)}
.research-agenda{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;margin:18px 0}
.research-agenda article{border-top:2px solid var(--line);padding-top:14px;min-width:0}
.research-agenda h3{font-size:13px;line-height:1.6;margin-bottom:8px}
.research-agenda p{font-size:12px;line-height:1.8;color:var(--mut)}
.implementation-detail>summary{cursor:pointer;font-size:12px;color:var(--body);padding:10px 0}
.implementation-detail[open]>summary{margin-bottom:12px}
.implementation-detail:not([open])>:not(summary){display:none}
.sec{margin-bottom:32px}
.sec-h h2{font-size:12px;color:var(--body);letter-spacing:.08em}
.lede{line-height:1.75;margin-bottom:15px}
@media(max-width:800px){.hero-layout{grid-template-columns:1fr;gap:16px}.hero-evidence{max-width:100%}
 .hero-evidence dl{grid-template-columns:1fr 1fr}.hero-evidence dd{font-size:20px}
 .scientific-chain{grid-template-columns:repeat(2,minmax(0,1fr))}.research-agenda{grid-template-columns:1fr;gap:15px}}
@media(max-width:560px){.evidence-row{grid-template-columns:25px minmax(0,1fr);gap:10px}
 .evidence-row>div:last-child{grid-column:2}.hero-evidence dl{grid-template-columns:1fr}.hero h1{font-size:28px}}
@media(max-width:620px){.top .hchip{display:none}.top-in{padding:10px 16px;gap:8px}}
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


def pill(status: str) -> str:
    cls = {"PASS": "pass", "SKIP": "skip"}.get(status, "fail")
    return f'<span class="pill {cls}">{html.escape(status)}</span>'


def stat(n: str, label: str, sub: str) -> str:
    return (f'<div class="stat"><span class="n">{n}</span>'
            f'<span class="l">{label}</span><span class="s">{sub}</span></div>')


def sec(num: str, ident: str, title: str, lede: str, body: str) -> str:
    num = next((f"{i:02d}" for i, (key, _) in enumerate(RAIL, 1) if key == ident), num)
    return (f'<section class="sec" id="{ident}">'
            f'<div class="sec-h"><span class="num">{num}</span><h2>{title}'
            f'<a class="anchor" href="#{ident}" aria-label="permalink">¶</a></h2></div>'
            f'<p class="lede">{lede}</p>{body}</section>')


RAIL = [("position", "Academic proposition"), ("evidence", "Measured evidence"),
        ("demo", "Softmax case study"), ("pipeline", "Research method"), ("models", "Model capability limits"), ("gates", "Validity checks"),
        ("research", "Research agenda"), ("architecture", "Architecture"),
        ("orchestration", "Orchestration"), ("state", "Verification ledger"),
        ("monitor", "Live operations"), ("start", "Use & reproduce"), ("limits", "Scope & licence")]


def rail(commit: str, date: str, version: str, nvers: int) -> str:
    items = "".join(
        f'<li><a href="#{i}"><span>{n:02d}</span>{t}</a></li>'
        for n, (i, t) in enumerate(RAIL, start=1))
    return (f'<nav class="rail" aria-label="Sections"><ol>{items}</ol>'
            f'<div class="rail-meta">build {commit} · {date}<br>v{version} · {nvers} releases<br>'
            f'MIT · operator CC BY-NC 4.0</div></nav>')


def hero(ctx: dict) -> str:
    data = _demo_data(ctx)
    selected = next((r for r in data.get("collapse", []) if r["dtype"] == "float32" and r["margin"] == 18), None)
    if (data.get('qualification') or {}).get('verdict') != 'PASS':
        selected = None
    before = _demo_number(selected["standard_gradient"][0]) if selected else "unavailable"
    after = _demo_number(selected["fixed_gradient"][0]) if selected else "unavailable"
    return f'''<div class="hero">
  <div class="hero-layout"><div>
  <p class="eyebrow">EIDOS · research infrastructure · pre-release</p>
  <h1>Make scientific claims answerable to evidence.</h1>
  <p class="thesis">An executable research workflow connecting falsifiable claims, experiments,
    independent checks and reproducible delivery. Numerical failures become tested safeguards
    that subsequent projects can reuse.</p>
  <p class="subthesis">The Softmax case traces a published repair from its mathematical mechanism
    through actual backend checks to training outcomes. Each level earns its own conclusion.</p>
  <div class="hero-actions"><a href="#demo">Explore the repair &amp; controls →</a>
    <a href="#evidence">Read the measured evidence</a><a href="#start">Reproduce &amp; use</a></div>
  </div><aside class="hero-evidence" aria-label="One measured numerical failure and repair">
    <p class="eyebrow">One assumption, made testable</p><h3>A confident prediction can lose its target gradient.</h3>
    <dl><div><dt>Standard · target gradient</dt><dd>{before}</dd></div>
    <div><dt>Repaired · target gradient</dt><dd class="fixed-value">{after}</dd></div></dl>
    <p>Measured float32 · logit gap 18.<br>Independent Decimal reference and broken controls.
      <a href="#demo">Inspect the calculation ↗</a></p>
  </aside></div>
  <div class="stats">
    {stat(str(len(data.get('collapse', []))+len(data.get('cancellation', []))), "numerical cases", "filed measurements")}
    {stat(str(ctx["ntests"]), "framework tests", f'source coverage {ctx["cov"]}%')}
    {stat(str(ctx["nchains"]), "execution chains", f'{ctx["npass"]} pass · {ctx["nskip"]} skip')}
  </div>
</div>'''


def sec_position() -> str:
    body = '''<p class="academic-proposition">Scientific progress depends on knowing which assumptions
    an experiment actually tested. EIDOS makes the path from a claim to its evidence explicit,
    inspectable and capable of failing.</p>
    <ol class="scientific-chain" aria-label="The executable scientific argument">
      <li><span>01 · CLAIM</span><strong>State a falsifiable proposition</strong>
        <p>Declare scope, assumptions, controls and the artifact that could refute it.</p></li>
      <li><span>02 · MEASURE</span><strong>Execute the actual method</strong>
        <p>Bind code, data, seeds, configuration and the backend that produced the result.</p></li>
      <li><span>03 · CHALLENGE</span><strong>Check independently</strong>
        <p>Use independent references, negative controls and artifact-bound verification.</p></li>
      <li><span>04 · TRANSFER</span><strong>Keep a reusable safeguard</strong>
        <p>Turn a diagnosed failure into a regression check and a qualified implementation.</p></li>
    </ol>
    <p>The methodological contribution is this executable connection between argument,
    computation and reproducibility. Its effectiveness across research domains remains an
    empirical question. The Softmax repair itself is the work of <b>Barron, Gnanapragasam
    and Tschannen</b>; EIDOS implements and evaluates it through the existing Paper2Agent integration.</p>
    <p><a href="https://arxiv.org/html/2610.31642v3">Original method · A Fix for Softmax and Cross-Entropy ↗</a>
    · <a href="../docs/ACADEMIC_POSITIONING.md">Contribution, evidence &amp; scope</a></p>'''
    return sec("01", "position", "Academic proposition",
               "A scientific claim becomes useful when its evidence can be inspected and challenged.", body)


def sec_evidence(ctx: dict) -> str:
    data = _demo_data(ctx) if ctx.get('demo') else {}
    count = len(data.get('collapse', []))+len(data.get('cancellation', []))
    qualified = (data.get('qualification') or {}).get('verdict') == 'PASS'
    kernel_measure = f'{count} recorded cases' if qualified else 'Reverification required'
    kernel_scope = ('float32/float64 numerical kernels checked against independent Decimal arithmetic. '
                    'Backend qualification is separate from a finite loss or a probability sum of one.' if qualified
                    else 'A checked numerical conclusion is withheld until implementation qualification passes.')
    trained = (data.get('training') or {}).get('status') == 'PASS'
    training_measure = 'A checked stationary point' if trained else 'Reverification required'
    training_scope = ('The bounded teacher–student case tests equality and parameter drift. '
                      'Final saved states and negative outcomes are retained. It does not establish generalisation.' if trained
                      else 'A stationary-point conclusion is withheld until the saved training artifacts pass acceptance.')
    matrix = ctx.get('matrix_summary') or {'status':'UNVERIFIED'}
    if matrix.get('status') == 'VERIFIED':
        measured = (f"{matrix['runs']} trajectories · {matrix['pairs']} paired endpoints"
                    f"<span class='evidence-measure'>{matrix['higher']} higher · {matrix['lower']} lower · {matrix['ties']} tie</span>")
        scope = ('Fixed versus standard final held-out accuracy. Three seeds; all specified precision/epsilon cells retained. '
                 'This is a bounded reconstruction, without a paper MATCH or a general superiority claim.')
    else:
        measured = '<span class="evidence-measure">Reverification required</span>'
        scope = 'Matrix summary withheld because current artifact acceptance has not passed.'
    body = f'''<div class="evidence-ledger">
      <article class="evidence-row"><span class="evidence-level">L1</span><div>
        <h3>Numerical mechanism</h3><p>Does the implementation preserve the derivative it is meant to compute?</p>
        <a href="#demo">Explore repair, reference &amp; negative controls →</a></div><div>
        <strong class="evidence-measure">{kernel_measure}</strong>
        <p class="evidence-scope">{kernel_scope}</p></div></article>
      <article class="evidence-row"><span class="evidence-level">L2</span><div>
        <h3>Training behavior</h3><p>Does repairing the arithmetic change the system that uses it?</p>
        <a href="reports/numerics/report.html">Teacher–student experiment &amp; saved models →</a></div><div>
        <strong class="evidence-measure">{training_measure}</strong>
        <p class="evidence-scope">{training_scope}</p></div></article>
      <article class="evidence-row"><span class="evidence-level">L3</span><div>
        <h3>Generalisation under a fixed budget</h3><p>Does numerical repair consistently improve the scientific endpoint?</p>
        <a href="reports/softmax-matrix/report.html">Every paired result, protocol &amp; reproduction bundle →</a></div><div>
        {measured}<p class="evidence-scope">{scope}</p></div></article>
    </div><p class="evidence-scope">These are distinct acceptance levels. Software tests support the framework's
    operation; scientific conclusions require their own measurements, comparisons and controls.</p>'''
    return sec("02", "evidence", "What the evidence supports",
               "A layered case study, including the outcomes that did not meet the scientific expectation.", body)


def sec_research() -> str:
    body = '''<div class="research-agenda">
      <article><h3>Numerical assumptions as research objects</h3>
        <p>Identify where finite-precision computation changes an intended mathematical property.
        Qualify each new backend with independent references and broken controls.</p></article>
      <article><h3>Mechanism versus downstream outcome</h3>
        <p>Align the cited architecture and implementation, register discriminating ablations,
        and retain all seeds to explain when a numerical repair changes learning.</p></article>
      <article><h3>Transfer across scientific projects</h3>
        <p>Test whether reusable checks catch new errors in independent AI4S projects.
        Compare review and reproduction outcomes against an explicit baseline.</p></article>
    </div><p>These are research questions for the next evaluation, with completion criteria in the
    <a href="../docs/FUNCTIONAL_COMPLETENESS.md">functional completeness ledger</a>.
    Broad improvements in research quality and autonomous scientific discovery have not been established.</p>'''
    return sec("06", "research", "The research agenda",
               "The current evidence defines the next experiments and the claims they must earn.", body)


def sec_pipeline(fragment: str) -> str:
    return sec("02", "pipeline", "An executable research method",
               "Problem formulation, registered evidence, independent checks and delivery. "
               "Each required gate constrains the conclusion a project may report.", fragment)


def sec_orchestration() -> str:
    """What runs, and what was removed — the site used to inherit the README's LangGraph claim."""
    rows = [
        ("chain registry", "tools/audit_chains.py",
         "eleven chains, decorator-registered, run in order with spans and verdicts"),
        ("scheduler", "tools/refresh_chains.py",
         "per-chain intervals; a heartbeat and 'nothing due' instead of a cron that always runs"),
        ("sampler", "tools/watch_pipeline.py",
         "every 15 s: probe, classify against a reference, derive one verdict, drive recovery"),
        ("typed operator", "framework/decision.py",
         "choice / yes-no / score from a local model; unreachable raises, it does not guess"),
        ("update governance", "tools/update_operator.py",
         "sense weekly, try in a throwaway environment, promote on a passing try, roll back"),
    ]
    body = "<table><caption>Five pieces, each with one job and one file. No agent graph.</caption>" \
           "<thead><tr><th>piece</th><th>file</th><th>what it does</th></tr></thead><tbody>"
    for name, path, why in rows:
        body += f"<tr><td><strong>{name}</strong></td><td class='mono'>{path}</td><td>{why}</td></tr>"
    body += "</tbody></table>"
    body += ("<p style='margin:10px 0 0;font-size:12px;color:var(--dim)'>Removed rather than "
             "documented as present: LangGraph/LangChain agents (no consumer), Hydra (never "
             "wired), and the vector memory layer (no consumer, and it segfaulted on this host). "
             "The README claimed the first of these until 2026-10-26; "
             "<a href='../docs/ORCHESTRATION.md'>docs/ORCHESTRATION.md</a> records what happened "
             "and <code>tests/test_documentation_claims.py</code> keeps it recorded.</p>")
    return sec("04", "orchestration", "Orchestration",
               "What actually runs, and what was deliberately taken out. A graph nobody executes "
               "is a diagram; the chains are the system.", body)


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


def sec_models(ctx: dict) -> str:
    evidence=ctx.get('model_quality') or {}
    def ratio(key, count):
        record=evidence.get(key) or {}
        numerator,denominator=record.get(count),record.get('n')
        if not isinstance(record.get('model'),str) or record['model'].removesuffix('.gguf') != 'ScienceRSI-8b.i1-Q4_K_M':
            return 'unavailable'
        if type(numerator) is not int or type(denominator) is not int or not 0<=numerator<=denominator or denominator<=0:
            return 'unavailable'
        return f'{numerator}/{denominator} ({100*numerator/denominator:.1f}%)'
    s4,s7=ratio('s4','agree'),ratio('s7','hits')
    inventory=evidence.get('inventory') or {}
    observed=html.escape(str(inventory.get('observed_at') or 'unavailable'))
    presence=[]
    for entry in inventory.get('models') or []:
        if not isinstance(entry,dict):
            continue
        state={True:'installed',False:'absent',None:'unknown'}.get(entry.get('installed'),'unknown')
        presence.append(html.escape(str(entry.get('name','unknown')))+' — '+state)
    presence_text='; '.join(presence) if presence else 'Host inventory unavailable'
    body=f'''<div class="grid2">
      <div class="card"><h3>ScienceRSI-8B · tested scientific judge candidate</h3>
        <p><code>ScienceRSI-8b.i1-Q4_K_M</code>, Qwen3 architecture, 16,384-token deployed context.
        Design-validity probe S4: <b>{s4}</b>. Held-out support probe S7: <b>{s7}</b>.</p>
        <p><b>Not promoted to a scientific gate.</b> It can draft hypotheses or objections for review.
        The measured failures include confounding, statistical misuse and selection bias.
        These scores belong to ScienceRSI; they do not measure Llama, Qwen2.5 or Gemma.</p>
        <p><a href="docs/MODEL_VERDICTS.md">Probe conditions, errors and uncertainty →</a></p></div>
      <div class="card"><h3>StartLux-Decision-4B · bounded decision operator</h3>
        <p>Typed routing and failure triage. A closed, constructed calibration task does not establish
        scientific reasoning, experimental design or literature-gap discovery.</p>
        <p><b>Experiment execution uses registered commands.</b> Scientific acceptance uses deterministic
        numerical checks and project evidence. Model confidence does not replace either.</p>
        <p><a href="docs/MODEL-TASK-QUALITY.md">Model roles and qualification limits →</a></p></div>
      </div><div class="card" style="margin-top:10px"><h3>Readiness follows the task</h3>
      <div class="tw"><table><caption>Model roles follow task evidence; stage readiness cannot award scientific PASS.</caption><thead><tr><th>Stage</th><th>Current authority and remaining qualification</th></tr></thead><tbody>
        <tr><td>Hypothesis &amp; literature</td><td>Source-linked drafts; no task-qualified autonomous research reasoner. Novelty needs a literature comparison.</td></tr>
        <tr><td>Experiment design</td><td>Draft controls, confounders and stopping rules; critical designs require human confirmation.</td></tr>
        <tr><td>Execution</td><td>Registered Python/CUDA/tool commands with recorded inputs and outputs; StartLux can suggest routing.</td></tr>
        <tr><td>Evaluation &amp; writing</td><td>Independent recomputation and bounded claims; models may draft, but cannot award scientific PASS.</td></tr>
      </tbody></table></div>
      <p>The legacy <code>llama3.1:8b</code>, <code>qwen2.5:14b</code> and <code>gemma2:9b</code>
        entries are proposed alternatives, not a qualified model team.</p>
      <p>Host snapshot {observed}: {presence_text}. No accepted EIDOS research-task evaluation exists for these candidates.
        <a href="docs/MODEL_TASK_READINESS.json">Dated inventory and evidence pointers →</a></p></div>'''
    return sec('', 'models', 'Model capability and scientific authority',
               'An installed model, a reachable endpoint and a task-qualified researcher are different claims.',body)


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
  <div class="card decision-measurements"><h3>Decision layer, measured</h3>
    <p>A typed operator returns <code>choice</code> / <code>yes-no</code> / <code>score</code>
    with probabilities in one pass; prose stays with generators. Median
    <b>{ctx["latency"]} ms</b> over HTTP for a two-question set.</p>
    <p>Constructed calibration task, n=100. Accuracy <b>{ctx["acc"]}</b>; abstention <b>{ctx["abs_a"]}</b> vs
    <b>{ctx["abs_u"]}</b> on answerable vs unanswerable items (Fisher
    p = {ctx["fisher"]}). The confidence floor is <b>not identified</b>
    (<code>tau_identified = {ctx["tau"]}</code>; lowest confidence on a correct answer
    {ctx["minconf"]}), so a gate may not use <code>none_probability ≥ 0.2</code> as a success
    criterion. The option set does the work, not the threshold.</p></div>
</div>{fixture_table(ctx.get("fixtures") or {}, ctx.get("robustness") or {})}'''
    return sec("05", "gates", "Gates: two kinds, plus a validator",
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
  <h3>Dependency versions</h3>
  {ctx["deps"]}
</div>
<div class="card" style="margin-top:10px">
  <h3>Consumers</h3>
  <p>A pointer, not a copy: the framework discovers each consumer, runs its gate and reports one
  verdict; every fixture keeps its own logic and evidence.</p>
  <div class="tw"><table><caption>Positive fixtures, deliberate negative controls, measured scientific
  cases and execution-chain fixtures have different evidence roles. Matching an expected rejection
  is a successful control.</caption>
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
    return sec("06", "state", "State, at this build",
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
    return sec("07", "monitor", "Monitor — the pipeline at build time",
               "A still frame, so the document cannot claim a state the monitor contradicts.",
               body)


def _demo_data(ctx: dict) -> dict:
    """Accept the existing serialized-payload convention or a prepared mapping."""
    value = ctx["demo"]
    return json.loads(value) if isinstance(value, str) else value


def _demo_json(ctx: dict) -> str:
    return json.dumps(_demo_data(ctx), separators=(",", ":")).replace("<", "\\u003c")


def _demo_number(value) -> str:
    if value is None:
        return "undefined"
    return f"{float(value):.5e}"


def _demo_gradient_rows(row: dict) -> str:
    cells = []
    for index, (standard, fixed, reference) in enumerate(zip(
            row["standard_gradient"], row["fixed_gradient"], row["reference_gradient"])):
        cells.append(f'<tr><th scope="row">g<sub>{index}</sub></th>'
                     f'<td class="num">{_demo_number(standard)}</td>'
                     f'<td class="num">{_demo_number(fixed)}</td>'
                     f'<td class="num" title="{html.escape(str(reference), quote=True)}">'
                     f'{_demo_number(reference)}</td></tr>')
    return "".join(cells)


def sec_demo(ctx: dict) -> str:
    """A filed numerical case study, with a fully visible no-JavaScript default."""
    data = _demo_data(ctx)
    rows = [row for row in data["collapse"] if row["dtype"] == "float32"]
    selected = next((row for row in rows if row["margin"] == 18), rows[0])
    options = "".join(f'<option value="{index}"'
                      f'{" selected" if row is selected else ""}>{row["margin"]:g}</option>'
                      for index, row in enumerate(rows))
    regime = "".join(
        f'<tr><th scope="row">{row["margin"]:g}</th>'
        f'<td class="num">{_demo_number(row["standard_error"])}</td>'
        f'<td class="num">{_demo_number(row["fixed_error"])}</td></tr>'
        for row in rows if row["margin"] in (0, 10, 16, 18, 20, 36, 40, 60, 80))
    download_labels = (("report", "Measurement report"), ("json", "Evidence JSON"),
                       ("csv", "Cases CSV"), ("pdf", "PDF report"),
                       ("docx", "Word report"), ("bundle", "Reproduction bundle"))
    links = "".join(f'<a href="{html.escape(data["downloads"][key], quote=True)}"'
                    f'{" download" if key != "report" else ""}>{label}</a>'
                    for key, label in download_labels if key in data["downloads"])
    if (pathlib.Path(__file__).resolve().parents[1] / "site/reports/softmax-matrix/report.html").is_file():
        links += '<a href="reports/softmax-matrix/report.html">Precision × ε follow-up · all paired outcomes</a>'
    verdict = html.escape(data["qualification"]["verdict"])
    figure = '''<figure class="numerics-publication" aria-labelledby="numerics-figure-caption">
    <div class="numerics-legend" aria-label="Series legend"><span class="standard">Standard · before repair</span>
      <span>Fixed · after repair</span><span class="reference">Independent Decimal</span></div>
    <div class="numerics-chart-grid" id="numerics-figure">
      <div class="numerics-plot"><h4 class="numerics-chart-title">a · Selected gradient by class</h4>
        <svg id="numerics-gradient-chart" role="img" aria-label="Selected measured gradients by class"></svg></div>
      <div class="numerics-plot"><h4 class="numerics-chart-title" id="numerics-sweep-title">b · Across the measured regime</h4>
        <svg id="numerics-sweep-chart" role="img" aria-label="Measured error sweep with selected case"></svg></div>
    </div>
    <div class="numerics-scrubber"><label for="numerics-scrub">Measured case</label>
      <input type="range" id="numerics-scrub" min="0" max="40" value="9" step="1">
      <output id="numerics-scrub-value" for="numerics-scrub">Gap 18</output></div>
    <p class="numerics-readout" id="numerics-chart-readout" aria-live="polite" aria-atomic="true"></p>
    <figcaption id="numerics-figure-caption"><b>Figure 1.</b> Mode × arithmetic × measured input.
      Both panels follow the selected case. The sweep shows relative L2 error for collapse and absolute L2 error for cancellation;
      exact zeros have a separate rail, and zero perturbation is excluded from the logarithmic x-axis.
      Deterministic cases; no error bars. White-background publication masters cover the full regime:
      <span class="numerics-figure-downloads"><a id="numerics-figure-svg" href="reports/numerics/figure-float32.svg" download>Print master · editable SVG</a>
      <a id="numerics-figure-pdf" href="reports/numerics/figure-float32.pdf" download>Print master · PDF · 183 mm</a></span>
    </figcaption>
  </figure>'''
    equal = next((row for row in data["cancellation"]
                  if row["dtype"] == "float32" and row["perturbation"] == 0), {})
    repair = f'''<div class="numerics-repair">
    <h3>Repair strategy · computation and evidence</h3>
    <div class="tw" tabindex="0" role="region" aria-label="Measured before and after repair">
    <table><caption>Before repair → After repair · float32, logit gap 18 or exact teacher equality</caption>
    <thead><tr><th scope="col">Mechanism</th><th scope="col">Before repair</th><th scope="col">After repair</th></tr></thead>
    <tbody><tr><th scope="row">Collapse</th><td>Target derivative {_demo_number(selected['standard_gradient'][0])}<br>
      Relative L2 error {_demo_number(selected['standard_error'])}</td>
      <td>Target derivative {_demo_number(selected['fixed_gradient'][0])}<br>Relative L2 error {_demo_number(selected['fixed_error'])}</td></tr>
    <tr><th scope="row">Cancellation at equality</th><td>Absolute gradient error {_demo_number(equal.get('standard_absolute_error'))}</td>
      <td>Absolute gradient error {_demo_number(equal.get('fixed_absolute_error'))}</td></tr></tbody></table></div>
    <div class="grid2 numerics-remedies">
      <div><h4>Collapse: preserve the small derivative</h4>
        <p>A max shift prevents exponent overflow; subtraction from 1 can still erase the target gradient.
        Exclude exactly one argmax before <code>log1p</code>; compute the target derivative as a
        <b>negative sum</b> of the non-target derivatives. Both forward and backward need the repair.</p></div>
      <div><h4>Cancellation: retain the logit difference</h4>
        <p>Subtracting rounded probabilities loses information near the teacher. Use teacher logits,
        centered logit differences and <code>expm1</code>/<code>log1p</code>, then enforce the zero-sum
        correction. Use the ordinary difference in the far branch; preserve exact equality.</p></div>
    </div>
    <details class="numerics-usage"><summary>Use the tested implementation · PyTorch, first-order float32/float64</summary>
    <pre><code>from framework.stable_numerics_torch import logit_distillation

loss = logit_distillation(student_logits, teacher_logits).mean()
loss.backward()
# For hard targets, use hard_cross_entropy(logits, targets).mean().</code></pre>
    <p>The source bundle contains the full implementation and independent tests. AMP, bfloat16 and higher-order derivatives require separate qualification.</p></details>
  </div>'''
    training = data.get("training", {})
    training_html = ""
    if training.get("status") == "PASS":
        training_rows = "".join(f'<tr><th scope="row">{row["seed"]}</th><td class="num">{_demo_number(row["standard_displacement"])}</td>'
                                f'<td class="num">{_demo_number(row["fixed_displacement"])}</td></tr>' for row in training["seeds"])
        training_html = f'''<div class="numerics-training"><h3>Optimizer-level before / after</h3>
        <p>Three trained teachers on modular addition; each student starts with exactly the same weights and represented logits.
        After {training['steps']:,} full-batch Adam steps, saved checkpoints independently reproduce these parameter displacements:</p>
        <p>Teacher training accuracy: {min(r['teacher_train_accuracy'] for r in training['seeds']) * 100:.3g}–{max(r['teacher_train_accuracy'] for r in training['seeds']) * 100:.3g}%.
        Held-out accuracy: {min(r['teacher_test_accuracy'] for r in training['seeds']) * 100:.4g}–{max(r['teacher_test_accuracy'] for r in training['seeds']) * 100:.4g}%.
        This teacher does not establish a generalization result; the comparison tests exact stationarity.</p>
        <div class="tw"><table><caption>Final parameter displacement (L2) · every registered seed</caption>
        <thead><tr><th scope="col">Seed</th><th scope="col">Before repair · standard</th><th scope="col">After repair · fixed</th></tr></thead>
        <tbody>{training_rows}</tbody></table></div>
        <figure class="numerics-publication" aria-labelledby="training-figure-caption">
        <div class="numerics-controls" role="group" aria-label="Training trajectory combinations">
          <div><label for="training-seed">Registered seed</label><select id="training-seed"><option value="all">All three seeds</option>
          {''.join(f'<option value="{r["seed"]}">Seed {r["seed"]}</option>' for r in training['seeds'])}</select></div>
          <div><label for="training-metric">Measured endpoint</label><select id="training-metric">
            <option value="parameter_displacement_l2">Parameter displacement · L2</option>
            <option value="heldout_kl_float64">Held-out KL · float64 evaluation</option></select></div>
          <div><label for="training-scale">Value scale</label><select id="training-scale">
            <option value="linear">Linear</option><option value="symlog">Signed symmetric log · ±1e−12</option></select></div>
          <fieldset><legend>Repair comparison</legend><label><input id="training-standard" type="checkbox" checked> Standard</label>
            <label><input id="training-fixed" type="checkbox" checked> Fixed</label></fieldset>
        </div>
        <div class="numerics-legend"><span class="standard">Standard · before repair</span><span>Fixed · after repair</span></div>
        <div class="numerics-plot"><h4 class="numerics-chart-title" id="training-chart-title">Movement from the teacher</h4>
          <svg id="training-chart" role="img" aria-label="Measured training trajectories for selected seeds and metric"></svg></div>
        <div class="numerics-scrubber"><label for="training-step">Adam step</label>
          <input id="training-step" type="range" min="0" max="{training['steps']}" step="100" value="{training['steps']}">
          <output id="training-step-value" for="training-step">{training['steps']}</output></div>
        <p class="numerics-readout" id="training-readout" aria-live="polite" aria-atomic="true"></p>
        <figcaption id="training-figure-caption"><b>Figure 2.</b> Seed × endpoint × scale × optimizer step, with measured checkpoints only.
          The cursor reads the selected step; curves retain the complete trajectory. Zero is preserved on both scales.
          Corrected mechanistic rerun after a documented batch-shape confound.
          All three registered seeds are available. This stationarity experiment does not establish improved generalization or reproduce all paper training results.
          <span class="numerics-figure-downloads"><a href="reports/numerics/training/trajectory.svg" download>SVG</a>
          <a href="reports/numerics/training/trajectory.pdf" download>PDF · 183 mm</a>
          <a href="reports/numerics/training/trajectory.csv" download>All trajectories</a>
          <a href="reports/numerics/training/evidence.json">Training evidence</a>
          <a href="reports/numerics/training/protocol.json">Prospective local protocol</a>
          <a href="reports/numerics/training/failed-batch-shape.zip" download>Preserved failed run</a></span></figcaption></figure></div>'''
    body = f'''<div class="numerics-intro">
    <p>Two floating-point failure modes in published softmax and cross-entropy kernels.
    <b>Softmax Collapse</b> loses the dominant target gradient;
    <b>Softmax Cancellation</b> loses the difference between nearby distributions.</p>
    <span class="pill {"pass" if verdict == "PASS" else "fail"}">Kernel checks {verdict}</span>
  </div>
  <div class="numerics-controls" role="group" aria-label="Inspect precomputed numerical evidence">
    <div><label for="numerics-mode">Failure mode</label><select id="numerics-mode">
      <option value="collapse">Softmax Collapse</option>
      <option value="cancellation">Softmax Cancellation</option></select></div>
    <div><label for="numerics-dtype">Arithmetic</label><select id="numerics-dtype">
      <option value="float32">float32</option><option value="float64">float64</option></select></div>
    <div><label for="numerics-case" id="numerics-case-label">Logit gap</label>
      <select id="numerics-case">{options}</select></div>
  </div>
  {figure}
  {repair}
  {training_html}
  <p id="numerics-explanation" class="numerics-note">One dominant target, two non-target classes.
    The fixed kernel sums non-target gradients before negating their sum at the target.</p>
  <div class="grid2 numerics-panels">
    <div class="card"><h3>Inspect the gradient</h3>
      <p id="numerics-status" class="numerics-note" aria-live="polite" aria-atomic="true">float32 ·
        logit gap {selected["margin"]:g} · target class 0</p>
      <div class="tw" tabindex="0" role="region" aria-label="Gradient comparison table">
      <table class="numerics-table"><caption>Gradient by class · Independent Decimal reference</caption>
        <thead><tr><th scope="col">Class</th><th scope="col" class="numerics-standard">Standard</th>
        <th scope="col" class="numerics-fixed">Fixed · v3</th><th scope="col">Reference</th></tr></thead>
        <tbody id="numerics-gradients">{_demo_gradient_rows(selected)}</tbody></table></div>
      <dl class="numerics-errors">
        <div><dt>Standard relative L2 error</dt><dd id="numerics-standard-error">{_demo_number(selected["standard_error"])}</dd></div>
        <div><dt>Fixed relative L2 error</dt><dd id="numerics-fixed-error">{_demo_number(selected["fixed_error"])}</dd></div>
      </dl>
      <p id="numerics-details" class="numerics-note">Loss: standard {_demo_number(selected["standard_loss"])};
        fixed {_demo_number(selected["fixed_loss"])}. Absolute gradient sum: standard
        {_demo_number(selected["standard_residual"])}; fixed {_demo_number(selected["fixed_residual"])}.</p>
      <p id="numerics-inputs" class="numerics-inputs"></p>
    </div>
    <div class="card"><h3>Across the measured regime</h3>
      <div class="tw" tabindex="0" role="region" aria-label="Precision regime table">
      <table class="numerics-table"><caption id="numerics-regime-caption">Selected logit gaps · float32 · relative L2 gradient error</caption>
        <thead><tr><th scope="col" id="numerics-regime-axis">Logit gap</th>
        <th scope="col" class="numerics-standard">Standard</th>
        <th scope="col" class="numerics-fixed">Fixed · v3</th></tr></thead>
        <tbody id="numerics-regime">{regime}</tbody></table></div>
      <p class="numerics-note">A zero reference gradient makes relative error undefined.
        The class-by-class values remain visible. Logit gap denotes the dominant logit
        minus either other logit; it differs from the paper’s log-sum-exp margin.</p>
    </div>
  </div>
  <details class="numerics-method"><summary>Numerical kernels · Eqs. 5–9</summary>
    <p>Exclude exactly one argmax before log1p. Hard-target gradients use a negative sum.
      Distillation uses centered logit deltas for the log-ratio s; far entries use q − p.</p>
    <div class="tw"><math aria-label="Fixed log softmax"><mrow><mi>log</mi><msub><mi>q</mi><mi>k</mi></msub>
      <mo>=</mo><msub><mover><mi>z</mi><mo>~</mo></mover><mi>k</mi></msub><mo>−</mo>
      <mi>log1p</mi><mo>(</mo><munder><mo>∑</mo><mrow><mi>j</mi><mo>≠</mo><msub><mi>i</mi><mi>max</mi></msub></mrow></munder>
      <msup><mi>e</mi><msub><mover><mi>z</mi><mo>~</mo></mover><mi>j</mi></msub></msup><mo>)</mo></mrow></math></div>
    <div class="tw"><math aria-label="Stable hard target derivative"><mrow><msub><mi>g</mi><mi>t</mi></msub>
      <mo>=</mo><mo>−</mo><munder><mo>∑</mo><mrow><mi>j</mi><mo>≠</mo><mi>t</mi></mrow></munder>
      <msub><mi>g</mi><mi>j</mi></msub></mrow></math></div>
    <div class="tw"><math aria-label="Stable distillation derivative"><mrow><msub><mi>u</mi><mi>k</mi></msub>
      <mo>=</mo><msub><mi>p</mi><mi>k</mi></msub><mi>expm1</mi><mo>(</mo><msub><mi>s</mi><mi>k</mi></msub><mo>)</mo>
      <mo>,</mo><mspace width="1em"/><msub><mi>g</mi><mi>k</mi></msub><mo>=</mo><msub><mi>u</mi><mi>k</mi></msub>
      <mo>−</mo><msub><mi>q</mi><mi>k</mi></msub><munder><mo>∑</mo><mi>i</mi></munder><msub><mi>u</mi><mi>i</mi></msub></mrow></math></div>
  </details>
  <p class="numerics-note numerics-scope">Offline, precomputed NumPy measurements of the v3 numerical kernels;
    selectors only choose filed cases. This does not reproduce the paper’s grokking or training
    experiments. Finite exponent range and input quantization still apply.</p>
  <div class="numerics-links"><a href="{html.escape(data["paper"], quote=True)}">Paper · {html.escape(data["paper_version"])}</a>
    <a href="reports/numerics/paper2agent.md">Existing Paper2Agent integration</a>{links}</div>
  <noscript><p class="numerics-note">JavaScript is disabled. The default measured case is shown above;
    the evidence downloads contain both modes and both dtypes.</p></noscript>'''
    return sec("08", "demo", "The demo: Softmax Collapse &amp; Cancellation",
               "Published numerical fixes, independently checked and exposed through the existing Paper2Agent chain.",
               body)


def sec_start() -> str:
    body = '''<div class="grid2">
  <div class="card"><h3>Instantiate or register</h3>
<pre><code># new project: inherits gates, tracking, rendering
bash bootstrap_project.sh my_study

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
python tools/build_site.py --bump patch --release --summary "Delivered capability"
python tools/versioning.py --check

# validate a project's claims
python tools/audit_validity.py --project ../my_study</code></pre></div>
</div>
<p style="margin-top:10px">The page has no external script, font or network call; formulas are
MathML, the demo is inline, and every number is computed at build time.</p>'''
    return sec("09", "start", "Start a project", "Two commands to instantiate, one to audit.",
               body)


def sec_limits() -> str:
    body = '''<div class="stack">
  <p><b>What is measured.</b> Tests, coverage, chain verdicts, Lean runs, decision calibration,
  and the demo's error against independent high-precision arithmetic.</p>
  <p><b>Open scientific acceptance.</b> Controlled evidence that these gates improve research
  quality across independent projects remains to be collected. The paired Softmax study
  does not reproduce the paper's generalisation results. AMP/bfloat16 and higher-order
  differentiation require separate qualification.</p>
  <p><b>Open engineering acceptance.</b> Generic Docker/Binder packaging and concurrent report
  publication need completion; a clean strict 24-hour stability run has not passed.
  Quarto is installed outside the
  repository and reached through <code>QUARTO_BIN</code>, so a clone without that variable
  reports SKIP; TinyTeX is a separate install and its absence limits PDF rendering. Coverage is
  uneven; <code>framework/inference</code> is exercised mainly by chains.</p>
  <p><b>Licence.</b> The framework is MIT. The decision operator's weights are CC BY-NC 4.0
  (non-commercial): a project that needs commercial terms must swap the operator, and the
  framework must not assume it is redistributable.</p></div>'''
    return sec("10", "limits", "Limits and licence", "What this page will not claim.", body)


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
<title>EIDOS v{ctx["version"]} — scientific claims, executable evidence</title>
<meta name="description" content="Research infrastructure connecting falsifiable claims, experiments,
independent verification and reproducible delivery. Explore the Softmax repair, controls and all paired outcomes.">
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="top-in">
  <span class="brand"><i>●</i>Eidos<span class="ver">v{ctx["version"]}</span></span>
  <span class="spacer"></span>
  <span class="hchip">Research preview</span>
  <span class="hchip">{ctx["nchains"]} chains · {ctx["ntests"]} tests</span>
  <a class="cta" href="http://127.0.0.1:8765/">Monitor →</a>
</div></header>
<div class="shell">{ctx["rail"]}<main id="main">
{hero(ctx)}
{sec_position()}
{sec_evidence(ctx)}
{sec_demo(ctx)}
{sec_pipeline(ctx["pipeline"])}
{sec_models(ctx)}
{sec_gates(ctx)}
{sec_research()}
{sec_architecture('<details class="implementation-detail"><summary>Inspect the implementation layers</summary>'+ctx["stack"]+'</details>')}
{sec_orchestration()}
{sec_state(ctx)}
{sec_monitor(ctx)}
{sec_start()}
{sec_limits()}
<footer>Generated by <code>tools/build_site.py</code> from <code>{ctx["commit"]}</code> on
{ctx["date"]} · v{ctx["version"]} · {ctx["nvers"]} recorded builds · MIT.
<br>Machine record: <a href="../docs/SELF_AUDIT.json">docs/SELF_AUDIT.json</a> ·
<a href="../docs/HEALTH.md">docs/HEALTH.md</a> · <a href="../README.md">README</a></footer>
</main></div>
<script id="demo-data" type="application/json">{_demo_json(ctx)}</script>
<script>{DEMO_JS}</script>
<script>{JS}</script>
</body></html>'''
    return head
