"""The pipeline views must be computable without a browser, a service, or a trace."""
import json
from pathlib import Path

from tools.build_pipeline import levels
from tools.pipeline_view import dag_svg, spark, waterfall
from tools.watch_pipeline import classify

ROOT = Path(__file__).resolve().parents[1]


def test_layering_puts_importers_above_their_dependencies():
    nodes = ["a", "b", "c"]
    edges = [{"source": "a", "target": "b", "kind": "hard"},
             {"source": "b", "target": "c", "kind": "soft"}]
    got = levels(nodes, edges)
    assert got["c"] == 0 and got["b"] == 1 and got["a"] == 2


def test_layering_survives_a_cycle_without_hanging():
    got = levels(["a", "b"], [{"source": "a", "target": "b", "kind": "hard"},
                              {"source": "b", "target": "a", "kind": "hard"}])
    assert set(got) == {"a", "b"}


def test_control_classification_follows_direction():
    assert classify({"value": 0, "reference": 1, "direction": "min"})[0] == "ALARM"
    assert classify({"value": 1, "reference": 1, "direction": "min"})[0] == "OK"
    assert classify({"value": 300, "reference": 180, "direction": "max"})[0] == "ALARM"
    assert classify({"value": None, "reference": 1, "direction": "min"})[0] == "UNOBSERVABLE"


def test_views_render_from_the_committed_artefacts():
    pipeline = json.loads((ROOT / "docs" / "pipeline.json").read_text(encoding="utf-8"))
    svg = dag_svg(pipeline["coupling"])
    assert "<svg" in svg and svg.count("<rect") >= len(pipeline["coupling"]["nodes"])
    bars = waterfall(pipeline["spans"])
    assert bars.count("wf-row") == len(pipeline["spans"])
    assert "<polyline" in spark([1, 2, 3])
