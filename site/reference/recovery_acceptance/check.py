"""Actual disposable-service recovery; source-checkout qualification, no real models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
NAME = "acceptance_http_fixture"
CHECK_NAMES = {
    "initial_real_service",
    "http_status_contract",
    "redirect_does_not_substitute_another_endpoint",
    "actual_process_crash_observed",
    "two_fault_samples_do_not_launch",
    "third_sample_starts_real_process",
    "real_endpoints_verify_recovery",
    "one_attempt_one_terminal",
    "healthy_service_is_not_restarted",
    "half_failed_service_is_not_healthy",
    "held_port_refuses_duplicate_launch",
    "windows_launchers_have_no_console",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def checked_payload(candidate):
    require(
        isinstance(candidate, dict)
        and set(candidate)
        == {"checks", "port", "boots", "processes_are_disposable", "sampling"},
        "invalid worker object",
    )
    json.dumps(candidate, allow_nan=False)
    rows = candidate["checks"]
    require(
        isinstance(rows, list) and len(rows) == len(CHECK_NAMES),
        "incomplete worker checks",
    )
    require(
        all(
            isinstance(row, dict)
            and type(row.get("name")) is str
            and row["name"] in CHECK_NAMES
            and type(row.get("passed")) is bool
            for row in rows
        ),
        "invalid worker verdict",
    )
    require(
        {row["name"] for row in rows} == CHECK_NAMES,
        "duplicate or missing worker check",
    )
    port = candidate["port"]
    require(type(port) is int and 0 < port <= 65535, "invalid fixture port")
    boots = candidate["boots"]
    require(isinstance(boots, list) and len(boots) == 2, "invalid boot inventory")
    require(
        all(
            isinstance(boot, dict)
            and type(boot.get("pid")) is int
            and boot["pid"] > 0
            and type(boot.get("port")) is int
            and boot["port"] == port
            and isinstance(boot.get("python"), str)
            and boot["python"]
            for boot in boots
        ),
        "invalid fixture process identity",
    )
    require(
        boots[0]["pid"] != boots[1]["pid"],
        "crash and restart must be different processes",
    )
    require(
        candidate["processes_are_disposable"] is True
        and isinstance(candidate["sampling"], str),
        "invalid fixture scope",
    )
    return candidate


def wait_for(test, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if test():
            return
        time.sleep(0.05)
    raise TimeoutError("disposable fixture did not reach its expected state")


def process_alive(pid: int) -> bool | None:
    """Observe fixture PIDs only; absence/exit is different from access failure."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        api.GetExitCodeProcess.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False if ctypes.get_last_error() == 87 else None
        try:
            code = wintypes.DWORD()
            return (
                code.value == 259
                if api.GetExitCodeProcess(handle, ctypes.byref(code))
                else None
            )
        finally:
            api.CloseHandle(handle)
    path = Path("/proc") / str(pid) / "stat"
    try:
        return path.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False
    except (OSError, IndexError):
        return None


