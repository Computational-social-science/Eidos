"""Run the registered loss-precision matrix without altering the frozen parent study."""
from __future__ import annotations
import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import json
from datetime import datetime, timezone
from pathlib import Path
import platform
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
SOURCES = ("reference/softmax_matrix/run.py", "reference/softmax_matrix/protocol.json",
           "reference/softmax_grokking/model.py", "reference/softmax_grokking/common.py",
           "reference/softmax_training/train.py", "reference/softmax_training/validate.py",
           "framework/stable_numerics_torch.py", "framework/verifiers/numerics.py", "uv.lock")


def execute():
    import numpy as np
    import torch
    from torch.nn import functional as F
    from reference.softmax_grokking.model import Transformer
    from reference.softmax_grokking.common import digest, source_digest, dataset, classification_metrics
    from reference.softmax_grokking.verify import validate as validate_parent
    from reference.softmax_training.train import actual_backend, state_hash
    from framework.stable_numerics_torch import hard_cross_entropy

    p = json.loads((HERE / "protocol.json").read_text())
    target = HERE / "docs/evidence.json"
    if target.exists():
        raise FileExistsError("Existing evidence is immutable; use a separately registered study for a rerun")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no silent CPU fallback")
    parent_path = ROOT / p["parent"]
    parent = json.loads(parent_path.read_text())
    parent_base = parent_path.parents[1]
    errors = validate_parent(parent, json.loads((parent_base / "protocol.json").read_text()))
    if errors:
        raise ValueError(errors)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    r = {"status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat(), "protocol": p,
         "parent_evidence_sha256": digest(parent_path), "source_sha256": {n: source_digest(ROOT / n) for n in SOURCES},
         "runtime": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__,
                     "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(), "device_type": "cuda",
                     "model_dtype": "float32", "tf32": False, "deterministic_algorithms": True, "amp": False},
         "runs": [], "artifacts": {}}
    target.parent.mkdir(exist_ok=True)
    (HERE / "checkpoints").mkdir(exist_ok=True)

    def publish():
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(r, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, target)

    try:
        r["backend_preflight"] = actual_backend("cuda")
        if r["backend_preflight"]["verdict"] != "PASS":
            raise RuntimeError("backend unqualified")
        publish()
        tokens, labels = dataset(p["modulus"])
        x = torch.tensor(tokens, device="cuda"); y = torch.tensor(labels, device="cuda")
        for seed in p["seeds"]:
            split = json.loads((parent_base / f"checkpoints/seed-{seed}-split.json").read_text())
            order = split["permutation"]; cut = int(len(order) * p["train_fraction"])
            train, test = order[:cut], order[cut:]; tx, ty = x[train], y[train]
            initial = torch.load(parent_base / f"checkpoints/seed-{seed}-initial.pt", map_location="cuda", weights_only=True)
            parent_run = next(v for v in parent["runs"] if v["seed"] == seed)
            for dtype in p["loss_dtypes"]:
                for epsilon in p["epsilons"]:
                    for arm in p["arms"]:
                        model = Transformer(p["modulus"], p["width"], p["heads"]).cuda()
                        model.load_state_dict(initial)
                        row = {"seed": seed, "loss_dtype": dtype, "epsilon": epsilon, "arm": arm,
                               "initial_state_sha256": state_hash(model), "split_sha256": parent_run["split_sha256"], "checkpoints": []}
                        r["runs"].append(row)
                        if row["initial_state_sha256"] != parent_run["initial_state_sha256"]:
                            raise RuntimeError("initial pairing mismatch")
                        optimizer = torch.optim.AdamW(model.parameters(), lr=p["lr"], betas=tuple(p["betas"]),
                                                      eps=epsilon, weight_decay=p["weight_decay"])
                        loss_dtype = getattr(torch, dtype)
                        def objective(logits):
                            return hard_cross_entropy(logits, ty).mean() if arm == "fixed" else F.cross_entropy(logits, ty)
                        started = time.monotonic()
                        for step in range(p["epochs"] + 1):
                            if step % p["log_interval"] == 0:
                                with torch.no_grad():
                                    full = model(x).cpu().numpy()
                                    represented = model(tx).detach()
                                logits_model = represented.requires_grad_(True)
                                logits_loss = logits_model.to(loss_dtype)
                                loss = objective(logits_loss)
                                grad_loss, = torch.autograd.grad(loss, logits_loss, retain_graph=True)
                                grad_model, = torch.autograd.grad(loss, logits_model)
                                if not torch.isfinite(loss) or not torch.isfinite(grad_loss).all() or not torch.isfinite(grad_model).all():
                                    raise FloatingPointError("nonfinite recorded loss/gradient")
                                idx = torch.arange(len(ty), device="cuda")
                                point = {"step": step, **classification_metrics(full, labels, train, test),
                                         "training_loss": loss.item(), "sample_count": len(ty),
                                         "zero_target_loss": int((grad_loss[idx, ty] == 0).sum().item()),
                                         "zero_target_model": int((grad_model[idx, ty] == 0).sum().item())}
                                row["checkpoints"].append(point); publish()
                                if step % 2000 == 0:
                                    print(f"seed={seed} {dtype} eps={epsilon:g} {arm} step={step} test={point['test_accuracy']:.4f} zero={point['zero_target_model']} elapsed={time.monotonic()-started:.1f}s", flush=True)
                            if step == p["epochs"]:
                                break
                            optimizer.zero_grad(set_to_none=True)
                            objective(model(tx).to(loss_dtype)).backward(); optimizer.step()
                        stem = HERE / f"checkpoints/seed-{seed}-{dtype}-eps-{epsilon:g}-{arm}"
                        torch.save(model.state_dict(), stem.with_suffix(".pt"))
                        stem.with_suffix(".json").write_text(json.dumps({k: v.detach().cpu().tolist() for k, v in model.state_dict().items()}, separators=(",", ":")), encoding="utf-8", newline="\n")
                        row["final_state_sha256"] = state_hash(model)
                        row["checkpoint_stem"] = stem.relative_to(HERE).as_posix()
                        for suffix in (".pt", ".json"):
                            path = stem.with_suffix(suffix); r["artifacts"][path.relative_to(HERE).as_posix()] = digest(path)
                        if dtype == "float32" and epsilon == 1e-8:
                            row["parent_baseline_match"] = row["final_state_sha256"] == parent_run["arms"][arm]["final_state_sha256"]
                            if not row["parent_baseline_match"]:
                                raise RuntimeError("parent baseline replay mismatch")
                        publish()
        r["status"] = "COMPLETE"; r["finished_at"] = datetime.now(timezone.utc).isoformat(); publish()
    except BaseException as exc:
        r["status"] = "INCOMPLETE" if isinstance(exc, KeyboardInterrupt) else "ERROR"
        r["error"] = f"{type(exc).__name__}: {exc}"; publish(); raise


if __name__ == "__main__":
    execute()
