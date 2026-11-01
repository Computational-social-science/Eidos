"""The layout audit must catch what a bounding-box intersection cannot.

Two failures shipped to the browser and were found by looking: a header band painted over the
column labels, and a footer that ran past its band. Both are now machine-checkable, and these
tests prove the checks fire by building a page that contains each defect.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "dashboard.html"

# The audit is a browser audit. A runner without Playwright (CI installs no browser) cannot
# exercise it, and a skipped test says that; a failure would blame the page for the runner.
pytest.importorskip(
    "playwright.sync_api", reason="browser layout audits need Playwright"
)


def _run_defective(tmp_path: Path, injected: str) -> subprocess.CompletedProcess:
    source = PAGE.read_text(encoding="utf-8")
    target = tmp_path / "defective.html"
    target.write_text(
        source.replace("</svg>", injected + "</svg>", 1), encoding="utf-8"
    )
    return subprocess.run(
        [
            sys.executable,
            "tools/audit_layout.py",
            "--widths",
            "1280",
            "--page",
            str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_an_opaque_rect_over_a_label_is_reported(tmp_path):
    run = _run_defective(
        tmp_path, "<rect x='300' y='22' width='420' height='16' fill='#12151a'/>"
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "painted over by a rect" in run.stdout


def test_an_html_overlay_is_reported(tmp_path):
    overlay = (
        "<div style='position:absolute;top:60px;left:20px;width:900px;height:40px;"
        "background:#12151a;z-index:99'></div>"
    )
    source = PAGE.read_text(encoding="utf-8")
    target = tmp_path / "overlay.html"
    target.write_text(source.replace("</body>", overlay + "</body>"), encoding="utf-8")
    run = subprocess.run(
        [
            sys.executable,
            "tools/audit_layout.py",
            "--widths",
            "1280",
            "--page",
            str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "is covered by" in run.stdout


def test_text_outside_the_viewbox_is_reported(tmp_path):
    run = _run_defective(
        tmp_path, "<text x='5000' y='20' font-size='10' fill='#fff'>far out</text>"
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "falls outside its viewBox" in run.stdout


def _run_text_fixture(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    target = tmp_path / "text-fragments.html"
    target.write_text(
        "<!doctype html><html><head><style>body{margin:20px;"
        "font:16px/20px Arial;min-height:200px}</style></head><body>"
        + body
        + "</body></html>",
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            "tools/audit_layout.py",
            "--widths",
            "1280",
            "--page",
            str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_wrapped_inline_note_does_not_overlap_a_preceding_label(tmp_path):
    run = _run_text_fixture(
        tmp_path,
        '<div style="width:220px"><span style="display:inline-block;'
        'padding:1px 7px;font-size:10px">PASS</span> '
        "<span>original measurement time retained in evidence</span></div>",
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_plain_text_in_a_parent_with_markup_still_detects_real_overlap(tmp_path):
    run = _run_text_fixture(
        tmp_path,
        '<div style="position:relative;height:50px">'
        '<div style="position:absolute;left:0;top:0">Parent words <b>bold</b></div>'
        '<span style="position:absolute;left:0;top:0">Collision</span></div>',
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "text overlap" in run.stdout


def test_tight_heading_line_boxes_do_not_collide_with_themselves(tmp_path):
    run = _run_text_fixture(
        tmp_path,
        '<h1 style="width:360px;font-size:48px;line-height:.98">'
        "Make scientific claims answerable to evidence.</h1>",
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_opaque_child_overlay_covers_direct_parent_text(tmp_path):
    run = _run_text_fixture(
        tmp_path,
        '<div style="position:relative">Visible words'
        '<span style="position:absolute;inset:0;background:black"></span></div>',
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "is covered by" in run.stdout


def test_transparent_child_overlay_does_not_visually_cover_text(tmp_path):
    run = _run_text_fixture(
        tmp_path,
        '<div style="position:relative">Visible words'
        '<span style="position:absolute;inset:0;'
        'background:rgba(255,255,255,0)"></span></div>',
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_an_opaque_image_overlay_remains_detected(tmp_path):
    image = "data:image/svg+xml," + quote(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10" fill="black"/></svg>'
    )
    run = _run_text_fixture(
        tmp_path,
        '<div style="position:relative"><span>Visible words</span>'
        '<img style="position:absolute;inset:0;width:100%;height:100%" '
        f'src="{image}"></div>',
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "is covered by" in run.stdout


@pytest.mark.parametrize(
    "overlay",
    [
        '<div style="position:absolute;inset:0;background:black">'
        '<span style="position:absolute;inset:0"></span></div>',
        '<div style="position:absolute;inset:0;background:black"></div>'
        '<div style="position:absolute;inset:0"></div>',
    ],
)
def test_transparent_hit_layer_does_not_hide_an_opaque_cover(tmp_path, overlay):
    run = _run_text_fixture(
        tmp_path,
        '<div style="position:relative"><span>Visible words</span>'
        + overlay
        + "</div>",
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "is covered by" in run.stdout
