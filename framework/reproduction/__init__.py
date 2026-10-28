"""Paper2Agent deliveries are toolboxes, and a toolbox is not evidence.

Paper2Agent (MIT, Nature 2026) converts a paper and its code into an MCP server plus a paper skill.
Its value to this framework is narrow and specific: it can produce an **independent execution** of a
published method, which is the only thing that can turn "the paper reports 0.927" into "we ran it and
got 0.927". Everything else about it — the prose, the tutorials, the tools — helps do work and proves
nothing.

So this module does not wrap the engine. It consumes a delivery under contract:

* `check_delivery()` refuses an incomplete tree. A conversion that did not produce a skill and an MCP
  entry point is not a delivery, and registering it would be the same defect as citing a paper we
  never read.
* `run_spec()` executes one reproduction spec — a command, the statistic it should produce, and a
  tolerance — and records observed versus expected.
* the record is what Gate S reads. A claim that cites a reproduced method without a `MATCH` record is
  blocked, not passed.

Nothing here trusts the agent's own report of success. The number is compared, or the verdict is
`UNRUN`.
"""

from __future__ import annotations

import datetime
import json
import shlex
import subprocess
from pathlib import Path

MATCH = "MATCH"
MISMATCH = "MISMATCH"
UNRUN = "UNRUN"

#: What a Paper2Agent delivery must contain to be registrable. The combined output contract is
#: `dist/<project>-agent/{skill/<paper>/, mcp/<repo>-mcp/}`; single-mode runs keep one of them.
REQUIRED_SKILL = ("SKILL.md",)
REQUIRED_MCP = ("USAGE.md",)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def check_delivery(root: str | Path) -> dict:
    """Validate a delivery tree. Returns findings; an empty `problems` list means registrable."""
    root = Path(root)
    problems: list[str] = []
    if not root.is_dir():
        return {"root": str(root), "problems": [f"{root} is not a directory"], "ok": False}

    skill = next((p for p in root.rglob("SKILL.md")), None)
    usage = next((p for p in root.rglob("USAGE.md")), None)
    if skill is None:
        problems.append("no SKILL.md: the paper skill is missing")
    if usage is None:
        problems.append("no USAGE.md: the MCP server has no delivery instructions, so it cannot be run")

    # A delivery that carries a test/verification report is easier to trust, but its absence is not a
    # refusal: the check that matters is running the thing, which `run_spec` does.
    reports = [p.name for p in root.rglob("*") if p.is_file()
               and p.suffix.lower() in (".json", ".md") and "verif" in p.name.lower()]
    return {"root": str(root), "skill": str(skill) if skill else None,
            "usage": str(usage) if usage else None, "reports": reports[:5],
            "problems": problems, "ok": not problems}


def compare(expected: float, observed: float, tolerance: float = 1e-3,
            relative: bool = False) -> tuple[str, float]:
    """The verdict and the realised error. Relative tolerance is opt-in, not the default."""
    delta = abs(float(observed) - float(expected))
    limit = abs(float(expected)) * tolerance if relative else float(tolerance)
    return (MATCH if delta <= limit else MISMATCH), delta


def run_spec(spec: dict, cwd: str | Path | None = None, timeout: float = 900.0) -> dict:
    """Execute one reproduction spec and compare what came back.

    `spec` fields: `paper`, `command` (string or list), optional `cwd`, `expected`, `tolerance`,
    `relative`, and `json_path` (dotted path into the JSON the command prints, default `value`).
    """
    command = spec.get("command")
    if isinstance(command, str):
        command = shlex.split(command)
    if not command:
        raise ValueError("spec has no command")

    try:
        completed = subprocess.run(command, cwd=str(cwd or spec.get("cwd") or Path.cwd()),
                                   capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"paper": spec.get("paper"), "verdict": UNRUN, "reason": str(exc), "ts": _now()}

    if completed.returncode != 0:
        return {"paper": spec.get("paper"), "verdict": UNRUN,
                "reason": f"command exited {completed.returncode}: {completed.stderr.strip()[:300]}",
                "ts": _now()}

    # Pretty-printed JSON ends with "}", so parsing the last line alone rejects valid output. Try the
    # whole stream first, then the last line for tools that log before printing.
    text = completed.stdout.strip()
    payload = None
    for candidate in (text, text.splitlines()[-1] if text else ""):
        try:
            payload = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if payload is None:
        return {"paper": spec.get("paper"), "verdict": UNRUN,
                "reason": f"output is not JSON: {text[:120]!r}", "ts": _now()}

    node = payload
    for part in str(spec.get("json_path") or "value").split("."):
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
            continue
        if not isinstance(node, dict) or part not in node:
            return {"paper": spec.get("paper"), "verdict": UNRUN,
                    "reason": f"output has no {spec.get('json_path') or 'value'}", "ts": _now()}
        node = node[part]

    verdict, delta = compare(spec["expected"], node, spec.get("tolerance", 1e-3),
                             bool(spec.get("relative", False)))
    return {"paper": spec.get("paper"), "tool": spec.get("tool"), "command": command,
            "expected": spec["expected"], "observed": node, "delta": delta,
            "tolerance": spec.get("tolerance", 1e-3), "relative": bool(spec.get("relative", False)),
            "verdict": verdict, "ts": _now()}


def write(record: dict, out_dir: str | Path) -> Path:
    paper = str(record.get("paper") or "unknown")
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in paper)
    path = Path(out_dir) / f"{safe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load(paper: str, out_dir: str | Path) -> dict | None:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in paper)
    path = Path(out_dir) / f"{safe}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def run_set(bundle: dict, cwd: str | Path | None = None) -> dict:
    """Run every spec for one paper. The verdict is MATCH only when all of them match.

    A paper is rarely one number: a table of gradients, a loss, a diagnostic baseline. Taking the best
    of them would be a new kind of p-hacking, so the set is judged as a set.
    """
    paper = bundle.get("paper")
    specs = bundle.get("specs") or []
    if not specs:
        raise ValueError("bundle has no specs")
    records = [run_spec({**spec, "paper": paper}, cwd=cwd) for spec in specs]
    verdicts = [r["verdict"] for r in records]
    if all(v == MATCH for v in verdicts):
        verdict = MATCH
    elif any(v == MISMATCH for v in verdicts):
        verdict = MISMATCH
    else:
        verdict = UNRUN
    return {"paper": paper, "verdict": verdict, "specs": records,
            "counts": {v: verdicts.count(v) for v in set(verdicts)}, "ts": _now()}
