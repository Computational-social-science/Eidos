"""Forty S7 cases: twenty-four with one planted defect, sixteen clean.

Twelve cases could not distinguish 0.75 from 0.92 (Wilson [0.646, 0.985]). These are written to make
the interval narrow enough to decide: twenty-four defects spread evenly over the four categories, and
sixteen clean studies that a careless detector would fail.

Labels are by construction — each defective case contains exactly one thing that breaks the claim, and
each clean case contains none. A clean case is not "vague": it states the designs, the numbers and the
verification, so "no objection" is a judgement rather than an absence of information.
"""

from __future__ import annotations

CASES = [
    # ---- statistics (6) -----------------------------------------------------
    ("X-01", "statistics",
     "Claim: the treatment raises recall. Evidence: p = 0.04 with n = 6 per group; twelve comparisons "
     "were run and none was corrected."),
    ("X-02", "statistics",
     "Claim: the design was adequately powered. Evidence: achieved power 0.41 for the claimed effect, "
     "against a pre-registered requirement of 0.80."),
    ("X-03", "statistics",
     "Claim: the groups differ. Evidence: a chi-square test was applied to continuous measurements, "
     "and the reported p = 0.03 is from that test."),
    ("X-04", "statistics",
     "Claim: the effect is 0.45. Evidence: the 95% interval is [0.02, 0.19]; the point estimate in the "
     "table is 0.45."),
    ("X-05", "statistics",
     "Claim: a large effect. Evidence: Cohen's d = 2.1 computed from n = 4 per group, with no interval "
     "reported."),
    ("X-06", "statistics",
     "Claim: the result is significant. Evidence: p = 0.049 after four subgroup splits were tried; only "
     "the significant split is reported."),

    # ---- support (6) --------------------------------------------------------
    ("X-07", "support",
     "Claim: X causes Y. Evidence: the cited paper reports a correlation in a different population and "
     "states that causation was not tested."),
    ("X-08", "support",
     "Claim: the effect replicates. Evidence: the cited replication used a different intervention and a "
     "different outcome measure."),
    ("X-09", "support",
     "Claim: the mechanism is established. Evidence: the citation is a narrative review that calls the "
     "mechanism hypothetical."),
    ("X-10", "support",
     "Claim: the method works in adults. Evidence: the cited study was conducted exclusively in "
     "children aged 6-9."),
    ("X-11", "support",
     "Claim: prior work reported the same 12% gain. Evidence: the cited paper reports 12% but for a "
     "different task and defines the metric differently."),
    ("X-12", "support",
     "Claim: the source supports the safety claim. Evidence: the source discusses efficacy only and "
     "says nothing about safety."),

    # ---- identification (6) -------------------------------------------------
    ("X-13", "identification",
     "Claim: prior work established the baseline. Evidence: the DOI resolves to a different paper by "
     "different authors with a similar title."),
    ("X-14", "identification",
     "Claim: the method follows established practice. Evidence: the cited article was retracted."),
    ("X-15", "identification",
     "Claim: the finding is published. Evidence: the only citation is to a preprint that was later "
     "rejected by the journal and never replaced."),
    ("X-16", "identification",
     "Claim: Smith et al. showed the effect. Evidence: the reference lists Smith, but the quoted "
     "sentence appears in the discussion of a different author's paper in the same volume."),
    ("X-17", "identification",
     "Claim: the instrument is validated. Evidence: the validation citation cannot be resolved in any "
     "index; no DOI, no venue, no year."),
    ("X-18", "identification",
     "Claim: the standard was followed. Evidence: the cited standard is a draft that was superseded "
     "before the study began."),

    # ---- design (6) ---------------------------------------------------------
    ("X-19", "design",
     "Claim: the intervention improved the outcome. Evidence: treatment and control differ by 12 years "
     "in baseline age, and age was not adjusted."),
    ("X-20", "design",
     "Claim: the primary outcome improved. Evidence: the pre-registration names a different primary "
     "outcome; the reported one was chosen after inspection."),
    ("X-21", "design",
     "Claim: the effect is due to the intervention. Evidence: there is no control arm; all participants "
     "received the intervention."),
    ("X-22", "design",
     "Claim: the improvement is real. Evidence: the measurement instrument was changed halfway through "
     "the study and the two halves are pooled."),
    ("X-23", "design",
     "Claim: the programme reduced dropout. Evidence: 31% of the treatment arm left the study and were "
     "excluded from the analysis; the control arm had 4% attrition."),
    ("X-24", "design",
     "Claim: the rating is unbiased. Evidence: the rater knew each participant's condition, and the "
     "outcome is a subjective rating."),

    # ---- clean (16) ---------------------------------------------------------
    ("X-25", None,
     "Claim: the intervention improves recall by 4 points. Evidence: pre-registered; power 0.93; two "
     "confounders named and both adjusted; citation verified and not retracted; independent "
     "replication reported; the 4-point estimate appears in the results table."),
    ("X-26", None,
     "Claim: the effect holds in the sampled population only. Evidence: power 0.88; three confounders "
     "adjusted; claims limited to the sampled population; sources verified."),
    ("X-27", None,
     "Claim: the assay is specific. Evidence: a negative control was included and behaved as expected; "
     "power 0.81; sources verified; no selective reporting declared."),
    ("X-28", None,
     "Claim: the result replicates. Evidence: two independent replications; pre-registered; citations "
     "verified; confounders named and adjusted."),
    ("X-29", None,
     "Claim: the estimate is 0.31. Evidence: 95% interval [0.22, 0.40]; n = 220; the estimate in the "
     "table is 0.31; one primary comparison pre-registered."),
    ("X-30", None,
     "Claim: the difference is significant after correction. Evidence: p = 0.008 with Holm correction "
     "across three pre-registered comparisons; intervals reported."),
    ("X-31", None,
     "Claim: the effect is moderate. Evidence: Cohen's d = 0.48, 95% interval [0.21, 0.75], n = 96 per "
     "arm; the interval excludes zero."),
    ("X-32", None,
     "Claim: the source supports the mechanism. Evidence: the cited experiment manipulates the "
     "mechanism directly and reports the predicted direction."),
    ("X-33", None,
     "Claim: the finding generalises to adults. Evidence: the cited studies include two adult samples "
     "and one adolescent sample, reported separately."),
    ("X-34", None,
     "Claim: the citation is to the original. Evidence: the reference resolves to the original paper; "
     "the review is cited alongside it as secondary."),
    ("X-35", None,
     "Claim: the standard was followed. Evidence: the cited standard is the current version, in force "
     "at the time of the study, and the methods section mirrors it."),
    ("X-36", None,
     "Claim: the groups are comparable. Evidence: randomised; baseline table shows balance on the five "
     "pre-specified covariates; all five adjusted anyway."),
    ("X-37", None,
     "Claim: the outcome is the pre-registered one. Evidence: the pre-registration names it, the "
     "analysis follows the registered plan, and deviations are listed in the supplement."),
    ("X-38", None,
     "Claim: attrition does not explain the result. Evidence: 6% versus 5% attrition, and a sensitivity "
     "analysis treating dropouts as failures keeps the direction."),
    ("X-39", None,
     "Claim: the rating is blinded. Evidence: raters were blinded to condition; blinding success was "
     "checked and reported."),
    ("X-40", None,
     "Claim: the control is adequate. Evidence: placebo control with identical administration, and a "
     "manipulation check confirming participants could not distinguish the arms."),
]
