"""Finite local retrieval/feedback comparison on one public numerical task.

Known-method reuse only. This is not sealed evaluation or an RSI experiment.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from framework.subprocesses import run_tree
from reference.rsi_bootstrap import c0, local_runtime as rt

QUERY = "log1mexp log(1-exp(-x)) cancellation accurate expm1 log1p loss derivative"
ORDER = [(arm, index) for index in range(1, 4) for arm in ("baseline", "retrieval-feedback")]
_clock = time.perf_counter
STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "the", "this", "to", "with", "x"}


def clock_identity() -> dict:
    measured = time.get_clock_info("perf_counter")
    deadline = time.get_clock_info("monotonic")
    return {"cost_clock": "perf_counter", "implementation": measured.implementation,
            "resolution_seconds": measured.resolution, "monotonic": measured.monotonic,
            "deadline_clock": "monotonic", "deadline_resolution_seconds": deadline.resolution}


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP


def load_bank(path: Path) -> dict:
    if Path(path).stat().st_size > 32768:
        raise ValueError("Method bank exceeds its size limit")
    value = rt.strict_json(Path(path).read_bytes())
    if not isinstance(value, dict) or set(value) != {"schema", "notice", "cards"} or value["schema"] != "eidos.local-method-bank.v1":
        raise ValueError("Unknown method-bank schema")
    if not isinstance(value["cards"], list) or not 1 <= len(value["cards"]) <= 32:
        raise ValueError("Method bank must contain 1-32 cards")
    seen = set()
    for card in value["cards"]:
        if not isinstance(card, dict) or set(card) != {"id", "title", "source_url", "checked_on", "text"}:
            raise ValueError("Invalid method card fields")
        if any(not isinstance(v, str) or not v.strip() for v in card.values()):
            raise ValueError("Method card fields must be nonempty strings")
        if not re.fullmatch("[a-z0-9-]{1,80}", card["id"]) or card["id"] in seen:
            raise ValueError("Duplicate or invalid method identity")
        seen.add(card["id"])
        url = urllib.parse.urlsplit(card["source_url"])
        if url.scheme != "https" or not url.hostname or url.username is not None or url.password is not None:
            raise ValueError("Method source must be an explicit HTTPS citation")
        if len(card["text"].encode()) > 2500 or len(card["title"]) > 160:
            raise ValueError("Method card text is too large")
    return value


def retrieve(bank: dict, query: str = QUERY) -> list[dict]:
    documents = [(card, tokens(card["title"] + " " + card["text"])) for card in bank["cards"]]
    frequency = Counter(word for _, words in documents for word in words)
    asked = tokens(query)
    ranked = []
    for card, words in documents:
        score = sum(1 / frequency[word] for word in sorted(asked & words)) / math.sqrt(max(1, len(words)))
        ranked.append({"card": card, "score": score})
    return sorted(ranked, key=lambda row: (-row["score"], row["card"]["id"]))[:2]


def choose_feedback(prior: list[dict]):
    usable = [row for row in prior if row["core"]["status"] in {"DEVELOPMENT_CONFORMING", "DEVELOPMENT_NONCONFORMING"}]
    if usable:
        return max(usable, key=lambda row: (row["core"]["candidate_conforming_points"], -row["ordinal"]))
    return prior[-1] if prior else None


def context_text(selected: list[dict], previous=None) -> str:
    parts = ["Externally authored known-method summaries (not discovered by this model):"]
    for row in selected:
        card = row["card"]
        parts.append(f"[{card['id']}] {card['source_url']}\n{card['text']}")
    if previous is not None:
        core = previous["core"]
        parts.append("Public development feedback from this arm only: " + core["status"])
        if core["status"] == "INVALID_RESPONSE":
            parts.append("The prior response was inadmissible; no numerical score was measured.")
        else:
            parts.append(f"Joint conformance: {core['candidate_conforming_points']}/23.")
            envelope = rt.strict_json(core["raw_response"])
            program = json.dumps(envelope["program"], separators=(",", ":"), allow_nan=False)
            parts.append("Prior program: " + program if len(program.encode()) <= 2400 else
                         "Prior program omitted because it exceeds the context budget; no prefix is accepted.")
            failed = []
            for dtype in ("float32", "float64"):
                points = [p for p in core["points"] if p["dtype"] == dtype and p["passed"] is False]
                for point in points[:1] + (points[-1:] if len(points) > 1 else []):
                    failed.append({k: point[k] for k in ("case", "dtype", "represented_input", "actual_outputs",
                                                         "loss_relative_error", "gradient_relative_error", "reason")})
            parts.append("Counterexamples: " + json.dumps(failed, separators=(",", ":"), allow_nan=False))
    result = "\n\n".join(parts)
    if len(result.encode()) > 6000:
        raise ValueError("Constructed retrieval/feedback context exceeds its declared limit")
    return result


def read_attempt(folder: Path) -> dict:
    protocol = rt.strict_json((folder / "protocol.json").read_bytes())
    outcome = rt.strict_json((folder / "outcome.json").read_bytes())
    record = rt.strict_json((folder / "result.json").read_bytes())
    core = rt.strict_json((folder / "core.json").read_bytes())
    response = rt.strict_json((folder / "response.json").read_bytes())
    identity = protocol["run_id"]
    if not (outcome["runtime_accepted"] is True and outcome["status"] == "COMPLETE" and
            type(outcome["controller_exit_code"]) is int and outcome["controller_exit_code"] == 0 and
            outcome["run_id"] == identity and record["protocol_sha256"] == outcome["protocol_sha256"] == rt.sha(folder / "protocol.json") and
            outcome["candidate_status"] == core["status"] and outcome["scientific_promotion"] is False and
            outcome["scientific_rsi"] == "NOT_DEMONSTRATED" and
            record["protocol"] == protocol and record["core"] == core and
            core["recorded_response_sha256"] == rt.sha(folder / "response.json") and
            core["raw_response"] == (response["choices"][0]["message"].get("content") or "") and
            record["target_usage"] == response["usage"] and rt.accepted(record, protocol, identity)):
        raise ValueError("Prior/actual attempt receipt is incomplete or inconsistent")
    return {"protocol": protocol, "record": record, "core": core, "outcome": outcome, "folder": folder}


def make_request(protocol: dict, arm: str, prior: list, allowance: int, campaign_file: Path) -> dict:
    selected = retrieve(load_bank(Path(protocol["bank_path"]))) if arm == "retrieval-feedback" else []
    previous = choose_feedback(prior) if arm == "retrieval-feedback" else None
    pins = [campaign_file, Path(protocol["bank_path"])]
    if previous is not None:
        pins += [previous["folder"] / "result.json", previous["folder"] / "response.json"]
    return {"kind": arm, "text": context_text(selected, previous) if selected else "",
            "inputs": [{"path": str(path), "sha256": rt.sha(path)} for path in pins],
            "token_allowance": allowance}


def verify_campaign(protocol: dict):
    if (protocol["query"] != QUERY or protocol["order"] != [list(item) for item in ORDER] or
            protocol["token_cap"] != 10000 or protocol["wall_cap_seconds"] != 3000):
        raise ValueError("Campaign procedure/budget differs from its preregistration")
    if rt.runtime_identity() != protocol["runtime"] or rt.sha(Path(protocol["config_path"])) != protocol["config_sha256"]:
        raise ValueError("Campaign configuration/runtime changed")
    if protocol["clock"] != clock_identity():
        raise ValueError("Campaign timing clock differs from its declaration")
    for relative, expected in protocol["sources"].items():
        if rt.sha(ROOT / relative) != expected:
            raise ValueError("Campaign source/bank/contract changed")


def summarize(folder: Path, protocol: dict, attempts: list) -> dict:
    verify_campaign(protocol)
    if [(row["arm"], row["ordinal"]) for row in attempts] != ORDER:
        raise ValueError("Campaign attempt inventory/order differs")
    prior = {"baseline": [], "retrieval-feedback": []}
    costs = {arm: {"tokens": 0, "seconds": 0.0} for arm in prior}
    seen = set()
    for row in attempts:
        arm = row["arm"]
        label = f"{arm}-{row['ordinal']}"
        if row["path"] != label or row["request_path"] != label + ".request.json":
            raise ValueError("Attempt paths do not bind their arm/ordinal")
        actual = read_attempt(folder / label)
        if row["outcome"] != actual["outcome"]:
            raise ValueError("Embedded outcome contradicts its standalone receipt")
        if row["stage"] != "COMPLETED" or row["token_cost"] != cost_observation(folder / label, actual):
            raise ValueError("Attempt stage/token-cost evidence differs")
        if actual["protocol"]["run_id"] in seen:
            raise ValueError("A model run was reused across proposal opportunities")
        seen.add(actual["protocol"]["run_id"])
        allowance = protocol["token_cap"] - costs[arm]["tokens"]
        expected = make_request(protocol, arm, prior[arm], allowance, folder / "campaign-protocol.json")
        request_path = folder / row["request_path"]
        if rt.strict_json(request_path.read_bytes()) != expected or actual["protocol"]["campaign_request"] != rt.request_context.load(request_path):
            raise ValueError("Actual context/history differs from the frozen procedure")
        if actual["protocol"]["config_sha256"] != protocol["config_sha256"]:
            raise ValueError("Attempt model/resource configuration differs")
        elapsed = row["charged_seconds"]
        measured = actual["record"]["wall_seconds"]
        resolution = protocol["clock"]["deadline_resolution_seconds"]
        if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or
                elapsed < 0 or elapsed + resolution < measured):
            raise ValueError("Attempt wall cost is invalid or under-reported")
        used = actual["record"]["used_model_tokens"]
        costs[arm]["tokens"] += used
        costs[arm]["seconds"] += elapsed
        if costs[arm]["tokens"] > protocol["token_cap"] or costs[arm]["seconds"] > protocol["wall_cap_seconds"]:
            raise ValueError("Campaign arm budget exceeded")
        details = response_details(actual)
        if row["measured"] != details:
            raise ValueError("Campaign result summary differs from actual evidence")
        prior[arm].append({**actual, "ordinal": row["ordinal"]})
    return {arm: {**costs[arm], "conforming_proposals": sum(item["core"]["status"] == "DEVELOPMENT_CONFORMING" for item in rows),
                  "numerical_proposals_evaluated": sum(item["core"]["status"] != "INVALID_RESPONSE" for item in rows),
                  "best_joint_points": max((item["core"]["candidate_conforming_points"] for item in rows
                                            if item["core"]["status"] != "INVALID_RESPONSE"), default=None)}
            for arm, rows in prior.items()}


def cost_observation(folder: Path, verified=None) -> dict:
    if verified is not None:
        return {"complete": True, "verified_tokens": verified["record"]["used_model_tokens"]}
    # Failed calls may have generated tokens without returning usable usage.
    # Preserve reported fields as diagnostics; do not silently charge zero.
    try:
        record = rt.strict_json((folder / "result.json").read_bytes())
        reported = {"target": record.get("target_usage"),
                    "control": record.get("format_control", {}).get("response", {}).get("usage")}
    except (OSError, ValueError, TypeError):
        reported = None
    return {"complete": False, "verified_tokens": None, "reported_usage_unverified": reported}


def all_costs(attempts: list) -> dict:
    return {
        arm: {"charged_seconds": sum(row.get("charged_seconds", 0) for row in attempts if row["arm"] == arm),
              "attempts_observed": sum(row["arm"] == arm for row in attempts),
              "token_accounting_complete": all(row["token_cost"]["complete"] for row in attempts if row["arm"] == arm),
              "verified_tokens_observed": sum(row["token_cost"]["verified_tokens"] or 0 for row in attempts if row["arm"] == arm)}
        for arm in ("baseline", "retrieval-feedback")}


def response_details(actual):
    core, record = actual["core"], actual["record"]
    cached = record["target_usage"].get("prompt_tokens_details", {}).get("cached_tokens")
    if type(cached) is not int or cached != 0:
        raise ValueError("Target was not observed with a fresh prompt cache")
    return {"candidate_status": core["status"], "points_evaluated": len(core["points"]),
            "joint_conforming_points": core.get("candidate_conforming_points"),
            "used_model_tokens": record["used_model_tokens"], "request_seconds": record["request_seconds"],
            "runtime_accepted": True, "scientific_promotion": False}


def execute(folder: Path, nonce: str, expected_sha: str) -> dict:
    protocol_file = folder / "campaign-protocol.json"
    protocol = rt.strict_json(protocol_file.read_bytes())
    if rt.sha(protocol_file) != expected_sha or protocol["run_id"] != nonce:
        raise ValueError("Campaign owner/protocol differs")
    (folder / "worker-claim").mkdir()
    attempts = []
    prior = {"baseline": [], "retrieval-feedback": []}
    spent = {arm: {"tokens": 0, "seconds": 0.0} for arm in prior}
    started = _clock()
    result = {"schema": "eidos.c0.method-campaign-result.v1", "run_id": nonce,
              "protocol_sha256": expected_sha, "attempts": attempts, "status": "INCOMPLETE",
              "scientific_promotion": False, "scientific_rsi": "NOT_DEMONSTRATED", "sealed_evaluation": "NOT_RUN"}
    try:
        for arm, ordinal in ORDER:
            begun = _clock()
            label = f"{arm}-{ordinal}"
            request_path = folder / (label + ".request.json")
            row = {"arm": arm, "ordinal": ordinal, "path": label, "request_path": request_path.name, "stage": "PREPARING"}
            attempts.append(row)  # Keep even the attempt that fails admission/execution.
            actual = None
            rt.write_json(folder / "progress.json", result)  # Durable launch intent before any model call.
            try:
                verify_campaign(protocol)
                if rt.sha(protocol_file) != expected_sha:
                    raise ValueError("Campaign protocol changed")
                allowance = protocol["token_cap"] - spent[arm]["tokens"]
                if allowance < 512 or spent[arm]["seconds"] + 960 > protocol["wall_cap_seconds"]:
                    raise ValueError("No arm budget remains")
                rt.write_json(request_path, make_request(protocol, arm, prior[arm], allowance, protocol_file))
                row["stage"] = "CALLING_RUNTIME"
                rt.write_json(folder / "progress.json", result)
                row["outcome"] = rt.run(Path(protocol["config_path"]), folder / label, request_path)
                actual = read_attempt(folder / label)
                row["measured"] = response_details(actual)
                row["stage"] = "COMPLETED"
            finally:
                row["charged_seconds"] = _clock() - begun
                row["token_cost"] = cost_observation(folder / label, actual)
                spent[arm]["seconds"] += row["charged_seconds"]
                rt.write_json(folder / "progress.json", result)
            spent[arm]["tokens"] += actual["record"]["used_model_tokens"]
            if spent[arm]["tokens"] > protocol["token_cap"] or spent[arm]["seconds"] > protocol["wall_cap_seconds"]:
                raise ValueError("Actual arm budget exceeded; no further generation allowed")
            prior[arm].append({**actual, "ordinal": ordinal})
            rt.write_json(folder / "progress.json", result)
            print(label, row["measured"]["candidate_status"], row["measured"]["joint_conforming_points"], flush=True)
        result["arms"] = summarize(folder, protocol, attempts)
        result["status"] = "COMPLETE"
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
    result["costs_including_failures"] = all_costs(attempts)
    result["wall_seconds"] = _clock() - started
    rt.write_json(folder / "campaign-result.json", result)
    return result


def run(config_path: Path, bank_path: Path, output: Path) -> dict:
    outer_started = _clock()
    base = rt.freeze(config_path)
    config = base["config"]
    if any(config["limits"][key] != value for key, value in
           {"context": 8192, "threads": 12, "max_tokens": 768, "total_seconds": 900}.items()):
        raise ValueError("This preregistered comparison requires the declared 8k/12-thread/768-token/900s profile")
    bank_path = Path(bank_path).resolve(strict=True)
    if not bank_path.is_relative_to(ROOT):
        raise ValueError("Campaign bank must be a source-controlled project resource")
    load_bank(bank_path)
    sources = {**base["sources"], str(bank_path.relative_to(ROOT)): rt.sha(bank_path),
               ".Codex/evals/rsi-retrieval-feedback.md": rt.sha(ROOT / ".Codex/evals/rsi-retrieval-feedback.md")}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    nonce = uuid.uuid4().hex
    protocol = {"schema": "eidos.c0.method-campaign.v1", "run_id": nonce, "runtime": rt.runtime_identity(),
                "clock": clock_identity(),
                "config_path": base["config_path"], "config_sha256": base["config_sha256"],
                "bank_path": str(bank_path), "sources": sources, "query": QUERY,
                "token_cap": 10000, "wall_cap_seconds": 3000, "order": [list(item) for item in ORDER],
                "scientific_promotion": False, "scope": "Combined known-method retrieval and public feedback; not RSI"}
    rt.write_json(output / "campaign-protocol.json", protocol)
    digest = rt.sha(output / "campaign-protocol.json")
    outcome = {"run_id": nonce, "protocol_sha256": digest, "runtime_accepted": False,
               "scientific_promotion": False, "scientific_rsi": "NOT_DEMONSTRATED"}
    setup_seconds = _clock() - outer_started
    dispatched = _clock()
    dispatch_seconds = 0.0
    verification_started = None
    try:
        try:
            child = run_tree([sys.executable, "-I", "-X", "utf8", str(Path(__file__).resolve()),
                              "--worker", str(output), nonce, digest], cwd=ROOT, timeout=6500)
        finally:
            dispatch_seconds = _clock() - dispatched
        verification_started = _clock()
        (output / "controller.log").write_text(child.stdout + child.stderr, encoding="utf-8")
        result = rt.strict_json((output / "campaign-result.json").read_bytes())
        if (child.returncode != 0 or result["run_id"] != nonce or result["protocol_sha256"] != digest or
                rt.sha(output / "campaign-protocol.json") != digest or result["status"] != "COMPLETE" or
                result["scientific_promotion"] is not False or result["scientific_rsi"] != "NOT_DEMONSTRATED" or
                result["sealed_evaluation"] != "NOT_RUN"):
            raise ValueError("Campaign worker did not complete its frozen comparison")
        arms = summarize(output, protocol, result["attempts"])
        if result["arms"] != arms or result["costs_including_failures"] != all_costs(result["attempts"]):
            raise ValueError("Parent campaign accounting disagrees")
        outcome.update(runtime_accepted=True, status="COMPLETE", arms=arms)
    except Exception as error:
        outcome.update(status="INCOMPLETE", error_type=type(error).__name__)
    outcome["timing"] = {"one_time_setup_seconds": setup_seconds,
                         "clock": clock_identity(),
                         "owned_worker_dispatch_seconds": dispatch_seconds,
                         "parent_verification_seconds": 0.0 if verification_started is None else _clock() - verification_started,
                         "total_api_seconds": _clock() - outer_started,
                         "scope": "run() entry through final receipt preparation; excludes interpreter/CLI startup and final atomic receipt write"}
    rt.write_json(output / "campaign-outcome.json", outcome)
    return outcome


def main() -> int:
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        result = execute(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
        return 0 if result["status"] == "COMPLETE" else 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bank", type=Path, default=Path(__file__).with_name("methods") / "cards.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        outcome = run(args.config, args.bank, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Campaign prerequisite/configuration error: {error}\n")
    print(json.dumps(outcome))
    return 0 if outcome["runtime_accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
