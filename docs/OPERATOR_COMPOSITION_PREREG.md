# Pre-registration — operator composition and its fixed points

**Status:** draft, not yet registered. This document is the consumer that justifies the
local-operator layer (`framework/surrogate`); it is written before any code runs, and its
predictions are stated so that they can fail.

## Motivation

Proposition A of the keystroke study measures a **single** damage event: one typo, one
restoration, one model response. Real use is a loop — a person types, a model answers, the
person types again — and nothing in the current design says what happens to the error rate
under repetition.

The equation-free literature supplies the right object. If `S` is one cycle (damage →
restoration), the error rate after `n` cycles is `S^n`. The questions a scientist actually
asks are system-level:

- does `S` have a **fixed point** — an error rate that reproduces itself?
- is that fixed point **stable** — does a perturbation decay?
- does the fixed point **disappear** at some operator mixture — a tipping point?

These are the same three questions the local-NO layer answers for a PDE, applied to a
discrete loop instead. That is the whole reason the layer exists in this framework.

## Design

**Unit of analysis:** a prompt–response pair under repeated exposure. `S` is defined on a
state vector `u = (error rate, mean edit count, token survival)`.

**Operator (mixture):** the per-cycle damage is drawn from a mixture with weight `α` on
adjacent-key substitution and `1 − α` on real-word substitution, severity held at the
matched level used in the confirmatory study (`k = 2`).

**Independent variable:** `α ∈ {0.0, 0.25, 0.5, 0.75, 1.0}`.

**Cycles:** `n = 8`, with `u_0` measured on clean input.

**Estimand:** the per-`α` map `S_α`, estimated by fitting the short-cycle operator on
cycles 1–4 and testing on 5–8 (local-in-time training, out-of-sample composition).

**Primary outcome:** existence and location of a fixed point `u*` with
`||S_α(u*) − u*|| < 1e-3`, and its spectral radius `ρ(α)`.

## Predictions (falsifiable, stated before running)

- **P1.** A fixed point exists for every `α` in the grid. *Falsified if* any `α` yields no
  converged fixed point from three starting states.
- **P2.** `ρ(α)` is increasing in `α`. *Falsified if* the ordering is violated at any
  adjacent pair after Holm correction.
- **P3.** There is a critical `α*` above which `ρ > 1` (the loop no longer absorbs a
  perturbation). *Falsified if* `ρ < 1` at `α = 1` or `ρ > 1` at `α = 0`.
- **P4.** The fixed-point error rate is higher than the one-shot rate from Proposition A.
  *Falsified if* the interval for `u*[0]` lies below the one-shot estimate.

## Analysis

- Fixed points by Newton on `ψ(u) = S_α(u) − u`; stability by the spectral radius of the
  finite-difference Jacobian (both in `framework/surrogate`).
- Bootstrap over prompts (1,000 resamples) for intervals on `u*` and `ρ`.
- Holm across the five `α` values for P2; P3 is a single ordered test.
- **Negative control:** a sham mixture that permutes the operator labels within cycle must
  show no monotone `ρ(α)`. If it does, the design cannot separate mixture from noise and
  the experiment is void.

## What would make this paper-worthy

A stable fixed point whose spectral radius crosses 1 at a mixture we can name would turn
"typing noise has a signature" into "the signature has a **tipping point** under repeated
exposure" — an irreversible-transition claim of the kind NHB publishes, and one that does
not require a second language corpus to be interesting.

## Honest limits

- The state vector is hand-chosen; a different `u` may have different fixed points.
- Eight cycles is short; a fixed point may be transient.
- The operator is fit on synthetic damage, not on real user sessions. The WildChat
  replication (referee objection O5) remains the ecological test.
