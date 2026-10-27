"""Client for a llama.cpp-served GGUF, with the two constraints S4/S7 depend on.

1. **Thinking is off.** A Qwen3 template spends the whole token budget on reasoning and returns an
   empty `content` even when `response_format: json_object` is set — measured on this host, 140
   tokens, empty body. An empty body is not a verdict; the client refuses to return one.
2. **JSON is required.** The reply is parsed here, and a parse failure raises with the raw text, so
   a malformed answer is a recorded failure rather than a silent `{}`.

No dependency on the OpenAI SDK: one POST, parsed, validated by the caller.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class JudgementUnavailable(RuntimeError):
    """The endpoint did not produce a judgement: down, empty, or unparseable."""


class EmptyJudgement(JudgementUnavailable):
    """The model spent its budget without writing content — the thinking-on failure mode."""


class LlamaCppClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8081", model: str = "ScienceRSI-8b",
                 temperature: float = 0.15, max_tokens: int = 400, timeout: float = 180.0,
                 api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else os.environ.get(
            "HERMES_LOCAL_LLAMACPP_KEY", "")

    def payload(self, system: str, user: str) -> dict:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": 0.9,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            # Not a preference: without this the reply is all reasoning and no content.
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }

    def ask(self, system: str, user: str) -> dict:
        body = json.dumps(self.payload(system, user)).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(f"{self.base_url}/v1/chat/completions", data=body,
                                         headers=headers)
        try:
            raw = urllib.request.urlopen(request, timeout=self.timeout).read()
        except urllib.error.URLError as exc:
            raise JudgementUnavailable(f"{self.base_url} did not answer: {exc}") from exc
        reply = json.loads(raw)
        choice = reply["choices"][0]["message"]
        content = (choice.get("content") or "").strip()
        usage = reply.get("usage") or {}
        if not content:
            raise EmptyJudgement(
                "the model wrote no content "
                f"({usage.get('completion_tokens', '?')} completion tokens); "
                "thinking was probably left on")
        try:
            return {"answer": json.loads(content), "usage": usage, "raw": content}
        except json.JSONDecodeError as exc:
            raise JudgementUnavailable(f"reply is not JSON ({exc}): {content[:200]!r}") from exc
