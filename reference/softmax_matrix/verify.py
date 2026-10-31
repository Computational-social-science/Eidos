"""CPU acceptance for all cells; favorable outcomes are not an acceptance rule."""
from __future__ import annotations
from datetime import datetime
import itertools
import json
import math
from pathlib import Path
import re
import sys
import zipfile
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from reference.softmax_matrix.run import SOURCES
from reference.softmax_grokking.common import digest, source_digest, load_weights, dataset, numpy_forward, classification_metrics, json_digest
from reference.softmax_grokking.verify import validate as validate_parent, state_hash
from reference.softmax_training.validate import qualified_backend
from framework.provenance import historical_lock_matches


def expected_cells(p):
    return list(itertools.product(p["seeds"], p["loss_dtypes"], p["epsilons"], p["arms"]))


def _hash(v):
    return isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) is not None


def validate_point(point, size, loss_dtype=None):
    errors = []
    if type(point.get("step")) is not int:
        errors.append("invalid step")
    if type(point.get("sample_count")) is not int or point["sample_count"] != size:
        errors.append("invalid sample inventory")
    for key in ("zero_target_loss", "zero_target_model"):
        value = point.get(key)
        if type(value) is not int or not 0 <= value <= size:
            errors.append("invalid count " + key)
    for key in ("train_accuracy", "test_accuracy", "mean_margin", "cross_entropy_float64", "training_loss"):
        value = point.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            errors.append("invalid metric " + key)
        elif ("accuracy" in key and not 0 <= value <= 1) or (key in ("cross_entropy_float64", "training_loss") and value < 0):
            errors.append("metric domain " + key)
    if not errors and (point["zero_target_model"] < point["zero_target_loss"] or
                       (loss_dtype == "float32" and point["zero_target_model"] != point["zero_target_loss"])):
        errors.append("inconsistent loss/model gradient zero counts")
    return errors


def validate_structure(r, p):
    errors = []
    if r.get("status") != "COMPLETE" or r.get("protocol") != p:
        errors.append("incomplete study or protocol mismatch")
    if not qualified_backend(r.get("backend_preflight", {})):
        errors.append("backend unqualified")
    runs = r.get("runs", [])
    actual = [(v["seed"], v["loss_dtype"], v["epsilon"], v["arm"]) for v in runs]
    expected = expected_cells(p)
    if len(actual) != len(expected) or set(actual) != set(expected) or any(type(v["seed"]) is not int for v in runs):
        errors.append("matrix inventory mismatch")
    steps = list(range(0, p["epochs"] + 1, p["log_interval"]))
    size = int(p["modulus"] ** 2 * p["train_fraction"])
    for v in runs:
        if [pt.get("step") for pt in v.get("checkpoints", [])] != steps:
            errors.append("incomplete trajectory")
        for pt in v.get("checkpoints", []):
            errors.extend(validate_point(pt, size, v["loss_dtype"]))
        if any(not _hash(v.get(k)) for k in ("initial_state_sha256", "final_state_sha256", "split_sha256")):
            errors.append("missing model or split hash")
        if v["loss_dtype"] == "float32" and v["epsilon"] == 1e-8 and v.get("parent_baseline_match") is not True:
            errors.append("parent baseline replay missing")
    return errors


