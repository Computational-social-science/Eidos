"""Owned controller/evaluator entry points; use local_runtime's parent CLI."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import psutil

from framework.subprocesses import quiet_flags, run_tree
from reference.rsi_bootstrap import c0, local_runtime as rt


def read_protocol(folder: Path, run_id: str, expected: str) -> dict:
    if not re.fullmatch("[0-9a-f]{32}", run_id) or not re.fullmatch("[0-9a-f]{64}", expected):
        raise ValueError("Invalid run/protocol identity")
    if rt.sha(folder / "protocol.json") != expected:
        raise RuntimeError("Frozen protocol changed")
    protocol = rt.strict_json((folder / "protocol.json").read_bytes())
    if (protocol["run_id"] != run_id or
            rt.strict_json((folder / "owner.json").read_bytes()) != {"run_id": run_id} or
            rt.runtime_identity() != protocol["runtime"]):
        raise RuntimeError("Protocol/owner/prompt identity differs")
    rt.validate_prompt(protocol)
    for module in (rt, c0, c0.grader, c0.expressions):
        if Path(module.__file__).resolve().parent != Path(__file__).resolve().parent:
            raise RuntimeError("Loaded numerical/runtime modules are outside the source checkout")
    return protocol


def timed_request(url, payload, seconds, server):
    expired = threading.Event()
    finished = threading.Event()
    errors = []

    def expire():
        if not finished.is_set():
            expired.set()
            try:
                if server.poll() is None:
                    server.terminate()
            except OSError as error:
                errors.append(type(error).__name__)

    timer = threading.Timer(seconds, expire)
    timer.daemon = True
    started = time.monotonic()
    timer.start()
    try:
        result = rt.json_request(url, payload, timeout=seconds)
        if expired.is_set() or time.monotonic() - started > seconds:
            raise TimeoutError("Owned model request exceeded its wall deadline")
        return result
    except Exception as error:
        if expired.is_set():
            raise TimeoutError("Owned model request exceeded its wall deadline") from error
        raise
    finally:
        finished.set()
        timer.cancel()
        timer.join(timeout=3)
        if timer.is_alive() or errors:
            raise RuntimeError("Request watchdog did not finish cleanly")


def evaluate(folder: Path, run_id: str, expected: str):
    protocol = read_protocol(folder, run_id, expected)
    (folder / "evaluation-claim").mkdir()
    raw = (folder / "response.json").read_bytes()
    response = rt.strict_json(raw)
    content = response["choices"][0]["message"].get("content") or ""
    result = c0.run_once(lambda prompt: content)
    result.update(run_id=run_id, protocol_sha256=expected,
                  evaluator_runtime=rt.runtime_identity(),
                  recorded_response_sha256=rt.hashlib.sha256(raw).hexdigest(),
                  transport_scope="Recorded-response evaluation; controller separately observes the owned provider")
    if ((folder / "response.json").read_bytes() != raw or rt.sha(folder / "protocol.json") != expected):
        result.update(status="INPUT_CHANGED", retained_for_development=False)
    if result["evaluator_runtime"] != protocol["runtime"]:
        result.update(status="INPUT_CHANGED", retained_for_development=False)
    for relative, digest in protocol["sources"].items():
        if rt.sha(ROOT / relative) != digest:
            result.update(status="INPUT_CHANGED", retained_for_development=False)
    rt.write_json(folder / "core.json", result)


def controller(folder: Path, run_id: str, expected: str) -> dict:
    protocol = read_protocol(folder, run_id, expected)
    (folder / "controller-claim").mkdir()
    limits = protocol["config"]["limits"]
    started = time.monotonic()
    deadline = started + limits["total_seconds"]
    stop = threading.Event()
    server = None
    monitor = None
    guard_monitor = None
    before = None
    errors = []
    samples = []
    observations = []
    record = {"schema": "eidos.c0.local-controller.v1", "run_id": run_id,
              "protocol_sha256": expected, "protocol": protocol, "status": "UNOBSERVED",
              "runtime": rt.runtime_identity(),
              "scientific_promotion": False, "scientific_rsi": "NOT_DEMONSTRATED",
              "sealed_evaluation": "NOT_RUN", "model_execution_attested": False,
              "samples": samples, "protected_observations": observations, "errors": errors}

    def sample():
        available = psutil.virtual_memory().available / 1048576
        rss = 0
        if server is not None and server.poll() is None:
            process = psutil.Process(server.pid)
            rss = sum(p.memory_info().rss for p in [process, *process.children(recursive=True)]) / 1048576
        result = {"elapsed_seconds": time.monotonic() - started, "available_mib": available, "tree_rss_mib": rss}
        samples.append(result)
        if server is None and available < limits["min_available_memory_mib"] + protocol["config"]["model"]["bytes"] / 1048576:
            raise RuntimeError("CPU weight admission exceeds available RAM headroom")
        if available < limits["min_available_memory_mib"] or rss > limits["max_tree_rss_mib"]:
            raise RuntimeError("Sampled RAM admission/usage limit exceeded")
        if server is not None and (folder / "server.log").stat().st_size > 10485760:
            raise RuntimeError("Sampled server-log size limit exceeded")
        if time.monotonic() > deadline:
            raise TimeoutError("Whole-trial deadline exceeded")

    def observe():
        observations.append({"elapsed_seconds": time.monotonic() - started,
                             "identities": rt.observe_guards(protocol["config"]["protected_services"], before)})

    def watch():
        while not stop.is_set():
            try:
                sample()
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
                if server is not None and server.poll() is None:
                    server.terminate()
                return
            stop.wait(0.5)

    def watch_guards():
        while not stop.is_set():
            try:
                observe()
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
                if server is not None and server.poll() is None:
                    server.terminate()
                return
            stop.wait(2)

    try:
        before = rt.observe_guards(protocol["config"]["protected_services"])
        record["protected_before"] = before
        sample()
        rt.verify_inputs(protocol)
        sample()
        observe()
        with socket.socket() as selector:
            selector.bind(("127.0.0.1", 0))
            port = selector.getsockname()[1]
        alias = "eidos-local-" + run_id
        command = rt.engine_command(protocol, port, alias)
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith("LLAMA_") and "API_KEY" not in k.upper() and
                       k.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
        environment.update(CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        record["command"] = command
        with (folder / "server.log").open("xb") as log:
            server = subprocess.Popen(command, cwd=folder, env=environment, stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=subprocess.STDOUT, creationflags=quiet_flags())
            record["owned_server"] = {"pid": server.pid, "created": psutil.Process(server.pid).create_time()}
            monitor = threading.Thread(target=watch, daemon=True)
            monitor.start()
            guard_monitor = threading.Thread(target=watch_guards, daemon=True)
            guard_monitor.start()
            endpoint = f"http://127.0.0.1:{port}"
            load_started = time.monotonic()
            while time.monotonic() - load_started < limits["load_seconds"]:
                if errors or server.poll() is not None:
                    raise RuntimeError("Owned server stopped or resource/service monitor failed")
                try:
                    remaining = limits["load_seconds"] - (time.monotonic() - load_started)
                    if remaining <= 0:
                        raise TimeoutError("Owned server load deadline exceeded")
                    health = rt.json_request(endpoint + "/health", timeout=min(1, remaining))
                    if (time.monotonic() - load_started <= limits["load_seconds"] and
                            health.get("status") == "ok"):
                        break
                except (OSError, TimeoutError):
                    pass
                stop.wait(0.25)
            else:
                raise TimeoutError("Owned server load deadline exceeded")
            listeners = {c.pid for c in psutil.net_connections(kind="tcp")
                         if c.status == psutil.CONN_LISTEN and c.laddr.port == port}
            if listeners != {server.pid}:
                raise RuntimeError("Model listener is not the owned process")
            remaining = limits["load_seconds"] - (time.monotonic() - load_started)
            if remaining <= 0:
                raise TimeoutError("Owned model identity exceeded the load deadline")
            identity = rt.json_request(endpoint + "/v1/models", timeout=min(2, remaining))
            if time.monotonic() - load_started > limits["load_seconds"]:
                raise TimeoutError("Owned model identity exceeded the load deadline")
            if [row.get("id") for row in identity.get("data", [])] != [alias]:
                raise RuntimeError("Owned provider model alias differs")
            record.update(provider_identity=identity, load_seconds=time.monotonic() - load_started)
            payload = {"model": alias, "temperature": 0, "top_p": 0.9, "seed": 19,
                       "max_tokens": limits["max_tokens"], "stream": False, "grammar": protocol["grammar"],
                       "chat_template_kwargs": {"enable_thinking": False},
                       "messages": [{"role": "user", "content": protocol["prompt"]}]}
            if "campaign_request" in protocol:
                record["preflight"] = rt.request_context.prepare(rt.json_request, endpoint, payload,
                    rt.format_payload(payload), limits, protocol["campaign_request"]["token_allowance"])
            request_started = time.monotonic()
            response = timed_request(endpoint + "/v1/chat/completions", payload, limits["request_seconds"], server)
            record.update(request=payload, request_seconds=time.monotonic() - request_started)
            record["target_usage"] = response.get("usage")
            rt.write_json(folder / "response.json", response)
            record["response_sha256"] = rt.sha(folder / "response.json")
            if "campaign_request" in protocol:
                rt.request_context.validate_target(record["target_usage"], record["preflight"], payload,
                    rt.format_payload(payload), limits, protocol["campaign_request"]["token_allowance"],
                    response["choices"][0]["message"].get("content") or "")
            evaluated = run_tree([sys.executable, "-I", "-X", "utf8", str(Path(__file__).resolve()),
                                  "evaluate", str(folder), run_id, expected],
                                 cwd=ROOT, timeout=limits["evaluation_seconds"])
            (folder / "evaluation.log").write_text(evaluated.stdout + evaluated.stderr, encoding="utf-8")
            if evaluated.returncode != 0:
                raise RuntimeError("Isolated evaluator failed")
            core = rt.strict_json((folder / "core.json").read_bytes())
            if (core.get("run_id") != run_id or core.get("protocol_sha256") != expected or
                    core.get("recorded_response_sha256") != record["response_sha256"]):
                raise RuntimeError("Evaluator/response/protocol binding differs")
            record["core"] = core
            control_payload = rt.format_payload(payload)
            control_started = time.monotonic()
            control = timed_request(endpoint + "/v1/chat/completions", control_payload,
                                    min(30, limits["request_seconds"]), server)
            choice = control["choices"][0]
            record["format_control"] = {"request": control_payload, "response": control,
                                         "seconds": time.monotonic() - control_started,
                                         "phase": "after target; backend smoke check only",
                                         "passed": choice.get("finish_reason") == "stop" and
                                                   choice["message"].get("content") == rt.FORMAT_LITERAL}
            if not record["format_control"]["passed"]:
                raise RuntimeError("Literal backend control failed")
            if "campaign_request" in protocol:
                record["used_model_tokens"] = rt.request_context.used_tokens(response["usage"], control["usage"],
                    record["preflight"], payload, control_payload, limits,
                    protocol["campaign_request"]["token_allowance"], core["raw_response"], choice["message"].get("content") or "")
            record["status"] = "COMPLETE"
    except Exception as error:
        record.update(status="INCOMPLETE", error_type=type(error).__name__)
        errors.append(type(error).__name__ + ": " + str(error))
    finally:
        stop.set()
        try:
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=3)
            record["owned_server_stopped"] = server is not None and server.poll() is not None
            record["owned_server_exit_code"] = None if server is None else server.poll()
            if monitor is not None:
                monitor.join(timeout=20)
            if guard_monitor is not None:
                guard_monitor.join(timeout=20)
            record["monitor_stopped"] = ((monitor is None or not monitor.is_alive()) and
                                         (guard_monitor is None or not guard_monitor.is_alive()))
            after = rt.observe_guards(protocol["config"]["protected_services"], before)
            record.update(protected_after=after, protected_services_preserved=before is not None and after == before)
            rt.verify_inputs(protocol)
            if rt.sha(folder / "protocol.json") != expected:
                raise RuntimeError("Protocol changed during execution")
            record["inputs_unchanged"] = True
        except Exception as error:
            errors.append("Cleanup/identity: " + type(error).__name__ + ": " + str(error))
        record.update(wall_seconds=time.monotonic() - started,
                      finished=datetime.now(timezone.utc).isoformat())
        if record["wall_seconds"] > limits["total_seconds"]:
            errors.append("Whole-trial deadline exceeded including cleanup")
        if errors or not record.get("monitor_stopped") or not record.get("owned_server_stopped"):
            record["status"] = "INCOMPLETE"
        rt.write_json(folder / "result.json", record)
    return record


def main() -> int:
    if len(sys.argv) != 5 or sys.argv[1] not in {"controller", "evaluate"}:
        raise ValueError("Use the configured local-runtime CLI")
    mode, folder, run_id, expected = sys.argv[1:]
    if mode == "evaluate":
        evaluate(Path(folder).resolve(strict=True), run_id, expected)
        return 0
    result = controller(Path(folder).resolve(strict=True), run_id, expected)
    return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
