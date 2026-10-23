# Surrogate reference study

**What this is.** A reference consumer for the empirical branch of Gate S. The system is
`du/dt = λ − u²`, chosen because its fixed point is known in closed form, `u*(λ) = √λ`.
A learned stepper sees only short-time pairs inside `λ ∈ [0.1, 1.0]`; the study then asks
whether it recovers the analytic fixed point on held-out `λ`, and whether the same test
fails when the training labels are shuffled.

**Why it is a fixture rather than a research project.** The truth is known by construction,
so the study can be audited in full and cannot be wrong in the way an open empirical study
can be wrong. It is here to exercise the gate, not to claim a result about the world.

## Results

Across the 19 held-out branches inside the training interval, 19 of 19 recover the analytic
fixed point within 5% relative error; the worst relative error is 2.0e-6; 19 of 19 have
spectral radius below 1 at the recovered point.

The control arm is the same procedure with shuffled training labels: it recovers 1 of 19
within 5% (5.3%), and the worst relative error is 2.14. The audit is therefore capable of
failing.

## What is not claimed

Behaviour outside `λ ∈ [0.1, 1.0]` — a learned stepper has no business asserting it — and
anything about a physical system: the equation is a test bed, not a model of one.
