"""Read-only training evidence gate; completion and provenance precede interpretation."""
from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from array import array
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def split_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _hash(value) -> bool:
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def checkpoint_vector(path: Path) -> tuple[str, list[float]]:
    """Read this model's contiguous float32 storages without unpickling model code."""
    with zipfile.ZipFile(path) as archive:
        names = sorted((n for n in archive.namelist() if re.search(r"/data/\d+$", n)),
                       key=lambda n: int(n.rsplit("/", 1)[1]))
        if len(names) != 4 or sum(archive.getinfo(n).file_size for n in names) > 20_000_000:
            raise ValueError("unexpected checkpoint storage inventory")
        byteorders = [n for n in archive.namelist() if n.endswith("/byteorder")]
        if len(byteorders) != 1 or archive.read(byteorders[0]) != b"little":
            raise ValueError("unsupported checkpoint byte order")
        content = b"".join(archive.read(name) for name in names)
        values = array("f")
        values.frombytes(content)
        import sys
        if sys.byteorder != "little":
            values.byteswap()
        return hashlib.sha256(content).hexdigest(), list(values)


def qualified_backend(value: dict) -> bool:
    cases, controls = value.get("cases", []), value.get("negative_controls", [])
    expected = {f"{dtype} hard margin {m}" for dtype, margins in
                (("float32", (0, 18, 80)), ("float64", (0, 40, 700))) for m in margins}
    expected |= {f"{dtype} {name}" for dtype in ("float32", "float64")
                 for name in ("equality", "near teacher", "far teacher")}
    return (value.get("verdict") == "PASS" and len(cases) == 12
            and {case.get("name") for case in cases} == expected
            and all(case.get("dtype") in ("float32", "float64")
                    and case.get("name", "").startswith(case["dtype"] + " ") for case in cases)
            and all(case.get("verdict") == "PASS" for case in cases)
            and {c.get("name") for c in controls} == {"lost target gradient", "nonzero stationary gradient"}
            and len(controls) == 2 and all(c.get("rejected") is True for c in controls))


