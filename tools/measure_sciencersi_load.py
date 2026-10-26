"""Load ScienceRSI-8b on the GPU and record what it costs.

Plan §5 asks for a measured footprint and a latency figure, not the model card's estimate. This
script loads the file with the plan's flags, samples `nvidia-smi` every half second, and writes the
measurement to `artifacts/evaluation/sciencersi_load.json`. The server it starts is left
running for the latency pass, and its PID is written down so it can be stopped deliberately.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "evaluation" / "sciencersi_load.json"
BIN = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "tools" / \
    "llamacpp-cuda-11146-win32-x64" / "llama-server.exe"
MODEL = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "models" / \
    "ScienceRSI-8b.i1-Q4_K_M.gguf"


def vram_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip().splitlines()[0]
    return int(out.replace("MiB", "").strip())


def main() -> int:
    log = ROOT / "artifacts" / "evaluation" / "sciencersi_serve.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    before = vram_mib()
    t0 = time.time()
    proc = subprocess.Popen(
        [str(BIN), "-m", str(MODEL), "-ngl", "99", "-c", "28672", "--port", "8081",
         "--host", "127.0.0.1", "--jinja", "--no-webui", "--metrics"],
        stdout=log.open("wb"), stderr=subprocess.STDOUT)
    peak = before
    ready = None
    while time.time() - t0 < 300:
        if proc.poll() is not None:
            print(json.dumps({"error": f"server exited {proc.returncode}", "log": str(log)}))
            return 1
        peak = max(peak, vram_mib())
        try:
            urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=2).read()
            ready = time.time() - t0
            break
        except Exception:
            time.sleep(0.5)
    if ready is None:
        proc.terminate()
        print(json.dumps({"error": "not healthy within 300 s", "peak_mib": peak}))
        return 1
    resident = vram_mib()
    record = {"pid": proc.pid, "model": MODEL.name, "quant": "q4_k_m", "ctx": 28672, "ngl": 99,
              "load_s": round(ready, 2), "vram_before_mib": before, "peak_mib": peak,
              "resident_mib": resident,
              "weights_gb": round((MODEL.stat().st_size) / 1e9, 2),
              "kv_gb": round((resident - before) / 1024 - (MODEL.stat().st_size / 1e9), 2)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
