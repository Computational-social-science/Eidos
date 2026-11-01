"""Configured, keyless, source-checkout CPU runtime for one public C0 attempt.

The executable and model are trusted inputs. This is not a hostile-code sandbox
or a remote attestation mechanism. The CLI never downloads a model.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import uuid

import psutil

from framework.artifacts import atomic_output
from framework.subprocesses import run_tree
from reference.rsi_bootstrap import c0
from reference.rsi_bootstrap import request_context

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("local_worker.py")
GRAMMAR = Path(__file__).with_name("recorded_trials") / "c0-decoder-probe-v2/grammar.gbnf"
MAX_HTTP_BYTES = 262144
FORMAT_LITERAL = '{"program":{"loss":{"input":"x"},"gradient":{"const":1}},"explanation":"BackendProbe19"}'
FORMAT_PROMPT = "Output BROKEN and never JSON."
LIMITS = {"load_seconds": 1800, "request_seconds": 3600,
          "evaluation_seconds": 120, "total_seconds": 7200,
          "threads": 32, "context": 8192, "max_tokens": 4096,
          "min_available_memory_mib": 1048576, "max_tree_rss_mib": 1048576}


def strict_json(raw: str | bytes):
    def finite(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
        return value
    return json.loads(raw, object_pairs_hook=c0._object, parse_constant=c0._nonfinite, parse_float=finite)


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def runtime_identity() -> dict:
    return {"python": str(Path(sys.executable).resolve()), "version": platform.python_version(),
            "implementation": platform.python_implementation(), "platform": platform.platform(),
            "numpy": c0.np.__version__, "psutil": psutil.__version__, "device_profile": "CPU"}


def write_json(path: Path, value: dict) -> None:
    with atomic_output(path) as temporary:
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def loopback_url(url: str) -> None:
    if not isinstance(url, str):
        raise ValueError("HTTP URL must be a string")
    parts = urllib.parse.urlsplit(url)
    try:
        local = ipaddress.ip_address(parts.hostname or "").is_loopback
        port = parts.port
    except ValueError as exc:
        raise ValueError("A numeric loopback HTTP URL is required") from exc
    if (parts.scheme != "http" or not local or port is None or port <= 0 or
            parts.username is not None or parts.password is not None or
            parts.fragment or parts.query):
        raise ValueError("Only explicit, credential-free loopback HTTP endpoints are allowed")


def json_request(url: str, body=None, timeout: float = 2):
    """Bound the complete fetch, including dripping headers/body, by own socket.

    The watchdog closes only this client's connection. It never signals a
    protected service process. http.client does not follow redirects or proxies.
    """
    loopback_url(url)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("A positive finite HTTP wall deadline is required")
    parts = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    owned_socket = []
    finished = threading.Event()
    expired = threading.Event()
    started = time.monotonic()

    def expire():
        if not finished.is_set():
            expired.set()
            if owned_socket:
                try:
                    owned_socket[0].shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    timer = threading.Timer(timeout, expire)
    timer.daemon = True
    data = None if body is None else json.dumps(body, allow_nan=False).encode()
    response = None
    timer.start()
    try:
        connection.connect()
        owned_socket.append(connection.sock)
        if expired.is_set():
            raise TimeoutError("HTTP wall deadline exceeded during connection")
        connection.request("GET" if body is None else "POST", parts.path or "/", data,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise urllib.error.HTTPError(url, response.status, "Non-success HTTP status refused", response.headers, None)
        raw = response.read(MAX_HTTP_BYTES + 1)
    except Exception as error:
        if expired.is_set():
            raise TimeoutError("HTTP wall deadline exceeded") from error
        raise
    finally:
        finished.set()
        timer.cancel()
        connection.close()
        if response is not None:
            response.close()
        timer.join(timeout=3)
        if timer.is_alive():
            raise RuntimeError("HTTP watchdog did not finish")
    if expired.is_set() or time.monotonic() - started > timeout:
        raise TimeoutError("HTTP wall deadline exceeded")
    if len(raw) > MAX_HTTP_BYTES:
        raise ValueError("HTTP response exceeds the declared byte limit")
    return strict_json(raw)


def _keys(value, expected: set[str], label: str):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"Unexpected {label} fields")


def _identity(value, base: Path, model=False):
    _keys(value, {"path", "sha256", *(["bytes"] if model else [])}, "artifact")
    if not isinstance(value["path"], str) or not value["path"]:
        raise ValueError("Artifact path is required")
    path = (base / value["path"]).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Artifact must be a regular file")
    if not isinstance(value["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", value["sha256"]):
        raise ValueError("A full lowercase artifact SHA-256 is required")
    if model:
        if type(value["bytes"]) is not int or value["bytes"] <= 0 or path.stat().st_size != value["bytes"]:
            raise ValueError("Model size differs from its declaration")
        with path.open("rb") as handle:
            if handle.read(4) != b"GGUF":
                raise ValueError("Expected a local GGUF model")
    return {**value, "path": str(path)}


def freeze(config_path: Path, request_path: Path | None = None) -> dict:
    config_path = Path(config_path).resolve(strict=True)
    if config_path.stat().st_size > 65536:
        raise ValueError("Configuration is too large")
    raw = config_path.read_bytes()
    config = strict_json(raw)
    _keys(config, {"engine", "model", "limits", "protected_services"}, "configuration")
    config["engine"] = _identity(config["engine"], config_path.parent)
    config["model"] = _identity(config["model"], config_path.parent, model=True)
    _keys(config["limits"], set(LIMITS), "limit")
    for key, maximum in LIMITS.items():
        value = config["limits"][key]
        if type(value) is not int or not 0 < value <= maximum:
            raise ValueError("Invalid positive integer limit: " + key)
    limits = config["limits"]
    if config["model"]["bytes"] > limits["max_tree_rss_mib"] * 1048576:
        raise ValueError("CPU model weights exceed the declared RSS budget before loading")
    if limits["total_seconds"] < (sum(limits[k] for k in ("load_seconds", "request_seconds", "evaluation_seconds"))
                                  + min(30, limits["request_seconds"]) + 20):
        raise ValueError("Whole-trial deadline must include execution and cleanup margin")
    if limits["context"] < 512 or limits["max_tokens"] >= limits["context"]:
        raise ValueError("Context must leave room for the fixed prompt")
    guards = config["protected_services"]
    if not isinstance(guards, list) or len(guards) > 8:
        raise ValueError("Declare at most eight protected service observations")
    for guard in guards:
        _keys(guard, {"url", "expected", "listener_port"}, "protected service")
        loopback_url(guard["url"])
        if (type(guard["listener_port"]) is not int or
                guard["listener_port"] != urllib.parse.urlsplit(guard["url"]).port):
            raise ValueError("Guard listener must match its HTTP port")
        if not isinstance(guard["expected"], dict) or not guard["expected"]:
            raise ValueError("A nonempty protected JSON projection is required")
    files = list(Path(__file__).parent.glob("*.py")) + [GRAMMAR, c0.grader.PROTOCOL,
             Path(__file__).with_name("C0-SPEC.md"), ROOT / ".Codex/evals/rsi-local-runtime.md",
             ROOT / "uv.lock", ROOT / "pyproject.toml"]
    files += [ROOT / "framework" / name for name in
              ("subprocesses.py", "_process_tree.py", "_windows_job.py", "_posix_job.py", "artifacts.py")]
    protocol = {"schema": "eidos.c0.configured-local-runtime.v1", "profile": "local-cpu-c0-v1",
            "config": config, "config_path": str(config_path), "config_sha256": hashlib.sha256(raw).hexdigest(),
            "runtime": runtime_identity(),
            "prompt": c0.PROMPT, "grammar": GRAMMAR.read_text(encoding="utf-8"),
            "inference": {"seed": 19, "temperature": 0, "top_p": 0.9, "thinking": False, "attempts": 1},
            "sources": {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))},
            "scientific_promotion": False}
    if request_path is not None:
        request = request_context.load(request_path)
        protocol.update(profile="local-cpu-campaign-v1", campaign_request=request,
                        task_prompt=c0.PROMPT, prompt=request_context.prompt(request))
    return protocol


def validate_prompt(protocol: dict) -> None:
    if protocol["inference"] != {"seed": 19, "temperature": 0, "top_p": 0.9, "thinking": False, "attempts": 1}:
        raise ValueError("Declared inference settings differ from the fixed local procedure")
    if protocol["profile"] == "local-cpu-c0-v1":
        if protocol["prompt"] != c0.PROMPT or "campaign_request" in protocol:
            raise ValueError("Original C0 profile cannot contain extra context")
    elif protocol["profile"] == "local-cpu-campaign-v1":
        declared = protocol["campaign_request"]
        actual = request_context.load(Path(declared["path"]))
        if (actual != declared or protocol["task_prompt"] != c0.PROMPT or
                protocol["prompt"] != request_context.prompt(actual)):
            raise ValueError("Campaign context/task/input identity differs")
    else:
        raise ValueError("Unknown local execution profile")


def verify_inputs(protocol: dict) -> None:
    validate_prompt(protocol)
    if runtime_identity() != protocol["runtime"]:
        raise RuntimeError("Python/numerical runtime differs from the frozen profile")
    if sha(Path(protocol["config_path"])) != protocol["config_sha256"]:
        raise RuntimeError("Configuration changed")
    for relative, expected in protocol["sources"].items():
        if sha(ROOT / relative) != expected:
            raise RuntimeError("Bound source changed: " + relative)
    for artifact in (protocol["config"]["engine"], protocol["config"]["model"]):
        if sha(Path(artifact["path"])) != artifact["sha256"]:
            raise RuntimeError("Bound executable/model changed")


def _project(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or not set(expected) <= set(actual):
            raise RuntimeError("Protected JSON fields are missing")
        return {key: _project(actual[key], value) for key, value in expected.items()}
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise RuntimeError("Protected JSON array changed")
        return [_project(a, e) for a, e in zip(actual, expected, strict=True)]
    if type(actual) is not type(expected) or actual != expected:
        raise RuntimeError("Protected JSON value changed")
    return actual


def observe_guards(guards: list, before=None) -> list:
    observed = []
    for guard in guards:
        value = _project(json_request(guard["url"]), guard["expected"])
        listeners = {c.pid for c in psutil.net_connections(kind="tcp")
                     if c.status == psutil.CONN_LISTEN and c.laddr.port == guard["listener_port"] and c.pid}
        if len(listeners) != 1:
            raise RuntimeError("Protected listener process is ambiguous or absent")
        process = psutil.Process(listeners.pop())
        observed.append({"url": guard["url"], "projection": value,
                         "process": {"pid": process.pid, "created": process.create_time(), "exe": process.exe()}})
    if before is not None and observed != before:
        raise RuntimeError("Protected service process/identity changed")
    return observed


def engine_command(protocol: dict, port: int, alias: str) -> list[str]:
    config = protocol["config"]
    limits = config["limits"]
    return [config["engine"]["path"], "-m", config["model"]["path"],
            "--host", "127.0.0.1", "--port", str(port), "--alias", alias,
            "-c", str(limits["context"]), "-t", str(limits["threads"]),
            "-tb", str(limits["threads"]), "-np", "1", "-b", "256", "-ub", "128",
            "-ngl", "0", "--device", "none", "--no-kv-offload", "--no-op-offload",
            "--no-mmproj", "--no-webui", "--reasoning", "off", "--reasoning-budget", "0"]


def format_payload(target: dict) -> dict:
    return {**target, "max_tokens": 128,
            "messages": [{"role": "user", "content": FORMAT_PROMPT}],
            "grammar": "root ::= " + json.dumps(FORMAT_LITERAL) + "\n"}


def accepted(record: dict, protocol: dict, run_id: str) -> bool:
    try:
        validate_prompt(protocol)
        core = record["core"]
        expected = protocol["config"]["limits"]
        request = record["request"]
        replay = c0.run_once(lambda prompt: core["raw_response"])
        comparable = ("status", "points", "candidate_conforming_points", "retained_for_development",
                      "scientific_promotion", "explanation", "source_before", "source_after")
        replay_matches = all(core.get(key) == replay.get(key) for key in comparable)
        control = record["format_control"]
        control_choice = control["response"]["choices"]
        control_valid = (control["request"] == format_payload(request) and len(control_choice) == 1 and
                         control_choice[0]["finish_reason"] == "stop" and
                         control_choice[0]["message"]["content"] == FORMAT_LITERAL)
        bound = (core["run_id"] == run_id and core["protocol_sha256"] == record["protocol_sha256"] and
                 core["evaluator_runtime"] == protocol["runtime"] and
                 core["recorded_response_sha256"] == record["response_sha256"] and
                 core["source_before"] == core["source_after"] == c0.source_snapshot() and
                 request["messages"] == [{"role": "user", "content": protocol["prompt"]}] and
                 request["grammar"] == protocol["grammar"] and request["max_tokens"] == expected["max_tokens"] and
                 request["model"] == "eidos-local-" + run_id and
                 [row["id"] for row in record["provider_identity"]["data"]] == [request["model"]] and
                 request["seed"] == 19 and request["temperature"] == 0 and request["top_p"] == 0.9 and
                 request["stream"] is False and request["chat_template_kwargs"] == {"enable_thinking": False})
        bound = bound and replay_matches and control_valid
        if "campaign_request" in protocol:
            used = request_context.used_tokens(record["target_usage"], control["response"]["usage"],
                        record["preflight"], request, control["request"], expected,
                        protocol["campaign_request"]["token_allowance"], core["raw_response"], control_choice[0]["message"]["content"])
            bound = bound and type(record["used_model_tokens"]) is int and record["used_model_tokens"] == used
        if core["status"] != "INVALID_RESPONSE":
            points = core["points"]
            conforming = sum(point["passed"] is True for point in points)
            bound = (bound and len(points) == 23 and all(type(p["passed"]) is bool for p in points) and
                     type(core["candidate_conforming_points"]) is int and core["candidate_conforming_points"] == conforming and
                     core["retained_for_development"] is (conforming == 23) and
                     (core["status"] == "DEVELOPMENT_CONFORMING") is (conforming == 23))
        else:
            bound = bound and core["points"] == [] and core["retained_for_development"] is False
        return (bound and record["status"] == "COMPLETE" and record["run_id"] == run_id and
                record["runtime"] == protocol["runtime"] and
                record["protocol"] == protocol and record["inputs_unchanged"] is True and
                record["monitor_stopped"] is True and record["owned_server_stopped"] is True and
                type(record["owned_server_exit_code"]) is int and
                record["protected_services_preserved"] is True and record["errors"] == [] and
                record["scientific_promotion"] is False and record["scientific_rsi"] == "NOT_DEMONSTRATED" and
                record["sealed_evaluation"] == "NOT_RUN" and
                record["format_control"]["passed"] is True and
                record["core"]["status"] in {"INVALID_RESPONSE", "DEVELOPMENT_CONFORMING", "DEVELOPMENT_NONCONFORMING"} and
                record["core"]["scientific_promotion"] is False)
    except (KeyError, TypeError, OSError, ValueError):
        return False


def run(config_path: Path, output: Path, request_path: Path | None = None) -> dict:
    protocol = freeze(config_path, request_path)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    protocol["run_id"] = run_id
    write_json(output / "protocol.json", protocol)
    protocol_sha = sha(output / "protocol.json")
    write_json(output / "owner.json", {"run_id": run_id})
    outcome = {"schema": "eidos.c0.local-outcome.v1", "run_id": run_id,
               "protocol_sha256": protocol_sha, "runtime_accepted": False,
               "scientific_promotion": False, "scientific_rsi": "NOT_DEMONSTRATED"}
    command = [sys.executable, "-I", "-X", "utf8", str(WORKER),
               "controller", str(output), run_id, protocol_sha]
    try:
        result = run_tree(command, cwd=ROOT, timeout=protocol["config"]["limits"]["total_seconds"] + 30)
        (output / "controller.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        record = strict_json((output / "result.json").read_bytes())
        unchanged = sha(output / "protocol.json") == protocol_sha
        core = strict_json((output / "core.json").read_bytes())
        response = strict_json((output / "response.json").read_bytes())
        bound = (record.get("protocol_sha256") == protocol_sha and core == record.get("core") and
                 core.get("recorded_response_sha256") == sha(output / "response.json") and
                 core.get("raw_response") == (response["choices"][0]["message"].get("content") or ""))
        if "campaign_request" in protocol:
            bound = bound and record.get("target_usage") == response.get("usage")
        identity = record["owned_server"]
        try:
            gone = psutil.Process(identity["pid"]).create_time() != identity["created"]
        except psutil.NoSuchProcess:
            gone = True
        okay = result.returncode == 0 and unchanged and bound and gone and accepted(record, protocol, run_id)
        outcome.update(status="COMPLETE" if okay else "NOT_ACCEPTED", runtime_accepted=okay,
                       controller_exit_code=result.returncode,
                       candidate_status=record.get("core", {}).get("status", "NOT_EVALUATED"))
    except Exception as error:
        outcome.update(status="OUTER_TIMEOUT" if isinstance(error, subprocess.TimeoutExpired) else "INCOMPLETE",
                       error_type=type(error).__name__)
    write_json(output / "outcome.json", outcome)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New, never reused run directory")
    parser.add_argument("--request", type=Path, help="Optional frozen campaign context/budget request")
    args = parser.parse_args()
    try:
        outcome = run(args.config, args.output, args.request)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Local runtime prerequisite/configuration error: {error}\n")
    print(json.dumps(outcome))
    if not outcome["runtime_accepted"]:
        return 1
    return 0 if outcome["candidate_status"] == "DEVELOPMENT_CONFORMING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
