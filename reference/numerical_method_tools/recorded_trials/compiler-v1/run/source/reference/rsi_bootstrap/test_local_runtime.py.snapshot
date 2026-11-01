"""Synthetic controls only; no language model is loaded by these tests."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import sys
import time

import psutil

import pytest

from reference.rsi_bootstrap import local_runtime as rt
from reference.rsi_bootstrap import local_worker as worker
from reference.rsi_bootstrap.test_c0 import response


@pytest.fixture
def config_file(tmp_path):
    engine = tmp_path / "engine.bin"
    model = tmp_path / "model.gguf"
    engine.write_bytes(b"synthetic engine; never execute")
    model.write_bytes(b"GGUFsynthetic weights; never load")
    identity = lambda p: {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    value = {"engine": identity(engine),
             "model": {**identity(model), "bytes": model.stat().st_size},
             "limits": {"load_seconds": 10, "request_seconds": 10,
                        "evaluation_seconds": 10, "total_seconds": 60,
                        "threads": 1, "context": 4096, "max_tokens": 768,
                        "min_available_memory_mib": 128,
                        "max_tree_rss_mib": 1024},
             "protected_services": []}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


def test_paths_are_config_relative_and_freeze_binds_sources(config_file, tmp_path, monkeypatch):
    path, _ = config_file
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    protocol = rt.freeze(path)
    assert Path(protocol["config"]["model"]["path"]).parent == path.parent
    assert protocol["prompt"] == rt.c0.PROMPT
    assert protocol["sources"] and protocol["grammar"]
    assert protocol["profile"] == "local-cpu-c0-v1"
    assert protocol["scientific_promotion"] is False


@pytest.mark.parametrize("kind", ["unknown", "bool_limit", "nan_limit", "negative",
                                  "deadline", "missing", "bad_hash", "bad_size",
                                  "remote", "credentials", "guard_port", "empty_expectation"])
def test_invalid_configuration_cannot_launch(config_file, kind):
    path, value = config_file
    if kind == "unknown": value["api_key"] = "not allowed"
    elif kind == "bool_limit": value["limits"]["threads"] = True
    elif kind == "nan_limit": value["limits"]["threads"] = float("nan")
    elif kind == "negative": value["limits"]["threads"] = -1
    elif kind == "deadline": value["limits"]["total_seconds"] = 1
    elif kind == "missing": value["model"]["path"] = "absent.gguf"
    elif kind == "bad_hash": value["model"]["sha256"] = "wrong"
    elif kind == "bad_size": value["model"]["bytes"] = True
    else:
        guard = {"url": "http://127.0.0.1:8081/health", "expected": {"status": "ok"},
                 "listener_port": 8081}
        if kind == "remote": guard["url"] = "https://example.com/health"
        elif kind == "credentials": guard["url"] = "http://key@127.0.0.1:8081/health"
        elif kind == "guard_port": guard["listener_port"] = True
        else: guard["expected"] = {}
        value["protected_services"] = [guard]
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        rt.freeze(path)


def test_duplicate_configuration_refused(config_file):
    path, _ = config_file
    path.write_text('{"engine":{},"engine":{}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        rt.freeze(path)


def test_weights_cannot_exceed_declared_cpu_memory_budget(config_file):
    path, value = config_file
    model = path.parent / value["model"]["path"]
    model.write_bytes(b"GGUF" + b"x" * 1048576)
    value["model"]["bytes"] = model.stat().st_size
    value["model"]["sha256"] = rt.sha(model)
    value["limits"]["max_tree_rss_mib"] = 1
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="RSS budget"):
        rt.freeze(path)


def test_overflowing_numeric_json_is_not_finite():
    with pytest.raises(ValueError, match="nonfinite"):
        rt.strict_json('{"number":1e999}')


def test_reused_output_is_never_overwritten(config_file, tmp_path):
    path, _ = config_file
    output = tmp_path / "run"
    output.mkdir()
    marker = output / "result.json"
    marker.write_text("historical failure", encoding="utf-8")
    with pytest.raises(FileExistsError):
        rt.run(path, output)
    assert marker.read_text() == "historical failure"


@pytest.fixture
def http_server():
    guard_calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/guard":
                guard_calls.append(True)
            slow = self.path in {"/slow_headers", "/slow_body"} or (self.path == "/guard" and len(guard_calls) > 2)
            if slow:
                try:
                    if self.path == "/slow_headers":
                        self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    else:
                        self.send_response(200)
                        self.end_headers()
                    for _ in range(100):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.05)
                except OSError:
                    pass
                return
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "https://example.com/")
                self.end_headers()
                return
            body = (b"x" * (rt.MAX_HTTP_BYTES + 1) if self.path == "/large"
                    else b'{"status":"ok","volatile":123}')
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_proxy_is_bypassed_and_guard_binds_process(http_server, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    assert rt.json_request(http_server)["status"] == "ok"
    port = int(http_server.rsplit(":", 1)[1])
    guards = [{"url": http_server, "expected": {"status": "ok"}, "listener_port": port}]
    before = rt.observe_guards(guards)
    assert before[0]["process"]["pid"] > 0
    assert rt.observe_guards(guards, before) == before
    changed = json.loads(json.dumps(before))
    changed[0]["process"]["created"] += 1
    with pytest.raises(RuntimeError):
        rt.observe_guards(guards, changed)


@pytest.mark.parametrize("path", ["/redirect", "/large"])
def test_http_refuses_redirects_and_oversized_bodies(http_server, path):
    with pytest.raises((OSError, ValueError)):
        rt.json_request(http_server + path)


@pytest.mark.parametrize("path", ["/slow_headers", "/slow_body"])
def test_http_wall_deadline_closes_only_own_connection(http_server, path):
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        rt.json_request(http_server + path, timeout=0.15)
    assert time.monotonic() - started < 1
    assert rt.json_request(http_server)["status"] == "ok"


@pytest.mark.parametrize("url", ["https://example.com", "http://localhost:80",
                                 "http://127.0.0.1@evil.example/", "file:///tmp/data"])
def test_no_external_or_ambiguous_http(url):
    with pytest.raises(ValueError):
        rt.json_request(url)


def test_positive_core_does_not_make_incomplete_runtime_accepted(config_file):
    path, _ = config_file
    protocol = rt.freeze(path)
    record = {"status": "COMPLETE", "run_id": "x", "protocol": protocol,
              "core": {"status": "DEVELOPMENT_CONFORMING", "scientific_promotion": False}}
    assert rt.accepted(record, protocol, "x") is False


def test_cpu_command_cannot_download_or_use_gpu(config_file):
    path, _ = config_file
    command = rt.engine_command(rt.freeze(path), 12345, "test-alias")
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("-ngl") + 1] == "0"
    assert command[command.index("--device") + 1] == "none"
    assert "--no-kv-offload" in command and "--no-op-offload" in command
    assert not any(arg in command for arg in ("--hf-repo", "--api-key", "--model-url"))


def _complete_record(protocol, run_id):
    core = rt.c0.run_once(lambda prompt: response())
    core.update(run_id=run_id, protocol_sha256="p", recorded_response_sha256="r")
    core["evaluator_runtime"] = protocol["runtime"]
    record = {"status": "COMPLETE", "run_id": run_id, "protocol": protocol, "runtime": protocol["runtime"],
            "protocol_sha256": "p", "response_sha256": "r", "core": core,
            "inputs_unchanged": True, "monitor_stopped": True, "owned_server_stopped": True,
            "owned_server_exit_code": 1, "scientific_promotion": False,
            "scientific_rsi": "NOT_DEMONSTRATED", "sealed_evaluation": "NOT_RUN",
            "provider_identity": {"data": [{"id": "eidos-local-" + run_id}]},
            "protected_services_preserved": True, "errors": [],
            "request": {"model": "eidos-local-" + run_id,
                        "messages": [{"role": "user", "content": protocol["prompt"]}],
                        "grammar": protocol["grammar"], "max_tokens": protocol["config"]["limits"]["max_tokens"],
                        "temperature": 0, "seed": 19, "top_p": 0.9, "stream": False,
                        "chat_template_kwargs": {"enable_thinking": False}}}
    record["format_control"] = {"passed": True, "request": rt.format_payload(record["request"]),
                                "response": {"choices": [{"finish_reason": "stop",
                                                           "message": {"content": rt.FORMAT_LITERAL}}]}}
    return record


@pytest.mark.parametrize("kind", ["positive", "timeout", "service", "monitor", "cleanup", "source",
                                  "nonce", "response", "grammar", "prompt", "budget", "points", "score",
                                  "retain", "promotion", "error", "duplicate_points", "wrong_case", "wrong_input",
                                  "nonbool", "actual_outputs", "control_missing", "control_content", "control_stop", "control_request", "evaluator_runtime"])
def test_parent_acceptance_binds_evidence_and_requires_full_runtime(config_file, kind):
    path, _ = config_file
    protocol = rt.freeze(path)
    record = _complete_record(protocol, "run")
    if kind == "timeout": record["status"] = "OUTER_TIMEOUT"
    elif kind == "service": record["protected_services_preserved"] = False
    elif kind == "monitor": record["monitor_stopped"] = False
    elif kind == "cleanup": record["owned_server_stopped"] = False
    elif kind == "source": record["core"]["source_after"] = {}
    elif kind == "nonce": record["core"]["run_id"] = "old"
    elif kind == "response": record["core"]["recorded_response_sha256"] = "wrong"
    elif kind == "grammar": record["request"]["grammar"] = "wrong"
    elif kind == "prompt": record["request"]["messages"] = []
    elif kind == "budget": record["request"]["max_tokens"] += 1
    elif kind == "points": record["core"]["points"].pop()
    elif kind == "score": record["core"]["candidate_conforming_points"] = 1
    elif kind == "retain": record["core"]["retained_for_development"] = False
    elif kind == "promotion": record["core"]["scientific_promotion"] = True
    elif kind == "error": record["errors"] = ["monitor failed"]
    elif kind == "duplicate_points": record["core"]["points"] = [record["core"]["points"][0]] * 23
    elif kind == "wrong_case": record["core"]["points"][0]["case"] = "substituted"
    elif kind == "wrong_input": record["core"]["points"][0]["represented_input"] = 1
    elif kind == "nonbool": record["core"]["points"][0]["passed"] = 1
    elif kind == "actual_outputs": record["core"]["points"][0]["actual_outputs"] = [0, 0]
    elif kind == "control_missing": record["format_control"] = {"passed": True}
    elif kind == "control_content": record["format_control"]["response"]["choices"][0]["message"]["content"] = "wrong"
    elif kind == "control_stop": record["format_control"]["response"]["choices"][0]["finish_reason"] = "length"
    elif kind == "control_request": record["format_control"]["request"]["max_tokens"] += 1
    elif kind == "evaluator_runtime": record["core"]["evaluator_runtime"] = {}
    assert rt.accepted(record, protocol, "run") is (kind == "positive")


def test_failed_identity_check_does_not_launch_or_erase_record(config_file, tmp_path, monkeypatch):
    path, _ = config_file
    protocol = rt.freeze(path)
    protocol["run_id"] = "1" * 32
    output = tmp_path / "run"
    output.mkdir()
    rt.write_json(output / "protocol.json", protocol)
    rt.write_json(output / "owner.json", {"run_id": protocol["run_id"]})
    Path(protocol["config"]["model"]["path"]).write_bytes(b"changed")
    def forbidden(*args, **kwargs):
        pytest.fail("Model must not launch after input drift")
    monkeypatch.setattr(worker.subprocess, "Popen", forbidden)
    result = worker.controller(output, protocol["run_id"], rt.sha(output / "protocol.json"))
    assert result["status"] == "INCOMPLETE" and "owned_server" not in result
    raw = (output / "result.json").read_bytes()
    with pytest.raises(FileExistsError):
        worker.controller(output, protocol["run_id"], rt.sha(output / "protocol.json"))
    assert (output / "result.json").read_bytes() == raw


@pytest.mark.parametrize("mode", ["normal", "invalid", "slow", "oversize", "bad_control", "source_changed", "slow_health", "slow_models", "guard_slow"])
def test_actual_owned_synthetic_process_controls(config_file, tmp_path, monkeypatch, http_server, mode):
    """Exercise real HTTP, a separate evaluator and owned process termination.

    The injected server explicitly synthesizes responses. This is not inference
    evidence and does not test the public CLI's engine selection.
    """
    path, config = config_file
    config["limits"].update(load_seconds=5, request_seconds=1, evaluation_seconds=10)
    if mode in {"slow_health", "slow_models"}: config["limits"]["load_seconds"] = 1
    if mode == "guard_slow":
        config["limits"]["request_seconds"] = 5
        config["protected_services"] = [{"url": http_server + "/guard", "expected": {"status": "ok"},
                                          "listener_port": int(http_server.rsplit(":", 1)[1])}]
    path.write_text(json.dumps(config), encoding="utf-8")
    protocol = rt.freeze(path)
    run_id = "2" * 32
    protocol["run_id"] = run_id
    output = tmp_path / "run"
    output.mkdir()
    rt.write_json(output / "protocol.json", protocol)
    rt.write_json(output / "owner.json", {"run_id": run_id})
    content = tmp_path / "content.json"
    content.write_text("invalid response" if mode == "invalid" else response(), encoding="utf-8")
    script = Path(__file__).with_name("runtime_controls") / "server.py"
    def command(_protocol, port, alias):
        return [sys._base_executable, "-I", "-X", "utf8", str(script), "--port", str(port),
                "--alias", alias, "--content", str(content), "--mode", mode,
                "--model", protocol["config"]["model"]["path"]]
    monkeypatch.setattr(rt, "engine_command", command)
    started = time.monotonic()
    record = worker.controller(output, run_id, rt.sha(output / "protocol.json"))
    complete = mode in {"normal", "invalid"}
    assert (record["status"] == "COMPLETE") is complete
    assert record["owned_server_stopped"] is True and record["monitor_stopped"] is True
    identity = record["owned_server"]
    if psutil.pid_exists(identity["pid"]):
        assert psutil.Process(identity["pid"]).create_time() != identity["created"]
    assert rt.accepted(record, protocol, run_id) is complete
    assert record["model_execution_attested"] is False
    if mode == "normal":
        assert record["core"]["candidate_conforming_points"] == 23
    elif mode == "invalid":
        assert record["core"]["status"] == "INVALID_RESPONSE"
    elif mode == "slow":
        assert time.monotonic() - started < 10
        assert not (output / "core.json").exists()
        assert any("TimeoutError" in error for error in record["errors"])
    elif mode in {"slow_health", "slow_models"}:
        assert record["error_type"] == "TimeoutError"
        assert not (output / "response.json").exists()
    elif mode == "oversize":
        assert any("byte limit" in error for error in record["errors"])
    elif mode == "bad_control":
        assert record["core"]["candidate_conforming_points"] == 23
        assert record["format_control"]["passed"] is False
    elif mode == "source_changed":
        assert any("Bound executable/model changed" in error for error in record["errors"])
    elif mode == "guard_slow":
        assert len(record["samples"]) >= 3  # RAM sampling continues during the blocked guard read.
        assert any("TimeoutError" in error for error in record["errors"])
        assert rt.json_request(http_server)["status"] == "ok"  # Protected process was not stopped.
