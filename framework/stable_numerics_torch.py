"""Optional PyTorch counterpart of :mod:`framework.stable_numerics`.

Install Torch independently in a consumer environment; Eidos does not require it.
Functions use the last class axis, preserve float32/float64 and device, and return
unreduced losses. Unlike the NumPy API, CE functions return a differentiable loss
Tensor: ``loss.sum().backward()`` computes the stable student gradient. Teacher
logits are detached. Custom CE backwards support first-order differentiation;
higher-order derivatives are deliberately unsupported.

Reference: https://arxiv.org/html/2610.31642v3 (Eqs. 5–9).
"""

from __future__ import annotations

import torch
from torch.autograd.function import once_differentiable


def _logits(value, name="logits"):
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must be a torch.Tensor")
    if value.dtype not in (torch.float32, torch.float64):
        raise TypeError(f"{name} must have dtype float32 or float64")
    if value.ndim < 1 or any(size == 0 for size in value.shape):
        raise ValueError(f"{name} must have nonempty class and batch axes")
    if not bool(torch.isfinite(value).all()):
        raise ValueError(f"{name} must contain only finite values")
    return value


def _finite(value, name):
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(f"{name} cannot be represented in the input dtype")
    return value


def log_softmax(logits):
    """Eq. 5 with exactly one argmax excluded, retaining tied maxima."""
    z = _logits(logits)
    index = z.argmax(dim=-1, keepdim=True)
    mask = torch.zeros_like(z, dtype=torch.bool).scatter(-1, index, True)
    shifted = torch.where(mask, 0, z - z.gather(-1, index))
    others = torch.where(mask, 0, shifted.exp())
    return _finite(shifted - others.sum(dim=-1, keepdim=True).log1p(), "log_softmax")


def softmax(logits):
    """Fixed differentiable softmax, including the dominant-class derivative."""
    return log_softmax(logits).exp()


class _HardCrossEntropy(torch.autograd.Function):
    @staticmethod
    def forward(ctx, z, targets):
        index = targets.unsqueeze(-1)
        logs = log_softmax(z)
        gradient = logs.exp().scatter(-1, index, 0)
        gradient.scatter_(-1, index, -gradient.sum(dim=-1, keepdim=True))
        ctx.save_for_backward(gradient)
        return -logs.gather(-1, index).squeeze(-1)

    @staticmethod
    @once_differentiable
    def backward(ctx, upstream):
        (gradient,) = ctx.saved_tensors
        return gradient * upstream.unsqueeze(-1), None


def hard_cross_entropy(logits, target):
    """Eqs. 6–7: unreduced hard-target CE with stable first-order backward."""
    z = _logits(logits)
    targets = torch.as_tensor(target, device=z.device)
    if targets.dtype not in (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64):
        raise TypeError("target must contain integers (not booleans)")
    if targets.shape != z.shape[:-1]:
        raise ValueError("target shape must equal logits.shape[:-1]")
    if bool(((targets < 0) | (targets >= z.shape[-1])).any()):
        raise ValueError("target index is outside the class axis")
    return _HardCrossEntropy.apply(z, targets.long())


class _LogitDistillation(torch.autograd.Function):
    @staticmethod
    def forward(ctx, student, teacher):
        log_q = log_softmax(student)
        q, p = log_q.exp(), softmax(teacher)
        loss = -(p * log_q).sum(dim=-1)
        delta = student - teacher
        d = delta - (p * delta).sum(dim=-1, keepdim=True)
        s = d - (p * d.expm1()).sum(dim=-1, keepdim=True).log1p()
        near = torch.isfinite(s) & (s.abs() < 1)
        # Do not evaluate expm1 on overflowing s in the unselected branch.
        near_s = torch.where(near, s, 0)
        u = torch.where(near, p * near_s.expm1(), q - p)
        gradient = u - q * u.sum(dim=-1, keepdim=True)
        ctx.save_for_backward(_finite(gradient, "distillation gradient"))
        return _finite(loss, "distillation loss")

    @staticmethod
    @once_differentiable
    def backward(ctx, upstream):
        (gradient,) = ctx.saved_tensors
        return gradient * upstream.unsqueeze(-1), None


def logit_distillation(student_logits, teacher_logits):
    """Eqs. 8–9: unreduced CE, stable custom backward, detached teacher."""
    student = _logits(student_logits, "student_logits")
    teacher = _logits(teacher_logits, "teacher_logits")
    if student.shape != teacher.shape:
        raise ValueError("student and teacher logits must have identical shapes")
    if student.dtype != teacher.dtype or student.device != teacher.device:
        raise TypeError("student and teacher logits must have identical dtypes and devices")
    return _LogitDistillation.apply(student, teacher.detach())
