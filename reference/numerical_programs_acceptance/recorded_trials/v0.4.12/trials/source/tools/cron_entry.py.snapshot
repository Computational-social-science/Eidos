"""Quiet scheduled checks, using the configured project interpreter and captured logs."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def runtime(root: Path = ROOT) -> dict:
    result = {"PYTHON": os.environ.get("EIDOS_PYTHON") or sys.executable}
    path = root / "scripts/monitor.env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.fullmatch(
                r'\s*set\s+"?(PYTHON|QUARTO_BIN)=(.*?)"?\s*', line, re.I
            )
            if match and match[2].strip():
                result[match[1].upper()] = os.path.expandvars(match[2].strip())
    if os.environ.get("EIDOS_PYTHON"):
        result["PYTHON"] = os.environ["EIDOS_PYTHON"]
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("watchdog", "contracts"))
    args = parser.parse_args(argv)
    from framework.artifacts import output_lock

    try:
        with output_lock(ROOT / "docs/status" / ("cron-owner-" + args.kind), timeout=0):
            return _run(args)
    except TimeoutError:
        print(f"BUSY EIDOS {args.kind}: another check owns this lifetime")
        return 75


def _run(args) -> int:
    configured = runtime()
    if configured.get("QUARTO_BIN"):
        os.environ["QUARTO_BIN"] = configured["QUARTO_BIN"]
    from tools.bounded_process import run_tree
    from tools.consumer_snapshot import atomic_json

    command = (
        [configured["PYTHON"], str(ROOT / "tools/watchdog.py"), "--json"]
        if args.kind == "watchdog"
        else [
            configured["PYTHON"],
            str(ROOT / "tools/contract_snapshot.py"),
            "--check",
            "--json",
        ]
    )
    record = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "kind": args.kind,
        "ok": False,
        "entry_python": sys.executable,
        "python_version": sys.version.split()[0],
        "isolated": bool(sys.flags.isolated),
        "utf8_mode": bool(sys.flags.utf8_mode),
        "pythonpath_present": bool(os.environ.get("PYTHONPATH")),
        "pythonhome_present": bool(os.environ.get("PYTHONHOME")),
    }
    record["console_window"] = None
    if os.name == "nt":
        import ctypes

        window = ctypes.windll.kernel32.GetConsoleWindow
        window.restype = ctypes.c_void_p
        record["console_window"] = int(window() or 0)
    issues = []
    try:
        run = run_tree(command, cwd=ROOT, timeout=300)
        record["exit_code"] = run.returncode
        if args.kind == "contracts":
            data = json.loads(run.stdout)
            if not isinstance(data, dict) or not isinstance(
                data.get("boundaries"), dict
            ):
                raise ValueError("invalid contract record")
            for name in ("regressions", "findings"):
                if not isinstance(data.get(name), list) or not all(
                    isinstance(v, str) for v in data[name]
                ):
                    raise ValueError("invalid contract changes")
            boundaries = data["boundaries"]
            if not boundaries or any(
                not isinstance(v, dict) or type(v.get("ok")) is not bool
                for v in boundaries.values()
            ):
                raise ValueError("invalid contract boundaries")
            record.update(
                ok=run.returncode == 0 and not data["regressions"],
                boundaries=boundaries,
            )
            issues = [*data["regressions"], *data["findings"]]
            record["findings"] = issues
            if run.returncode != (1 if data["regressions"] else 0):
                raise ValueError("contract exit and structured verdict disagree")
            record["execution_ok"] = True
        else:
            data = json.loads(run.stdout)
            if (
                not isinstance(data, dict)
                or type(data.get("schema")) is not int
                or data["schema"] != 1
                or data.get("check_completed") is not True
                or type(data.get("healthy")) is not bool
                or not isinstance(data.get("problems"), list)
                or not all(isinstance(v, str) and v for v in data["problems"])
                or not isinstance(data.get("incident_key"), str)
                or not data["incident_key"]
                or not isinstance(data.get("verdict"), str)
                or data["verdict"] not in {"OK", "ALARM", "STALE", "UNKNOWN"}
                or data["healthy"] != (data["verdict"] == "OK")
                or data["healthy"] != (not bool(data["problems"]))
                or run.returncode != (0 if data["healthy"] else 1)
            ):
                raise ValueError("invalid or contradictory watchdog result")
            record.update(ok=data["healthy"], execution_ok=True, health=data)
            issues = data["problems"]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        record.update(ok=False, execution_ok=False, error=type(exc).__name__)
        issues = [f"checker execution error: {type(exc).__name__}"]
    path = ROOT / "docs/status" / f"cron-{args.kind}.json"
    _publish(path, record, issues, atomic_json)
    # A completed negative health check is not a scheduler execution failure.
    # Its negative verdict remains in the receipt and the transition notice.
    return 0 if record["execution_ok"] else 1


def _publish(path, record, issues, atomic_json):
    from framework.artifacts import output_lock

    with output_lock(path.parent / ("notification-" + record["kind"]), timeout=5):
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(previous, dict):
                previous = {}
        except (OSError, ValueError):
            previous = {}
        health = record.get("health", {})
        # Ages and durations change at every poll; the watchdog's incident key
        # represents causes, so an unchanged outage does not notify repeatedly.
        key = hashlib.sha256(
            json.dumps(
                [
                    record["execution_ok"],
                    record["ok"],
                    health.get("verdict"),
                    health.get("incident_key") if health else sorted(issues),
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        record.update(issues=issues, notification_key=key, notified=False)
        if issues and key != previous.get("notification_key"):
            print(
                f"{'ALARM' if not record['ok'] else 'CHANGE'} EIDOS {record['kind']}: "
                + "; ".join(issues),
                flush=True,
            )
            record["notified"] = True
        elif not issues and previous.get("issues"):
            print(f"RECOVERED EIDOS {record['kind']}", flush=True)
            record["notified"] = True
        atomic_json(path, record)


if __name__ == "__main__":
    raise SystemExit(main())
