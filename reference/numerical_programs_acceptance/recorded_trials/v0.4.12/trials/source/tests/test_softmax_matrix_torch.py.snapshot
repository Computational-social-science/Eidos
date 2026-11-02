"""Qualify the mixed loss/model precision interface against Decimal."""
import numpy as np
import pytest
torch = pytest.importorskip("torch")


@pytest.mark.parametrize("loss_dtype", ["float32", "float64"])
@pytest.mark.parametrize("margin", [18, 40])
def test_loss_cast_returns_accurate_float32_model_gradient(loss_dtype, margin):
    from framework.stable_numerics_torch import hard_cross_entropy
    from framework.verifiers.numerics import probe_hard_cross_entropy
    device = "cuda" if torch.cuda.is_available() else "cpu"
    def candidate(z, target):
        model_logits = torch.tensor(z, device=device, requires_grad=True)
        loss = hard_cross_entropy(model_logits.to(getattr(torch, loss_dtype)), target)
        loss.backward()
        return loss.item(), model_logits.grad.cpu().numpy()
    result = probe_hard_cross_entropy(candidate, np.array([margin, 0, 0], dtype=np.float32), 0)
    assert result["verdict"] == "PASS", result
