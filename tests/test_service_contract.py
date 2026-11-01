"""Real HTTP statuses and unattributed listeners cannot manufacture service health."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import pytest

from framework import recovery, services


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            redirect = self.path == "/redirect"
            code = 307 if redirect else int(self.path.lstrip("/"))
            self.send_response(code)
            self.send_header("Content-Length", "0")
            if redirect:
                self.send_header("Location", "/200")
            self.end_headers()

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
    )
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, True),
        (204, True),
        (401, True),
        (403, True),
        (404, False),
        (405, False),
        (410, False),
        (429, False),
        (500, False),
        (503, False),
    ],
)
def test_declared_status_contract_with_real_http(endpoint, status, expected):
    origin, _ = endpoint
    assert services.answers(origin + "/" + str(status)) is expected


def test_redirect_is_not_a_successful_declared_endpoint(endpoint):
    origin, _ = endpoint
    assert services.answers(origin + "/redirect") is False


def test_unattributed_listener_cannot_trigger_a_duplicate_start(
    endpoint, tmp_path, monkeypatch
):
    origin, port = endpoint
    monkeypatch.setattr(recovery, "ENDPOINTS", {"svc": (origin + "/503",)})
    monkeypatch.setattr(recovery, "PORTS", {"svc": (port,)})
    monkeypatch.setattr(recovery, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(recovery, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(recovery, "port_owner", lambda port: None)
    monkeypatch.setattr(recovery, "_listener_table", lambda: None)
    monkeypatch.setattr(
        recovery.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("duplicate start"),
    )
    result = recovery.execute(recovery.RecoveryPlan("svc", "start", "controlled", True))
    assert result["skipped"] is True and result["ok"] is False
    assert "port already held" in result["reason"]


def test_preflight_verdict_uses_the_measurements_it_reports(monkeypatch):
    samples = iter((True, False))
    monkeypatch.setattr(recovery, "ENDPOINTS", {"svc": ("test:endpoint",)})
    monkeypatch.setattr(recovery, "PORTS", {})
    monkeypatch.setattr(recovery, "_answers", lambda url: next(samples))
    result = recovery.preflight("svc")
    assert result["healthy"] == all(result["answered"].values())


@pytest.mark.parametrize(
    "engine_status,model_status,engine_up,model_up",
    [
        (404, 200, False, True),
        (200, 403, True, True),
        (401, 401, True, True),
        (503, 429, False, False),
    ],
)
def test_monitor_and_recovery_share_presence_policy(
    tmp_path, monkeypatch, engine_status, model_status, engine_up, model_up
):
    from tools import watch_pipeline as watcher
    import framework.project

    monkeypatch.setattr(watcher, "ROOT", tmp_path)
    monkeypatch.setattr(watcher, "STATUS", tmp_path)
    monkeypatch.setattr(watcher, "DURATIONS", tmp_path / "durations.jsonl")
    monkeypatch.setattr(framework.project, "load_projects", lambda **kwargs: {})
    monkeypatch.setattr(watcher, "http_json", lambda url: (200, {"status": "ok"}))
    monkeypatch.setattr(
        watcher,
        "http_status",
        lambda url, *args: (
            engine_status
            if ":8081/" in url
            else model_status if ":18434/" in url else 200
        ),
    )
    result = watcher.measure()
    assert bool(result["decision_service"]["value"]) is engine_up
    assert bool(result["runtime_18434"]["value"]) is model_up


def test_preflight_does_not_publish_credential_bearing_command_lines(monkeypatch):
    monkeypatch.setattr(recovery, "ENDPOINTS", {})
    monkeypatch.setattr(recovery, "PORTS", {"svc": (9999,)})
    monkeypatch.setattr(recovery, "OWNER_HINTS", {"svc": ("llama-server",)})
    monkeypatch.setattr(recovery, "port_owner", lambda port: 4242)
    monkeypatch.setattr(recovery, "process_name", lambda pid: "llama-server")
    monkeypatch.setattr(
        recovery, "command_line", lambda pid: "llama-server --api-key FIXTURE-SECRET"
    )
    import json

    look = recovery.preflight("svc")
    assert look["owned_by_self"] is True
    assert "FIXTURE-SECRET" not in json.dumps(look)


def test_unobservable_socket_refuses_launch_without_spending_budget(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(recovery, "ENDPOINTS", {})
    monkeypatch.setattr(recovery, "PORTS", {"svc": (9999,)})
    monkeypatch.setattr(recovery, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(recovery, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(recovery, "port_owner", lambda port: None)
    monkeypatch.setattr(recovery, "_listener_table", lambda: None)
    monkeypatch.setattr(
        recovery.socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("controlled")),
    )
    monkeypatch.setattr(
        recovery.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("unobserved start"),
    )
    result = recovery.execute(recovery.RecoveryPlan("svc", "start", "controlled", True))
    assert result["skipped"] is True and "unobservable" in result["reason"]
    assert "attempted" not in result


@pytest.mark.parametrize(
    "body,code,expected",
    [
        (
            "TCP 127.0.0.1:1234 0.0.0.0:0 LISTENING 42\nTCP [::]:55 [::]:0 LISTENING 9",
            0,
            {1234: 42, 55: 9},
        ),
        ("TCP 127.0.0.1:1234 127.0.0.1:80 ESTABLISHED 42", 0, {}),
        ("TCP 127.0.0.1:1234 0.0.0.0:0 UNKNOWN_STATE 42", 0, None),
        ("TCP incomplete", 0, None),
        ("TCP 127.0.0.1:1234 0.0.0.0:0 LISTENING not-a-pid", 0, None),
        ("TCP 127.0.0.1:70000 0.0.0.0:0 LISTENING 42", 0, None),
        ("", 0, None),
        ("TCP 127.0.0.1:1234 0.0.0.0:0 LISTENING 42", 1, None),
    ],
)
def test_listener_table_requires_a_complete_valid_observation(
    monkeypatch, body, code, expected
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        recovery.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=code, stdout=body),
    )
    assert recovery._listener_table() == expected