def validate(r, p, base=HERE):
    try:
        errors = validate_structure(r, p)
        if errors:
            return errors
        times = [datetime.fromisoformat(v) for v in (p["registered_at"], r["started_at"], r["finished_at"])]
        if any(v.tzinfo is None for v in times) or not times[0] < times[1] <= times[2]:
            errors.append("invalid registration/execution times")
        runtime = r.get("runtime", {})
        if (runtime.get("model_dtype") != "float32" or runtime.get("device_type") != "cuda" or
                runtime.get("tf32") is not False or runtime.get("amp") is not False or
                runtime.get("deterministic_algorithms") is not True or
                any(not runtime.get(k) for k in ("python", "torch", "numpy", "cuda", "device"))):
            errors.append("runtime policy mismatch")
        if set(r.get("source_sha256", {})) != set(SOURCES):
            errors.append("source inventory mismatch")
        for name in SOURCES:
            recorded = r.get("source_sha256", {}).get(name)
            matches = historical_lock_matches(ROOT, recorded) if name == "uv.lock" else recorded == source_digest(ROOT / name)
            if not matches:
                errors.append("source mismatch: " + name)
        parent_path = ROOT / p["parent"]
        parent = json.loads(parent_path.read_text())
        parent_base = parent_path.parents[1]
        if digest(parent_path) != r.get("parent_evidence_sha256") or validate_parent(parent, json.loads((parent_base / "protocol.json").read_text())):
            errors.append("invalid parent")
        parents = {v["seed"]: v for v in parent["runs"]}
        tokens, labels = dataset(p["modulus"])
        expected_artifacts = set()
        for v in r["runs"]:
            seed, dtype, eps, arm = (v[k] for k in ("seed", "loss_dtype", "epsilon", "arm"))
            name = f"checkpoints/seed-{seed}-{dtype}-eps-{eps:g}-{arm}"
            if v.get("checkpoint_stem") != name:
                errors.append("checkpoint stem mismatch")
                continue
            expected_artifacts.update(name + suffix for suffix in (".pt", ".json"))
            stem = Path(base) / name
            weights = load_weights(stem, p)
            if state_hash(weights) != v["final_state_sha256"]:
                errors.append("final tensor hash mismatch")
            original = parents[seed]
            if v["initial_state_sha256"] != original["initial_state_sha256"] or v["split_sha256"] != original["split_sha256"]:
                errors.append("unpaired initial model or split")
            if dtype == "float32" and eps == 1e-8 and v["final_state_sha256"] != original["arms"][arm]["final_state_sha256"]:
                errors.append("parent baseline hash mismatch")
            split = json.loads((parent_base / f"checkpoints/seed-{seed}-split.json").read_text())
            if json_digest(split) != v["split_sha256"]:
                errors.append("split binding mismatch")
            order = split["permutation"]; cut = int(len(order) * p["train_fraction"])
            metrics = classification_metrics(numpy_forward(weights, tokens, p["heads"]), labels, order[:cut], order[cut:])
            for key, value in metrics.items():
                accuracy = "accuracy" in key
                absolute = 1e-12 if accuracy else (0 if key == "cross_entropy_float64" else 2e-8)
                if not math.isclose(value, v["checkpoints"][-1][key], rel_tol=0 if accuracy else 2e-4,
                                    abs_tol=absolute):
                    errors.append(f"{name}: independent {key} mismatch")
        if set(r.get("artifacts", {})) != expected_artifacts:
            errors.append("artifact inventory mismatch")
        for name, value in r.get("artifacts", {}).items():
            path = (Path(base) / name).resolve()
            if not path.is_relative_to(Path(base).resolve()) or not _hash(value) or digest(path) != value:
                errors.append("artifact digest mismatch")
        return errors
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError, zipfile.BadZipFile) as exc:
        return ["invalid evidence: " + str(exc)]


def main():
    try:
        p = json.loads((HERE / "protocol.json").read_text())
        r = json.loads((HERE / "docs/evidence.json").read_text())
        errors = validate(r, p)
        if not errors:
            errors = validate_final_check(r)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({"status": "FAIL" if errors else "PASS", "findings": errors}, indent=2))
    return int(bool(errors))


def validate_final_check(r, base=HERE):
    try:
        base = Path(base)
        audit = json.loads((base / "docs/final-gradient-check.json").read_text())
        if (audit.get("status") != "PASS" or audit.get("runtime") != r["runtime"] or
                audit.get("evidence_sha256") != digest(base / "docs/evidence.json") or
                audit.get("analysis_source_sha256") != source_digest(base / "final_check.py")):
            return ["final gradient check provenance mismatch"]
        records = audit["checks"]
        keys = ("seed", "loss_dtype", "epsilon", "arm")
        expected = {tuple(v[k] for k in keys): v for v in r["runs"]}
        if len(records) != len(expected) or {tuple(v[k] for k in keys) for v in records} != set(expected):
            return ["final gradient check inventory mismatch"]
        for row in records:
            v = expected[tuple(row[k] for k in keys)]
            if (row.get("matches") is not True or row.get("all_finite") is not True or
                    row.get("checkpoint_sha256") != digest(base / (v["checkpoint_stem"] + ".pt"))):
                return ["final gradient checkpoint mismatch"]
            point = v["checkpoints"][-1]
            for key in ("zero_target_model", "zero_target_loss"):
                if type(row[key]) is not int or row[key] != point[key]:
                    return ["final gradient count mismatch"]
            if type(row["training_loss"]) not in (float, int) or not math.isfinite(row["training_loss"]) or not math.isclose(row["training_loss"], point["training_loss"], rel_tol=1e-14, abs_tol=0):
                return ["final gradient loss mismatch"]
        return []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ["invalid final gradient check: " + str(exc)]


if __name__ == "__main__":
    raise SystemExit(main())