def validate_report(report: dict, protocol: dict, *, check_files: bool = True) -> list[str]:
    errors = []
    if report.get("status") != "COMPLETE":
        errors.append("training evidence is not COMPLETE")
    if report.get("protocol") != protocol:
        errors.append("embedded protocol differs from registered protocol")
    runtime = report.get("runtime", {})
    if (runtime.get("dtype") != protocol.get("dtype") or runtime.get("device_type") != protocol.get("device")
            or runtime.get("deterministic_algorithms") is not True or runtime.get("tf32") is not False):
        errors.append("runtime differs from declared dtype/device/determinism policy")
    runs = report.get("runs", [])
    if sorted(r.get("seed", -1) for r in runs) != sorted(protocol.get("seeds", [])) or not runs:
        errors.append("declared seeds are missing, duplicated or replaced")
    if not qualified_backend(report.get("backend_preflight", {})):
        errors.append("actual backend has not passed independent qualification")
    try:
        if datetime.fromisoformat(report["started_at"]) <= datetime.fromisoformat(protocol["registered_at"]):
            errors.append("execution did not follow prospective local registration")
    except (KeyError, TypeError, ValueError):
        errors.append("missing or invalid registration/execution times")
    steps, interval = protocol.get("distillation_steps", 0), protocol.get("log_interval", 1)
    expected = list(range(0, steps + 1, interval)) if steps > 0 and interval > 0 else []
    for run in runs:
        seed = run.get("seed")
        if not _hash(run.get("teacher_state_sha256")) or not _hash(run.get("data_sha256")):
            errors.append(f"seed {seed}: valid teacher/data hashes are required")
        variants = run.get("variants", {})
        if set(variants) != {"standard", "fixed"}:
            errors.append(f"seed {seed}: both declared variants are required")
        for name, variant in variants.items():
            if variant.get("initial_logits_equal") is not True:
                errors.append(f"seed {seed}: {name} initial logit equality was not established")
            if (not _hash(variant.get("initial_state_sha256")) or not _hash(variant.get("final_state_sha256"))
                    or variant.get("initial_state_sha256") != run.get("teacher_state_sha256")):
                errors.append(f"seed {seed}: {name} did not start at teacher weights")
            rows = variant.get("checkpoints", [])
            if [row.get("step") for row in rows] != expected or not rows:
                errors.append(f"seed {seed}: {name} checkpoint sequence is incomplete")
            for row in rows:
                for key in ("parameter_displacement_l2", "heldout_kl_float64", "test_accuracy", "teacher_agreement"):
                    value = row.get(key)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        errors.append(f"seed {seed}: non-finite or missing {key}")
                    elif (key == "parameter_displacement_l2" and value < 0) or (key in ("test_accuracy", "teacher_agreement") and not 0 <= value <= 1):
                        errors.append(f"seed {seed}: {key} outside its physical domain")
                if name == "fixed" and row.get("parameter_displacement_l2") != 0:
                    errors.append(f"seed {seed}: fixed student left exact stationarity")
            if name == "fixed" and variant.get("final_state_sha256") != run.get("teacher_state_sha256"):
                errors.append(f"seed {seed}: fixed final parameter hash differs from teacher")
    expected_artifacts = {f"checkpoints/seed-{seed}-{variant}.pt" for seed in protocol.get("seeds", [])
                          for variant in ("teacher", "standard", "fixed")}
    expected_artifacts |= {f"checkpoints/seed-{seed}-split.json" for seed in protocol.get("seeds", [])}
    artifacts = report.get("artifacts", {})
    if set(artifacts) != expected_artifacts or not expected_artifacts or not all(_hash(h) for h in artifacts.values()):
        errors.append("complete teacher/student/split artifact inventory is required")
    if check_files:
        required = ("reference/softmax_training/protocol.json", "reference/softmax_training/train.py",
                    "reference/softmax_training/validate.py", "framework/stable_numerics_torch.py",
                    "framework/verifiers/numerics.py")
        hashes = report.get("source_sha256", {})
        for name in required:
            path = ROOT / name
            if not path.is_file() or hashes.get(name) != source_digest(path):
                errors.append(f"source provenance mismatch: {name}")
        for name, checksum in artifacts.items():
            path = (HERE / name).resolve()
            if not path.is_relative_to(HERE) or not path.is_file() or digest(path) != checksum:
                errors.append(f"checkpoint provenance mismatch: {name}")
        for run in runs:
            seed = run.get("seed")
            try:
                split = json.loads((HERE / f"checkpoints/seed-{seed}-split.json").read_text(encoding="utf-8"))
                permutation = split.get("permutation", [])
                if (split.get("modulus") != protocol["modulus"] or split.get("seed") != seed
                        or len(permutation) != protocol["modulus"] ** 2
                        or any(type(v) is not int for v in permutation)
                        or sorted(permutation) != list(range(protocol["modulus"] ** 2))
                        or run.get("data_sha256") != split_digest(split)):
                    errors.append(f"seed {seed}: dataset/split identity mismatch")
                teacher_hash, teacher_vector = checkpoint_vector(HERE / f"checkpoints/seed-{seed}-teacher.pt")
                expected_size = 3 * protocol["modulus"] * protocol["hidden_width"] + protocol["hidden_width"] + protocol["modulus"]
                if teacher_hash != run.get("teacher_state_sha256") or len(teacher_vector) != expected_size:
                    errors.append(f"seed {seed}: teacher weights differ from recorded state")
                for name, variant in run.get("variants", {}).items():
                    final_hash, final_vector = checkpoint_vector(HERE / f"checkpoints/seed-{seed}-{name}.pt")
                    if final_hash != variant.get("final_state_sha256") or len(final_vector) != len(teacher_vector):
                        errors.append(f"seed {seed}: {name} checkpoint state mismatch")
                    measured = math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(final_vector, teacher_vector)))
                    recorded = variant["checkpoints"][-1]["parameter_displacement_l2"]
                    if not math.isclose(measured, recorded, rel_tol=1e-10, abs_tol=1e-15):
                        errors.append(f"seed {seed}: {name} final displacement not reproduced from weights")
            except (OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile, OverflowError) as exc:
                errors.append(f"seed {seed}: invalid checkpoint/split: {exc}")
    return errors


def main() -> int:
    try:
        report = json.loads((HERE / "docs/evidence.json").read_text(encoding="utf-8"))
        protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
        errors = validate_report(report, protocol)
    except (OSError, ValueError, TypeError) as exc:
        errors = [f"training evidence unavailable: {exc}"]
    print(json.dumps({"status": "FAIL" if errors else "PASS", "findings": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
