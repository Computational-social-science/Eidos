"""Checkpoint-bound endpoint analysis; it cannot reconstruct unrecorded gradients."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.softmax_grokking.common import digest, source_digest


def validate_endpoints(base: Path) -> list[str]:
    """Verify provenance, inventory and count consistency without requiring Torch."""
    try:
        result = json.loads((base / "docs/gradient-endpoints.json").read_text())
        report = json.loads((base / "docs/evidence.json").read_text())
        p = report["protocol"]
        expected = {(s, a, k) for s in p["seeds"] for a in ("standard", "fixed") for k in ("standard", "fixed")}
        rows = result["endpoints"]
        if (result["status"] != "COMPLETE" or len(rows) != len(expected) or
                {(r["seed"], r["training_arm"], r["evaluation_kernel"]) for r in rows} != expected):
            return ["endpoint inventory mismatch"]
        if (result["evidence_sha256"] != digest(base / "docs/evidence.json") or
                result["analysis_source_sha256"] != source_digest(Path(__file__))):
            return ["endpoint provenance mismatch"]
        runtime = result["runtime"]
        if any(runtime.get(k) != report["runtime"].get(k) for k in
               ("torch", "cuda", "device", "dtype", "tf32", "deterministic_algorithms")):
            return ["endpoint runtime mismatch"]
        for r in rows:
            size = int(p["modulus"] ** 2 * p["train_fraction"])
            count = r["zero_target_gradient_count"]
            if (r["sample_count"] != size or type(count) is not int or not 0 <= count <= size or
                    r["zero_target_gradient_fraction"] != count / size or
                    r["checkpoint_sha256"] != digest(base / f"checkpoints/seed-{r['seed']}-{r['training_arm']}.pt")):
                return ["endpoint count or checkpoint mismatch"]
        return []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ["invalid endpoint evidence: " + str(exc)]


def analyze(base: Path) -> dict:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    from torch.nn import functional as F
    from framework.stable_numerics_torch import hard_cross_entropy
    from reference.softmax_grokking.model import Transformer
    from reference.softmax_grokking.common import dataset
    from reference.softmax_grokking.verify import validate

    report = json.loads((base / "docs/evidence.json").read_text())
    p = json.loads((base / "protocol.json").read_text())
    errors = validate(report, p, base=base, extension="parent" in p)
    if errors:
        raise ValueError(errors)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tokens, labels = dataset(p["modulus"])
    rows = []
    for run in report["runs"]:
        seed = run["seed"]
        split = json.loads((base / f"checkpoints/seed-{seed}-split.json").read_text())
        train = split["permutation"][:int(len(labels) * p["train_fraction"])]
        x = torch.tensor(tokens[train], device="cuda")
        y = torch.tensor(labels[train], device="cuda")
        for arm in ("standard", "fixed"):
            checkpoint = base / f"checkpoints/seed-{seed}-{arm}.pt"
            model = Transformer(p["modulus"], p["width"], p["heads"]).cuda()
            model.load_state_dict(torch.load(checkpoint, map_location="cuda", weights_only=True))
            logits = model(x).detach().requires_grad_(True)
            for kernel in ("standard", "fixed"):
                loss = (F.cross_entropy(logits, y) if kernel == "standard" else
                        hard_cross_entropy(logits, y).mean())
                gradient, = torch.autograd.grad(loss, logits)
                target = gradient[torch.arange(len(y), device="cuda"), y]
                if not torch.isfinite(gradient).all():
                    raise ValueError("nonfinite gradient")
                zeros = int((target == 0).sum().item())
                rows.append({"seed": seed, "training_arm": arm, "evaluation_kernel": kernel,
                             "checkpoint_sha256": digest(checkpoint), "sample_count": len(train),
                             "zero_target_gradient_count": zeros,
                             "zero_target_gradient_fraction": zeros / len(train)})
    return {"status": "COMPLETE", "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Final-checkpoint endpoint only; no claim about unrecorded gradient trajectories.",
            "definition": "Target-class derivative of full-training-batch mean CE; both kernels at each saved final model.",
            "evidence_sha256": digest(base / "docs/evidence.json"),
            "analysis_source_sha256": source_digest(Path(__file__)),
            "runtime": {"torch": torch.__version__, "cuda": torch.version.cuda,
                        "device": torch.cuda.get_device_name(), "dtype": "float32",
                        "tf32": False, "deterministic_algorithms": True}, "endpoints": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", choices=("softmax_grokking", "softmax_grokking_extension"))
    args = parser.parse_args()
    base = ROOT / "reference" / args.study
    result = analyze(base)
    (base / "docs/gradient-endpoints.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
