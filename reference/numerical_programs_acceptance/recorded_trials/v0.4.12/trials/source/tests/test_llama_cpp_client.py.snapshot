"""The client must not return an empty judgement, and must always ask with thinking off.

The first test is the defect: on this host, a Qwen3 template with `response_format: json_object`
returned 140 completion tokens and an empty `content`. A client that reads `content` and moves on
records that as a verdict. Here it is an exception.
"""

from __future__ import annotations

import io
import json

import pytest

from framework.inference import llama_cpp


def _reply(content, completion_tokens=35, reasoning=None):
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return io.BytesIO(json.dumps({"choices": [{"message": message}],
                                  "usage": {"completion_tokens": completion_tokens}}).encode())


def test_the_payload_disables_thinking_and_requires_json():
    payload = llama_cpp.LlamaCppClient().payload("s", "u")
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0.15


def test_an_empty_content_is_an_exception_not_a_verdict(monkeypatch):
    monkeypatch.setattr(llama_cpp.urllib.request, "urlopen",
                        lambda *a, **k: type("R", (), {"read": staticmethod(lambda: _reply(
                            "  ", completion_tokens=140, reasoning="…thinking…").read())})())
    with pytest.raises(llama_cpp.EmptyJudgement, match="no content"):
        llama_cpp.LlamaCppClient().ask("s", "u")


def test_a_non_json_reply_keeps_the_raw_text(monkeypatch):
    monkeypatch.setattr(llama_cpp.urllib.request, "urlopen",
                        lambda *a, **k: type("R", (), {"read": staticmethod(lambda: _reply(
                            "Verdict: fail").read())})())
    with pytest.raises(llama_cpp.JudgementUnavailable, match="not JSON"):
        llama_cpp.LlamaCppClient().ask("s", "u")


def test_a_well_formed_reply_is_parsed(monkeypatch):
    body = '{"verdict":"FAIL","checks":[],"blocking":[]}'
    monkeypatch.setattr(llama_cpp.urllib.request, "urlopen",
                        lambda *a, **k: type("R", (), {"read": staticmethod(lambda: _reply(
                            body).read())})())
    out = llama_cpp.LlamaCppClient().ask("s", "u")
    assert out["answer"]["verdict"] == "FAIL"
    assert out["usage"]["completion_tokens"] == 35
