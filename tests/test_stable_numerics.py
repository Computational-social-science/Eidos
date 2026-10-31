"""Independent high-precision checks for arXiv:2610.31642v3, Eqs. 5–9."""

from decimal import Decimal, localcontext

import numpy as np
import pytest

from framework.stable_numerics import (
    hard_cross_entropy,
    log_softmax,
    logit_distillation,
    softmax,
)


def decimal_reference(student, teacher=None, target=None):
    """Evaluate the mathematical definitions, not the implementation's formulas."""
    with localcontext() as ctx:
        ctx.prec = 400
        z = [Decimal.from_float(float(x)) for x in student]
        normalizer = sum((x - max(z)).exp() for x in z)
        logs = [x - max(z) - normalizer.ln() for x in z]
        q = [x.exp() for x in logs]
        if target is not None:
            p = [Decimal(int(i == target)) for i in range(len(z))]
        else:
            t = [Decimal.from_float(float(x)) for x in teacher]
            total = sum((x - max(t)).exp() for x in t)
            p = [(x - max(t)).exp() / total for x in t]
        loss = -sum(a * b for a, b in zip(p, logs))
        return float(loss), np.array([float(a - b) for a, b in zip(q, p)])


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_native_collapse_is_preserved(dtype):
    z = np.array([9, -9, -9], dtype=dtype)
    loss, gradient = hard_cross_entropy(z, 0)
    expected_loss, expected_grad = decimal_reference(z, target=0)
    assert loss.dtype == gradient.dtype == dtype
    assert loss > 0 and gradient[0] < 0
    np.testing.assert_allclose(loss, expected_loss, rtol=2e-6)
    np.testing.assert_allclose(gradient, expected_grad, rtol=2e-6)
    assert gradient.sum() == 0
    assert log_softmax(z)[0] < 0
    if dtype == np.float32:
        naive = np.exp(z - z.max())
        assert (naive / naive.sum())[0] - 1 == 0


@pytest.mark.parametrize("dtype,margin", [(np.float32, 80), (np.float64, 40), (np.float64, 700)])
def test_high_margin_target_gradient_has_no_absolute_tolerance_floor(dtype, margin):
    z = np.array([margin, 0, 0], dtype=dtype)
    loss, gradient = hard_cross_entropy(z, 0)
    expected_loss, expected_grad = decimal_reference(z, target=0)
    assert gradient[0] < 0 and expected_grad[0] < 0
    np.testing.assert_allclose(loss, expected_loss, rtol=3e-6, atol=0)
    np.testing.assert_allclose(gradient, expected_grad, rtol=3e-6, atol=0)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("values,target", [([2, 2, 0], 1), ([10000, -10000, 0], 1), ([0], 0)])
def test_hard_targets_ties_wrong_extreme_and_single_class(dtype, values, target):
    z = np.array(values, dtype=dtype)
    loss, gradient = hard_cross_entropy(z, target)
    expected_loss, expected_grad = decimal_reference(z, target=target)
    np.testing.assert_allclose(loss, expected_loss, rtol=2e-6, atol=1e-7)
    np.testing.assert_allclose(gradient, expected_grad, rtol=2e-6, atol=1e-7)
    assert np.isfinite(gradient).all()
    np.testing.assert_allclose(softmax(z).sum(), 1, rtol=1e-6)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_distillation_exact_equality(dtype):
    z = np.array([[2, 1, 0], [9, -9, -9], [2, 2, 2]], dtype=dtype)
    loss, gradient = logit_distillation(z, z.copy())
    assert loss.shape == (3,) and loss.dtype == gradient.dtype == dtype
    np.testing.assert_array_equal(gradient, np.zeros_like(z))


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_near_logits_match_decimal(dtype):
    teacher = np.array([2, 1, 0], dtype=dtype)
    student = teacher + np.array([-1e-7, 1e-7, 0], dtype=dtype)
    loss, gradient = logit_distillation(student, teacher)
    expected_loss, expected_grad = decimal_reference(student, teacher=teacher)
    np.testing.assert_allclose(loss, expected_loss, rtol=2e-6)
    np.testing.assert_allclose(gradient, expected_grad, rtol=3e-6, atol=1e-22)
    assert gradient[0] < 0 < gradient[1] and gradient[2] > 0
    assert abs(gradient.sum()) <= np.finfo(dtype).eps * np.max(abs(gradient))


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_far_distributions_stay_finite(dtype):
    s = np.array([[10000, -10000, 0], [0, 10000, -10000]], dtype=dtype)
    t = np.array([[-10000, 10000, 0], [10000, -10000, 0]], dtype=dtype)
    with np.errstate(all="raise"):
        loss, gradient = logit_distillation(s, t)
    assert np.isfinite(loss).all() and np.isfinite(gradient).all()
    for i in range(2):
        expected_loss, expected_grad = decimal_reference(s[i], teacher=t[i])
        np.testing.assert_allclose(loss[i], expected_loss, rtol=2e-6)
        np.testing.assert_allclose(gradient[i], expected_grad, atol=1e-7)


