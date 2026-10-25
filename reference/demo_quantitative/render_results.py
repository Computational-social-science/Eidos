"""Render the measurement into a document — the render chain, not a screenshot.

Quarto is located through QUARTO_BIN, then PATH, then the repository's tools/quarto. The artefact
is written next to this script so the project carries its own output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"
EVIDENCE = DOCS / "evidence.json"
QMD = DOCS / "results.qmd"


def quarto() -> str | None:
    """QUARTO_BIN, then PATH, then a sibling tools/ checkout at any ancestor."""
    candidates = [os.environ.get("QUARTO_BIN"), shutil.which("quarto")]
    for ancestor in (HERE, *HERE.parents):
        candidates.append(str(ancestor / "tools" / "quarto" / "bin" / "quarto.exe"))
    candidates.append("/usr/local/bin/quarto")
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def main() -> int:
    binary = quarto()
    if binary is None:
        print("quarto not found: set QUARTO_BIN (SKIP, not a pass)")
        return 3
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    # Static markdown, numbers substituted here: an executable chunk would make the demo depend
    # on a Jupyter kernel, and a render chain that needs one is a render chain nobody runs.
    QMD.write_text(f"""---
title: "Planted-truth recovery"
format: html
---

The planted effect is **{data['theta_true']}**. Across {data['n_sims']} simulations of
{data['n_per_sim']} observations the mean estimate is **{data['theta_hat']}**
(bias {data['bias']:+.4f}), and the interval covers the planted value in
**{data['coverage']:.3f}** of runs.

| estimator | coverage |
|---|---|
| honest | {data['coverage']:.3f} |
| shifted by {data['bias_shift']} | {data['coverage_biased']:.3f} |
""", encoding="utf-8")
    run = subprocess.run([binary, "render", str(QMD), "--to", "html"],
                         cwd=HERE, capture_output=True, text=True, timeout=300)
    html = DOCS / "results.html"
    if run.returncode != 0 or not html.is_file():
        print(run.stdout[-800:], run.stderr[-800:])
        return 1
    print(f"rendered {html.relative_to(HERE)} ({html.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
