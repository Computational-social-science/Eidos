"""Independently reload each final model and replay the two gradient interfaces."""
from __future__ import annotations
import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
from datetime import datetime, timezone
import json
import math
import platform
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    import torch
    from torch.nn import functional as F
    from framework.stable_numerics_torch import hard_cross_entropy
    from reference.softmax_grokking.model import Transformer
    from reference.softmax_grokking.common import dataset, digest, source_digest
    from reference.softmax_matrix.verify import validate
    r = json.loads((HERE / "docs/evidence.json").read_text()); p = r["protocol"]
    errors = validate(r, json.loads((HERE / "protocol.json").read_text()))
    if errors:
        raise ValueError(errors)
    target = HERE / "docs/final-gradient-check.json"
    if target.exists():
        raise FileExistsError("Keep the previous check; register a separate analysis for a rerun")
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_num_threads(4)
    runtime = {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__,
               "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(), "device_type": "cuda",
               "model_dtype": "float32", "tf32": torch.backends.cuda.matmul.allow_tf32,
               "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
               "amp": torch.is_autocast_enabled()}
    if runtime != r["runtime"]:
        raise RuntimeError("Final check must use the recorded runtime")
    tokens, labels = dataset(p["modulus"])
    parent_base = (ROOT / p["parent"]).parents[1]
    rows = []
    for v in r["runs"]:
        seed, dtype, eps, arm = (v[k] for k in ("seed", "loss_dtype", "epsilon", "arm"))
        split = json.loads((parent_base / f"checkpoints/seed-{seed}-split.json").read_text())
        train = split["permutation"][:int(len(labels) * p["train_fraction"])]
        x = torch.tensor(tokens[train], device="cuda"); y = torch.tensor(labels[train], device="cuda")
        model = Transformer(p["modulus"], p["width"], p["heads"]).cuda()
        checkpoint = HERE / (v["checkpoint_stem"] + ".pt")
        model.load_state_dict(torch.load(checkpoint, map_location="cuda", weights_only=True))
        with torch.no_grad():
            represented = model(x)
        z = represented.detach().requires_grad_(True)
        q = z.to(getattr(torch, dtype)); q.retain_grad()
        loss = hard_cross_entropy(q, y).mean() if arm == "fixed" else F.cross_entropy(q, y)
        loss.backward()
        if not torch.isfinite(loss) or not torch.isfinite(q.grad).all() or not torch.isfinite(z.grad).all():
            raise FloatingPointError(f"Nonfinite final loss/gradient: {(seed, dtype, eps, arm)}")
        idx = torch.arange(len(y), device="cuda")
        observed = {"zero_target_loss": int((q.grad[idx, y] == 0).sum().item()),
                    "zero_target_model": int((z.grad[idx, y] == 0).sum().item())}
        final = v["checkpoints"][-1]
        matched = all(observed[k] == final[k] for k in observed) and math.isclose(loss.item(), final["training_loss"], rel_tol=1e-14, abs_tol=0)
        rows.append({"seed": seed, "loss_dtype": dtype, "epsilon": eps, "arm": arm, **observed,
                     "training_loss": loss.item(), "all_finite": True,
                     "checkpoint_sha256": digest(checkpoint), "matches": matched})
    result = {"status": "PASS" if all(v["matches"] for v in rows) else "FAIL",
              "generated_at": datetime.now(timezone.utc).isoformat(), "runtime": runtime,
              "evidence_sha256": digest(HERE / "docs/evidence.json"),
              "analysis_source_sha256": source_digest(Path(__file__)),
              "scope": "Final gradients independently reloaded on the recorded CUDA runtime; intermediate counts remain producer-recorded trajectories.",
              "checks": rows}
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "checks": len(rows)}))
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
