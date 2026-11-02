"""Twenty held-out S7 cases, written after the 40-case failures were seen.

The prompt was changed because of X-23 and X-33, so a re-run on those forty would be a training score,
not evidence. These cases are new, follow the same construction rule (one planted defect or none), and
differ in surface form: shorter evidence, numbers inline, one table-like case. Twelve defects, three
per category; eight clean.
"""

from __future__ import annotations

CASES = [
    # ---- statistics (3) -----------------------------------------------------
    ("H-01", "statistics",
     "Claim: the arms differ on response time. Evidence: medians 410 ms versus 380 ms; n = 5 per arm; "
     "p = 0.06; no interval reported; the claim says 'significantly faster'."),
    ("H-02", "statistics",
     "Claim: the model is better on three benchmarks. Evidence: 14 benchmarks were evaluated, three "
     "were significant at p < 0.05, and only those three are reported."),
    ("H-03", "statistics",
     "Claim: the interaction is real. Evidence: the interaction term has p = 0.21 and the paper "
     "attributes the effect to the interaction."),

    # ---- support (3) --------------------------------------------------------
    ("H-04", "support",
     "Claim: the method is safe in pregnancy. Evidence: the cited trial excluded pregnant "
     "participants and the paper says safety in pregnancy was not assessed."),
    ("H-05", "support",
     "Claim: our throughput gain matches published work. Evidence: the cited work reports latency, "
     "not throughput, and uses different hardware."),
    ("H-06", "support",
     "Claim: the effect is causal. Evidence: the cited study is an observational cohort that adjusted "
     "for measured confounders and explicitly declines a causal reading."),

    # ---- identification (3) -------------------------------------------------
    ("H-07", "identification",
     "Claim: the dataset is the standard benchmark. Evidence: the cited benchmark paper was withdrawn "
     "by its authors before publication."),
    ("H-08", "identification",
     "Claim: the metric is established. Evidence: the reference points to a blog post with no author, "
     "no date, and a dead link."),
    ("H-09", "identification",
     "Claim: the technique originates in Jones 2019. Evidence: the same technique appears in a 2016 "
     "paper by a different group, which is not cited."),

    # ---- design (3) ---------------------------------------------------------
    ("H-10", "design",
     "Claim: the training helps. Evidence: participants who completed all sessions improved more than "
     "those who dropped out; completers are compared with dropouts."),
    ("H-11", "design",
     "Claim: the measured improvement is due to the tool. Evidence: the tool was introduced in the "
     "same week as a workflow change, and both are attributed to the tool."),
    ("H-12", "design",
     "Claim: the annotation is reliable. Evidence: two annotators labelled the same items, agreement "
     "was computed after adjudication, and the adjudicated labels are reported as the reliability "
     "estimate."),

    # ---- clean (8) ----------------------------------------------------------
    ("H-13", None,
     "Claim: the effect is 0.12 with interval [0.04, 0.20]. Evidence: n = 180 per arm; pre-registered "
     "primary outcome; one comparison; estimate and interval reported as stated."),
    ("H-14", None,
     "Claim: the sample is representative. Evidence: random sampling from the frame; response rate "
     "71%; non-response analysis reported and null."),
    ("H-15", None,
     "Claim: the citation supports the definition. Evidence: the definition is quoted verbatim from "
     "the cited paper, page and section given."),
    ("H-16", None,
     "Claim: the control is a true control. Evidence: same task, same duration, no feedback content; "
     "participants could not tell the arms apart on a manipulation check."),
    ("H-17", None,
     "Claim: the effect persists at follow-up. Evidence: follow-up at 6 months, 88% retained, effect "
     "size 0.18 with interval excluding zero."),
    ("H-18", None,
     "Claim: the model comparison is fair. Evidence: same prompts, same decoding settings, same "
     "hardware budget, three seeds per model, intervals across seeds."),
    ("H-19", None,
     "Claim: the measure is validated. Evidence: the validation study is cited with DOI, reports "
     "convergent validity against two established measures."),
    ("H-20", None,
     "Claim: the finding is not an artefact of the analysis. Evidence: the pre-registered analysis is "
     "reported alongside two alternative specifications, all three in the same direction."),
]
