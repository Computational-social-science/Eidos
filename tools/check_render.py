"""Prove the render chain end to end: Quarto -> HTML, DOCX, PDF.

The contract snapshot only asks whether Quarto answers `--version`; the chain audit
renders a *minimal* document. Neither proves that a real PDF comes out, because PDF
needs a LaTeX distribution that Quarto finds on its own. This tool renders a small
manuscript with mathematics and a table through the same bridge the framework uses,
checks that each output file exists and is non-trivial, and writes the evidence to
``docs/RENDER_CHECK.json``.

    python tools/check_render.py            # writes the artefact, exit 1 on failure
    python tools/check_render.py --json     # machine-readable to stdout
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.quarto_bridge import QuartoBridge  # noqa: E402

QMD = """---
title: "Render check"
format:
  html: default
  pdf: default
  docx: default
---

A line with mathematics $\\pi_d = 0.2036$ and a display:

$$ \\Delta = \\frac{p_1 - p_2}{\\sqrt{p(1-p)(1/n_1 + 1/n_2)}} $$

| arm | n | rate |
|-----|---|------|
| A   | 30 | 0.20 |
| B   | 30 | 0.45 |

The table and the display are the parts that break silently when a template is wrong.
"""


def tool_version(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    first = (out.stdout or out.stderr).strip().splitlines()
    return first[0][:80] if first else "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="docs/RENDER_CHECK.json")
    args = ap.parse_args(argv)

    workdir = Path(tempfile.mkdtemp(prefix="eidos-render-",
                                    dir=os.environ.get("TMPDIR") or None))
    manuscript = workdir / "manuscript"
    manuscript.mkdir(parents=True)
    (manuscript / "index.qmd").write_text(QMD, encoding="utf-8")

    bridge = QuartoBridge({"project_root": str(workdir),
                           "manuscript_dir": "manuscript",
                           "output_dir": "outputs"})
    if not bridge.quarto_available:
        payload = {"ok": False, "reason": "quarto not found", "formats": {}}
    else:
        result = bridge.render(format="all")
        formats = {}
        for fmt, ext in (("html", ".html"), ("pdf", ".pdf"), ("docx", ".docx")):
            target = manuscript / f"index{ext}"
            size = target.stat().st_size if target.exists() else 0
            formats[fmt] = {"ok": size > 1024,
                            "bytes": size,
                            "reported": bool(result.get("formats", {}).get(fmt, {})
                                             .get("success"))}
        payload = {"ok": all(f["ok"] for f in formats.values()) and bool(formats),
                   "quarto": tool_version([bridge.quarto_cmd] if bridge.quarto_cmd else []),
                   "pdflatex": tool_version(["pdflatex", "--version"]),
                   "formats": formats,
                   "generated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds")}

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload))
    else:
        print(f"quarto   : {payload.get('quarto')}")
        print(f"pdflatex : {payload.get('pdflatex') or 'not on PATH (Quarto may still find TinyTeX)'}")
        for fmt, row in payload.get("formats", {}).items():
            print(f"{'PASS' if row['ok'] else 'FAIL'}  {fmt:5s} {row['bytes']:>9,} bytes")
        print(f"{'PASS' if payload['ok'] else 'FAIL'}  wrote {out}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
