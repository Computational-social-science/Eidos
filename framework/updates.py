"""Dependency versions: sense them, try them in isolation, promote or roll back.

The design separates three things that are usually tangled:

* **sensing** never touches the lock. It asks PyPI and GitHub what exists and writes an event
  when the answer differs from what is pinned.
* **trying** never touches the production environment. It builds a throwaway environment at the
  candidate version, runs a probe, and stores the result with the artifact hash.
* **promoting** requires a passing try for that exact version, recorded within the last
  ``TRY_TTL`` seconds. A version cannot be promoted because it looks fine.

Everything the framework runs is pinned in ``lock/versions.lock.json``, which is the single
source of truth: the lock names a version and, for artifacts, a sha256. The history in that file
is what rollback restores.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "lock" / "versions.lock.json"
SENSE = ROOT / "docs" / "status" / "updates.json"
EVENTS = ROOT / "docs" / "status" / "updates.jsonl"
TRIES = ROOT / "docs" / "status" / "update_tries"

TRY_TTL = 7 * 24 * 3600          # a passing try is evidence for a week, not forever
HTTP_TIMEOUT = 8

#: What each dependency is and where its truth lives. ``kind`` decides how a candidate is tried.
SOURCES: dict[str, dict] = {
    "quarto": {"kind": "binary", "repo": "quarto-dev/quarto-cli", "cmd": ["quarto", "--version"],
               "env": ["QUARTO_BIN"], "paths": ["../tools/quarto/bin/quarto.exe"]},
    "dvc": {"kind": "pypi", "packages": ["dvc"]},
    # The distribution is mlflow-skinny on this host, the import name is mlflow.
    "mlflow": {"kind": "pypi", "packages": ["mlflow", "mlflow-skinny"]},
    "llama.cpp": {"kind": "binary", "repo": "ggml-org/llama.cpp", "tag_pattern": r"^b(\d+)$",
                  "cmd": ["llama-server", "--version"],
                  "globs": ["$LOCALAPPDATA/hermes/tools/llamacpp-cuda-*/llama-server.exe"]},
    "decision_model": {"kind": "artifact", "repo": None,
                       "path": "../decision-service/models"},
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- lock

def load_lock() -> dict:
    if not LOCK.is_file():
        return {"pins": {}, "history": []}
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    data.setdefault("pins", {})
    data.setdefault("history", [])
    return data


def save_lock(data: dict) -> None:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pinned(name: str) -> dict:
    return (load_lock()["pins"].get(name) or {})


# --------------------------------------------------------------------------- observe

def resolve(spec: dict) -> Path | None:
    """Find a binary without hard-coding this machine: env var, repo-relative path, glob."""
    name = spec["cmd"][0]
    for key in spec.get("env", []):
        value = os.environ.get(key)
        if not value:
            continue
        path = Path(value)
        for candidate in (path, path / f"{name}.exe", path / name):
            if candidate.is_file():
                return candidate
    for rel in spec.get("paths", []):
        path = (ROOT / rel)
        if path.is_file():
            return path
    for pattern in spec.get("globs", []):
        # Longest key first: "$APPDATA" is a substring of "$LOCALAPPDATA", and replacing the
        # short one first corrupts the long one.
        for key in sorted(os.environ, key=len, reverse=True):
            pattern = pattern.replace(f"${{{key}}}", os.environ[key])
            pattern = pattern.replace(f"${key}", os.environ[key])
            pattern = pattern.replace(f"%{key}%", os.environ[key])
        # Glob from the first wildcard segment: Path("a/*/b.exe").parent is literally "a/*".
        parts = Path(pattern).parts
        cut = next((i for i, chunk in enumerate(parts) if "*" in chunk), None)
        if cut is not None:
            base = Path(*parts[:cut]) if cut else Path(".")
            hits = sorted(base.glob(str(Path(*parts[cut:]))))
            if hits:
                return hits[-1]
    found = shutil.which(name)
    return Path(found) if found else None


def installed(name: str) -> dict:
    """What this host actually runs, measured rather than assumed."""
    spec = SOURCES.get(name) or {}
    if spec.get("kind") == "pypi":
        from importlib.metadata import version
        for package in spec.get("packages", [spec.get("package")]):
            try:
                return {"version": version(package), "how": f"metadata:{package}"}
            except Exception:                                      # noqa: BLE001
                continue
        return {"version": None, "how": "not installed"}
    if spec.get("kind") == "binary":
        exe = resolve(spec)
        if not exe:
            return {"version": None, "how": "not on PATH"}
        try:
            out = subprocess.run([str(exe)] + list(spec["cmd"][1:]),
                                 capture_output=True, text=True, timeout=20)
            text = (out.stdout or out.stderr).strip()
            if name == "llama.cpp":
                # Upstream tags builds (b11671); report the build, not the dev version line.
                match = __import__("re").search(r"build (\d+)", text)
                version = f"b{match.group(1)}" if match else text.splitlines()[0] if text else None
            else:
                version = text.splitlines()[0] if text else None
            return {"version": version, "how": str(exe)}
        except (OSError, subprocess.SubprocessError) as exc:
            return {"version": None, "how": f"error: {type(exc).__name__}"}
    if spec.get("kind") == "artifact":
        path = (ROOT / spec["path"]).resolve()
        if not path.is_dir():
            return {"version": None, "how": f"missing: {path}"}
        gguf = sorted(path.glob("**/*.gguf"))
        return {"version": gguf[0].name if gguf else None,
                "sha256": sha256(gguf[0]) if gguf else None,
                "how": str(path)}
    return {"version": None, "how": "unknown source"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- sense

def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "eidos-update-sensor"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def latest(name: str, fetch=None) -> dict:
    """The newest version the upstream offers, or a reason why it could not be asked."""
    spec = SOURCES.get(name) or {}
    fetch = fetch or _get_json
    try:
        if spec.get("kind") == "pypi":
            package = spec.get("package") or (spec.get("packages") or [None])[0]
            data = fetch(f"https://pypi.org/pypi/{package}/json")
            return {"version": data["info"]["version"], "source": "pypi"}
        if spec.get("repo") and spec.get("tag_pattern"):
            # llama.cpp tags builds (b11876) but marks a different release as "latest" (v0.7.0),
            # so the newest *build* has to be found by filtering the list.
            import re
            pattern = re.compile(spec["tag_pattern"])
            data = fetch(f"https://api.github.com/repos/{spec['repo']}/releases?per_page=30")
            tags = [str(row.get("tag_name") or "") for row in data]
            builds = [(int(m.group(1)), tag) for tag in tags
                      if (m := pattern.match(tag))]
            best = max(builds) if builds else None
            return {"version": best[1] if best else None, "source": "github"}
        if spec.get("repo"):
            data = fetch(f"https://api.github.com/repos/{spec['repo']}/releases/latest")
            tag = str(data.get("tag_name") or "").lstrip("v")
            return {"version": tag or None, "source": "github"}
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        return {"version": None, "source": "unreachable", "error": f"{type(exc).__name__}"}
    return {"version": None, "source": "no upstream configured"}


def sense(fetch=None, offline: bool = False) -> dict:
    """Ask every source; write the answer. Never changes a pin."""
    report = {"ts": _now(), "offline": offline, "items": {}}
    for name in SOURCES:
        have = installed(name)
        pin = pinned(name).get("version")
        if offline:
            offer = {"version": None, "source": "offline"}
        else:
            offer = latest(name, fetch=fetch)
        state = "current"
        if offer.get("version") and pin and _different(offer["version"], pin):
            order = _compare(offer["version"], pin)
            state = "behind" if order > 0 else "ahead" if order < 0 else "behind"
        elif offer.get("version") is None:
            state = "unknown"
        report["items"][name] = {"pinned": pin, "installed": have.get("version"),
                                 "available": offer.get("version"), "state": state,
                                 "source": offer.get("source"),
                                 "note": offer.get("error") or have.get("how")}
    SENSE.parent.mkdir(parents=True, exist_ok=True)
    SENSE.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    behind = [n for n, item in report["items"].items() if item["state"] == "behind"]
    if behind:
        _event({"kind": "sense", "behind": behind,
                "detail": {n: report["items"][n]["available"] for n in behind}})
    return report


def _compare(a: str, b: str) -> int:
    """-1 if a < b, 0 if equal, 1 if a > b, comparing the numbers inside the strings."""
    import re
    na = [int(x) for x in re.findall(r"\d+", str(a))]
    nb = [int(x) for x in re.findall(r"\d+", str(b))]
    return (na > nb) - (na < nb)


def _different(a: str, b: str) -> bool:
    return str(a).strip().lstrip("v") != str(b).strip().lstrip("v")


def _event(row: dict) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), **row}
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- try

PROBES = {
    "dvc": """
