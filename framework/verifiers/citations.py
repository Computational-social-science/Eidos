"""Citation identity and retraction, before a claim is allowed to exist.

`proofpath` answers one question per reference: does this exist, and has it been retracted. It does
not ask whether the source *supports* the sentence — that is Step 3 (Callimachus), and the plan
keeps them apart so two tools never judge the same sentence.

Fail closed. A reference that cannot be resolved, that resolves to a retracted work, or whose
provider was unreachable, is `BLOCKED`: a claim may not cite it. The distinction between
"unresolved" and "provider was down" is kept in the record because they need different actions —
one is a bad citation, the other is a retry.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTEFACT = ROOT / "artifacts" / "literature" / "proofpath.json"
CACHE = ROOT / "artifacts" / "literature" / "cache" / "resolve.json"

VERIFIED = "VERIFIED"
BLOCKED = "BLOCKED"
UNAVAILABLE = "SOURCE_UNAVAILABLE"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _binary() -> str | None:
    found = shutil.which("proofpath")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / ("proofpath.exe" if os.name == "nt" else "proofpath")
    return str(local) if local.is_file() else None


def classify(payload: dict) -> dict:
    """Map proofpath's answer onto the three states a claim may point at."""
    result = (payload or {}).get("result") or {}
    state = str(result.get("state") or "")
    retraction = payload.get("retraction")
    best = result.get("best") or {}
    notes = result.get("notes") or []

    if retraction:
        return {"status": BLOCKED, "reason": "retracted",
                "retraction": retraction, "doi": best.get("doi"),
                "title": best.get("title"), "notes": notes}
    if state.startswith("RESOLVED"):
        return {"status": VERIFIED, "reason": None, "doi": best.get("doi"),
                "title": best.get("title"), "match": result.get("match"), "notes": notes}
    if state.startswith("UNVERIFIED"):
        # The provider was unreachable or rate-limited: retry later, do not call it a bad citation.
        return {"status": UNAVAILABLE, "reason": "provider unavailable",
                "detail": state, "notes": notes}
    return {"status": BLOCKED, "reason": "unresolved", "detail": state, "notes": notes}


def resolve(reference: str, timeout: int = 120) -> dict:
    """Ask proofpath about one reference. Network; callers that need reproducibility use the cache."""
    binary = _binary()
    if not binary:
        return {"reference": reference, "status": UNAVAILABLE,
                "reason": "proofpath not installed (uv tool install git+https://github.com/Yigtwxx/proofpath)",
                "ts": _now()}
    try:
        done = subprocess.run([binary, "resolve", reference, "--format", "json"],
                              capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return {"reference": reference, "status": UNAVAILABLE,
                "reason": f"{type(exc).__name__}: {exc}", "ts": _now()}
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"reference": reference, "status": UNAVAILABLE,
                "reason": f"proofpath said {done.stdout[:120]!r} (exit {done.returncode})",
                "ts": _now()}
    record = classify(payload)
    record.update({"reference": reference, "ts": _now(), "raw": payload})
    return record


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _update_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")


def check(references: list[str], network: bool = True, cache_path: Path | None = None,
          out: Path | None = None) -> dict:
    """Resolve every reference, preferring the cache so a rerun works offline.

    The plan requires exactly this: responses cached under artifacts/literature/cache/, and reruns
    that work without the network. `network=False` is the offline mode — a reference with no cached
    answer comes back UNAVAILABLE rather than being silently accepted.
    """
    cache_file = cache_path or CACHE
    cache = _load_cache(cache_file)
    records = []
    for reference in references:
        cached = cache.get(reference)
        if cached:
            record = dict(cached, cached=True, ts=_now())
        elif network:
            record = resolve(reference)
            if record["status"] != UNAVAILABLE:
                cache[reference] = {k: v for k, v in record.items() if k != "raw"}
        else:
            record = {"reference": reference, "status": UNAVAILABLE,
                      "reason": "offline and not cached", "ts": _now()}
        records.append(record)

    if network:
        _update_cache(cache_file, cache)

    blocked = [r for r in records if r["status"] != VERIFIED]
    verdict = "PASS" if records and not blocked else "BLOCKED"
    result = {"ts": _now(), "verdict": verdict, "n": len(records),
              "verified": sum(1 for r in records if r["status"] == VERIFIED),
              "blocked": [{"reference": r["reference"], "status": r["status"],
                           "reason": r.get("reason")} for r in blocked],
              "records": records}
    target = out or ARTEFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["artefact"] = str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target)
    return result
