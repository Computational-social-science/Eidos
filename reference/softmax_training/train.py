"""Execute the prospectively specified, bounded teacher–student training comparison."""
from __future__ import annotations

import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import copy
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from framework import stable_numerics_torch as kernels
from framework.verifiers.numerics import kernel_regression_report
from reference.softmax_training.validate import digest, source_digest, split_digest, validate_report


def state_hash(model):
    content = b"".join(value.detach().cpu().contiguous().numpy().tobytes()
                       for value in model.state_dict().values())
    return hashlib.sha256(content).hexdigest()


def prepare_teacher_targets(teacher, train_x, test_x, temperature):
    """Match GEMM batch dimensions; slicing a full-batch cache changes rounding."""
    with torch.no_grad():
        train_scaled = teacher(train_x) / temperature
        heldout = teacher(test_x)
        return train_scaled, F.log_softmax((heldout / temperature).double(), -1), heldout


def require_equal_logits(student, teacher):
    if not torch.equal(student, teacher):
        raise RuntimeError("initial logits differ; stationarity experiment is confounded")


def actual_backend(device):
    def hard(z, target):
        tensor = torch.tensor(z, device=device, requires_grad=True)
        loss = kernels.hard_cross_entropy(tensor, target)
        loss.backward()
        return loss.item(), tensor.grad.detach().cpu().numpy()
    def soft(student, teacher):
        tensor = torch.tensor(student, device=device, requires_grad=True)
        loss = kernels.logit_distillation(tensor, torch.tensor(teacher, device=device))
        loss.backward()
        return loss.item(), tensor.grad.detach().cpu().numpy()
    return kernel_regression_report(hard, soft, f"torch {torch.__version__}; {device}; actual autograd")


