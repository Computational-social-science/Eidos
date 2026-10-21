"""The decision client against a real HTTP server (not a mock of the client).

The operator returns typed answers: `choice` with per-option probabilities, `noul`
with a yes probability, or `score`. These tests exercise the actual request shape
and parsing over a socket, plus the one rule the module exists to enforce: an
unreachable service raises, it never degrades silently.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.decision import (
    Decision, DecisionClient, DecisionUnavailable, NONE_THRESHOLD,
)


class _Handler(BaseHTTPRequestHandler):
    payloads: list = []
    response: dict = {}

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        _Handler.payloads.append(json.loads(self.rfile.read(length)))
        body = json.dumps(_Handler.response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - http.server API
        pass


@pytest.fixture()
def server():
    _Handler.payloads = []
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_choose_parses_typed_answer_and_sends_criteria(server):
    _Handler.response = {"model": "startlux", "answers": {"answer": {
        "type": "choice", "choice": "schematic", "confidence": 0.91,
        "probabilities": {"result_plot": 0.08, "schematic": 0.91},
        "none_probability": 0.01}}}

    options = {"result_plot": "plots measured data", "schematic": "draws a workflow"}
    decision = DecisionClient(server).choose("What kind of figure is this?", options, "Fig. 2 caption")

    assert decision.choice == "schematic"
    assert decision.confidence == 0.91
    assert decision.probabilities["schematic"] == 0.91
    assert decision.accepted(min_confidence=0.6) is True
    assert decision.is_none_likely() is False

    sent = _Handler.payloads[-1]
    assert sent["questions"]["answer"]["type"] == "choice"
    assert sent["questions"]["answer"]["criteria"] == options
    assert sent["state"] == {"text": "Fig. 2 caption"}


def test_yes_no_uses_noul(server):
    _Handler.response = {"answers": {"answer": {
        "type": "noul", "noul": 0.87, "none_probability": 0.02}}}

    decision = DecisionClient(server).yes_no("Does the caption open with a summary?", {"text": "..."})

    assert decision.type == "noul"
    assert decision.raw["noul"] == 0.87
    assert decision.probability == 0.87
    assert decision.accepted(min_confidence=0.6) is True
    assert _Handler.payloads[-1]["questions"]["answer"]["type"] == "noul"


def test_a_confident_no_is_accepted():
    """p(yes)=0.02 is a confident 'no', not a failed decision."""
    decision = Decision(question="q", type="noul", raw={"noul": 0.02})
    assert decision.probability == 0.02
    assert decision.accepted(min_confidence=0.6) is True


def test_a_coin_flip_is_not_accepted():
    decision = Decision(question="q", type="noul", raw={"noul": 0.5})
    assert decision.accepted(min_confidence=0.6) is False


def test_none_probability_blocks_acceptance():
    decision = Decision(question="q", type="choice", choice="a",
                        confidence=0.99, none_probability=0.3)
    assert decision.is_none_likely() is True
    assert decision.choice_or_none() is None
    assert decision.accepted(min_confidence=0.6) is False


def test_threshold_is_the_measured_one():
    decision = Decision(question="q", type="choice", choice="a",
                        confidence=0.9, none_probability=NONE_THRESHOLD)
    assert decision.is_none_likely() is True  # >= threshold, not >


def test_unreachable_service_raises_never_falls_back():
    client = DecisionClient("http://127.0.0.1:1", timeout=2)
    with pytest.raises(DecisionUnavailable):
        client.yes_no("Is this a decision?", "evidence")


def test_health_reports_down_without_raising():
    status = DecisionClient("http://127.0.0.1:1", timeout=1).health()
    assert status["up"] is False


def test_health_reports_up(server):
    status = DecisionClient(server).health()
    assert status["up"] is True


# --------------------------------------------------------------------------- #
# two acceptance modes: the contract the calibration forced
# --------------------------------------------------------------------------- #

def test_closed_set_rejects_a_forced_choice():
    """Live value: a 7-way category question no option fitted, still named one."""
    decision = Decision(question="q", type="choice", choice="gate_logic",
                        confidence=0.783, none_probability=0.464)
    assert decision.accepted(0.6) is False


def test_open_set_rejects_the_abstention_choice_even_when_confident():
    decision = Decision(question="q", type="choice", choice="not_stated",
                        confidence=0.99, none_probability=0.01)
    assert decision.accepted(0.6, none_threshold=None,
                             abstention_option="not_stated") is False


def test_open_set_ignores_an_inert_none_probability():
    decision = Decision(question="q", type="choice", choice="yes",
                        confidence=0.9, none_probability=0.3)
    assert decision.accepted(0.6, none_threshold=None,
                             abstention_option="not_stated") is True
    # The threshold is still honoured when the caller asks for it.
    assert decision.accepted(0.6, abstention_option="not_stated") is False
