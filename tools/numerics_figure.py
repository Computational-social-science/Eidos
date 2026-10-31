"""Editable, data-grounded vector panels using Nature's published figure dimensions."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter
from matplotlib.lines import Line2D
import numpy as np

GUIDE = "https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/"
FONT = "Arial" if any(font.name == "Arial" for font in font_manager.fontManager.ttflist) else "DejaVu Sans"
STANDARD, FIXED, REFERENCE = "#d55e00", "#0072b2", "#222222"
STYLE = {"font.family": FONT, "font.size": 6.5, "axes.titlesize": 7, "axes.formatter.use_mathtext": False,
         "mathtext.fontset": "custom", "mathtext.rm": FONT,
         "mathtext.it": f"{FONT}:italic", "mathtext.bf": f"{FONT}:bold",
         "axes.labelsize": 6.5, "xtick.labelsize": 6, "ytick.labelsize": 6,
         "legend.fontsize": 6.5, "axes.linewidth": .55, "lines.linewidth": 1,
         "text.color": "#111111", "axes.labelcolor": "#111111",
         "xtick.color": "#111111", "ytick.color": "#111111",
         "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
         "svg.hashsalt": "eidos-numerics-v2", "savefig.facecolor": "white"}


def _positive_line(axis, x, y, label, color, linestyle="-", marker=None):
    y = np.asarray(y, dtype=float)
    # Exact zero has no logarithm. Break the line and annotate the count inside the panel.
    axis.plot(x, np.where(y > 0, y, np.nan), label=label, color=color,
              linestyle=linestyle, marker=marker, markersize=2.5, markerfacecolor="white")
    zero = y == 0
    if zero.any():
        axis.text(.97, .93 - .07 * len(axis.texts), f"{label}: {int(zero.sum())} exact zero",
                  transform=axis.transAxes, ha="right", color="#111111", fontsize=6,
                  bbox={"facecolor": "white", "edgecolor": "none", "alpha": .9, "pad": 1})


def create_figure(data: dict, dtype: str):
    """Four panels; numerical transforms are presentation of filed measurements only."""
    collapse = [r for r in data["collapse"] if r["dtype"] == dtype]
    cancellation = [r for r in data["cancellation"] if r["dtype"] == dtype]
    if not collapse or not cancellation:
        raise ValueError(f"no measured cases for {dtype}")
    with plt.rc_context(STYLE):
        figure, axes = plt.subplots(2, 2, figsize=(183 / 25.4, 132 / 25.4))
        figure.subplots_adjust(left=.105, right=.98, bottom=.115, top=.9, wspace=.34, hspace=.53)
        a, b, c, d = axes.flat
        x = [row["margin"] for row in collapse]
        for key, label, color, style in (("standard_gradient", "Standard", STANDARD, "--"),
                                          ("fixed_gradient", "Fixed", FIXED, "-"),
                                          ("reference_gradient", "Decimal reference", REFERENCE, ":")):
            _positive_line(a, x, [abs(float(r[key][0])) for r in collapse], label, color, style)
        a.set(xlabel="Logit gap (dominant minus non-target)", ylabel="|Target gradient|",
              yscale="log", title=f"a   Collapse · {dtype}")
        for key, label, color, style in (("standard_error", "Standard", STANDARD, "--"),
                                          ("fixed_error", "Fixed", FIXED, "-")):
            _positive_line(b, x, [r[key] for r in collapse], label, color, style)
        b.set(xlabel="Logit gap (dominant minus non-target)", ylabel="Relative gradient error (L2)",
              yscale="log", title="b   Error against independent arithmetic")
        near = sorted((row for row in cancellation if not row["stationary"]),
                      key=lambda r: max(abs(v) for v in r["represented_delta"]), reverse=True)
        delta = [max(abs(v) for v in row["represented_delta"]) for row in near]
        for key, label, color, style in (("standard_error", "Standard", STANDARD, "--"),
                                       ("fixed_error", "Fixed", FIXED, "-")):
            _positive_line(c, delta, [r[key] for r in near], label, color, style, "o")
        c.set(xlabel="Represented student–teacher logit gap (max norm)", ylabel="Relative gradient error (L2)",
              xscale="log", yscale="log", title="c   Cancellation near the teacher")
        if delta:
            c.set_xlim(max(delta) * 1.4, min(delta) / 1.4)
        equal = next(row for row in cancellation if row["perturbation"] == 0)
        errors = [equal["standard_absolute_error"], equal["fixed_absolute_error"], 0.0]
        d.bar([0, 1, 2], errors, width=.45, color=[STANDARD, FIXED, "#777777"], linewidth=0)
        d.scatter([1, 2], [errors[1], 0], s=12, color=[FIXED, "#777777"], marker="o", zorder=3)
        d.set(xticks=[0, 1, 2], xticklabels=["Standard", "Fixed", "Reference"],
              ylabel="Absolute gradient error (L2)", title="d   Exact student–teacher equality")
        maximum = max(errors)
        d.set_ylim(0, maximum * 1.35 if maximum else 1)
        d.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=False)
        for index, value in enumerate(errors):
            d.annotate("exact zero" if value == 0 else f"{value:.2e}", (index, value),
                       xytext=(0, 5), textcoords="offset points", ha="center", fontsize=6)
        for axis in axes.flat:
            if axis.get_xscale() in ('log','symlog'):
                axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:.0e}'))
            if axis.get_yscale() in ('log','symlog'):
                axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:.0e}'))
            axis.spines[["top", "right"]].set_visible(False)
            axis.tick_params(direction="out", length=2.5, width=.5)
            axis.set_title(axis.get_title(), loc="left", fontsize=7, pad=9)
            axis.set_title("")
            axis.grid(axis="y", color="#e6e6e6", linewidth=.4, zorder=0)
            axis.set_axisbelow(True)
        handles = [Line2D([], [], color=STANDARD, linestyle="--", label="Standard"),
                   Line2D([], [], color=FIXED, label="Fixed · v3"),
                   Line2D([], [], color=REFERENCE, linestyle=":", label="Independent Decimal reference")]
        figure.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(.54, .985))
        figure.text(.105, .025, "Exact-zero counts are annotated in each log panel; no positive floor is substituted.",
                    fontsize=6, color="#111111")
        return figure


def render_figures(output: Path, data: dict) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for dtype in ("float32", "float64"):
        figure = create_figure(data, dtype)
        try:
            with plt.rc_context(STYLE):
                figure.savefig(output / f"figure-{dtype}.svg", metadata={"Date": None, "Creator": "Eidos"})
                figure.savefig(output / f"figure-{dtype}.pdf",
                               metadata={"Creator": "Eidos", "CreationDate": None, "ModDate": None})
                figure.savefig(output / f"figure-{dtype}.png", dpi=300)
            path = output / f"figure-{dtype}.svg"
            tree = ET.parse(path)
            root = tree.getroot()
            root.set("role", "img")
            root.set("aria-labelledby", "figure-title figure-description")
            title = ET.Element("{http://www.w3.org/2000/svg}title", {"id": "figure-title"})
            title.text = f"Softmax Collapse and Cancellation, measured {dtype} kernels"
            description = ET.Element("{http://www.w3.org/2000/svg}desc", {"id": "figure-description"})
            description.text = ("Four panels compare standard and fixed gradients to independent Decimal arithmetic. "
                                "Exact zero is not replaced with a logarithmic floor. Deterministic cases, no error bars.")
            root.insert(0, title)
            root.insert(1, description)
            tree.write(path, encoding="utf-8", xml_declaration=True)
        finally:
            plt.close(figure)
    policy = {"source": GUIDE, "checked_on": "2026-10-31", "width_mm": 183, "height_mm": 132,
              "font": FONT, "font_pt": 6.5, "font_range_pt": [6, 7], "pdf_font_type": 42,
              "editable_text": True, "rasterized": False, "colours": [STANDARD, FIXED, REFERENCE],
              "zero_policy": "exact zeros separate from logarithmic axes; no invented numerical floor",
              "replication": "deterministic grids; no error bars or sample-based significance claims"}
    (output / "figure-policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    return policy
