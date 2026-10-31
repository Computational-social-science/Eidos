"""Exact edit-rate repair; private text is never copied into output evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
SOURCES = ("run.py", "verify.py", "protocol.json", "pyproject.toml", "uv.lock")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distance(source: str, target: str) -> int:
    """Unit-cost minimum edit distance, with O(len(target)) storage."""
    previous = list(range(len(target) + 1))
    for i, left in enumerate(source, 1):
        current = [i]
        for j, right in enumerate(target, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def legacy_cost(source: str, target: str) -> int:
    """HPAF's existing opcode-cost definition, including default autojunk."""
    return sum(max(i2 - i1, j2 - j1)
               for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, source, target).get_opcodes()
               if tag != "equal")


def load_pairs(path: Path) -> list[tuple[str, str]]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, list) or not value:
        raise ValueError("corpus must be a nonempty JSON list")
    pairs = []
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ValueError(f"invalid row {index}")
        source = row.get("goal")
        target = row.get("perturbation", row.get("perturbed_text"))
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError(f"non-string or missing pair at row {index}")
        pairs.append((source, target))
    return pairs


def inputs(argv: list[str]) -> list[Path]:
    paths = [Path(item).resolve() for item in argv] if argv else [HERE / "pairs.json", HERE / "short-graph.json"]
    names = [path.name for path in paths]
    if len(set(names)) != len(names):
        raise ValueError("corpus basenames must be unique")
    return paths


def produce(paths: list[Path], output: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise FileExistsError("refusing existing output; use a fresh path: " + str(output))
    source_before = {name: digest(HERE / name) for name in SOURCES}
    before = {path.name: digest(path) for path in paths}
    records = []
    for path in paths:
        for index, (source, target) in enumerate(load_pairs(path)):
            old, repaired = legacy_cost(source, target), distance(source, target)
            records.append({"corpus": path.name, "row": index,
                            "source_length": len(source), "target_length": len(target),
                            "legacy_cost": old, "distance": repaired,
                            "legacy_rate": old / max(len(source), 1),
                            "repaired_rate": repaired / max(len(source), 1)})
    if before != {path.name: digest(path) for path in paths}:
        raise ValueError("corpus changed during execution")
    if source_before != {name: digest(HERE / name) for name in SOURCES}:
        raise ValueError("source/config/lock changed during execution")
    result = {"generated": datetime.now(timezone.utc).isoformat(),
              "scope": "Retrospective complete-file metric audit; no attack or model evaluation.",
              "python": platform.python_version(), "executable": sys.executable,
              "source_sha256": source_before,
              "data_sha256": before, "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", action="append", default=[])
    parser.add_argument("--output", type=Path, default=HERE / "results/evidence.json")
    args = parser.parse_args()
    try:
        record = produce(inputs(args.corpus), args.output)
    except (OSError, ValueError) as exc:
        print("metric production failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"records": len(record["records"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
