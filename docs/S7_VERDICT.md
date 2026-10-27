# S7: a referee that spots problems and mislabels them

S4 asked for an inequality, and the model got the inequalities wrong with the numbers in front of it.
S7 asks a different question on purpose: find what a referee would object to, and name its category.
Twelve scenarios, eight with one planted defect (two per category), four clean. A defect counts as
found only when a major or fatal objection carries the right category; a clean case counts only when
no major or fatal objection appears — otherwise "object to everything" would score well.

## Result: 9/12 (0.750)

| quantity | value |
|---|---|
| planted defects detected at all (major or fatal) | **8/8** |
| …of which the category was right | 6/8 |
| clean cases left clean | 3/4 |
| exact agreement | 9/12 = **0.750** |

Against the 0.90 bar, not promotable. But the shape of the failure is different from S4, and more
informative:

| case | planted | objection raised | problem |
|---|---|---|---|
| S7-03 | support (correlation presented as causation) | `design` | detected, mislabelled |
| S7-04 | support (replication of a different intervention) | `identification` | detected, mislabelled |
| S7-11 | none — negative control behaved as expected | `design` (major) | **invented an objection** |

## Why the category is not a detail

S7's schema ties each category to the artefact a pointer must land in: `statistics` →
`stat_recompute.json`, `support` → a support record, `identification` → `proofpath.json`
(`framework/verifiers/pointers.py`). A miscategorised objection points at the wrong artefact, so the
pointer check fails and the objection cannot be adjudicated. The model is not merely imprecise here;
it breaks the mechanism that would let a human check it.

And the false positive is worse than a miss: a clean study was failed on an objection that does not
exist. For a gate, that is the expensive direction.

## Decision

1. **S7 stays a human referee.** The model may draft objections for a human to screen — its detection
   rate (8/8) makes that useful — but it does not gate.
2. **No model is a gate component in this framework.** S4 fails arithmetic, S7 fails categorisation
   and specificity. Gate S stays deterministic; the model drafts prose and nothing else.
3. This closes the plan's P2 for S7 as well: 0.750 against 0.90, with the failure mode identified
   rather than averaged away.

## What would change this

A category-constrained decode — ask for one category at a time, or resolve the pointer first and let
the artefact determine the category — would remove the mislabelling by construction. That is a
different architecture, not a better prompt, and it is not attempted here.


## Category fixed by the artefact: 11/12 (0.917), not yet established

The section above ends with a hypothesis: resolve the artefact first, let its type decide the
category, and ask the model only whether that evidence supports the claim. `tools/probe_s7_constrained.py`
does exactly that on the same twelve cases — the model never names a category, so it cannot mislabel
one.

| mode | accuracy | Wilson 95% |
|---|---|---|
| open-ended (model picks category) | 9/12 = 0.750 | [0.468, 0.911] |
| **category fixed by the artefact** | **11/12 = 0.917** | **[0.646, 0.985]** |

Three cases moved up (support read as design, support read as identification, and the invented
objection on a clean study) and one moved down: on S7-09 the model answered that the artefact shows
rigour and replication but does not establish the claimed **four-point** improvement — which is a fair
reading of an artefact that lists the design and never states the magnitude. My label said "supported"
because I wrote the case before the run; the model's objection is arguably better than my label, but I
am not relabelling after seeing the answer.

The honest statistical statement: the point estimate clears 0.90, the **interval does not**. At n = 12
the lower bound is 0.646, and a paired comparison of the two modes (3 improved, 1 worse) gives an exact
McNemar p = 0.625. The direction is right; the evidence is not sufficient to claim the bar is met.

So the policy stays "do not gate on S7" — but the reason changed from *the model cannot do this* to
*this variant might, and twelve cases cannot tell*. Forty cases would put the lower bound near 0.80
even at 0.90 observed; that is the next measurement, not a conclusion.
