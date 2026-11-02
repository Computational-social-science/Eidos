"""One palette, one place.

The document and the monitor are the same product seen twice, so they must not hold two
copies of the same colour: a change here has to move both, or the pair drifts apart one
"small tweak" at a time. Everything visual that is not layout lives in this module.
"""

from __future__ import annotations

TOKENS = {
    "bg": "#0e1013",
    "panel": "#15181d",
    "panel2": "#101318",
    "line": "#232830",
    "fg": "#e6e8eb",
    "body": "#c3cad4",
    "mut": "#98a2b3",
    "dim": "#7d8899",       # 4.96:1 on --panel: the darkest text allowed at 9-10 px
    "accent": "#5b8def",
    "ok": "#57ab5a",
    "ok_text": "#6cbf6e",   # on a tinted chip the mark needs more luminance than the fill
    "warn": "#d29922",
    "bad": "#e5534b",
    "bad_text": "#ef6b62",
}

STATE = {
    "IDLE": "#2a2f36",
    "RUNNING": "#5b8def",
    "PASS": "#57ab5a",
    "SKIP": "#7d8590",
    "FAIL": "#e5534b",
    "STALE": "#d29922",
}

# Text drawn *inside* a solid state block: dark ink on the light fills, white on red.
INK = {"IDLE": "#c9d1d9", "RUNNING": "#0b0e12", "PASS": "#0b0e12",
       "SKIP": "#0b0e12", "FAIL": "#ffffff", "STALE": "#141414"}

SEVERITY = {"FAIL": 5, "STALE": 4, "RUNNING": 3, "SKIP": 2, "PASS": 1, "IDLE": 0}


def root_css() -> str:
    """The `:root` block both pages open their stylesheet with."""
    return ":root{" + ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in TOKENS.items()) + "}"
