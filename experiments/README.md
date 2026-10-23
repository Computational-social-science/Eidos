# Explorations (not part of the framework)

Code here is exploratory: it is not imported by `framework/`, not run in CI, and not a
gate. It is kept because a negative result is worth more than a deleted file.

## `loops/` + `audit_self_rewrite.py`

An iterated self-rewrite loop (`p_{n+1} = S(p_n)`) as a consumer of the local-operator
layer. Two claims held, one did not:

| claim | result |
|---|---|
| one-step prediction on held-out iterations | **held** — median cosine error 0.117 |
| the learned operator's fixed point matches the observed one | **failed** — agreement 0.44–0.94 |
| shuffled-pair control | caught (test error 0.37) |

The failure is informative: a random-feature operator fitted on a short orbit predicts the
next step well and extrapolates badly when iterated, because Newton walks the map off the
data manifold (the predicted vector's norm drifts to 1.57 from 1.0). Fixed-point claims
therefore need either an on-manifold parameterisation or a richer operator; neither is
justified until a project actually needs it.

**Status:** dormant. Do not promote into `framework/` without a consuming project and a
gate that passes.
