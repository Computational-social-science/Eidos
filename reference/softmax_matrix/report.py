"""Generate every paired result and publication panel from accepted evidence."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from reference.softmax_matrix.verify import validate, validate_final_check


def build(output):
    p = json.loads((HERE / "protocol.json").read_text())
    r = json.loads((HERE / "docs/evidence.json").read_text())
    errors = validate(r, p)
    if not errors:
        errors = validate_final_check(r)
    if errors:
        raise ValueError(errors)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    from tools.numerics_figure import STYLE, STANDARD, FIXED
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    markers = ("o", "s", "D")
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 3, figsize=(183 / 25.4, 130 / 25.4), sharex=True, sharey=True)
        fig.subplots_adjust(left=.08, right=.97, bottom=.10, top=.86, wspace=.14, hspace=.31)
        for i, dtype in enumerate(p["loss_dtypes"]):
            for j, epsilon in enumerate(p["epsilons"]):
                axis = axes[i, j]
                for run in r["runs"]:
                    if run["loss_dtype"] != dtype or run["epsilon"] != epsilon:
                        continue
                    pts = run["checkpoints"]
                    axis.plot([v["step"] for v in pts], [100 * v["test_accuracy"] for v in pts],
                              color=FIXED if run["arm"] == "fixed" else STANDARD,
                              linestyle="-" if run["arm"] == "fixed" else "--", linewidth=.75,
                              marker=markers[run["seed"]], markevery=10, markersize=2, alpha=.8)
                axis.set_title(f"{'abcdef'[i*3+j]}   {dtype} · ε = {epsilon:g}", loc="left", fontsize=7)
                axis.set_ylim(-2, 102); axis.set_xlim(0, p["epochs"])
                axis.set_xticks([0, 5000, 10000]); axis.set_yticks([0, 50, 100])
                if i == 1: axis.set_xlabel("Epoch")
                if j == 0: axis.set_ylabel("Held-out accuracy (%)")
                axis.spines[["top", "right"]].set_visible(False)
                axis.grid(axis="y", color="#dddddd", linewidth=.4)
        handles = [Line2D([], [], color=STANDARD, linestyle="--", label="Standard"),
                   Line2D([], [], color=FIXED, label="Fixed")]
        handles += [Line2D([], [], color="#333333", linestyle="none", marker=m, markersize=3,
                           label=f"Seed {seed}") for seed, m in enumerate(markers)]
        fig.legend(handles=handles, ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(.53, .985))
        fig.text(.08, .025, "Model and forward: float32. Only loss-entry logits change precision. All registered seeds; no confidence intervals.", fontsize=6)
        for fmt in ("svg", "pdf", "png"):
            metadata = {"Date": None} if fmt == "svg" else ({"CreationDate": None, "ModDate": None} if fmt == "pdf" else {})
            fig.savefig(output / f"accuracy-matrix.{fmt}", dpi=300, metadata=metadata)
        plt.close(fig)
    trajectories = [{"seed": v["seed"], "loss_dtype": v["loss_dtype"], "epsilon": v["epsilon"],
                     "arm": v["arm"], **pt} for v in r["runs"] for pt in v["checkpoints"]]
    with (output / "trajectories.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(trajectories[0])); writer.writeheader(); writer.writerows(trajectories)
    paired = []
    lines = ["# Loss precision × epsilon: paired reconstruction", "",
             "All 36 specified training trajectories completed, with independently checked final models and gradient endpoints.", "",
             "Locally registered follow-up; three seeds, float32 model/forward, two supported loss precisions and three epsilon values. Not an exact paper reproduction. bfloat16 remains UNQUALIFIED.", "",
             "All cells below are retained. Delta is fixed minus standard in percentage points; no population inference or significance test.", "",
             "| Loss dtype | Epsilon | Seed | Standard test (%) | Fixed test (%) | Delta (pp) |",
             "|---|---:|---:|---:|---:|---:|"]
    for dtype in p["loss_dtypes"]:
        for eps in p["epsilons"]:
            for seed in p["seeds"]:
                arms = {v["arm"]: v for v in r["runs"] if (v["seed"], v["loss_dtype"], v["epsilon"]) == (seed, dtype, eps)}
                a, b = (arms[k]["checkpoints"][-1] for k in ("standard", "fixed"))
                row = {"loss_dtype": dtype, "epsilon": eps, "seed": seed,
                       "standard_test_accuracy": a["test_accuracy"], "fixed_test_accuracy": b["test_accuracy"],
                       "delta_percentage_points": 100 * (b["test_accuracy"] - a["test_accuracy"]),
                       "standard_margin": a["mean_margin"], "fixed_margin": b["mean_margin"],
                       "standard_zero_target_model": a["zero_target_model"], "fixed_zero_target_model": b["zero_target_model"]}
                paired.append(row)
                lines.append(f"| {dtype} | {eps:g} | {seed} | {100*a['test_accuracy']:.3f} | {100*b['test_accuracy']:.3f} | {row['delta_percentage_points']:+.3f} |")
    wins = sum(v["delta_percentage_points"] > 0 for v in paired)
    losses = sum(v["delta_percentage_points"] < 0 for v in paired)
    fixed_points = [pt for run in r["runs"] if run["arm"] == "fixed" for pt in run["checkpoints"]]
    standard_points = [pt for run in r["runs"] if run["arm"] == "standard" for pt in run["checkpoints"]]
    maximum_zeros = max(pt["zero_target_model"] for pt in standard_points)
    fixed_zeros = max(pt["zero_target_model"] for pt in fixed_points)
    best = max(run["checkpoints"][-1]["test_accuracy"] for run in r["runs"])
    lines[4:4] = [f"**Observed result:** fixed CE is higher in {wins}/{len(paired)} paired endpoints, lower in {losses}/{len(paired)}, and tied in {len(paired)-wins-losses}/{len(paired)}. The best final held-out accuracy across all arms is {100*best:.3f}%. These runs do not reproduce the paper's high-generalization table and do not establish a uniform finite-budget generalization benefit.", "",
                  f"At the model interface, the fixed arm's maximum target-zero count is {fixed_zeros} across {len(fixed_points)} producer-recorded checkpoints; standard CE reaches {maximum_zeros}/{standard_points[0]['sample_count']}. Final gradient counts are independently reloaded; intermediate counts are recorded by the producer.", ""]
    lines += ["", "## Evidence and limitations", "",
              "Six float32/epsilon=1e-8 final model hashes exactly replay the parent experiment. All cells reuse that parent's original initial models and splits.", "",
              "Each trajectory records 51 checkpoints, including actual training-batch target-gradient zero counts before and after the loss-to-model precision boundary. Final counts are independently replayed from all 36 saved models on the recorded CUDA runtime. Intermediate counters remain producer logs, not an independently reloaded trajectory.", "",
              "Final held-out predictions, margins and float64 cross-entropy are independently recomputed from raw saved tensors by NumPy. Cross-entropy comparisons use relative error with no absolute floor.", "",
              "The full loss-precision/epsilon grid of supported kernels is covered; the paper's bf16 grid, additional baselines, unspecified architecture/initialization choices and further tasks remain outside this reconstruction. Generalization can depend strongly on seed and implementation choices.", "",
              "[Source paper, section 6 and Table 1](https://arxiv.org/html/2610.31642v3#S6). The protocol and source hashes define this local study; completed cells are not selected for favorable outcomes.", "",
              "Downloads: [trajectories](trajectories.csv), [paired endpoints](paired.csv), [protocol](protocol.json), [raw evidence](evidence.json), [final gradient audit](final-gradient-check.json), [source and checkpoints](reproduce.zip).", "",
              "Publication masters: [editable SVG](accuracy-matrix.svg), [PDF at 183 mm](accuracy-matrix.pdf).", "",
              "CPU acceptance: `python reference/softmax_matrix/verify.py`. Retraining needs the recorded CUDA runtime and a separately registered output location; the original producer refuses overwrite."]
    (HERE / "docs/REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with (output / "paired.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(paired[0])); writer.writeheader(); writer.writerows(paired)
    header = "---\ntitle: 'Softmax: loss precision and epsilon matrix'\nlang: en\nformat:\n  html:\n    embed-resources: true\n  pdf:\n    pdf-engine: lualatex\n    geometry: margin=1in\n  docx: default\n---\n\n"
    pictures = """