import json, subprocess, sys
out = subprocess.run([sys.executable, "-m", "dvc", "version"], capture_output=True, text=True)
print(json.dumps({"ok": out.returncode == 0 and "DVC version" in out.stdout,
                  "version": out.stdout.splitlines()[0] if out.stdout else None}))
""",
    "mlflow": """
import json, tempfile, os
import mlflow
store = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
mlflow.set_tracking_uri(store)
with mlflow.start_run():
    mlflow.log_metric("probe", 0.5)
runs = mlflow.search_runs(experiment_ids=["0"])
print(json.dumps({"ok": float(runs.iloc[0]["metrics.probe"]) == 0.5,
                  "version": mlflow.__version__}))
""",
}

QUARTO_FIXTURE = """---
title: probe
---

```{python}
print(1 + 1)
```
"""


def try_candidate(name: str, version: str, artifact: Path | None = None,
                  python: str | None = None, timeout: int = 900) -> dict:
    """Install the candidate somewhere disposable, run its probe, record the verdict."""
    spec = SOURCES.get(name)
    if not spec:
        raise KeyError(f"unknown dependency: {name}")
    record = {"ts": _now(), "name": name, "version": version, "kind": spec["kind"],
              "ok": False, "detail": {}}
    TRIES.mkdir(parents=True, exist_ok=True)
    work = TRIES / f"{name}-{version}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    try:
        if spec["kind"] == "pypi":
            record["detail"] = _try_pypi(name, version, work, python or sys.executable, timeout)
        elif spec["kind"] == "binary" and name == "quarto":
            record["detail"] = _try_quarto(version, artifact, work, timeout)
        elif spec["kind"] == "binary":
            record["detail"] = _try_binary(spec, artifact, timeout)
        else:
            record["detail"] = {"ok": False, "reason": "artifacts are tried by hash, not installed"}
        record["ok"] = bool(record["detail"].get("ok"))
    except (OSError, subprocess.SubprocessError, KeyError) as exc:
        record["detail"] = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    record["ts"] = _now()
    (TRIES / f"{name}-{version}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _event({"kind": "try", "name": name, "version": version, "ok": record["ok"],
            "detail": record["detail"]})
    return record


def _distribution(name: str) -> str:
    spec = SOURCES[name]
    return spec.get("package") or (spec.get("packages") or [name])[0]


def _try_pypi(name: str, version: str, work: Path, python: str, timeout: int) -> dict:
    env = work / "venv"
    steps = [["uv", "venv", "--python", python, str(env)],
             ["uv", "pip", "install", "--python", str(env / "Scripts" / "python.exe"),
              f"{_distribution(name)}=={version}"]]
    for cmd in steps:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if done.returncode != 0:
            return {"ok": False, "reason": f"{cmd[0]} failed",
                    "stderr": (done.stderr or done.stdout)[-400:]}
    probe = work / "probe.py"
    probe.write_text(PROBES[name], encoding="utf-8")
    run = subprocess.run([str(env / "Scripts" / "python.exe"), str(probe)],
                         capture_output=True, text=True, timeout=timeout)
    try:
        result = json.loads(run.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"ok": False, "reason": "probe produced no verdict",
                "stdout": run.stdout[-300:], "stderr": run.stderr[-300:]}
    result["isolated_at"] = str(env)
    return result


def _try_quarto(version: str, artifact: Path | None, work: Path, timeout: int) -> dict:
    if not artifact or not Path(artifact).is_file():
        return {"ok": False, "reason": "no candidate binary given (--artifact)"}
    exe = Path(artifact)
    got = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=timeout)
    text = (got.stdout or "").strip()
    if version not in text:
        return {"ok": False, "reason": f"binary reports {text!r}, expected {version}"}
    doc = work / "probe.qmd"
    doc.write_text(QUARTO_FIXTURE, encoding="utf-8")
    out = work / "probe.html"
    run = subprocess.run([str(exe), "render", str(doc), "--to", "html", "--output", str(out)],
                         capture_output=True, text=True, timeout=timeout, cwd=str(work))
    ok = run.returncode == 0 and out.is_file() and out.stat().st_size > 0
    return {"ok": ok, "version": text, "bytes": out.stat().st_size if out.is_file() else 0,
            "stderr": (run.stderr or "")[-300:]}


def _try_binary(spec: dict, artifact: Path | None, timeout: int) -> dict:
    if not artifact or not Path(artifact).is_file():
        return {"ok": False, "reason": "no candidate binary given (--artifact)"}
    run = subprocess.run([str(artifact), "--version"], capture_output=True, text=True,
                         timeout=timeout)
    return {"ok": run.returncode == 0, "version": (run.stdout or "").strip().splitlines()[:1]}


# --------------------------------------------------------------------------- promote

def passing_try(name: str, version: str, ttl: int = TRY_TTL) -> dict | None:
    path = TRIES / f"{name}-{version}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if not record.get("ok"):
        return None
    try:
        age = time.time() - datetime.datetime.fromisoformat(record["ts"]).timestamp()
    except (KeyError, ValueError):
        return None
    return record if age <= ttl else None


def promote(name: str, version: str, note: str = "", allow_downgrade: bool = False) -> dict:
    """Move a pin forward. Refuses without a passing try, and refuses to move backwards.

    A try only says the candidate works; it says nothing about whether the candidate is newer.
    Without the direction check, a passing try of an older version is enough to roll production
    backwards — which is what happened on 2026-10-25 while demonstrating the loop.
    """
    if name not in SOURCES:
        raise KeyError(f"unknown dependency: {name}")
    current = (load_lock()["pins"].get(name) or {}).get("version")
    if current and _compare(version, current) < 0 and not allow_downgrade:
        raise PermissionError(
            f"{name} {version} is older than the pinned {current}; "
            "pass allow_downgrade=True (CLI: --allow-downgrade --note <why>) if that is intended")
    evidence = passing_try(name, version)
    if evidence is None:
        raise PermissionError(
            f"no passing try for {name} {version}: run `update_operator.py try {name} {version}`")
    lock = load_lock()
    previous = lock["pins"].get(name)
    lock["history"].append({"ts": _now(), "name": name, "from": previous, "to": version,
                            "why": note or "promoted after a passing try"})
    lock["pins"][name] = {"version": version, "sha256": (previous or {}).get("sha256"),
                          "pinned_at": _now(),
                          "evidence": str(TRIES / f"{name}-{version}.json")}
    save_lock(lock)
    _refresh_pinned(name, version)
    _event({"kind": "promote", "name": name, "from": (previous or {}).get("version"),
            "to": version})
    return lock["pins"][name]


def rollback(name: str) -> dict:
    """Restore the pin this dependency had before its last promotion."""
    lock = load_lock()
    prior = [h for h in lock["history"] if h["name"] == name]
    if not prior:
        raise LookupError(f"no history for {name}")
    last = prior[-1]
    lock["pins"][name] = last["from"] or {}
    lock["history"].append({"ts": _now(), "name": name, "from": {"version": last["to"]},
                            "to": (last["from"] or {}).get("version"), "why": "rollback"})
    save_lock(lock)
    _refresh_pinned(name, (last["from"] or {}).get("version"))
    _event({"kind": "rollback", "name": name, "to": (last["from"] or {}).get("version")})
    return lock["pins"][name]


def _refresh_pinned(name: str, version: str | None) -> None:
    """Keep the sense report consistent with the lock, so the page cannot show a stale pin."""
    if not SENSE.is_file() or version is None:
        return
    try:
        data = json.loads(SENSE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    (data.setdefault("items", {}).setdefault(name, {}))["pinned"] = version
    SENSE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")


def report() -> dict:
    """The latest sense, refreshed with what this host runs now."""
    data = {}
    if SENSE.is_file():
        data = json.loads(SENSE.read_text(encoding="utf-8"))
    items = data.get("items") or {}
    for name in SOURCES:
        item = items.setdefault(name, {})
        item["pinned"] = pinned(name).get("version")
        item["installed"] = installed(name).get("version")
        if item.get("state") is None:
            item["state"] = "unknown"
    return {"ts": data.get("ts"), "items": items}