def execute(protocol):
    device = protocol["device"]
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("protocol requires CUDA; no silent CPU fallback")
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    preflight = actual_backend(device)
    if preflight["verdict"] != "PASS":
        raise RuntimeError("actual backend qualification failed: " + json.dumps(preflight))
    report = {"status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat(),
              "protocol": protocol, "backend_preflight": preflight, "runs": [], "artifacts": {},
              "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                          "numpy": np.__version__, "cuda": torch.version.cuda,
                          "device": torch.cuda.get_device_name() if device == "cuda" else "cpu",
                          "dtype": "float32", "device_type": device,
                          "tf32": False, "deterministic_algorithms": True}}
    paths = ("reference/softmax_training/protocol.json", "reference/softmax_training/train.py",
             "reference/softmax_training/validate.py", "framework/stable_numerics_torch.py",
             "framework/verifiers/numerics.py")
    report["source_sha256"] = {path: source_digest(ROOT / path) for path in paths}
    report["source_hash_policy"] = "UTF-8 with LF line endings; data/model artifacts hashed as raw bytes"
    output = HERE / "docs"
    output.mkdir(exist_ok=True)
    checkpoints = HERE / "checkpoints"
    checkpoints.mkdir(exist_ok=True)

    def publish():
        temporary = output / "evidence.json.tmp"
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, output / "evidence.json")

    publish()
    try:
        for seed in protocol["seeds"]:
            torch.manual_seed(seed)
            p = protocol["modulus"]
            a, b = torch.meshgrid(torch.arange(p), torch.arange(p), indexing="ij")
            pairs = torch.stack((a.flatten(), b.flatten()), dim=1)
            labels = (pairs[:, 0] + pairs[:, 1]) % p
            permutation = torch.randperm(len(labels), generator=torch.Generator().manual_seed(seed))
            cut = int(len(labels) * protocol["train_fraction"])
            train, test = permutation[:cut].to(device), permutation[cut:].to(device)
            x = F.one_hot(pairs, p).flatten(1).to(device=device, dtype=torch.float32)
            y = labels.to(device)
            teacher = nn.Sequential(nn.Linear(2 * p, protocol["hidden_width"]), nn.ReLU(),
                                    nn.Linear(protocol["hidden_width"], p)).to(device)
            optimizer = torch.optim.Adam(teacher.parameters(), lr=protocol["teacher_lr"], betas=tuple(protocol["betas"]))
            teacher_steps = 0
            for step in range(1, protocol["teacher_max_steps"] + 1):
                optimizer.zero_grad(set_to_none=True)
                F.cross_entropy(teacher(x[train]), y[train]).backward()
                optimizer.step()
                teacher_steps = step
                if step >= protocol["teacher_min_steps"] and step % 25 == 0:
                    with torch.no_grad():
                        if float((teacher(x[train]).argmax(-1) == y[train]).float().mean()) == 1:
                            break
            teacher.eval().requires_grad_(False)
            with torch.no_grad():
                teacher_logits = teacher(x)
                train_target, log_p, heldout_teacher = prepare_teacher_targets(
                    teacher, x[train], x[test], protocol["temperature"])
                probabilities = F.softmax(train_target, dim=-1)
                p64 = log_p.exp()
            split = {"modulus": p, "seed": seed, "permutation": permutation.tolist()}
            split_path = checkpoints / f"seed-{seed}-split.json"
            split_path.write_text(json.dumps(split), encoding="utf-8")
            report["artifacts"][split_path.relative_to(HERE).as_posix()] = digest(split_path)
            run = {"seed": seed, "teacher_steps": teacher_steps, "teacher_state_sha256": state_hash(teacher),
                   "data_sha256": split_digest(split),
                   "teacher_train_accuracy": float((teacher_logits[train].argmax(-1) == y[train]).float().mean()),
                   "teacher_test_accuracy": float((teacher_logits[test].argmax(-1) == y[test]).float().mean()),
                   "variants": {}}
            initial = [value.detach().clone() for value in teacher.parameters()]
            teacher_path = checkpoints / f"seed-{seed}-teacher.pt"
            torch.save(teacher.state_dict(), teacher_path)
            report["artifacts"][teacher_path.relative_to(HERE).as_posix()] = digest(teacher_path)
            for name in ("standard", "fixed"):
                model = copy.deepcopy(teacher).requires_grad_(True)
                optimizer = torch.optim.Adam(model.parameters(), lr=protocol["student_lr"],
                    betas=tuple(protocol["betas"]), eps=protocol["epsilon"], weight_decay=protocol["weight_decay"])
                variant = {"initial_state_sha256": state_hash(model), "checkpoints": []}
                for step in range(protocol["distillation_steps"] + 1):
                    if step % protocol["log_interval"] == 0:
                        with torch.no_grad():
                            logits = model(x[test])
                            log_q = F.log_softmax((logits / protocol["temperature"]).double(), dim=-1)
                            drift = sum(((value.double() - old.double()) ** 2).sum()
                                        for value, old in zip(model.parameters(), initial)).sqrt()
                            variant["checkpoints"].append({"step": step, "parameter_displacement_l2": drift.item(),
                                "heldout_kl_float64": (p64 * (log_p - log_q)).sum(-1).mean().item(),
                                "test_accuracy": float((logits.argmax(-1) == y[test]).float().mean()),
                                "teacher_agreement": float((logits.argmax(-1) == heldout_teacher.argmax(-1)).float().mean())})
                    if step == protocol["distillation_steps"]:
                        break
                    optimizer.zero_grad(set_to_none=True)
                    logits = model(x[train]) / protocol["temperature"]
                    if step == 0:
                        require_equal_logits(logits, train_target)
                        variant["initial_logits_equal"] = True
                    if name == "fixed":
                        loss = kernels.logit_distillation(logits, train_target).mean()
                    else:
                        loss = -(probabilities * F.log_softmax(logits, dim=-1)).sum(-1).mean()
                    (loss * protocol["loss_scale"]).backward()
                    optimizer.step()
                variant["final_state_sha256"] = state_hash(model)
                model_path = checkpoints / f"seed-{seed}-{name}.pt"
                torch.save(model.state_dict(), model_path)
                report["artifacts"][model_path.relative_to(HERE).as_posix()] = digest(model_path)
                run["variants"][name] = variant
                print(f"seed={seed} {name}: parameter drift={variant['checkpoints'][-1]['parameter_displacement_l2']:.8g}", flush=True)
            report["runs"].append(run)
            publish()
        report["status"] = "COMPLETE"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        errors = validate_report(report, protocol)
        report["acceptance"] = {"status": "FAIL" if errors else "PASS", "findings": errors}
        publish()
        if errors:
            raise RuntimeError("training acceptance failed: " + "; ".join(errors))
        return report
    except BaseException as exc:
        report["status"] = "INCOMPLETE" if isinstance(exc, KeyboardInterrupt) else "ERROR"
        report["error"] = f"{type(exc).__name__}: {exc}"
        publish()
        raise


if __name__ == "__main__":
    execute(json.loads((HERE / "protocol.json").read_text(encoding="utf-8")))
