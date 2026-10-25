"""The monitor's state machine and its assembly view must be correct without a browser."""

import tools.chain_states as cs
import tools.dashboard as dash

PIPE = {"chain_modules": {"gates": ["framework.gates"],
                          "quarto": ["framework.quarto_bridge"],
                          "decision": ["framework.decision"]}}
SIGNALS = {"decision_service": {"state": "OK", "source": "127.0.0.1:8090/health"},
           "quarto": {"state": "OK", "source": "framework.quarto_bridge"}}


def test_state_machine_rejects_illegal_jumps():
    # FAIL -> PASS is the classic cheat: it must fall back to STALE, not pass.
    assert cs.transition("FAIL", "PASS") == "STALE"
    assert cs.transition("PASS", "FAIL") == "STALE"
    assert cs.transition("PASS", "RUNNING") == "RUNNING"
    assert cs.transition("RUNNING", "PASS") == "PASS"


def test_advance_marks_running_when_a_run_is_live():
    assert cs.advance({"a": "PASS"}, {"a": "PASS"}, live=True)["a"] == "RUNNING"


def test_topology_puts_status_on_nodes_and_names_faults():
    svg, faults, users = dash.topology(PIPE, {"gates": "FAIL", "quarto": "PASS",
                                              "decision": "PASS"}, {}, SIGNALS, 0)
    assert "data-chain='gates'" in svg
    assert "data-module='framework.gates'" in svg
    assert dash.PALETTE["FAIL"] in svg          # the failing chain's fill is the fault colour
    assert "gates = FAIL" in faults
    assert users["framework.gates"] == ["gates"]


def test_services_are_a_third_column_with_their_own_state():
    svg, _, _ = dash.topology(PIPE, {"gates": "PASS", "quarto": "PASS",
                                     "decision": "PASS"}, {}, SIGNALS, 0)
    assert svg.count("data-service=") == 2
    assert "decision · :8090" in svg and ">quarto</text>" in svg


def test_a_down_service_is_named_in_the_fault_line():
    signals = dict(SIGNALS, decision_service={"state": "ALARM", "source": "x"})
    _, faults, _ = dash.topology(PIPE, {"gates": "PASS", "quarto": "PASS",
                                        "decision": "PASS"}, {}, signals, 0)
    assert "decision_service = DOWN" in faults


def test_module_state_is_the_worst_of_its_consumers():
    assert dash.worst(["PASS", "FAIL"]) == "FAIL"
    assert dash.worst(["PASS", "SKIP"]) == "SKIP"
    assert dash.worst([]) == "IDLE"


def test_dashboard_builds_an_animated_assembly_page():
    page = dash.build()
    # The header is the name and its release: "Eidos v4.0.0". The title carries the rest.
    assert "class=\"brand\"" in page and ">●</i>Eidos" in page
    assert "— assembly and status" in page
    assert "--bg:#0e1013" in page              # dark theme
    assert page.count("data-chain=") >= 1      # chains carry their own state
    assert page.count("data-module=") >= 1     # modules carry the worst state of their users
    assert page.count("data-service=") >= 1    # services are the third column
    assert "<title>" in page                   # hover gives the detail
    assert "transition:fill" in page.replace(" ", "")
    # Cost contract: no per-frame animation inside the SVG. Measured on this page, 15 SMIL
    # dots cost 38% of one core and a stroke-opacity keyframe on 15 paths cost 34%; both
    # repaint the whole SVG layer. Direction is therefore geometry (an arrowhead), and the
    # only animation left is an HTML dot the compositor can handle.
    assert "animateMotion" not in page
    assert "marker-end='url(#ah)'" in page
    assert "@keyframes beat" in page and "prefers-reduced-motion" in page
    assert "POLL_MS" in page and "setInterval(poll" not in page


def test_an_authenticated_service_is_up_not_down(monkeypatch):
    """401 proves the server is alive: treating it as absence made a live runtime look dead."""
    import tools.watch_pipeline as wp

    monkeypatch.setattr(wp, "http_status", lambda *a, **k: 401)
    signals = wp.measure()
    assert signals["runtime_18434"]["value"] == 1
    assert signals["runtime_18434"]["note"] == "auth required"


def test_diagnosis_names_the_service_failure():
    """The monitor does not invent a cause: it asks framework.diagnosis."""
    from framework.diagnosis import FailureDiagnosisEngine

    diag = FailureDiagnosisEngine().diagnose(
        "service:runtime_18434", {"evidence": {"error": "no answer"}})
    assert "not answering on 18434" in diag.root_cause
    assert diag.category.value == "environment"
    assert diag.suggested_actions


def test_recovery_is_planned_by_the_framework_and_refuses_what_it_cannot_do():
    from framework import recovery

    runtime = recovery.plan("runtime_18434")
    assert runtime.available is True
    assert "llama.cpp" in runtime.description
    quarto = recovery.plan("quarto")
    assert quarto.available is False and quarto.reason


def test_the_page_shows_diagnosis_and_offers_recovery():
    page = dash.build()
    assert "diagnosis" in page and "recovery" in page
    assert "data-restart" in page
    assert "/api/restart/" in page


