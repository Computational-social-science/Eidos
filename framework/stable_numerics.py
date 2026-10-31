"""NumPy operators from arXiv:2610.31642v3, Eqs. 5–9.

The final axis contains classes; leading axes are independent examples. Inputs
must be nonempty finite float32/float64 arrays. Outputs retain that dtype and
losses are unreduced (shape ``logits.shape[:-1]``). Cross-entropy functions return
``(loss, gradient)``; the gradient is with respect to logits/student logits only.
Teacher logits are fixed targets. No training experiment is implied by this API.

The stable formulas cannot recover values below the dtype's exponent range, or
differences already rounded away in the input. Unrepresentable log-probabilities
or losses raise FloatingPointError rather than silently returning infinities.
"""

from __future__ import annotations

import numpy as np


def _logits(value, name="logits") -> np.ndarray:
    array = np.asarray(value)
    if array.dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise TypeError(f"{name} must have dtype float32 or float64")
    if array.ndim < 1 or any(size == 0 for size in array.shape):
        raise ValueError(f"{name} must have a nonempty final class axis and batch axes")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _finite(value: np.ndarray, name: str) -> np.ndarray:
    if not np.isfinite(value).all():
        raise FloatingPointError(f"{name} cannot be represented in the input dtype")
    return value


def log_softmax(logits) -> np.ndarray:
    """Eq. 5: exclude exactly one argmax, including when maxima are tied."""
    z = _logits(logits)
    index = np.argmax(z, axis=-1)[..., None]
    maximum = np.take_along_axis(z, index, axis=-1)
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        shifted = z - maximum
        # Setting one exponential to zero retains other tied maxima in the sum.
        others = np.exp(shifted)
        np.put_along_axis(others, index, 0, axis=-1)
        result = shifted - np.log1p(others.sum(axis=-1, keepdims=True))
    return _finite(result, "log_softmax")


def softmax(logits) -> np.ndarray:
    """Exponentiate the fixed log-softmax (probabilities can still round to one)."""
    with np.errstate(under="ignore"):
        return np.exp(log_softmax(logits))


def hard_cross_entropy(logits, target) -> tuple[np.ndarray, np.ndarray]:
    """Eqs. 6–7: unreduced CE and stable gradient for integer hard targets.

    ``target`` must have exactly the leading shape of ``logits`` (a scalar for
    one vector). A max-logit shift avoids overflow even for confidently wrong
    targets. The target derivative is the negative sum of non-target entries,
    rather than subtraction from a probability rounded to one.
    """
    z = _logits(logits)
    targets = np.asarray(target)
    if targets.dtype.kind not in "iu":
        raise TypeError("target must contain integers (not booleans)")
    if targets.shape != z.shape[:-1]:
        raise ValueError("target shape must equal logits.shape[:-1]")
    if np.any(targets < 0) or np.any(targets >= z.shape[-1]):
        raise ValueError("target index is outside the class axis")
    indices = targets.astype(np.intp, copy=False)[..., None]
    logs = log_softmax(z)
    loss = -np.take_along_axis(logs, indices, axis=-1)[..., 0]
    with np.errstate(under="ignore"):
        gradient = np.exp(logs)
    np.put_along_axis(gradient, indices, 0, axis=-1)
    target_gradient = -gradient.sum(axis=-1, keepdims=True)
    np.put_along_axis(gradient, indices, target_gradient, axis=-1)
    return loss, gradient


def logit_distillation(student_logits, teacher_logits) -> tuple[np.ndarray, np.ndarray]:
    """Eqs. 8–9: forward soft-target CE and cancellation-resistant gradient.

    Student and teacher must have identical shape and dtype. Near distributions
    use centered logit deltas, log1p and expm1. For ``abs(log(q/p)) >= 1``, or a
    row whose centered exponential cannot be represented, use the paper's far
    fallback ``q-p``. Finally apply ``u-q*sum(u)``. Equality gives exact zero.
    """
    student = _logits(student_logits, "student_logits")
    teacher = _logits(teacher_logits, "teacher_logits")
    if student.shape != teacher.shape:
        raise ValueError("student and teacher logits must have identical shapes")
    if student.dtype != teacher.dtype:
        raise TypeError("student and teacher logits must have identical dtypes")
    log_q = log_softmax(student)
    with np.errstate(under="ignore"):
        q, p = np.exp(log_q), softmax(teacher)
        loss = -np.sum(p * log_q, axis=-1)
    # Far distributions can overflow delta/expm1 even though q-p is bounded.
    # Contain those intermediates and select the bounded fallback for that row.
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        delta = student - teacher
        d = delta - np.sum(p * delta, axis=-1, keepdims=True)
        normalizer = np.log1p(np.sum(p * np.expm1(d), axis=-1, keepdims=True))
        s = d - normalizer
        near = np.isfinite(s) & (np.abs(s) < 1)
        expm1_s = np.zeros_like(s)
        np.expm1(s, out=expm1_s, where=near)
        u = np.where(near, p * expm1_s, q - p)
        gradient = u - q * np.sum(u, axis=-1, keepdims=True)
    return _finite(loss, "distillation loss"), _finite(gradient, "distillation gradient")
