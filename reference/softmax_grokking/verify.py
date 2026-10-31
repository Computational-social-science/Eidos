"""Independent artifact-bound acceptance; completion never implies superiority."""
from __future__ import annotations
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from reference.softmax_grokking.common import (digest, source_digest, dataset, numpy_forward,
                                               classification_metrics, load_weights, json_digest)
from reference.softmax_training.validate import qualified_backend


def state_hash(weights):
    return hashlib.sha256(b"".join(v.astype("<f4").tobytes() for v in weights.values())).hexdigest()


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _points(points, steps, keys, errors):
    if not isinstance(points, list) or [p.get("step") for p in points] != steps:
        errors.append("incomplete checkpoint inventory")
        return
    for point in points:
        for key in keys:
            value = point.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                errors.append("invalid metric: " + key)
            elif ("accuracy" in key and not 0 <= value <= 1) or (key in ("cross_entropy_float64", "parameter_displacement_l2") and value < 0):
                errors.append("metric domain: " + key)


def _validate(report, protocol, check_files, base, extension):
    errors = []
    if report.get("status") != "COMPLETE": errors.append("study is not COMPLETE")
    if report.get("protocol") != protocol: errors.append("protocol mismatch")
    runs = report.get("runs", [])
    if sorted(r.get("seed", -1) for r in runs) != protocol["seeds"]: errors.append("seed inventory mismatch")
    runtime = report.get("runtime", {})
    if (runtime.get("dtype") != protocol["dtype"] or runtime.get("device_type") != protocol["device"]
            or runtime.get("tf32") is not False or runtime.get("deterministic_algorithms") is not True
            or not all(runtime.get(k) for k in ("python", "torch", "numpy", "cuda", "device"))):
        errors.append("runtime or determinism policy mismatch")
    registered, started, finished = [datetime.fromisoformat(v) for v in
        (protocol["registered_at"], report["started_at"], report["finished_at"])]
    if any(v.tzinfo is None for v in (registered, started, finished)) or not registered < started <= finished:
        errors.append("invalid study times")
    if not qualified_backend(report.get("backend_preflight", {})): errors.append("backend unqualified")
    expected_steps = list(range(0, protocol["epochs"] + 1, protocol["log_interval"]))
    expected_artifacts = set()
    for run in runs:
        seed, arms = run["seed"], run.get("arms", {})
        if set(arms) != {"standard", "fixed"}: errors.append("missing training arm"); continue
        initial = run.get("initial_state_sha256")
        if not _hash(initial): errors.append("missing initial state hash")
        stems = [f"seed-{seed}-initial", f"seed-{seed}-standard", f"seed-{seed}-fixed"]
        expected_artifacts.add(f"checkpoints/seed-{seed}-split.json")
        if not _hash(run.get("split_sha256")): errors.append("missing split hash")
        for arm in arms.values():
            if arm.get("initial_state_sha256") != initial or not _hash(arm.get("initial_state_sha256")):
                errors.append("arms are not paired")
            if not _hash(arm.get("final_state_sha256")): errors.append("missing final state hash")
            _points(arm.get("checkpoints"), expected_steps,
                    ("train_accuracy", "test_accuracy", "mean_margin", "cross_entropy_float64"), errors)
        distill = run.get("distillation", {})
        qualified = arms["fixed"]["checkpoints"][-1]["test_accuracy"] >= protocol["teacher_minimum_test_accuracy"]
        if not qualified:
            if distill.get("status") != "SKIP" or not distill.get("reason") or distill.get("variants"):
                errors.append("unqualified teacher must explicitly SKIP")
        else:
            variants = distill.get("variants", {})
            if distill.get("status") != "COMPLETE" or set(variants) != {"standard", "fixed"}:
                errors.append("qualified teacher needs completed distillation")
            for name, variant in variants.items():
                stems.append(f"seed-{seed}-distill-{name}")
                if variant.get("initial_state_sha256") != arms["fixed"].get("final_state_sha256") or variant.get("initial_logits_equal") is not True:
                    errors.append("distillation does not start at exact teacher")
                if not _hash(variant.get("final_state_sha256")): errors.append("missing distillation hash")
                d = protocol["distillation"]
                _points(variant.get("checkpoints"), list(range(0, d["steps"] + 1, d["log_interval"])),
                        ("parameter_displacement_l2", "heldout_kl_float64", "test_accuracy"), errors)
                if variant["checkpoints"][0]["parameter_displacement_l2"] != 0:
                    errors.append("distillation initial displacement is not zero")
                if name == "fixed" and (variant["final_state_sha256"] != variant["initial_state_sha256"] or
                        any(p["parameter_displacement_l2"] != 0 for p in variant["checkpoints"])):
                    errors.append("fixed stationarity is not exact")
        expected_artifacts.update(f"checkpoints/{stem}{suffix}" for stem in stems for suffix in (".pt", ".json"))
    if set(report.get("artifacts", {})) != expected_artifacts: errors.append("artifact inventory mismatch")
    if any(not _hash(v) for v in report.get("artifacts", {}).values()): errors.append("invalid artifact digest")
    if extension:
        records = report.get("parent_replay_checks", [])
        expected = {(s, arm, 10000) for s in protocol["seeds"] for arm in ("standard", "fixed")}
        actual = {(r.get("seed"), r.get("arm"), r.get("step")) for r in records}
        if len(records) != 6 or actual != expected or any(not _hash(r.get("sha256")) for r in records):
            errors.append("parent replay inventory mismatch")
        if not _hash(report.get("parent_evidence_sha256")): errors.append("missing parent digest")
    if not check_files: return errors
    prefix = "reference/" + base.name
    required_sources = (prefix+"/run.py", prefix+"/protocol.json", "reference/softmax_grokking/model.py",
        "reference/softmax_grokking/common.py", "reference/softmax_training/train.py", "reference/softmax_training/validate.py",
        "framework/stable_numerics_torch.py", "framework/verifiers/numerics.py")
    if set(report.get("source_sha256", {})) != set(required_sources): errors.append("source inventory mismatch")
    for name in required_sources:
        if report.get("source_sha256", {}).get(name) != source_digest(ROOT/name): errors.append("source mismatch: " + name)
    for name, value in report.get("artifacts", {}).items():
        path = (base/name).resolve()
        if not path.is_relative_to(base.resolve()) or not path.is_file() or digest(path) != value:
            errors.append("artifact mismatch: " + name)
    tokens, labels = dataset(protocol["modulus"])
    for run in runs:
        seed = run["seed"]
        split = json.loads((base/f"checkpoints/seed-{seed}-split.json").read_text())
        order = split["permutation"]
        if (split["seed"] != seed or split["modulus"] != protocol["modulus"] or
                any(type(i) is not int for i in order) or sorted(order) != list(range(len(labels))) or run["split_sha256"] != json_digest(split)):
            errors.append("split mismatch")
            continue
        cut = int(len(labels)*protocol["train_fraction"]); train, test = order[:cut], order[cut:]
        initial = load_weights(base/f"checkpoints/seed-{seed}-initial", protocol)
        if state_hash(initial) != run["initial_state_sha256"]: errors.append("initial tensor hash mismatch")
        models = {}
        for name, arm in run["arms"].items():
            weights = load_weights(base/f"checkpoints/seed-{seed}-{name}", protocol); models[name] = weights
            if state_hash(weights) != arm["final_state_sha256"]: errors.append("final tensor hash mismatch")
            metrics = classification_metrics(numpy_forward(weights, tokens, protocol["heads"]), labels, train, test)
            for key, value in metrics.items():
                # GPU float32 producer vs independent CPU float64 forward; accuracy is exact.
                accuracy = "accuracy" in key
                if not math.isclose(value, arm["checkpoints"][-1][key], rel_tol=0 if accuracy else 2e-4,
                                    abs_tol=1e-12 if accuracy else 2e-8):
                    errors.append(f"{seed}/{name}: independent {key} mismatch")
        teacher = models["fixed"]
        temp = protocol["distillation"]["temperature"]
        teacher_logits = numpy_forward(teacher, tokens[test], protocol["heads"])/temp
        log_p = teacher_logits - np.logaddexp.reduce(teacher_logits, axis=-1, keepdims=True)
        for name, variant in run["distillation"].get("variants", {}).items():
            weights = load_weights(base/f"checkpoints/seed-{seed}-distill-{name}", protocol)
            if state_hash(weights) != variant["final_state_sha256"]: errors.append("distillation tensor hash mismatch")
            drift = math.sqrt(sum(float(np.square(weights[k].astype(float)-teacher[k].astype(float)).sum()) for k in weights))
            final = variant["checkpoints"][-1]
            if not math.isclose(drift, final["parameter_displacement_l2"], rel_tol=1e-10, abs_tol=0):
                errors.append("independent displacement mismatch")
            logits = numpy_forward(weights, tokens[test], protocol["heads"])/temp
            log_q = logits - np.logaddexp.reduce(logits, axis=-1, keepdims=True)
            kl = float((np.exp(log_p)*(log_p-log_q)).sum(-1).mean())
            accuracy = float((logits.argmax(-1) == labels[test]).mean())
            if not math.isclose(kl, final["heldout_kl_float64"], rel_tol=2e-4, abs_tol=2e-8): errors.append("independent heldout KL mismatch")
            if not math.isclose(accuracy, final["test_accuracy"], abs_tol=5e-8): errors.append("independent distillation accuracy mismatch")
    if extension:
        parent_path = ROOT/protocol["parent"]
        parent = json.loads(parent_path.read_text())
        parent_protocol = json.loads((HERE/"protocol.json").read_text())
        if digest(parent_path) != report["parent_evidence_sha256"] or validate(parent, parent_protocol):
            errors.append("parent evidence invalid")
        parents = {r["seed"]:r for r in parent["runs"]}
        for run in runs:
            p = parents[run["seed"]]
            if run["initial_state_sha256"] != p["initial_state_sha256"] or run["split_sha256"] != p["split_sha256"]:
                errors.append("parent pairing mismatch")
        for r in report["parent_replay_checks"]:
            if r["sha256"] != parents[r["seed"]]["arms"][r["arm"]]["final_state_sha256"]:
                errors.append("parent replay hash mismatch")
    return errors


def validate(report, protocol, *, check_files=True, base=HERE, extension=False):
    try:
        return _validate(report, protocol, check_files, Path(base), extension)
    except (OSError, ValueError, KeyError, IndexError, TypeError, OverflowError) as exc:
        return ["malformed evidence: " + str(exc)]


def main(base=HERE, extension=False):
    try:
        report = json.loads((base/"docs/evidence.json").read_text())
        protocol = json.loads((base/"protocol.json").read_text())
        errors = validate(report, protocol, base=base, extension=extension)
    except (OSError, ValueError) as exc: errors = [str(exc)]
    print(json.dumps({"status":"FAIL" if errors else "PASS", "findings":errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__": raise SystemExit(main())