def test_auto_recovery_waits_for_a_sustained_fault(monkeypatch, tmp_path):
    """One bad sample is noise; three in a row is a fault worth one attempt."""
    import tools.watch_pipeline as wp

    monkeypatch.setattr(wp, "RECOVERY_STATE", tmp_path / "rs.json")
    monkeypatch.setattr(wp, "RECOVERIES", tmp_path / "rec.jsonl")
    monkeypatch.setenv("EIDOS_AUTO_RECOVER", "1")
    calls = []
    import framework.recovery as rec
    monkeypatch.setattr(rec, "execute", lambda p: (calls.append(p.service), {"ok": True, "pid": 1})[1])

    states = {"runtime_18434": {"state": "ALARM",
                                "recovery": {"available": True, "description": "start it"}}}
    wp.maybe_auto_recover(states)
    wp.maybe_auto_recover(states)
    assert calls == []
    wp.maybe_auto_recover(states)
    assert calls == ["runtime_18434"]
    # and it does not fire again while the fault persists
    wp.maybe_auto_recover(states)
    assert calls == ["runtime_18434"]


def test_the_verdict_is_computed_once_for_text_and_colour():
    from tools.status_view import derive

    d = derive({"quarto": {"state": "OK"}, "runtime_18434": {"state": "ALARM"}},
               {"gates": "FAIL", "demo": "SKIP"},
               {"framework.gates": ["gates"]})
    assert d["overall"] == "ALARM"
    assert "runtime_18434 = DOWN" in d["faults"]
    assert "chain:gates = FAIL" in d["faults"]
    assert not any("demo" in f for f in d["faults"])      # SKIP is not a fault
    assert d["counts"]["fail"] == 1 and d["counts"]["skip"] == 1


def test_page_text_and_colour_cannot_disagree(monkeypatch):
    """Inject a failing chain and check the pill, the fault line and the fill together."""
    import tools.dashboard as dash

    status = {"ts": "2026-01-01T00:00:00+00:00", "overall": "OK", "samples": 1,
              "live_run": False, "chains": {"gates": "FAIL"},
              "signals": {"quarto": {"state": "OK"}}, "alarms": []}
    pipeline = {"chain_modules": {"gates": ["framework.gates"]},
                "coupling": {"nodes": ["framework.gates"], "edges": []}}
    traces = {"trace": {"start_ts": 0},
              "spans": [{"name": "gates", "duration_ms": 5, "status": "FAIL",
                         "attributes": {"detail": "x", "requires": ""}}]}

    def fake_load(path, default):
        name = str(path)
        if name.endswith("current.json"):
            return status
        if name.endswith("timeline.json"):
            return [{"ts": status["ts"], "states": {"gates": "FAIL"}}]
        if name.endswith("pipeline.json"):
            return pipeline
        if name.endswith("latest.json"):
            return traces
        return default

    monkeypatch.setattr(dash, "load", fake_load)
    page = dash.build()
    assert 'id="ov">ALARM' in page                       # the pill says ALARM despite status.overall
    assert "FAULT" in page and "chain:gates = FAIL" in page
    assert page.count("fill='#e5534b'") >= 1             # and the node is red


def test_ranking_counts_incidents_not_transitions(monkeypatch, tmp_path):
    import json as _json
    from datetime import datetime, timedelta, timezone

    import tools.dashboard as dash

    path = tmp_path / "faults.jsonl"
    now = datetime.now(timezone.utc)
    rows = [now - timedelta(minutes=30), now - timedelta(minutes=28), now - timedelta(minutes=2)]
    path.write_text("".join(_json.dumps({"ts": t.isoformat(), "signal": "svc"}) + "\n"
                            for t in rows), encoding="utf-8")
    monkeypatch.setattr(dash, "STATUS", tmp_path)
    ranked = dash.fault_ranking()
    assert ranked and ranked[0][0] == "svc" and ranked[0][1] == 2   # two incidents, not three


def test_watchdog_fails_when_the_sample_is_old(monkeypatch, tmp_path):
    import json as _json
    from datetime import datetime, timedelta, timezone

    import tools.watchdog as wd

    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    current = tmp_path / "current.json"
    current.write_text(_json.dumps({"ts": old}), encoding="utf-8")
    monkeypatch.setattr(wd, "CURRENT", current)
    monkeypatch.setattr(wd, "LOG", tmp_path / "watchdog.log")
    assert wd.main(["--quiet"]) == 1
    assert "not sampled" in (tmp_path / "watchdog.log").read_text(encoding="utf-8")


def test_gate_s_rejects_prose_that_contradicts_its_evidence():
    """S9: the span exists, the pointer resolves, the register matches the file — and the
    sentence still says 19 where the evidence says 1."""
    from pathlib import Path
    from framework.validity import ScientificValidityGate

    root = Path(__file__).resolve().parents[1] / "reference" / "prose_lie"
    gate = ScientificValidityGate(root, register=root / "analysis" / "CLAIMS.yaml",
                                  document=root / "docs" / "REPORT.md")
    result = gate.run()
    assert result.status == "FAIL"
    assert any(f.startswith("[S9]") for f in result.details["findings"])


def test_dashboard_check_rejects_a_missing_page(monkeypatch, tmp_path):
    import tools.dashboard as dash

    monkeypatch.setattr(dash, "OUT", tmp_path / "nope.html")
    assert dash.main(["--check"]) == 1
