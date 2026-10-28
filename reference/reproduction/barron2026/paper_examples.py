"""The paper's own examples, run as written.

Reproduction target: Barron, Gnanapragasam & Tschannen, *A fix for softmax and cross-entropy*
(arXiv:2610.31642), Sections 2 and 3. The functions below are the paper's code, copied verbatim from
the listing at the end of each section; nothing is re-derived. Running them produces the numbers the
paper prints, which is the only thing S12 will accept as evidence.

    .venv-repro/Scripts/python.exe reference/reproduction/barron2026/paper_examples.py

The paper prints four significant digits, in fp32 unless stated. Tolerances in the specs are set to
that precision, not to the code's.

What this does NOT test: that JAX's autodiff and the analytic gradient agree beyond this example, or
anything about the training results in Section 4 (Slingshot, grokking) — those need the training
runs, not the kernels.
"""

from __future__ import annotations

import json

import jax
import jax.numpy as jnp
import optax

jax.config.update("jax_enable_x64", True)      # the paper's fp64 reference gradient


def log_softmax(z):
    i_max = jnp.argmax(z, axis=-1)
    z_max = jnp.take_along_axis(z, i_max[..., None], axis=-1)      # Max logit.
    is_max = jax.nn.one_hot(i_max, z.shape[-1], dtype=bool)        # Max mask.
    shifted = jnp.where(is_max, 0.0, z - z_max)                    # Exact 0 at argmax.
    others = jnp.where(is_max, -jnp.inf, shifted)                  # Exclude argmax from sum.
    m = -jax.nn.logsumexp(others, axis=-1, keepdims=True)          # Logit margin.
    return shifted - jax.nn.softplus(-m)                           # log_softmax(z).


softmax = lambda z: jnp.exp(log_softmax(z))


def cross_entropy(z, t):
    z_t = jnp.take_along_axis(z, t[..., None], axis=-1)            # Target logit.
    is_t = jax.nn.one_hot(t, z.shape[-1], dtype=bool)              # Target mask.
    others = jnp.where(is_t, -jnp.inf, z - z_t)                    # Exclude target from sum.
    m = -jax.nn.logsumexp(others, axis=-1)                         # Logit margin.
    return jax.nn.softplus(-m)                                     # -log_softmax(z)_t.


def soft_target_cross_entropy(z_S, z_T):
    log_q = log_softmax(z_S)
    q, p = jnp.exp(log_q), softmax(z_T)
    delta = z_S - z_T                                              # Logit difference.
    d = delta - jnp.sum(p * delta, axis=-1, keepdims=True)         # Center under p.
    s = d - jnp.log1p(jnp.sum(p * jnp.expm1(d), axis=-1, keepdims=True))   # log(q/p).
    u = p * jnp.expm1(s)                                           # Difference q - p.
    g = u - q * jnp.sum(u, axis=-1, keepdims=True)                 # Ensures sum(g) = 0.
    sg = jax.lax.stop_gradient
    loss = -jnp.sum(p * sg(log_q), axis=-1)                        # Forward loss.
    return loss + jnp.sum(sg(g) * (z_S - sg(z_S)), axis=-1)        # Custom gradient g.


def main() -> None:
    out: dict = {}

    # Section 2 example: z = [9, -9, -9], t = 0, fp32.
    z = jnp.array([9.0, -9.0, -9.0], dtype=jnp.float32)
    t = jnp.array(0)
    out["log_softmax"] = [float(v) for v in log_softmax(z)]
    out["softmax_grad_t"] = float(jax.grad(lambda zz: softmax(zz)[0])(z)[0])
    value, grad = jax.value_and_grad(cross_entropy)(z, t)
    out["ce_value"] = float(value)
    out["ce_grad_other"] = float(grad[1])
    out["ce_grad_sum"] = float(jnp.sum(grad))
    std_ce = optax.softmax_cross_entropy_with_integer_labels
    std_value, std_grad = jax.value_and_grad(lambda zz: std_ce(zz, t))(z)
    out["standard_ce_value"] = float(std_value)
    out["standard_ce_grad_t"] = float(std_grad[0])

    # Section 3 example: z_T = [2, 1, 0], z_S = z_T + [-1e-7, 1e-7, 0].
    z_T = jnp.array([2.0, 1.0, 0.0], dtype=jnp.float32)
    z_S = z_T + jnp.array([-1e-7, 1e-7, 0.0], dtype=jnp.float32)
    fixed = jax.grad(soft_target_cross_entropy)(z_S, z_T)
    out["soft_grad"] = [float(v) for v in fixed]

    def std_soft(zs, zt):
        return -jnp.sum(jax.nn.softmax(zt) * jax.nn.log_softmax(zs))

    out["standard_soft_grad"] = [float(v) for v in jax.grad(std_soft)(z_S, z_T)]

    exact = jax.grad(soft_target_cross_entropy)(
        z_S.astype(jnp.float64), z_T.astype(jnp.float64))
    out["exact_grad"] = [float(v) for v in exact]
    out["fixed_max_abs_error"] = float(jnp.max(jnp.abs(fixed.astype(jnp.float64) - exact)))

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
