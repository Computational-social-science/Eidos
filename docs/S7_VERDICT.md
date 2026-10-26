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
