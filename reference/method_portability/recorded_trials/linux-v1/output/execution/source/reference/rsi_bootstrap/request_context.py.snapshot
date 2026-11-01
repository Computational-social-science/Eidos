"""Explicit, input-bound campaign context and local token-budget checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from reference.rsi_bootstrap import c0


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    path = Path(path).resolve(strict=True)
    if path.stat().st_size > 32768:
        raise ValueError("Campaign request is too large")
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=c0._object, parse_constant=c0._nonfinite)
    if not isinstance(value, dict) or set(value) != {"kind", "text", "inputs", "token_allowance"}:
        raise ValueError("Unexpected campaign request fields")
    if not isinstance(value["kind"], str) or value["kind"] not in {"baseline", "retrieval-feedback"}:
        raise ValueError("Unknown campaign request kind")
    text = value["text"]
    if not isinstance(text, str) or len(text.encode("utf-8")) > 6000 or "\x00" in text:
        raise ValueError("Invalid campaign context text")
    if (value["kind"] == "baseline" and text != "") or (value["kind"] == "retrieval-feedback" and not text.strip()):
        raise ValueError("Baseline/treatment context isolation failed")
    allowance = value["token_allowance"]
    if type(allowance) is not int or not 512 <= allowance <= 10000:
        raise ValueError("Invalid campaign token allowance")
    inputs = value["inputs"]
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 8:
        raise ValueError("Campaign request must bind its input files")
    bound = {}
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("Invalid context input identity")
        if not isinstance(item["path"], str) or not item["path"]:
            raise ValueError("Context input path is missing")
        source = (path.parent / item["path"]).resolve(strict=True)
        if not source.is_file() or source.stat().st_size > 8388608 or str(source) in bound:
            raise ValueError("Context input is oversized, duplicate or not a file")
        expected = item["sha256"]
        if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected) or digest(source) != expected:
            raise ValueError("Context input changed or has an invalid digest")
        bound[str(source)] = expected
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "kind": value["kind"], "text": text, "inputs": bound, "token_allowance": allowance}


def prompt(request: dict) -> str:
    if request["kind"] == "baseline":
        return c0.PROMPT
    return (c0.PROMPT + "\nExternal known-method context and public development feedback follow.\n"
            "Use these as sourced input; their presence does not establish discovery or correctness.\n"
            + request["text"])


def _template_request(payload: dict) -> dict:
    return {"messages": payload["messages"], "chat_template_kwargs": payload["chat_template_kwargs"]}


def prepare(fetch, endpoint: str, target: dict, control: dict, limits: dict, allowance: int) -> dict:
    record = {}
    for name, payload in (("target", target), ("control", control)):
        apply_request = _template_request(payload)
        applied = fetch(endpoint + "/apply-template", apply_request, timeout=2)
        text = applied.get("prompt")
        if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
            raise ValueError("Backend template response is missing or oversized")
        token_request = {"content": text, "add_special": True, "parse_special": True, "with_pieces": False}
        tokenized = fetch(endpoint + "/tokenize", token_request, timeout=2)
        record[name] = {"apply_request": apply_request, "apply_response": applied,
                        "tokenize_request": token_request, "tokenize_response": tokenized}
    reserved = validate_preflight(record, target, control, limits)
    if reserved > allowance:
        raise ValueError("Insufficient model-token budget before generation")
    return record


def validate_preflight(record: dict, target: dict, control: dict, limits: dict) -> int:
    reserved = 0
    for name, payload in (("target", target), ("control", control)):
        row = record[name]
        if row["apply_request"] != _template_request(payload):
            raise ValueError("Template preflight does not bind the actual messages")
        text = row["apply_response"]["prompt"]
        if (not isinstance(text, str) or len(text.encode("utf-8")) > 65536 or
                payload["messages"][0]["content"] not in text):
            raise ValueError("Backend rendered prompt dropped or changed the input")
        if row["tokenize_request"] != {"content": text, "add_special": True, "parse_special": True, "with_pieces": False}:
            raise ValueError("Tokenization does not bind the rendered template")
        tokens = row["tokenize_response"]["tokens"]
        if (not isinstance(tokens, list) or not tokens or len(tokens) > limits["context"] or
                any(type(token) is not int or token < 0 for token in tokens)):
            raise ValueError("Invalid backend token inventory")
        cost = len(tokens) + payload["max_tokens"] + 64
        if cost > limits["context"]:
            raise ValueError("Prompt/output reserve would exceed the model context")
        reserved += cost
    return reserved


def _usage(usage: dict, name: str, record: dict, payload: dict, limits: dict, content: str) -> int:
    values = [usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Model usage must contain nonnegative integer counts")
    n_prompt, n_output, n_total = values
    if not isinstance(content, str) or (content and n_output == 0):
        raise ValueError("Nonempty model text cannot have zero completion tokens")
    measured = len(record[name]["tokenize_response"]["tokens"])
    if (n_total != n_prompt + n_output or n_output > payload["max_tokens"] or n_prompt == 0 or
            abs(n_prompt - measured) > 64 or n_prompt + payload["max_tokens"] > limits["context"]):
        raise ValueError("Model usage disagrees with output/context/tokenization bounds")
    return n_total


def validate_target(usage: dict, record: dict, target: dict, control: dict, limits: dict, allowance: int, content: str):
    if validate_preflight(record, target, control, limits) > allowance:
        raise ValueError("Model-token reservation exceeds the available budget")
    used = _usage(usage, "target", record, target, limits, content)
    reserved_control = len(record["control"]["tokenize_response"]["tokens"]) + control["max_tokens"] + 64
    if used + reserved_control > allowance:
        raise ValueError("Target leaves insufficient budget for its control")


def used_tokens(target_usage: dict, control_usage: dict, record: dict, target: dict, control: dict,
                limits: dict, allowance: int, target_content: str, control_content: str) -> int:
    validate_target(target_usage, record, target, control, limits, allowance, target_content)
    total = (_usage(target_usage, "target", record, target, limits, target_content) +
             _usage(control_usage, "control", record, control, limits, control_content))
    if total > allowance:
        raise ValueError("Actual model-token budget exceeded")
    return total
