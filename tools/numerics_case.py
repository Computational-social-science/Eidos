"""Build the scientific showcase from measured kernels, never browser arithmetic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
import platform
import tomllib
import os
import shutil
import subprocess
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from framework import stable_numerics as kernels
from framework.verifiers import numerics

PAPER = "https://arxiv.org/html/2610.31642v3"


def training_summary() -> dict:
    path = ROOT / "reference/softmax_training/docs/evidence.json"
    if not path.is_file():
        return {"status": "UNRUN"}
    from reference.softmax_training.validate import validate_report
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        protocol = json.loads((path.parents[1] / "protocol.json").read_text(encoding="utf-8"))
        errors = validate_report(report, protocol)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {"status": "ERROR", "findings": [str(exc)]}
    return {"status": "FAIL" if errors else "PASS", "findings": errors,
            "scope": report.get("protocol", {}).get("scope"), "runtime": report.get("runtime"),
            "trajectories": [{"seed": run["seed"], "variant": name,
                              "checkpoints": variant["checkpoints"]}
                             for run in report.get("runs", [])
                             for name, variant in run["variants"].items()],
            "steps": protocol.get("distillation_steps"), "seeds": [
                {"seed": r["seed"], "teacher_train_accuracy": r["teacher_train_accuracy"],
                 "teacher_test_accuracy": r["teacher_test_accuracy"],
                 "standard_displacement": r["variants"]["standard"]["checkpoints"][-1]["parameter_displacement_l2"],
                 "fixed_displacement": r["variants"]["fixed"]["checkpoints"][-1]["parameter_displacement_l2"]}
                for r in report.get("runs", [])]}


def _error(observed, reference) -> tuple[float | None, float, float]:
    # Compare in the independent arithmetic, before rounding its reference to binary64.
    with localcontext() as context:
        context.prec = 80
        values = [Decimal.from_float(float(value)) for value in observed]
        absolute = sum(((value - expected) ** 2 for value, expected in zip(values, reference)), Decimal(0)).sqrt()
        norm = sum((expected ** 2 for expected in reference), Decimal(0)).sqrt()
        relative = float(absolute / norm) if norm else (0.0 if absolute == 0 else None)
        return relative, float(absolute), float(norm)


def _standard_logs(z):
    shifted = z - z.max()
    return shifted - np.log(np.exp(shifted).sum())  # numerics: intentional negative baseline


def build_case() -> dict:
    """Actual NumPy float32/64 cases; references use independent Decimal arithmetic."""
    collapse, cancellation = [], []
    for dtype in ("float32", "float64"):
        for margin in range(0, 81, 2):
            z = np.array([margin, 0, 0], dtype=dtype)
            logs = _standard_logs(z)
            standard = np.exp(logs)
            standard[0] -= 1
            loss, fixed = kernels.hard_cross_entropy(z, 0)
            expected_loss, reference = numerics.reference_cross_entropy(z, 0)
            standard_error, _, _ = _error(standard, reference)
            fixed_error, _, _ = _error(fixed, reference)
            collapse.append({"dtype": dtype, "margin": margin,
                             "fixed_dtype": str(fixed.dtype), "fixed_loss_dtype": str(np.asarray(loss).dtype),
                             "standard_loss": float(-logs[0]), "fixed_loss": float(loss),
                             "fixed_loss_relative_error": numerics._relative_error(float(loss), expected_loss),
                             "reference_loss": str(expected_loss),
                             "standard_gradient": standard.tolist(), "fixed_gradient": fixed.tolist(),
                             "reference_gradient": [str(value) for value in reference],
                             "standard_error": standard_error, "fixed_error": fixed_error,
                             "standard_residual": abs(float(standard.astype(np.float64).sum())),
                             "fixed_residual": abs(float(fixed.astype(np.float64).sum()))})
        teacher = np.array([2, 1, 0], dtype=dtype)
        teacher_shifted = teacher - teacher.max()
        p = np.exp(teacher_shifted) / np.exp(teacher_shifted).sum()
        for perturbation in (0, 1e-3, 1e-5, 1e-7, 1e-9, 1e-12, 1e-14):
            student = teacher + np.array([-perturbation, perturbation, 0], dtype=dtype)
            # Conventional softmax forward versus exp(log_softmax) backward.
            standard = np.exp(_standard_logs(student)) - p
            _, fixed = kernels.logit_distillation(student, teacher)
            reference = numerics.reference_distillation(student, teacher)
            standard_error, standard_absolute, norm = _error(standard, reference)
            fixed_error, fixed_absolute, _ = _error(fixed, reference)
            cancellation.append({"dtype": dtype, "perturbation": perturbation,
                                 "student": student.tolist(), "teacher": teacher.tolist(),
                                 "represented_delta": (student - teacher).tolist(),
                                 "standard_gradient": standard.tolist(), "fixed_gradient": fixed.tolist(),
                                 "reference_gradient": [str(value) for value in reference],
                                 "standard_error": standard_error, "fixed_error": fixed_error,
                                 "standard_absolute_error": standard_absolute,
                                 "fixed_absolute_error": fixed_absolute,
                                 "reference_norm": norm, "stationary": bool(np.array_equal(student, teacher))})
    qualification = numerics.kernel_regression_report()
    failed = []
    for mechanism, rows in (("collapse", collapse), ("cancellation", cancellation)):
        for row in rows:
            tolerance = 5e-5 if row["dtype"] == "float32" else 1e-11
            error = row["fixed_error"]
            invalid = error is None or not np.isfinite(error) or error > tolerance
            if mechanism == "collapse":
                loss_error = row["fixed_loss_relative_error"]
                invalid = (invalid or not np.isfinite(loss_error) or loss_error > tolerance
                           or row["fixed_dtype"] != row["dtype"] or row["fixed_loss_dtype"] != row["dtype"]
                           or len(row["fixed_gradient"]) != len(row["reference_gradient"]))
            if invalid:
                failed.append({"mechanism": mechanism, "dtype": row["dtype"],
                               "parameter": row.get("margin", row.get("perturbation")),
                               "relative_error": error})
    qualification["sweep"] = {"verdict": "FAIL" if failed else "PASS",
                               "checked": len(collapse) + len(cancellation), "failed": failed}
    if failed:
        qualification["verdict"] = "FAIL"
    return {"paper": PAPER, "paper_version": "2610.31642v3", "backend": f"numpy {np.__version__}",
            "scope": "Published numerical kernels and a separately qualified adapted optimizer-stationarity experiment; not paper-wide training, grokking or generalisation.",
            "provenance": {"python": platform.python_version(),
                           "eidos": tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"],
                           "seed": None, "data": "deterministic logit grids, no sampled or external dataset",
                           "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ("framework/stable_numerics.py", "framework/verifiers/numerics.py",
                                           "tools/numerics_case.py", "tools/numerics_figure.py", "uv.lock")}},
            "qualification": qualification, "collapse": collapse,
            "cancellation": cancellation,
            "training": training_summary(),
            "figures": {dtype: {fmt: f"reports/numerics/figure-{dtype}.{fmt}"
                                for fmt in ("svg", "pdf")} for dtype in ("float32", "float64")},
            "downloads": {"report": "reports/numerics/report.html", "json": "reports/numerics/evidence.json",
                          "csv": "reports/numerics/cases.csv", "bundle": "reports/numerics/reproduce.zip",
                          "pdf": "reports/numerics/report.pdf", "docx": "reports/numerics/report.docx"}}


def _report_source(data: dict) -> str:
    from tools.publication import header, declarations, caption_tables, caption_figures
    lines = ["## Summary", "",
             "Softmax arithmetic can lose scientifically relevant derivatives while conventional stability checks still pass. "
             "We evaluate the published repairs [1] using independently defined high-precision references, deliberately broken "
             "controls and saved teacher–student models. The tested kernels preserve small target gradients and exact "
             "stationarity within the qualified input range. The training experiment separates numerical correctness "
             "from generalisation. This report records the repair, unfavorable outcomes and reproducible artifacts, "
             "with explicit limits on backend qualification and downstream claims.", "",
             "## Scope and research gap", "",
             f"Source: [A Fix for Softmax and Cross-Entropy, v3]({PAPER}).",
             "This reproduces published numerical mechanisms and repairs the existing Paper2Agent integration.",
             "It is not a novel scientific discovery or a reproduction of the paper's training outcomes.", "",
             "The scientific gap in the source paper is a numerical failure hidden by conventional stability checks: a finite, well-scaled loss can still have an incorrect gradient.",
             "Eidos uses this as an adversarial acceptance case: reproducing a displayed number alone is insufficient.", "",
             "## Mechanisms", "",
             r"For hard target 0 and $z=(m,0,0)$, the exact target derivative is $-2e^{-m}/(1+2e^{-m})$.",
             "The standard subtraction `q[0]-1` becomes zero after the precision cliff while the other derivatives remain positive. A max shift prevents overflow but does not repair this subtraction.",
             "The fixed forward excludes exactly one argmax before `log1p`; the hard-target backward computes the target derivative as the negative sum of the other derivatives (source Eqs. 5-7).", "",
             "For distillation, the true gradient is student probability minus teacher probability. Near equal logits this subtraction loses relative accuracy; exact equality should yield zero.",
             "The repair uses centered logit differences, `expm1`/`log1p`, and a zero-sum correction, with the ordinary difference retained for the far branch (source Eqs. 8-9). Teacher logits are required for this contract; already-rounded probabilities cannot recover lost information.", "",
             "## Methods", "", "### Numerical execution and independent references", "",
             f"Backend: {data['backend']}. Decimal references use represented inputs and adaptive precision.",
             f"Eidos {data['provenance']['eidos']}; Python {data['provenance']['python']}. No random seed applies to this deterministic grid.",
             "Source and lock SHA-256 hashes are recorded in evidence.json; bundle checksums cover the shipped source.",
             "The browser selects recorded cases; it does not simulate float32 training.", "",
             "### Statistics and experimental units", "",
             "The 96 numerical cases are deterministic input settings, not 96 independent random replicates. "
             "No error bars, confidence intervals or significance tests are used for this grid. The teacher–student "
             "experiment reports every one of three declared seed pairs; an experimental unit is one trained model, "
             "and the paired arms share their initial teacher and split. Individual trajectories are shown.", "",
             "## Numerical results", "",
             '::: {.content-visible when-format="pdf"}',
             '![Figure 1 | Numerical repair in float32. a, Target-gradient magnitude across the logit gap. b, Relative L2 gradient error against independent Decimal arithmetic. c, Relative error near the teacher, using represented logit differences. d, Absolute L2 error at exact teacher equality. Lines show deterministic cases; no error bars or random sampling apply. Exact zeros are labelled and excluded from logarithmic traces. All quantities are dimensionless.](figure-float32.pdf){width=100%}', ':::', '',
             '::: {.content-visible when-format="html"}',
             '![Figure 1 | Numerical repair in float32. a, Target-gradient magnitude. b, Relative L2 error against Decimal arithmetic. c, Relative error near the teacher using represented logit differences. d, Absolute L2 error at exact equality. Deterministic cases; no error bars. Exact zeros are labelled rather than given a positive floor. All quantities are dimensionless.](figure-float32.svg){width=100%}', ':::', '',
             '::: {.content-visible when-format="docx"}',
             '![Figure 1 | Numerical repair in float32. a, Target-gradient magnitude. b, Relative L2 error against Decimal arithmetic. c, Relative error near the teacher using represented logit differences. d, Absolute L2 error at exact equality. Deterministic cases; no error bars. Exact zeros are labelled. All quantities are dimensionless.](figure-float32.png){width=100%}', ':::', '',
             "| Input dtype | Dominant logit | Standard target gradient | Fixed target gradient | Fixed relative L2 error |",
             "|---|---:|---:|---:|---:|"]
    for dtype, margin in (("float32", 18), ("float64", 40), ("float64", 80)):
        row = next(r for r in data["collapse"] if r["dtype"] == dtype and r["margin"] == margin)
        lines.append(f"| {dtype} | {margin} | {row['standard_gradient'][0]:.6e} | "
                     f"{row['fixed_gradient'][0]:.6e} | {row['fixed_error']:.3e} |")
    lines += ["", '::: {.content-visible when-format="pdf"}', "```{=latex}", r"\newpage", "```", ":::", "",
              "## Cancellation and stationarity", "",
              "| Input dtype | Requested perturbation | Represented perturbation | Standard absolute error | Fixed absolute error |",
              "|---|---:|---:|---:|---:|"]
    for row in data["cancellation"]:
        if row["perturbation"] in (0, 1e-7):
            lines.append(f"| {row['dtype']} | {row['perturbation']:.1e} | {row['represented_delta'][0]:.6e} | "
                         f"{row['standard_absolute_error']:.6e} | {row['fixed_absolute_error']:.6e} |")
    lines += ["", "## Controls and acceptance", "",
              f"Qualification: **{data['qualification']['verdict']}** on {len(data['qualification']['cases'])} cases.",
              "Both deliberately broken controls must be rejected: a lost target gradient and nonzero stationary gradient.",
              "Validation uses relative gradient errors, not an absolute tolerance floor.", "",
              "## What the Eidos pipeline demonstrates", "",
              "| Stage | Acceptance evidence |",
              "|---|---|",
              "| Literature to tool | Existing Paper2Agent conversion upgraded; four MCP tools retained, with call traces |",
              "| Independent verification | Decimal definitions over represented inputs; float32/64 dtype preservation |",
              "| Falsification | Collapsed target and stationary-noise controls must be rejected |",
              "| Repeatable delivery | 82 collapse and 14 cancellation cases feed the site, JSON, CSV and this report |",
              "| Reuse | NumPy kernels, optional first-order Torch kernels and a numerical audit in CI |",
              "| Provenance | Locked dependencies, source SHA-256 and a checksummed source bundle |", "",
              "## Reuse and limits", "",
              "Use `framework.stable_numerics` for NumPy and `framework.stable_numerics_torch` for optional Torch.",
              "The existing MCP/agent retains four tools and explicitly separates teacher logits from legacy probabilities.",
              "Supported inputs are finite float32/float64; exponent underflow and already-rounded inputs cannot be recovered.",
              "Torch custom loss backward is first-order only; AMP/bfloat16 and higher-order derivatives need separate qualification.",
              "Static screening is heuristic. A passing built-in kernel does not certify a consumer's untested backend.", "",
              "## Reproduce", "", "```bash", "uv sync --locked --extra dev",
              "uv run --no-sync python reproduce.py", "uv run --no-sync python -m pytest tests -q", "```", "",
              "The ZIP includes source, lock, tests, evidence, and checksums. JSON and CSV expose every displayed case."]
    training = data.get("training", {})
    if training.get("status") == "PASS":
        lines += ["", "## Optimizer-level before / after", "",
                  "A corrected mechanistic rerun uses trained modular-addition MLP teachers and three declared seeds.",
                  f"Both students start with identical represented logits; each runs {training['steps']} full-batch Adam steps.", "",
                  "| Seed | Standard final parameter L2 displacement | Fixed final parameter L2 displacement | Teacher held-out accuracy (%) |",
                  "|---|---:|---:|---:|"]
        for row in training["seeds"]:
            lines.append(f"| {row['seed']} | {row['standard_displacement']:.8g} | {row['fixed_displacement']:.8g} | {row['teacher_test_accuracy'] * 100:.4g} |")
        lines += ["", "All teachers reached 100% training accuracy but approximately 0-0.0712% held-out accuracy.",
                  "This is a stationarity mechanism experiment, not evidence for generalisation or the full paper's training results.",
                  "Saved weights independently reproduce the primary endpoint. All seeds, split identities, protocol and model checkpoints are included in the source bundle.",
                  "The first run failed because a full-batch teacher cache differed from a training-batch forward. The failed code, evidence and checkpoints are preserved; the corrected run asserts exact initial logit equality.", "",
                  '::: {.content-visible when-format="pdf"}',
                  '![Figure 2 | Stationarity across all three seed pairs. a, Parameter L2 displacement from the initial teacher. b, Held-out KL evaluated in float64. Every line is one paired training trajectory; all fixed trajectories coincide at zero. No error bars or population inference. The KL axis is symmetric log with a linear region within plus or minus 1e-12; signed numerical residuals are retained.](training/trajectory.pdf){width=100%}', ':::', '',
                  '::: {.content-visible when-format="html"}',
                  '![Figure 2 | All three paired seeds. a, Parameter L2 displacement. b, Held-out KL in float64. Individual trajectories; fixed arms coincide at zero. No error bars. Symmetric-log KL axis, linear within plus or minus 1e-12; signed residuals are retained.](training/trajectory.svg){width=100%}', ':::', '',
                  '::: {.content-visible when-format="docx"}',
                  '![Figure 2 | All three paired seeds. a, Parameter L2 displacement. b, Held-out KL in float64. Individual trajectories; fixed arms coincide at zero. No error bars. Symmetric-log KL axis, linear within plus or minus 1e-12.](training/trajectory.png){width=100%}', ':::', '']
    captions = ['Table 1 | Selected collapse cases and dimensionless gradient errors.',
                'Table 2 | Requested and represented perturbations and absolute gradient errors.',
                'Table 3 | Pipeline stages and their acceptance evidence.']
    if training.get('status') == 'PASS':
        captions.append('Table 4 | Final displacement and teacher held-out accuracy for every seed pair.')
    return header('Independent validation of Softmax numerical repairs') + caption_figures(caption_tables('\n'.join(lines), captions)) + declarations()


def export_case(output: Path, data: dict | None = None) -> None:
    from framework.artifacts import output_lock
    with output_lock(output):
        _export_case(output, data)


def _export_case(output: Path, data: dict | None = None) -> None:
    """Export evidence, a single-source report and a self-contained source bundle."""
    data = build_case() if data is None else data
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    from tools.numerics_figure import render_figures
    render_figures(output, data)
    evidence = json.dumps(data, indent=2, allow_nan=False).encode("utf-8")
    (output / "evidence.json").write_bytes(evidence)
    (output / "report.qmd").write_text(_report_source(data), encoding="utf-8")
    (output / "paper2agent.md").write_bytes((ROOT / "reference/barron2026_agent/docs/REPORT.md").read_bytes())
    if data.get("training", {}).get("status") == "PASS":
        from tools.training_figure import render_training
        target = output / "training"
        target.mkdir(exist_ok=True)
        directory = ROOT / "reference/softmax_training"
        report = json.loads((directory / "docs/evidence.json").read_text(encoding="utf-8"))
        render_training(target, report)
        for origin, name in ((directory / "docs/evidence.json", "evidence.json"),
                             (directory / "protocol.json", "protocol.json"),
                             (directory / "docs/failed-batch-shape.zip", "failed-batch-shape.zip")):
            (target / name).write_bytes(origin.read_bytes())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["mechanism", "dtype", "input_parameter", "standard_target_gradient",
                     "fixed_target_gradient", "reference_target_gradient", "standard_relative_error", "fixed_relative_error"])
    for mechanism, rows in (("collapse", data["collapse"]), ("cancellation", data["cancellation"])):
        for row in rows:
            writer.writerow([mechanism, row["dtype"], row.get("margin", row.get("perturbation")),
                             row["standard_gradient"][0], row["fixed_gradient"][0], row["reference_gradient"][0],
                             row["standard_error"], row["fixed_error"]])
    (output / "cases.csv").write_text(stream.getvalue(), encoding="utf-8")
    payloads = {"pyproject.toml": (ROOT / "pyproject.toml").read_bytes(), "uv.lock": (ROOT / "uv.lock").read_bytes(),
                "evidence.json": evidence, "report.qmd": _report_source(data).encode("utf-8"),
                "cases.csv": stream.getvalue().encode("utf-8"),
                "README.md": ("# Eidos numerical reproduction\n\n" + data["scope"] +
                              "\n\nuv sync --locked --extra dev\nuv run --no-sync python reproduce.py\n"
                              "uv run --no-sync python -m pytest tests -q\n\nSource: " + PAPER + "\n").encode("utf-8"),
              "reproduce.py": b"import hashlib,json\nfrom pathlib import Path\nfrom tools.numerics_case import build_case,export_case\nroot=Path(__file__).parent\nfor name,digest in json.loads((root/'checksums.json').read_text()).items():\n    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:\n        raise SystemExit('Checksum mismatch: '+name)\ndata=build_case()\nexport_case(root/'regenerated',data)\nprint(json.dumps(data['qualification'],indent=2))\nprint('Regenerated all 96 displayed cases, CSV, report source and bundle in regenerated/')\nraise SystemExit(0 if data['qualification']['verdict']=='PASS' else 1)\n"}
    payloads["tools/numerics_case.py"] = Path(__file__).read_bytes()
    payloads["tools/numerics_figure.py"] = (ROOT / "tools/numerics_figure.py").read_bytes()
    payloads["tools/training_figure.py"] = (ROOT / "tools/training_figure.py").read_bytes()
    payloads["tools/publication.py"] = (ROOT / "tools/publication.py").read_bytes()
    payloads["tools/verify_barron_mcp.py"] = (ROOT / "tools/verify_barron_mcp.py").read_bytes()
    payloads["README.md"] += ("\nCPU verification of the saved training run:\n"
                              "uv run --no-sync python -m framework.project check softmax_training\n"
                              "\nExisting MCP/agent (optional dependency):\n"
                              "uv sync --locked --extra dev --extra agent\n"
                              "uv run --no-sync python -m framework.project check barron2026_agent\n"
                              "\nTo rerun training, use a CUDA environment matching reference/softmax_training/docs/evidence.json runtime.\n"
                              "python reference/softmax_training/train.py\n"
                              "This adapted stationarity experiment does not reproduce the paper's generalisation result.\n").encode("utf-8")
    for name in ("softmax_training", "barron2026_agent"):
        payloads[f"projects/{name}/project.yaml"] = (ROOT / f"projects/{name}/project.yaml").read_bytes()
    for path in sorted((output / "training").glob("*")):
        if path.is_file():
            payloads[f"training/{path.name}"] = path.read_bytes()
    for path in sorted(output.glob("figure-*")):
        if path.suffix in {".svg", ".pdf", ".png", ".json"}:
            payloads[path.name] = path.read_bytes()
    for path in sorted((ROOT / "framework").rglob("*.py")):
        payloads[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("test_stable_numerics.py", "test_numerics_preflight.py", "test_numerics_case.py", "test_numerics_figure.py",
                 "test_training_consumer.py", "test_training_figure.py", "test_softmax_training_torch.py", "test_stable_numerics_torch.py"):
        payloads[f"tests/{name}"] = (ROOT / "tests" / name).read_bytes()
    # Preserve the existing converted tool/agent, excluding environments and generated caches.
    for directory in (ROOT / "reference/barron2026_agent", ROOT / "reference/reproduction/barron2026/mcp",
                      ROOT / "reference/softmax_training"):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and (path.suffix in {".py", ".md", ".json", ".yaml", ".txt", ".pt", ".zip"}
                                   or path.name in {"LICENSE", "COPYING", "NOTICE"}) and "__pycache__" not in path.parts:
                payloads[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    payloads["reference/reproduction/barron2026/specs.json"] = (ROOT / "reference/reproduction/barron2026/specs.json").read_bytes()
    checksums = {name: hashlib.sha256(content).hexdigest() for name, content in payloads.items()}
    from framework.artifacts import atomic_output
    with atomic_output(output / "reproduce.zip") as temporary:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
            for name, content in payloads.items():
                bundle.writestr(name, content)
            bundle.writestr("checksums.json", json.dumps(checksums, indent=2))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "site/reports/numerics")
    parser.add_argument("--render", action="store_true", help="also render HTML, PDF and DOCX with Quarto")
    args = parser.parse_args(argv)
    from framework.artifacts import output_lock
    with output_lock(args.out):
        return _deliver(args)


def _deliver(args) -> int:
    data = build_case()
    _export_case(args.out, data)
    if args.render:
        quarto = os.environ.get("QUARTO_BIN") or shutil.which("quarto")
        if not quarto:
            print("ERROR: Quarto is required for --render; configure QUARTO_BIN")
            return 2
        from tools.publication import reference_docx, finish_docx
        reference_docx(args.out, quarto)
        for target in ("html", "pdf", "docx"):
            result = subprocess.run([quarto, "render", "report.qmd", "--to", target], cwd=args.out)
            if result.returncode or not (args.out / f"report.{target}").is_file():
                print(f"ERROR: {target} report delivery failed")
                return 2
        finish_docx(args.out)
    print(f"{data['qualification']['verdict']}: {len(data['collapse'])} collapse and "
          f"{len(data['cancellation'])} cancellation cases exported to {args.out}")
    training_ok = data.get("training", {}).get("status") not in ("FAIL", "ERROR")
    return 0 if data["qualification"]["verdict"] == "PASS" and training_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
