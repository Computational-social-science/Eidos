"""The monitor's state machine and its renderers must be correct without a browser."""

from pathlib import Path

import tools.chain_states as cs
import tools.dashboard as dash

ROOT = Path(__file__).resolve().parents[1]


def test_state_machine_rejects_illegal_jumps():
    # FAIL -> PASS is the classic cheat: it must fall back to STALE, not pass.
    assert cs.transition("FAIL", "PASS") == "STALE"
    assert cs.transition("PASS", "FAIL") == "STALE"
    assert cs.transition("PASS", "RUNNING") == "RUNNING"
    assert cs.transition("RUNNING", "PASS") == "PASS"
    assert cs.transition("IDLE", "RUNNING") == "RUNNING"


def test_advance_marks_running_when_a_run_is_live():
    out = cs.advance({"a": "PASS"}, {"a": "PASS"}, live=True)
    assert out["a"] == "RUNNING"


def test_gantt_collapses_runs_of_constant_state():
    timeline = [
        {"ts": "2026-01-01T00:00:00Z", "states": {"a": "PASS"}},
        {"ts": "2026-01-01T00:00:05Z", "states": {"a": "PASS"}},
        {"ts": "2026-01-01T00:00:10Z", "states": {"a": "RUNNING"}},
    ]
    svg = dash.gantt_svg(timeline)
    # two segments, not three: the two PASS samples collapse into one block
    assert svg.count("<rect") == 2
    assert "PASS" in svg and "RUNNING" in svg


def test_dashboard_builds_self_contained():
    page = dash.build()
    assert "<title>Eidos pipeline — monitor</title>" in page
    assert "drawTimeline" in page and "PALETTE" in page
    assert "<svg" in page          # state machine, timeline, coupling are all SVG
    assert page.count("<section") == 5
