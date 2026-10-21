#!/usr/bin/env python
"""Snapshot the external contracts this framework depends on.

WHY THIS EXISTS
    The coupling audit showed where the real coupling is: not between Python modules, but
    at six boundaries -- BootLoops, Quarto, DVC, MLflow, the decision service and the local
    model runtimes. `audit_chains` exercises those boundaries functionally, once; it does
    not notice that a tool's version changed underneath it. This records what each boundary
    is, so a change is visible instead of silent.

WHAT IT WRITES
    `artifacts/contracts.json`: for each boundary, the kind of contract, whether it
    answered, and its identity (version string, model id, path).

MODES
    default   write the snapshot and report drift against the previous one.
    --check   do not write; exit 1 if a boundary that answered last time is now missing
              (a regression), 0 otherwise. Drift is reported but is not a failure -- a
              new Quarto version is news, not a broken build.

MISSING IS NOT FAILURE
    Absent tools are SKIP, matching the gate semantics: an optional tool that is not
    installed has not failed, it has not run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts" / "contracts.json"


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
        text = (proc.stdout or proc.stderr).strip()
        return proc.returncode, (text.splitlines()[0] if text else "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def _http(url: str, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - a probe must not raise
        return None


def _tcp(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def probe_quarto() -> dict:
    env = os.environ.get("QUARTO_BIN")
    candidates = [env] if env else []
    candidates += [shutil.which("quarto"),
                   str(Path.home() / ".workbuddy-ai" / "binaries" / "quarto" / "bin" / "quarto.exe"),
                   r"C:\Program Files\Quarto\bin\quarto.exe"]
    for path in candidates:
        if path and Path(path).is_file():
            rc, out = _run([path, "--version"])
            if rc == 0:
                return {"ok": True, "version": out, "path": path}
    return {"ok": False, "reason": "quarto not found"}


def probe_dvc() -> dict:
    rc, out = _run([sys.executable, "-m", "dvc", "version"])
    return {"ok": rc == 0, "version": out.splitlines()[0] if out else "",
            "reason": "" if rc == 0 else out[:120]}


def probe_mlflow() -> dict:
    rc, out = _run([sys.executable, "-c", "import mlflow; print(mlflow.__version__)"])
    return {"ok": rc == 0, "version": out, "reason": "" if rc == 0 else out[:120]}


def probe_decision(url: str = "http://127.0.0.1:8090") -> dict:
    health = _http(url + "/health")
    if not health:
        return {"ok": False, "reason": f"no /health at {url}"}
    # "answer_kind" not "kind": the static contract type must not change when the service
    # is down, or the diff reports a spurious kind drift on every outage.
    return {"ok": True, "model": health.get("model"),
            "answer_kind": health.get("kind"),
            "engine": (health.get("engine") or {}).get("name")}


def probe_bootloops() -> dict:
    cfg = Path.home() / ".bootloops" / "config.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "reason": "~/.bootloops/config.json unreadable"}
    root = data.get("bootloops_root") or data.get("root")
    if not root or not Path(root).is_dir():
        return {"ok": False, "reason": f"root missing: {root!r}"}
    return {"ok": True, "root": root,
            "has_activate": (Path(root) / "activate.sh").is_file()}


def probe_runtimes() -> dict:
    out = {}
    ollama = _http("http://127.0.0.1:11434/api/tags")
    out["ollama"] = {"ok": ollama is not None,
                     "models": len((ollama or {}).get("models", [])) if ollama else 0}
    out["llamacpp_18434"] = {"ok": _tcp(18434), "note": "TCP reachability only (API needs a key)"}
    out["llamacpp_8081"] = {"ok": _tcp(8081)}
    out["ok"] = all(v.get("ok") for v in out.values())
    if not out["ok"]:
        out["reason"] = ", ".join(k for k, v in out.items()
                                  if k not in ("kind", "ok", "reason") and not v.get("ok"))
    return out


def collect() -> dict:
    return {
        "quarto": {"kind": "CLI", **probe_quarto()},
        "dvc": {"kind": "CLI", **probe_dvc()},
        "mlflow": {"kind": "library", **probe_mlflow()},
        "decision": {"kind": "HTTP", **probe_decision()},
        "bootloops": {"kind": "toolkit", **probe_bootloops()},
        "runtimes": {"kind": "HTTP/TCP", **probe_runtimes()},
    }


def diff(old: dict, new: dict) -> list[str]:
    findings = []
    for name, entry in new.items():
        before = old.get(name)
        if not before:
            findings.append(f"{name}: new boundary")
            continue
        if before.get("ok") and not entry.get("ok"):
            findings.append(f"{name}: was answering, now missing ({entry.get('reason', '')})")
        for key in ("version", "model", "kind", "root"):
            if key in entry and key in before and entry[key] != before[key]:
                findings.append(f"{name}.{key}: {before[key]!r} -> {entry[key]!r}")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="compare only; exit 1 on regression")
    ap.add_argument("--allow-missing", action="store_true",
                    help="report missing boundaries but do not fail (a CI host has none installed)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    new = collect()
    old = {}
    if SNAPSHOT.is_file():
        try:
            old = json.loads(SNAPSHOT.read_text(encoding="utf-8")).get("boundaries", {})
        except ValueError:
            old = {}
    findings_all = diff(old, new)
    regressions = [f for f in findings_all if "now missing" in f]
    # A boundary that stopped answering is one fact, not two: keep it out of the drift list
    # so the watchdog does not print the same outage twice.
    findings = [f for f in findings_all if f not in regressions]

    if not args.check:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps({"boundaries": new}, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps({"boundaries": new, "findings": findings,
                          "regressions": regressions}, indent=2))
        # Machine-readable mode must emit ONE document and nothing else: a trailing
        # human-readable line made json.loads fail in the cron watchdog.
        return 1 if (regressions and not args.allow_missing) else 0
    else:
        for name, entry in new.items():
            state = "OK     " if entry.get("ok") else "MISSING"
            detail = entry.get("version") or entry.get("model") or entry.get("root") or entry.get("reason") or ""
            if name == "runtimes":
                detail = ", ".join(f"{k}={'up' if v.get('ok') else 'down'}"
                                   for k, v in entry.items() if k not in ("kind", "ok"))
            print(f"{state} {name:<10} {detail}")
        for f in findings:
            print(f"DRIFT  {f}")
        if not findings:
            print("no drift against the previous snapshot")

    if regressions and not args.allow_missing:
        print(f"\nFAIL  {len(regressions)} boundary(ies) stopped answering", file=sys.stderr)
        return 1
    if regressions:
        print(f"\nWARN  {len(regressions)} boundary(ies) missing (allowed here)", file=sys.stderr)
        return 0
    print("\nPASS  contracts recorded" if not args.check else "\nPASS  no regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
