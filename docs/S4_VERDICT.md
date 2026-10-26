# S4: what the model can judge, and what it cannot

Question: can ScienceRSI-8b.i1-Q4_K_M decide S4 (design validity) well enough to gate on — the plan's
P2, with a promotion bar of 0.90? Four measurements on this host, in the order they were run.

## 1. Prose, zero-shot — 11/15 (0.733)

Fifteen labelled cases (`tools/probe_s4.py`), labels computed from the case fields by a stated rule,
not assigned by eye. The split matters more than the total:

| decided by | agreement |
|---|---|
| the headline power number (9 cases) | 9/9 |
| a qualification — declaration, pre-registration, confounders, the 0.75 floor (6 cases) | 2/6 |

## 2. Prompt rewrite — no gain on holdout

Stating the five clauses explicitly, then greedy demonstration selection on 10 train cases, judged on
5 held-out cases: **train 7→8, holdout 4/5 → 4/5**. Clauses about the number took effect; the clause
about the confounder count did not.

## 3. Extraction from prose — 7/10, fail-safe

`framework/verifiers/extract_s4.py` reads the four fields and refuses to guess. On the fifteen
template cases it is exact (15/15, circular — the patterns were written against that shape). On ten
paraphrases written after tuning it scores **7/10**, and the decisive property is that it is *never
confidently wrong*: every failure returns INCOMPLETE rather than a verdict. A reader gets "I could
not read this", which is usable; a wrong verdict would be worse than the model it replaces.

This is also why S4 must consume a structured artefact (`stat_recompute.json`-shaped), not prose: a
gate cannot rest on a 70% reader.

## 4. Structured fields, same model — 13/15 (0.867)

The same fifteen cases, same model, same rule, but with the fields handed over as JSON:

| input | agreement |
|---|---|
| prose | 11/15 |
| structured fields | **13/15** |

Two misses moved (the undeclared shortfall and the missing pre-registration), which supports the
extraction hypothesis for those. Two did not:

* `s4-06` — `confounders_named: 3, confounders_adjusted: 1` → the model answers **PASS**;
* `s4-08` — `power: 0.74` with a declared shortfall → the model answers **WEAK_PASS**, applying the
  declaration below the 0.75 floor where it does not belong.

Structured calls are also far cheaper: the engine logged ~128 ms and 7 output tokens per structured
judgement, against 620–1000 ms for the prose prompt, because the answer is a label rather than a
justification.

Both misses are comparisons between numbers it was given. That is not a reading failure and not a prompting
failure; it is the model declining to apply an inequality.

## Decision

1. **S4's rule-shaped checks are deterministic.** The comparison lives in
   `extract_s4.verdict()` and reads a structured artefact. A gate on arithmetic may not depend on a
   model that gets arithmetic wrong with the numbers in front of it.
2. **ScienceRSI is not promoted as the S4 judge.** P2 closes as a **negative result** for this use:
   0.867 < 0.90 with clean input. No prompt compile, no weight change, no "try again with more
   examples".
3. **What the model is still for** is the part no rule covers — whether a design answers the question
   it claims to, whether a confounder list is complete. That is not measured here, and it is not
   allowed to override a verifier artefact when it is.

## What would change this

A behavioural probe on a **different** rule family (S7 objection triage) where the answer is not an
inequality. If the model fails that too, the honest conclusion is that this model is not a gate
component at all — and the framework says so rather than routing around it.