::: {.content-visible when-format="pdf"}
![All seeds and both repair arms across the supported matrix.](accuracy-matrix.pdf){width=100%}
:::
::: {.content-visible when-format="html"}
![All seeds and both repair arms across the supported matrix.](accuracy-matrix.svg){width=100%}
:::
::: {.content-visible when-format="docx"}
![All seeds and both repair arms across the supported matrix.](accuracy-matrix.png){width=100%}
:::
"""
    (output / "report.qmd").write_text(header + pictures + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for source, name in ((HERE / "protocol.json", "protocol.json"), (HERE / "docs/evidence.json", "evidence.json"),
                         (HERE / "docs/final-gradient-check.json", "final-gradient-check.json")):
        shutil.copyfile(source, output / name)
    return paired


def bundle(output):
    output = Path(output)
    files = {}
    for folder in (HERE, ROOT / "reference/softmax_grokking", ROOT / "framework"):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix in (".py", ".json", ".yaml", ".md", ".pt") and "__pycache__" not in path.parts:
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("pyproject.toml", "uv.lock", "configs/global/framework.yaml", "projects/softmax_matrix/project.yaml",
                 "reference/softmax_training/train.py", "reference/softmax_training/validate.py",
                 "tools/numerics_figure.py", "tests/test_softmax_matrix.py", "tests/test_softmax_matrix_torch.py"):
        files[name] = (ROOT / name).read_bytes()
    files["SOURCE-README.md"] = (ROOT / "README.md").read_bytes()
    for path in ROOT.glob("LICENSE*"):
        if path.is_file(): files[path.name] = path.read_bytes()
    files["README.md"] = b"Eidos supported loss-precision matrix. Select a Python >=3.11 environment.\nuv sync --locked --extra dev --extra verifiers\nuv run --no-sync python reference/softmax_matrix/verify.py\nuv run --no-sync python -m pytest tests/test_softmax_matrix.py -q\nThe saved CPU acceptance does not rerun CUDA training. All models and original parent initial states are included.\n"
    files["checksums.json"] = json.dumps({n: hashlib.sha256(b).hexdigest() for n, b in files.items()}, indent=2).encode()
    with zipfile.ZipFile(output / "reproduce.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, body)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--render", action="store_true")
    args = parser.parse_args(); output = ROOT / "site/reports/softmax-matrix"
    rows = build(output)
    if args.render:
        import os
        quarto = os.environ.get("QUARTO_BIN") or shutil.which("quarto")
        if not quarto: raise RuntimeError("Quarto missing")
        for fmt in ("html", "pdf", "docx"):
            subprocess.run([quarto, "render", "report.qmd", "--to", fmt], cwd=output, check=True)
    bundle(output)
    print(json.dumps({"paired_cells": len(rows), "output": str(output)}))


if __name__ == "__main__":
    main()
