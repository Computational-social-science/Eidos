# DEMO · Is a reworded question the same question?

This is the onboarding demo. It measures one thing, reports it with an interval, and states what
it cannot support. If you are copying this project, the useful part is the shape, not the result.

## What was measured

Twelve short states, each paired with one canonical question and two rewordings that ask the same
thing. The operator answers all three; a verbatim repeat of the canonical wording follows, as a
control that would fail if the operator were stochastic.

Across the twelve items, agreement across the three wordings is 1.000. The lower bound of the
95% Wilson interval is 0.758: twelve successes constrain the rate far less than the point estimate
suggests, and the report says so rather than rounding to certainty.

The verbatim repeat agrees with the first answer in every item (1.000). That is the control: had
it fallen below one, the agreement measure would be partly sampling noise and the first claim
would mean less than it appears to.

Chance for three options is 0.333, so the agreement is not the arithmetic of guessing — but the
items are easy and share a template, which is the limitation below.

## What this does not show

- **Ceiling**: 12/12 with a lower bound of 0.758 is consistent with a true agreement as low as
  three in four. The demo demonstrates the instrument, not a property of the operator.
- **No human labels**: agreement between wordings is not agreement with a reader. Nothing here
  speaks to whether the answer is right.
- **One model, one prompt shape, twelve items**: the scope block says exactly this, and Gate S
  refuses a claim whose scope is silent.

## Why it is a demo

Every claim above cites a number that a script wrote, not a number typed by hand. Change the
items, re-run `build_evidence.py`, and the register's values stop matching the artefact — Gate S
fails until both are updated. That is the onboarding lesson: the evidence and the sentence are
one object.
