"""Optional first-order autograd checks; Torch is not a core dependency."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from framework import stable_numerics as reference
from framework import stable_numerics_torch as stable


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_hard_ce_stable_backward(dtype):
    z = torch.tensor([[9, -9, -9], [10000, -10000, 0], [2, 2, 0]], dtype=dtype, requires_grad=True)
    target = torch.tensor([0, 1, 1])
    loss = stable.hard_cross_entropy(z, target)
    loss.sum().backward()
    expected_loss, expected_grad = reference.hard_cross_entropy(z.detach().numpy(), target.numpy())
    np.testing.assert_allclose(loss.detach().numpy(), expected_loss, rtol=2e-6)
    np.testing.assert_allclose(z.grad.numpy(), expected_grad, rtol=2e-6, atol=1e-15)
    assert z.grad[0, 0] < 0


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_distillation_backward_and_detached_teacher(dtype):
    t = torch.tensor([[2, 1, 0], [10000, -10000, 0]], dtype=dtype, requires_grad=True)
    s = (t.detach() + torch.tensor([[-1e-7, 1e-7, 0], [-20000, 20000, 0]], dtype=dtype)).requires_grad_()
    loss = stable.logit_distillation(s, t)
    loss.sum().backward()
    expected_loss, expected_grad = reference.logit_distillation(s.detach().numpy(), t.detach().numpy())
    np.testing.assert_allclose(loss.detach().numpy(), expected_loss, rtol=2e-6)
    np.testing.assert_allclose(s.grad.numpy(), expected_grad, rtol=4e-6, atol=1e-20)
    assert t.grad is None
    assert torch.isfinite(s.grad).all()


def test_distillation_equality_exact_zero_and_upstream_scaling():
    z = torch.tensor([[2, 1, 0], [9, -9, -9]], dtype=torch.float32, requires_grad=True)
    stable.logit_distillation(z, z.detach()).sum().backward()
    assert torch.count_nonzero(z.grad) == 0
    z.grad.zero_()
    (stable.hard_cross_entropy(z, torch.tensor([0, 0])) * 3).sum().backward()
    _, grad = reference.hard_cross_entropy(z.detach().numpy(), np.array([0, 0]))
    np.testing.assert_allclose(z.grad.numpy(), grad * 3, rtol=2e-6)


def test_log_softmax_autograd_collapse_and_tie():
    z = torch.tensor([9, -9, -9], dtype=torch.float32, requires_grad=True)
    stable.softmax(z)[0].backward()
    assert z.grad[0] > 0
    tied = torch.tensor([2.0, 2.0, 0.0], dtype=torch.float64, requires_grad=True)
    assert torch.autograd.gradcheck(stable.log_softmax, (tied,))


def test_regular_losses_gradcheck():
    s = torch.tensor([1.2, 0.4, -0.7], dtype=torch.float64, requires_grad=True)
    t = torch.tensor([0.8, 0.1, -0.4], dtype=torch.float64)
    assert torch.autograd.gradcheck(lambda x: stable.hard_cross_entropy(x, 1), (s,))
    assert torch.autograd.gradcheck(lambda x: stable.logit_distillation(x, t), (s,))


def test_validation():
    z = torch.tensor([1.0, 2.0])
    for bad in (torch.tensor([1, 2]), torch.tensor([float("nan")]), torch.tensor([])):
        with pytest.raises((TypeError, ValueError)):
            stable.log_softmax(bad)
    for bad in (-1, 2, True, 1.0, torch.tensor([0])):
        with pytest.raises((TypeError, ValueError)):
            stable.hard_cross_entropy(z, bad)
    with pytest.raises(TypeError):
        stable.logit_distillation(z, z.double())


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA runtime unavailable")
def test_cuda_first_order_backward():
    z = torch.tensor([9.0, -9.0, -9.0], device="cuda", requires_grad=True)
    stable.hard_cross_entropy(z, 0).backward()
    assert z.grad[0] < 0 and torch.isfinite(z.grad).all()
