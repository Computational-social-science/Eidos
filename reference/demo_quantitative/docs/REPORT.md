# DEMO · A planted truth, and an estimator that must fail

The effect is known by construction: theta = 0.5. The honest estimator is the difference in means;
the corrupted one is the same interval shifted by +0.30. Both are run on identical simulated data
over 400 replications of 200 observations.

Across those simulations the interval covers the planted effect in 0.927 of runs. The corrupted
estimator covers the planted effect in 0.432 of runs — less than half, which is what a measurement
that can fail looks like. A pipeline that reported both as acceptable would be blind, and no
amount of prose would repair that.

The bias of the honest estimator is -0.0076, and the acceptance gate requires it to stay within
0.05 in absolute value. Every threshold states its direction: coverage must be at least 0.90, the
corrupted coverage at most 0.60, and the bias at most 0.05. A bare number would pass the corrupted
case by reading "at most" as "at least".

## What this does not show

- **No real data.** The truth is planted, so this measures the instrument, not a phenomenon.
- **A known variance.** The interval uses the true sigma; an estimated variance would widen it.
- **One corruption.** A different shift would give a different corrupted rate.

## Why it is a demo

The measurement, the acceptance gate and the rendered document are all produced by the project's
own gate command. `show_vacuous.py` then demonstrates the complementary failure: a gate command
that exits 0 and writes nothing is refused because the registry declares what it must leave behind.
