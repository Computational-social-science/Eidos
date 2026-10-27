"""Swap the model on the Hermes llama.cpp router, and prove which one is resident.

Every hand-made swap this project has done went wrong the same way: the launcher was killed, the
llama-server child kept the port, and the next service silently talked to the wrong weights (StartLux
prompts into ScienceRSI, answered with `Prompt contains invalid tokens`). The router has an API for
this, so the procedure belongs in code:

    GET  /models                      what is resident
    POST /models/unload {"model": …}  release it
    POST /v1/chat/completions         autoloads the requested model (router mode)
    GET  /v1/models                   confirm the path that actually loaded

The budget check comes from the registry and the last measurement, not from optimism: ScienceRSI at
28672 costs 8.6 GB, at 16384 about 7.0 GB (docs/MODEL_SMOKE.md).

Usage:
    python tools/serve_model.py swap --model ScienceRSI-8b.i1-Q4_K_M --dry-run
    python tools/serve_model.py swap --model StartLux-Decision-4B-Q8_0
    python tools/serve_model.py status
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = os.environ.get("HERMES_LOCAL_LLAMACPP_URL", "http://127.0.0.1:18434")
KEY = os.environ.get("HERMES_LOCAL_LLAMACPP_KEY", "")


def plan(loaded: str | None, target: str, used_gb: float, footprint_gb: float,
         budget_gb: float) -> tuple[str, str]:
    """Decide before touching anything. Pure, so the decision can be tested without a GPU."""
    if loaded == target:
        return "noop", f"{target} is already resident"
    if used_gb + footprint_gb > budget_gb and loaded:
        return "refuse", (f"{target} needs {footprint_gb:.1f} GB, the card has "
                          f"{budget_gb - used_gb:.1f} GB free with {loaded} resident "
                          f"({used_gb:.1f} GB used); unload it first")
    if used_gb + footprint_gb > budget_gb:
        return "refuse", (f"{target} needs {footprint_gb:.1f} GB, only "
                          f"{budget_gb - used_gb:.1f} GB is free")
    return "swap", f"{target} fits: {used_gb:.1f} + {footprint_gb:.1f} <= {budget_gb:.1f} GB"


def _request(method: str, path: str, body: dict | None = None, timeout: float = 30.0):
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def resident() -> tuple[str | None, dict]:
    """The loaded model and its record, or (None, {})."""
    for entry in _request("GET", "/v1/models").get("data", []):
        status = (entry.get("status") or {}).get("value")
        if status == "loaded":
            return entry.get("id"), entry
    return None, {}


def vram_used_gb() -> float:
    import subprocess
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip().splitlines()[0]
    return int(out.replace("MiB", "").strip()) / 1024


def footprint(name: str) -> float:
    """Registry footprint, tolerating the router's dotted id versus the registry's hyphenated key."""
    from framework.inference import ModelManager
    registry = ModelManager.MODEL_REGISTRY
    for candidate in (name, name.replace(".", "-"), name.replace("-", ".")):
        spec = registry.get(candidate)
        if spec:
            return spec.vram_gb
    sq = lambda text: "".join(ch for ch in text.lower() if ch.isalnum())      # noqa: E731
    for key, spec in registry.items():
        if sq(key) == sq(name):
            return spec.vram_gb
    return 7.0


def swap(target: str, budget: float, dry_run: bool) -> int:
    loaded_id, _ = resident()
    used = vram_used_gb()
    wanted = footprint(target)
    action, why = plan(loaded_id, target, used, wanted, budget)
    print(f"resident: {loaded_id or 'none'} | used {used:.1f} GB | {action}: {why}")
    if action in ("noop", "refuse"):
        return 0 if action == "noop" else 2
    if dry_run:
        return 0

    if loaded_id:
        _request("POST", "/models/unload", {"model": loaded_id})
        print(f"unloaded {loaded_id}")
        time.sleep(2)

    started = time.time()
    _request("POST", "/v1/chat/completions", {
        "model": target, "max_tokens": 1, "temperature": 0,
        "messages": [{"role": "user", "content": "ok"}]}, timeout=300)
    loaded_s = time.time() - started

    now_id, record = resident()
    path = str(record.get("model") or "")
    print(f"loaded {now_id} in {loaded_s:.1f}s from {path or 'unknown path'}")
    if now_id != target:
        print(f"REFUSED: asked for {target}, router reports {now_id}", file=sys.stderr)
        return 2
    print(f"identity confirmed: {Path(path).name if path else now_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    s = sub.add_parser("swap", help="make one model resident")
    s.add_argument("--model", required=True)
    s.add_argument("--budget", type=float, default=10.5)
    s.add_argument("--dry-run", action="store_true")
    sub.add_parser("status", help="what is resident")
    args = ap.parse_args(argv)

    if args.action == "status":
        loaded_id, record = resident()
        print(json.dumps({"resident": loaded_id, "path": record.get("model"),
                          "used_gb": round(vram_used_gb(), 1)}, indent=2))
        return 0
    return swap(args.model, args.budget, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
