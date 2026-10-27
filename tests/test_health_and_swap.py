"""Two small tools whose whole value is that they say what they measured.

health.py prints a verdict *and* the age and seq behind it, because a bare `overall: OK` was read as
health for ten hours while the sampler was dead. serve_model.py decides before it touches anything,
because the hand swaps killed the wrong process twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import health  # noqa: E402
import serve_model  # noqa: E402


def test_ok_carries_no_evidence():
    verdict, evidence = health.classify({"overall": "OK", "stale": False, "sample_age_s": 4.2})
    assert verdict == "OK" and evidence == []


def test_a_stale_sample_is_never_ok_even_when_the_verdict_says_so():
    verdict, evidence = health.classify({"overall": "OK", "stale": True, "sample_age_s": 36000})
    assert verdict == "STALE"
    assert any("36000" in e for e in evidence)


def test_an_alarm_lists_its_faults():
    verdict, evidence = health.classify({"overall": "ALARM", "stale": False,
                                         "derived": {"faults": ["decision_service = DOWN"]}})
    assert verdict == "ALARM" and "decision_service = DOWN" in evidence


def test_an_unknown_overall_is_not_ok():
    verdict, _ = health.classify({"overall": "RUNNING", "stale": False})
    assert verdict == "UNKNOWN"


def test_no_swap_when_the_target_is_already_resident():
    action, _ = serve_model.plan("StartLux-Decision-4B-Q8_0", "StartLux-Decision-4B-Q8_0",
                                 7.0, 7.0, 10.5)
    assert action == "noop"


def test_refuse_when_another_model_holds_the_budget():
    action, why = serve_model.plan("StartLux-Decision-4B-Q8_0", "ScienceRSI-8b.i1-Q4_K_M",
                                   7.0, 7.0, 10.5)
    assert action == "refuse"
    assert "3.5 GB free" in why


def test_refuse_when_nothing_is_resident_but_it_still_does_not_fit():
    action, _ = serve_model.plan(None, "ScienceRSI-8b.i1-Q4_K_M", 5.0, 7.0, 10.5)
    assert action == "refuse"


def test_swap_when_it_fits():
    action, why = serve_model.plan(None, "ScienceRSI-8b.i1-Q4_K_M", 1.6, 7.0, 10.5)
    assert action == "swap" and "fits" in why


def test_the_router_id_resolves_to_the_deployed_context():
    """The registry records what the preset runs, not what the framework once wished for.

    History: 16384 declared while 40960 ran (a wish), then 40960 recorded (the deployment), then the
    preset reduced to 16384 and measured at 6.2 GiB. The test pins the last measured state, so the
    registry cannot drift back to either a wish or a superseded measurement.
    """
    assert serve_model.context_of("ScienceRSI-8b.i1-Q4_K_M") == 16384
    assert serve_model.footprint("ScienceRSI-8b.i1-Q4_K_M") == 6.2


SAMPLE_INI = """
# hermes-decision: {"model_id": "A", "window": 40960}
[A]
ctx-size = 40960
model = /models/a.gguf
[B]
ctx-size = 16384
"""


def test_preset_sections_are_parsed_and_comments_ignored():
    sections = serve_model.parse_presets(SAMPLE_INI)
    assert set(sections) == {"A", "B"}
    assert sections["A"]["ctx-size"] == "40960"
    assert sections["A"]["model"] == "/models/a.gguf"


def test_a_changed_preset_is_reported_as_needing_a_restart():
    note = serve_model.describe("A", "40960", 16384, "16384", "llama_cpp")
    assert "restart the router" in note


def test_a_model_served_elsewhere_is_not_compared_with_this_preset():
    """StartLux runs on 8081 from the decision service; the Hermes preset is not its deployment."""
    assert serve_model.describe("StartLux", "65536", 16384, None, "startlux") == ""


def test_a_registry_that_disagrees_with_the_preset_is_reported():
    note = serve_model.describe("A", "8192", 16384, None, "llama_cpp")
    assert "registry declares 16384" in note


def test_agreement_is_silent():
    assert serve_model.describe("A", "16384", 16384, None, "llama_cpp") == ""