def worker(base: Path, owner: str) -> dict:
    from framework import recovery, services
    from framework.subprocesses import quiet_flags
    from tools import watch_pipeline as watcher

    for module, name in (
        (recovery, "framework/recovery.py"),
        (services, "framework/services.py"),
        (watcher, "tools/watch_pipeline.py"),
    ):
        require(
            Path(module.__file__).resolve() == ROOT / name,
            "loaded source differs from receipt inputs",
        )

    base = base.resolve()
    parent = (Path(tempfile.gettempdir()) / "eidos-recovery-acceptance").resolve()
    require(
        base.parent == parent and base.name.startswith("run-"), "unexpected workspace"
    )
    config_path = base / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    require(config["owner"] == owner, "workspace ownership mismatch")
    recovery.ROOT = base / "framework-home"
    recovery.ROOT.mkdir()
    recovery.STATE = base / "recovery_state.json"
    recovery.LOG = base / "recoveries.jsonl"
    watcher.RECOVERY_STATE = recovery.STATE
    watcher.RECOVERIES = recovery.LOG
    watcher.STATUS = base
    os.environ["EIDOS_AUTO_RECOVER"] = "1"
    recovery.ACTIONS = {
        NAME: {
            "root": "repo",
            "kind": "python",
            "script": ("service.py",),
            "description": "restart this disposable loopback fixture",
        }
    }
    initial = subprocess.Popen(
        [sys.executable, str(base / "service.py")],
        cwd=base,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=quiet_flags(),
    )
    boots_path = base / "boots.jsonl"

    def boots():
        try:
            return [
                json.loads(line)
                for line in boots_path.read_text(encoding="utf-8").splitlines()
            ]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    wait_for(lambda: bool(boots()))
    port = boots()[0]["port"]
    config["port"] = port
    config_path.write_text(json.dumps(config), encoding="utf-8")
    origin = "http://127.0.0.1:" + str(port)
    services.ENDPOINTS = {NAME: (origin + "/health", origin + "/engine")}
    recovery.ENDPOINTS = services.ENDPOINTS
    recovery.HEALTH = {NAME: origin + "/health"}
    recovery.PORTS = {NAME: (port,)}
    recovery.OWNER_HINTS = {NAME: ("service.py",)}
    checks = []

    def check(name, passed, **detail):
        checks.append({"name": name, "passed": bool(passed), **detail})

    def sample():
        look = services.check(NAME)
        return {
            NAME: {
                "state": "OK" if look["healthy"] else "ALARM",
                "recovery": {"available": recovery.plan(NAME).available},
            }
        }

    check("initial_real_service", services.check(NAME)["healthy"])
    matrix = []
    for code in (200, 204, 401, 403, 404, 405, 410, 429, 500, 503):
        observed = services.answers(origin + "/status/" + str(code))
        expected = 200 <= code < 300 or code in (401, 403)
        matrix.append({"status": code, "observed": observed, "expected": expected})
    check(
        "http_status_contract",
        all(row["observed"] == row["expected"] for row in matrix),
        rows=matrix,
    )
    check(
        "redirect_does_not_substitute_another_endpoint",
        not services.answers(origin + "/redirect"),
    )

    request = urllib.request.Request(
        origin + "/crash",
        method="POST",
        data=json.dumps({"owner": owner}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        require(response.status == 202, "fixture rejected owned crash request")
    require(initial.wait(timeout=5) == 17, "the initial fixture did not actually crash")
    wait_for(lambda: not services.check(NAME)["healthy"])
    check(
        "actual_process_crash_observed",
        initial.returncode == 17 and not services.check(NAME)["healthy"],
    )
    for _ in range(2):
        watcher.maybe_auto_recover(sample())
        time.sleep(0.05)
    check("two_fault_samples_do_not_launch", len(boots()) == 1)
    third = watcher.maybe_auto_recover(sample())[NAME]
    attempt = third.get("recovery_auto", {}).get("result", {})
    check(
        "third_sample_starts_real_process",
        attempt.get("attempted")
        and attempt.get("ok")
        and attempt.get("pid") != initial.pid,
    )
    require(attempt.get("pid"), "automatic recovery refused: " + json.dumps(attempt))
    wait_for(lambda: len(boots()) == 2 and services.check(NAME)["healthy"])
    watcher.maybe_auto_recover(sample())
    state = json.loads(recovery.STATE.read_text(encoding="utf-8"))[NAME]
    events = [
        json.loads(line)
        for line in recovery.LOG.read_text(encoding="utf-8").splitlines()
    ]
    check(
        "real_endpoints_verify_recovery",
        not state["pending"] and state["attempts"] == 0 and state["failures"] == 0,
    )
    check(
        "one_attempt_one_terminal",
        sum(row["phase"] == "attempt" for row in events) == 1
        and sum(
            row["phase"] == "verified" and row["outcome"] == "recovered"
            for row in events
        )
        == 1,
    )
    healthy = recovery.execute(recovery.plan(NAME))
    check(
        "healthy_service_is_not_restarted",
        healthy.get("skipped") and healthy.get("ok") and len(boots()) == 2,
    )

    config["engine_status"] = 503
    config_path.write_text(json.dumps(config), encoding="utf-8")
    check("half_failed_service_is_not_healthy", not services.check(NAME)["healthy"])
    held = recovery.execute(recovery.plan(NAME))
    check(
        "held_port_refuses_duplicate_launch",
        held.get("skipped") and not held.get("ok") and not held.get("attempted"),
    )
    check(
        "windows_launchers_have_no_console",
        os.name != "nt" or all(row["console_window"] == 0 for row in boots()),
    )
    return {
        "checks": checks,
        "port": port,
        "boots": boots(),
        "processes_are_disposable": True,
        "sampling": "three distinct real probes at accelerated intervals; default cooldown constants unchanged",
    }


def main() -> int:
    if sys.flags.optimize:
        raise SystemExit("Qualification requires normal interpreter mode; omit -O/-OO.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/RECOVERY-LIVE-ACCEPTANCE.json"
    )
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--owner", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--fault-worker",
        action="store_true",
        help="negative control: worker failure must invalidate the output",
    )
    parser.add_argument(
        "--fault-worker-json",
        choices=("list", "empty", "checks-null"),
        help="negative control: malformed zero-exit JSON must invalidate the output",
    )
    args = parser.parse_args()
    if args.worker:
        if args.fault_worker:
            raise RuntimeError("controlled worker failure")
        if args.fault_worker_json:
            print(
                json.dumps(
                    {"list": [], "empty": {}, "checks-null": {"checks": None}}[
                        args.fault_worker_json
                    ]
                )
            )
            return 0
        print(json.dumps(worker(args.worker, args.owner)))
        return 0

    from framework.artifacts import atomic_output, output_lock
    from framework.subprocesses import run_tree
    from tools.owned_workspace import owned_workspace

    source_paths = [
        "framework/recovery.py",
        "framework/services.py",
        "tools/watch_pipeline.py",
        "framework/artifacts.py",
        "framework/subprocesses.py",
        "framework/_process_tree.py",
        "framework/_windows_job.py",
        "framework/_posix_job.py",
        "tools/owned_workspace.py",
        "pyproject.toml",
        "uv.lock",
        "reference/recovery_acceptance/check.py",
        "reference/recovery_acceptance/service.py",
    ]

    def fingerprints():
        return {
            name: hashlib.sha256(
                (ROOT / name).read_text(encoding="utf-8").encode()
            ).hexdigest()
            for name in source_paths
        }

    before = fingerprints()
    data = {"checks": []}
    owner = ""
    try:
        with owned_workspace(
            Path(tempfile.gettempdir()) / "eidos-recovery-acceptance", prefix="run-"
        ) as base:
            owner = uuid.uuid4().hex
            (base / "service.py").write_bytes(
                Path(__file__).with_name("service.py").read_bytes()
            )
            (base / "config.json").write_text(
                json.dumps({"owner": owner, "port": 0}), encoding="utf-8"
            )
            env = dict(
                os.environ,
                PYTHONUTF8="1",
                NO_PROXY="127.0.0.1,localhost",
                no_proxy="127.0.0.1,localhost",
            )
            run = run_tree(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    str(base),
                    "--owner",
                    owner,
                    *(["--fault-worker"] if args.fault_worker else []),
                    *(
                        ["--fault-worker-json", args.fault_worker_json]
                        if args.fault_worker_json
                        else []
                    ),
                ],
                cwd=ROOT,
                env=env,
                timeout=75,
            )
            require(run.returncode == 0, "fixture worker failed: " + run.stderr[-2000:])
            candidate = json.loads(run.stdout)
            data = checked_payload(candidate)

            def closed():
                with socket.socket() as probe:
                    probe.settimeout(0.5)
                    return probe.connect_ex(("127.0.0.1", data["port"])) != 0 and all(
                        process_alive(boot["pid"]) is False for boot in data["boots"]
                    )

            try:
                wait_for(closed, seconds=5)
                cleanup_verified = True
            except TimeoutError:
                cleanup_verified = False
            data["checks"].append(
                {
                    "name": "owned_job_closes_disposable_services",
                    "passed": cleanup_verified,
                }
            )
    except Exception as exc:
        detail = str(exc).replace(owner, "[fixture-owner]") if owner else str(exc)
        data["checks"].append(
            {
                "name": "fixture_execution",
                "passed": False,
                "error": type(exc).__name__,
                "detail": detail[-2400:],
            }
        )
    after = fingerprints()
    passed = before == after and all(row["passed"] for row in data["checks"])
    record = {
        "schema": 1,
        "kind": "eidos.disposable-recovery-acceptance",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "optimization_level": sys.flags.optimize,
        "source_sha256_lf": after,
        "stable_sources": before == after,
        **data,
        "limits": [
            "Disposable HTTP service, not a real model-service restart or legacy-runtime migration.",
            "Source-checkout qualification, not installed-wheel, reboot or 24-hour acceptance.",
            "401/403 qualify authenticated presence, not successful inference or credential validity.",
            "Default retry/cooldown wall time is not accelerated or qualified by this short probe.",
        ],
    }
    output = args.out.resolve()
    with output_lock(output.parent / ("recovery-receipt-" + output.name)):
        if output.exists():
            require(
                json.loads(output.read_text(encoding="utf-8")).get("kind")
                == record["kind"],
                "refusing to replace a non-recovery document",
            )
        with atomic_output(output) as temporary:
            temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": record["status"],
                "checks": len(record["checks"]),
                "failed": [
                    row["name"] for row in record["checks"] if not row["passed"]
                ],
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
