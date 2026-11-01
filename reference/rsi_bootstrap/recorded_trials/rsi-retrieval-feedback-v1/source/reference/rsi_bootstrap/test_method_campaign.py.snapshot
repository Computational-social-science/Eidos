"""Method/context/accounting controls. Every provider in this file is synthetic."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import uuid

import pytest

from reference.rsi_bootstrap import c0, local_runtime as rt, local_worker as worker
from reference.rsi_bootstrap import method_campaign as campaign, request_context as context
from reference.rsi_bootstrap.test_c0 import response
from reference.rsi_bootstrap.test_local_runtime import config_file

BANK = Path(__file__).with_name("methods") / "cards.json"


def request_file(tmp_path, kind="retrieval-feedback", text="Known method input.", allowance=10000):
    source = tmp_path / "source.txt"
    source.write_text("Pinned input", encoding="utf-8")
    path = tmp_path / "request.json"
    rt.write_json(path, {"kind": kind, "text": text, "token_allowance": allowance,
                         "inputs": [{"path": source.name, "sha256": rt.sha(source)}]})
    return path


def test_deterministic_retrieval_selects_actual_known_method():
    bank = campaign.load_bank(BANK)
    selected = campaign.retrieve(bank)
    assert selected[0]["card"]["id"] == "log1mexp-piecewise"
    assert len(selected) == 2
    assert campaign.retrieve({**bank, "cards": list(reversed(bank["cards"]))}) == selected
    assert "log(-expm1(-x))" in campaign.context_text(selected)


@pytest.mark.parametrize("kind", ["duplicate", "missing_source", "credentials", "oversize"])
def test_bad_method_cards_refused(tmp_path, kind):
    bank = campaign.load_bank(BANK)
    if kind == "duplicate": bank["cards"].append(copy.deepcopy(bank["cards"][0]))
    elif kind == "missing_source": del bank["cards"][0]["source_url"]
    elif kind == "credentials": bank["cards"][0]["source_url"] = "https://key@example.com/"
    else: bank["cards"][0]["text"] = "x" * 2501
    file = tmp_path / "bank.json"
    rt.write_json(file, bank)
    with pytest.raises(ValueError): campaign.load_bank(file)


@pytest.mark.parametrize("kind", ["unhashable_kind", "unknown", "baseline_leak", "oversize", "unbound", "bool_budget"])
def test_context_is_explicit_bound_and_arm_isolated(tmp_path, kind):
    file = request_file(tmp_path)
    value = rt.strict_json(file.read_bytes())
    if kind == "unhashable_kind": value["kind"] = []
    elif kind == "unknown": value["provider_api_key"] = "not allowed"
    elif kind == "baseline_leak": value["kind"] = "baseline"
    elif kind == "oversize": value["text"] = "x" * 6001
    elif kind == "unbound": value["inputs"][0]["sha256"] = "0" * 64
    else: value["token_allowance"] = True
    rt.write_json(file, value)
    with pytest.raises(ValueError): context.load(file)


def test_context_changes_do_not_mutate_original_task_or_legacy_profile(config_file, tmp_path):
    config, _ = config_file
    extra = request_file(tmp_path)
    original = rt.freeze(config)
    augmented = rt.freeze(config, extra)
    assert original["prompt"] == c0.PROMPT and "campaign_request" not in original
    assert augmented["profile"] == "local-cpu-campaign-v1"
    assert augmented["task_prompt"] == c0.PROMPT and augmented["prompt"].startswith(c0.PROMPT)
    rt.validate_prompt(augmented)
    extra.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError): rt.validate_prompt(augmented)


def test_feedback_best_earliest_tie_and_no_invented_invalid_score():
    rows = [{"ordinal": i, "core": {"status": "DEVELOPMENT_NONCONFORMING", "candidate_conforming_points": n}}
            for i, n in [(1, 5), (2, 5), (3, 4)]]
    assert campaign.choose_feedback(rows)["ordinal"] == 1
    invalid = {"ordinal": 4, "core": {"status": "INVALID_RESPONSE"}}
    assert campaign.choose_feedback([invalid]) is invalid
    text = campaign.context_text(campaign.retrieve(campaign.load_bank(BANK)), invalid)
    assert "no numerical score was measured" in text and "0/23" not in text


def test_feedback_contains_only_four_actual_failed_public_observations():
    bad = {"loss": {"input": "x"}, "gradient": {"const": 0}}
    core = c0.run_once(lambda prompt: response(bad))
    previous = {"ordinal": 1, "core": core}
    text = campaign.context_text(campaign.retrieve(campaign.load_bank(BANK)), previous)
    points = json.loads(text.split("Counterexamples: ", 1)[1])
    assert len(points) == 4 and len({p["case"] for p in points}) == 4
    expected = []
    for dtype in ("float32", "float64"):
        failed = [p for p in core["points"] if p["dtype"] == dtype and p["passed"] is False]
        expected.extend([failed[0]["case"], failed[-1]["case"]])
    assert [p["case"] for p in points] == expected
    assert "expected_outputs" not in text


def test_baseline_cannot_receive_a_previous_response(tmp_path):
    file = tmp_path / "campaign-protocol.json"
    rt.write_json(file, {"synthetic": True})
    value = campaign.make_request({"bank_path": str(BANK)}, "baseline",
                                  [{"foreign_history": "must not be inspected"}], 10000, file)
    assert value["text"] == "" and len(value["inputs"]) == 2
    assert context.prompt({"kind": "baseline", "text": ""}) == c0.PROMPT


def preflight():
    target = {"messages": [{"role": "user", "content": "Target"}],
              "chat_template_kwargs": {"enable_thinking": False}, "max_tokens": 768}
    control = rt.format_payload(target)
    def fake(url, body, timeout):
        return {"prompt": body["messages"][0]["content"]} if url.endswith("apply-template") else {"tokens": [1] * 20}
    limits = {"context": 8192}
    record = context.prepare(fake, "http://127.0.0.1:1", target, control, limits, 10000)
    return target, control, limits, record


@pytest.mark.parametrize("kind", ["positive", "empty_target", "target_zero", "control_zero", "reserve", "context", "bool_token", "wrong_template", "prompt_changed", "false_total", "bool_usage", "too_many_output", "actual_over_budget"])
def test_preflight_and_actual_usage_refuse_incoherent_budgets(kind):
    target, control, limits, record = preflight()
    first = {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50}
    second = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
    allowance = 10000
    target_content, control_content = "Generated program", rt.FORMAT_LITERAL
    if kind in {"target_zero", "empty_target"}: first.update(completion_tokens=0, total_tokens=20)
    if kind == "empty_target": target_content = ""
    if kind == "control_zero": second.update(completion_tokens=0, total_tokens=20)
    if kind == "reserve": allowance = 512
    elif kind == "context": limits["context"] = 200
    elif kind == "bool_token": record["target"]["tokenize_response"]["tokens"][0] = True
    elif kind == "wrong_template": record["target"]["apply_request"]["messages"][0]["content"] = "Foreign"
    elif kind == "prompt_changed": record["target"]["apply_response"]["prompt"] = "Foreign"
    elif kind == "false_total": first["total_tokens"] = 51
    elif kind == "bool_usage": first["completion_tokens"] = True
    elif kind == "too_many_output": first.update(completion_tokens=769, total_tokens=789)
    elif kind == "actual_over_budget": first.update(prompt_tokens=85, total_tokens=115)
    if kind in {"positive", "empty_target"}:
        expected = 50 if kind == "empty_target" else 80
        assert context.used_tokens(first, second, record, target, control, limits, allowance, target_content, control_content) == expected
    else:
        with pytest.raises(ValueError): context.used_tokens(first, second, record, target, control, limits, allowance, target_content, control_content)


@pytest.fixture(scope="module", params=["positive", "invalid"])
def synthetic_campaign(tmp_path_factory, request):
    root = tmp_path_factory.mktemp("method-campaign")
    engine, model = root / "engine.bin", root / "model.gguf"
    engine.write_bytes(b"synthetic, never execute")
    model.write_bytes(b"GGUF synthetic, never load")
    config = {"engine": {"path": str(engine), "sha256": rt.sha(engine)},
              "model": {"path": str(model), "sha256": rt.sha(model), "bytes": model.stat().st_size},
              "limits": {"load_seconds": 5, "request_seconds": 2, "evaluation_seconds": 10,
                         "total_seconds": 60, "threads": 1, "context": 8192, "max_tokens": 768,
                         "min_available_memory_mib": 128, "max_tree_rss_mib": 1024}, "protected_services": []}
    config_path = root / "config.json"
    rt.write_json(config_path, config)
    base = rt.freeze(config_path)
    output = root / "campaign"
    output.mkdir()
    nonce = uuid.uuid4().hex
    protocol = {"run_id": nonce, "runtime": rt.runtime_identity(), "clock": campaign.clock_identity(), "config_path": str(config_path),
                "config_sha256": rt.sha(config_path), "bank_path": str(BANK.resolve()),
                "sources": base["sources"], "query": campaign.QUERY,
                "order": [list(row) for row in campaign.ORDER], "token_cap": 10000, "wall_cap_seconds": 3000}
    rt.write_json(output / "campaign-protocol.json", protocol)
    protocol_sha = rt.sha(output / "campaign-protocol.json")
    content = root / "content.json"
    content.write_text(response() if request.param == "positive" else "invalid response", encoding="utf-8")
    script = Path(__file__).with_name("runtime_controls") / "server.py"

    def command(_protocol, port, alias):
        return [sys._base_executable, "-I", "-X", "utf8", str(script), "--port", str(port),
                "--alias", alias, "--content", str(content), "--mode", "normal", "--model", str(model)]

    def fake_run(config_file, folder, request_path):
        folder.mkdir()
        job = rt.freeze(config_file, request_path)
        identity = uuid.uuid4().hex
        job["run_id"] = identity
        rt.write_json(folder / "protocol.json", job)
        rt.write_json(folder / "owner.json", {"run_id": identity})
        record = worker.controller(folder, identity, rt.sha(folder / "protocol.json"))
        okay = rt.accepted(record, job, identity)
        outcome = {"status": "COMPLETE" if okay else "INCOMPLETE", "runtime_accepted": okay,
                   "run_id": identity, "protocol_sha256": rt.sha(folder / "protocol.json"),
                   "controller_exit_code": 0 if okay else 1,
                   "candidate_status": record.get("core", {}).get("status"),
                   "scientific_promotion": False, "scientific_rsi": "NOT_DEMONSTRATED"}
        rt.write_json(folder / "outcome.json", outcome)
        return outcome

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(rt, "engine_command", command)
        patch.setattr(rt, "run", fake_run)
        result = campaign.execute(output, nonce, protocol_sha)
    assert result["status"] == "COMPLETE", result
    return output, protocol, result


def test_complete_synthetic_comparison_retains_all_six_proposals(synthetic_campaign):
    folder, protocol, result = synthetic_campaign
    arms = campaign.summarize(folder, protocol, result["attempts"])
    assert len(result["attempts"]) == 6
    valid = result["attempts"][0]["measured"]["candidate_status"] != "INVALID_RESPONSE"
    assert all(arm["conforming_proposals"] == (3 if valid else 0) for arm in arms.values())
    assert all(arm["best_joint_points"] == (23 if valid else None) for arm in arms.values())
    assert result["scientific_promotion"] is False and result["scientific_rsi"] == "NOT_DEMONSTRATED"


@pytest.mark.parametrize("kind", ["missing", "order", "path", "false_score", "underreported_time", "budget", "query", "outcome", "token_cost", "stage"])
def test_parent_campaign_reconstruction_refuses_false_comparisons(synthetic_campaign, kind):
    folder, protocol, result = synthetic_campaign
    protocol, rows = copy.deepcopy(protocol), copy.deepcopy(result["attempts"])
    if kind == "missing": rows.pop()
    elif kind == "order": rows.reverse()
    elif kind == "path": rows[1]["path"] = rows[0]["path"]
    elif kind == "false_score": rows[0]["measured"]["joint_conforming_points"] = 0
    elif kind == "underreported_time": rows[0]["charged_seconds"] = 0
    elif kind == "budget": protocol["token_cap"] = 20000
    elif kind == "query": protocol["query"] = "Foreign task"
    elif kind == "outcome": rows[0]["outcome"]["candidate_status"] = "fabricated"
    elif kind == "token_cost": rows[0]["token_cost"]["verified_tokens"] = 0
    else: rows[0]["stage"] = "PENDING"
    with pytest.raises(ValueError): campaign.summarize(folder, protocol, rows)


def fresh_execution(synthetic_campaign, tmp_path):
    _, protocol, _ = synthetic_campaign
    protocol = copy.deepcopy(protocol)
    protocol["run_id"] = uuid.uuid4().hex
    file = tmp_path / "campaign-protocol.json"
    rt.write_json(file, protocol)
    return protocol, rt.sha(file)


def test_failed_attempt_still_retains_cost_and_unknown_tokens(synthetic_campaign, tmp_path, monkeypatch):
    protocol, digest = fresh_execution(synthetic_campaign, tmp_path)
    calls = []
    def fail(*args):
        calls.append(args)
        assert (tmp_path / "progress.json").is_file()
        raise TimeoutError("Synthetic runtime failure")
    monkeypatch.setattr(rt, "run", fail)
    result = campaign.execute(tmp_path, protocol["run_id"], digest)
    assert result["status"] == "INCOMPLETE" and len(calls) == 1
    row = result["attempts"][0]
    assert row["charged_seconds"] > 0 and row["token_cost"]["verified_tokens"] is None
    assert result["costs_including_failures"]["baseline"]["token_accounting_complete"] is False
    assert (tmp_path / "progress.json").is_file()


def test_wall_overrun_stops_before_another_arm_generates(synthetic_campaign, tmp_path, monkeypatch):
    folder, _, source_result = synthetic_campaign
    protocol, digest = fresh_execution(synthetic_campaign, tmp_path)
    actual = campaign.read_attempt(folder / "baseline-1")
    calls = []
    def fake(*args):
        calls.append(args)
        return source_result["attempts"][0]["outcome"]
    ticks = iter([0.0, 1.0, 4002.0, 4003.0])
    monkeypatch.setattr(campaign, "_clock", lambda: next(ticks))
    monkeypatch.setattr(rt, "run", fake)
    monkeypatch.setattr(campaign, "read_attempt", lambda _: actual)
    result = campaign.execute(tmp_path, protocol["run_id"], digest)
    assert result["status"] == "INCOMPLETE" and len(calls) == 1
    assert "Actual arm budget exceeded" in result["error"]
    assert result["costs_including_failures"]["baseline"]["charged_seconds"] == 4001


def test_outer_setup_total_and_failed_dispatch_are_measured(synthetic_campaign, tmp_path, monkeypatch):
    _, protocol, _ = synthetic_campaign
    config = rt.strict_json(Path(protocol["config_path"]).read_bytes())
    config["limits"].update(threads=12, context=8192, max_tokens=768, total_seconds=900)
    file = tmp_path / "config.json"
    rt.write_json(file, config)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(campaign, "run_tree", timeout)
    outcome = campaign.run(file, BANK, tmp_path / "run")
    assert outcome["runtime_accepted"] is False
    timing = outcome["timing"]
    assert timing["one_time_setup_seconds"] > 0 and timing["owned_worker_dispatch_seconds"] >= 0
    assert timing["parent_verification_seconds"] == 0
    assert timing["total_api_seconds"] >= timing["one_time_setup_seconds"] + timing["owned_worker_dispatch_seconds"]
