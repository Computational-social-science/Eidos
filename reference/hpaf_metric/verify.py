"""Independent C++ and exhaustive edit-graph checks; never import producer functions."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import difflib
import hashlib
import itertools
import json
from pathlib import Path
import sys

import rapidfuzz
from rapidfuzz.distance.metrics_cpp import levenshtein_distance

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_distance(source: str, target: str, alphabet: str = "aβ") -> int:
    """Breadth-first search over unit edits, independent of the DP recurrence."""
    queue, seen = deque([(source, 0)]), {source}
    bound = max(len(source), len(target))
    while queue:
        word, depth = queue.popleft()
        if word == target:
            return depth
        neighbors = {word[:i] + word[i + 1:] for i in range(len(word))}
        neighbors.update(word[:i] + c + word[i + 1:] for i in range(len(word)) for c in alphabet)
        if len(word) < bound:
            neighbors.update(word[:i] + c + word[i:] for i in range(len(word) + 1) for c in alphabet)
        for neighbor in neighbors - seen:
            seen.add(neighbor)
            queue.append((neighbor, depth + 1))
    raise ValueError("unreachable graph target")


def qualify() -> dict:
    words = ["".join(p) for size in range(4) for p in itertools.product("aβ", repeat=size)]
    checked, legacy_rejected, zero_rejected = 0, 0, 0
    for source, target in itertools.product(words, repeat=2):
        exact = graph_distance(source, target)
        reference = levenshtein_distance(source, target, weights=(1, 1, 1))
        if reference != exact:
            raise ValueError("C++ backend failed independent edit-graph qualification")
        old = sum(max(i2 - i1, j2 - j1)
                  for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, source, target).get_opcodes()
                  if tag != "equal")
        legacy_rejected += old != exact
        zero_rejected += exact != 0
        checked += 1
    if not legacy_rejected or not zero_rejected:
        raise ValueError("broken controls not rejected")
    return {"ordered_pairs": checked, "legacy_control_mismatches": legacy_rejected,
            "zero_control_mismatches": zero_rejected, "graph_max_length": 3,
            "graph_alphabet": "aβ", "reference": "RapidFuzz C++ unit-cost Levenshtein",
            "rapidfuzz": rapidfuzz.__version__, "backend": levenshtein_distance.__module__}


def validate(evidence: Path, paths: list[Path]) -> dict:
    raw = evidence.read_bytes()
    value = json.loads(raw)
    sources = ("run.py", "verify.py", "protocol.json", "pyproject.toml", "uv.lock")
    if value.get("source_sha256") != {name: digest(HERE / name) for name in sources}:
        raise ValueError("source/config/lock mismatch")
    if value.get("data_sha256") != {path.name: digest(path) for path in paths}:
        raise ValueError("corpus hash mismatch")
    if len({path.name for path in paths}) != len(paths):
        raise ValueError("duplicate corpus basename")
    rows = []
    summary = {}
    for path in paths:
        corpus = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(corpus, list) or not corpus:
            raise ValueError("corpus must be nonempty")
        entries = []
        for index, pair in enumerate(corpus):
            source = pair["goal"]
            target = pair["perturbation"] if "perturbation" in pair else pair["perturbed_text"]
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError("pair must contain strings")
            exact = levenshtein_distance(source, target, weights=(1, 1, 1))
            legacy = sum(max(i2 - i1, j2 - j1)
                         for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, source, target).get_opcodes()
                         if tag != "equal")
            entries.append({"corpus": path.name, "row": index, "source_length": len(source),
                            "target_length": len(target), "legacy_cost": legacy, "distance": exact,
                            "legacy_rate": legacy / max(len(source), 1),
                            "repaired_rate": exact / max(len(source), 1)})
        summary[path.name] = {"pairs": len(entries),
                              "legacy_mismatches": sum(r["legacy_cost"] != r["distance"] for r in entries),
                              "maximum_overestimate": max(r["legacy_cost"] - r["distance"] for r in entries),
                              "underestimates": sum(r["legacy_cost"] < r["distance"] for r in entries)}
        rows.extend(entries)
    # JSON bool is not an integer distance; compare both values and JSON types.
    if json.dumps(value.get("records"), sort_keys=True) != json.dumps(rows, sort_keys=True):
        raise ValueError("record inventory or metric mismatch")
    qualification = qualify()
    if (raw != evidence.read_bytes() or value["data_sha256"] != {path.name: digest(path) for path in paths}
            or value["source_sha256"] != {name: digest(HERE / name) for name in sources}):
        raise ValueError("inputs changed during verification")
    return {"generated": datetime.now(timezone.utc).isoformat(), "accepted": True,
            "evidence_sha256": hashlib.sha256(raw).hexdigest(), "records": len(rows),
            "per_corpus": summary, "qualification": qualification,
            "scope": "Complete supplied-file code-point edit metrics; not scientific novelty or model safety."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", action="append", type=Path, default=[])
    parser.add_argument("--evidence", type=Path, default=HERE / "results/evidence.json")
    parser.add_argument("--output", type=Path, default=HERE / "results/verification.json")
    parser.add_argument("--check", action="store_true", help="validate without publishing or replacing a record")
    args = parser.parse_args()
    try:
        if not args.check and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError("refusing existing output; use a fresh path: " + str(args.output))
        result = validate(args.evidence, args.corpus or [HERE / "pairs.json", HERE / "short-graph.json"])
        if not args.check:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("metric verification rejected: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"accepted": True, "records": result["records"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
