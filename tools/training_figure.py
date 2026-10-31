"""Export every registered training trajectory; no desired-result filtering."""
from __future__ import annotations

import csv
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from tools.numerics_figure import STYLE, STANDARD, FIXED


def render_training(output: Path, report: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(STYLE):
        figure, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 70 / 25.4))
        figure.subplots_adjust(left=.11, right=.98, bottom=.24, top=.8, wspace=.36)
        rows = []
        for run in report["runs"]:
            for name, variant in run["variants"].items():
                points = variant["checkpoints"]
                for axis, key in zip(axes, ("parameter_displacement_l2", "heldout_kl_float64")):
                    axis.plot([r["step"] for r in points], [r[key] for r in points],
                              color=FIXED if name == "fixed" else STANDARD,
                              linestyle="-" if name == "fixed" else "--", linewidth=.85,
                              alpha=1 if name == "fixed" else .65)
                rows.extend({"seed": run["seed"], "variant": name, **r} for r in points)
        axes[0].set(xlabel="Full-batch Adam step", ylabel="Parameter displacement (L2)",
                    title="a   Movement from the teacher")
        axes[1].set(xlabel="Full-batch Adam step", ylabel="Held-out KL (evaluated in float64)",
                    title="b   Distribution drift")
        axes[1].set_yscale("symlog", linthresh=1e-12)
        for axis in axes:
            title = axis.get_title()
            axis.set_title("")
            axis.set_title(title, loc="left", fontsize=7, pad=10)
            axis.spines[["top", "right"]].set_visible(False)
            axis.tick_params(direction="out", length=2.5, width=.5)
            axis.grid(axis="y", color="#e6e6e6", linewidth=.4)
        figure.legend(handles=[Line2D([], [], color=STANDARD, linestyle="--", label="Standard · each of 3 seeds"),
                               Line2D([], [], color=FIXED, label="Fixed · all 3 seeds coincide at exact zero")],
                      loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(.53, .99))
        figure.text(.11, .035, "KL axis: signed symmetric log, linear within ±1e−12. No data floor or confidence intervals.", fontsize=6)
        try:
            figure.savefig(output / "trajectory.svg", metadata={"Date": None, "Creator": "Eidos"})
            figure.savefig(output / "trajectory.pdf", metadata={"CreationDate": None, "ModDate": None, "Creator": "Eidos"})
            figure.savefig(output / "trajectory.png", dpi=300)
        finally:
            plt.close(figure)
    with (output / "trajectory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