def test_batch_shapes_and_shift_invariance():
    z = np.array([[[2, 1, 0], [9, -9, -9]]], dtype=np.float64)
    loss, grad = hard_cross_entropy(z, np.array([[1, 0]]))
    assert loss.shape == (1, 2) and grad.shape == z.shape
    shifted_loss, shifted_grad = hard_cross_entropy(z + 100, np.array([[1, 0]]))
    np.testing.assert_array_equal(loss, shifted_loss)
    np.testing.assert_array_equal(grad, shifted_grad)
    _, equal_shift = logit_distillation(z + 100, z)
    np.testing.assert_array_equal(equal_shift, np.zeros_like(z))


@pytest.mark.parametrize("bad", [np.array(1.0), np.array([]), np.array([1, 2]), np.array([1.0], dtype=np.float16), np.array([np.nan]), np.array([np.inf])])
def test_invalid_logits(bad):
    with pytest.raises((ValueError, TypeError)):
        log_softmax(bad)


@pytest.mark.parametrize("target", [-1, 3, True, 1.0, np.array([1])])
def test_invalid_targets(target):
    with pytest.raises((ValueError, TypeError)):
        hard_cross_entropy(np.array([2.0, 1.0, 0.0]), target)


def test_distillation_rejects_shape_dtype_and_nonfinite():
    z = np.array([2.0, 1.0, 0.0])
    for teacher in (z[:2], z.astype(np.float32), np.array([np.nan, 1, 0])):
        with pytest.raises((ValueError, TypeError)):
            logit_distillation(z, teacher)


def test_unrepresentable_result_is_an_explicit_error():
    z = np.array([np.finfo(np.float32).max, -np.finfo(np.float32).max], dtype=np.float32)
    with pytest.raises(FloatingPointError, match="cannot be represented"):
        hard_cross_entropy(z, 1)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_seeded_real_vectors_against_independent_decimal(dtype):
    rng = np.random.default_rng(20261031)
    student = rng.normal(size=(7, 5)).astype(dtype)
    teacher = rng.normal(size=(7, 5)).astype(dtype)
    # Includes arbitrary target positions and both close and far distributions.
    student[0] = teacher[0] + np.array([1e-7, 0, -1e-7, 0, 0], dtype=dtype)
    targets = rng.integers(0, 5, size=7)
    loss, gradient = hard_cross_entropy(student, targets)
    distill_loss, distill_gradient = logit_distillation(student, teacher)
    for row in range(7):
        expected_loss, expected_grad = decimal_reference(student[row], target=targets[row])
        np.testing.assert_allclose(loss[row], expected_loss, rtol=3e-6)
        np.testing.assert_allclose(gradient[row], expected_grad, rtol=3e-6, atol=0)
        expected_loss, expected_grad = decimal_reference(student[row], teacher=teacher[row])
        np.testing.assert_allclose(distill_loss[row], expected_loss, rtol=3e-6)
        np.testing.assert_allclose(distill_gradient[row], expected_grad, rtol=1e-5, atol=0)
