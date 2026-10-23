# Local neural operators in the Eidos chain

**Reference.** G. Fabiani, H. Vandecasteele, S. Goswami, C. Siettos, I. G. Kevrekidis,
*Enabling Local Neural Operators to perform Equation-Free System-Level Analysis*,
Nature Machine Intelligence (2026), DOI 10.1038/s42256-026-01265-1. Code: MIT,
`Centrum-IntelliPhysics/local-neural-operator-time-stepper-instead-of-just-time-stepper`.

## What is borrowed, and what is not

The paper's contribution is not a more accurate surrogate. It is that a **short-time**
operator, learned from data, can be embedded in *system-level* numerics — fixed points,
stability, branch continuation — so the quantities a scientist actually wants are computed
without writing the PDE down.

Eidos borrows **that layer**, not the implementation:

| borrowed | not borrowed |
|---|---|
| local-in-time training on short pairs `(u_t, u_{t+dt})` | DeepONet / Fourier NO architectures |
| Newton on `psi(u) = S(u) - u`, finite-difference Jacobian | Newton-GMRES at PDE scale |
| spectral radius of `dS/du` as the stability criterion | Arnoldi on 10^5-dimensional states |
| warm-started continuation in a parameter | pseudo-arclength at fold points, gap-tooth |

The rationale is the framework's own rule: **no module without a consumer**. A full NO
stack would be a fourth unwritten location. What ships here is the smallest layer that a
consumer can actually call, plus a gate that proves the layer works.

## Interface

```python
from framework.surrogate import RandomFeatureOperator, fixed_point, spectral_radius, continue_branch

op = RandomFeatureOperator(n_features=256, seed=0).fit(u, u_next, lam)  # short pairs
u_star, info = fixed_point(op.step, lam, u0)          # info["converged"]
rho = spectral_radius(op.step, u_star, lam)           # < 1 -> attracting
branch = continue_branch(op.step, lams, u0)           # fixed point per parameter value
```

`RandomFeatureOperator` is a random-feature ridge regressor on the **increment**: cheap,
deterministic, and honest about being a placeholder for a richer operator.

## Acceptance: a planted truth, not a demo

`tools/audit_surrogate.py` trains on `du/dt = lam - u^2`, whose fixed point `u* = sqrt(lam)`
is known in closed form. The gate requires:

1. **Recovery** — at least 90% of held-out `lam` within 5% relative error;
2. **Stability** — spectral radius below 1 at those fixed points;
3. **A control that can fail** — shuffle the training labels and the same test must
   collapse. Measured: 19/19 recovered and stable; shuffled labels drop to 5%.

The continuation runs **inside** the training interval. A learned stepper has no business
asserting behaviour outside its data, so no extrapolation claim is made.

## What this is not

- Not a claim that token sequences or keystroke streams are C1 function spaces. For
  discrete state the correct analogue is a transfer/Koopman operator, and that is a
  different piece of mathematics.
- Not a solver. The module computes system-level quantities of a *learned map*; it does
  not integrate a PDE.
- Not wired into any project yet. It is exercised by the chain audit and by tests; the
  first intended consumer is the operator-composition fixed-point experiment
  (`docs/OPERATOR_COMPOSITION_PREREG.md`).
