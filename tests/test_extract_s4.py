"""What the S4 investigation actually established, and what the gate should do about it.

Arc: the prose probe scored 11/15 with every miss being an ignored field; the prompt rewrite moved
nothing on holdout; extraction on unseen paraphrases is 7/10 but never confidently wrong; giving the
model the fields themselves reaches 13/15 — and the two remaining misses are the confounder
comparison and the 0.75 floor, both still wrong with the numbers in front of it.

That last fact decides the design: those checks are arithmetic, so they belong to a rule engine over
an artefact, not to a model. The model is demoted from S4 judge to nothing on the rule-shaped part.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import probe_s4  # noqa: E402
from framework.verifiers import extract_s4  # noqa: E402

# Written after the extractor was tuned on an earlier set: this is the generalisation measurement.
UNSEEN = [
    ("U1", "With 0.45 power against a target of 0.80, the study was underpowered; the protocol was "
           "registered.", "FAIL"),
    ("U2", "The design achieved power of 0.82 and was registered in advance; four confounders were "
           "listed, and four were held constant.", "PASS"),
    ("U3", "Power reached 0.76; no shortfall statement appears anywhere; the analysis plan was not "
           "registered.", "FAIL"),
    ("U4", "Power reached 0.76; the protocol declared the shortfall prior to data collection; "
           "registration was completed.", "WEAK_PASS"),
    ("U5", "Power is 0.89; two confounders were identified and only one was adjusted; the study was "
           "pre-registered.", "FAIL"),
    ("U6", "Power is 0.89; three confounders were identified and all were adjusted; no pre-registration "
           "is on file.", "WEAK_PASS"),
    ("U7", "The paper presents no power analysis at all; two confounders were adjusted out of two "
           "named.", "FAIL"),
    ("U8", "Power of 0.81 was obtained, the design was pre-registered, and the single confounder named "
           "was also adjusted.", "PASS"),
    ("U9", "Power of 0.70 with the shortfall declared in advance and a registered protocol; two "
           "confounders named, two adjusted.", "FAIL"),
    ("U10", "Power of 0.77, no declaration of any shortfall, protocol registered; one confounder "
            "named, one adjusted.", "FAIL"),
]


def test_the_rule_engine_matches_every_template_case():
    """The fifteen probe cases state their fields in a fixed shape; on those, the rule is exact."""
    for case in probe_s4.CASES:
        fields = extract_s4.extract(probe_s4.prompt(case))
        assert extract_s4.complete(fields), case["id"]
        assert extract_s4.verdict(fields) == probe_s4.label(case), case["id"]


def test_unseen_prose_is_read_seven_times_in_ten():
    """Free prose is not a reliable input for a rule engine, and the number is recorded, not hidden."""
    correct = 0
    for _, text, want in UNSEEN:
        fields = extract_s4.extract(text)
        if extract_s4.complete(fields) and extract_s4.verdict(fields) == want:
            correct += 1
    assert correct == 7


def test_it_never_fails_confidently():
    """The safety property: an unreadable case is INCOMPLETE, never a confident wrong verdict.

    A rule engine that says "I could not read this" is usable; one that guesses is worse than the
    model it replaced.
    """
    confident_wrong = []
    for cid, text, want in UNSEEN:
        fields = extract_s4.extract(text)
        if extract_s4.complete(fields) and extract_s4.verdict(fields) != want:
            confident_wrong.append(cid)
    assert confident_wrong == []


def test_a_target_is_not_an_achieved_value():
    """"0.45 power against a target of 0.80" must read 0.45; reading the target is a silent error."""
    fields = extract_s4.extract(
        "With 0.45 power against a target of 0.80, the study was underpowered; the protocol was "
        "registered.")
    assert fields["power"] == 0.45
