"""Read the four fields before judging them.

The probe showed the model follows rules about the *number* and ignores a rule about a *different
field in the same sentence* (three confounders named, one adjusted, called PASS with the rule in the
prompt). The hypothesis is that the failure is extraction, not judgement: it never forms the
confounder pair.

This module forms the fields, deterministically, and says UNKNOWN when the text does not state them
rather than guessing. `verdict()` then applies the rule the probe labels use, so a verdict here is
checkable against the sentence that produced it.

Nothing in this module calls a model. It is the pre-pass, not the judge.
"""

from __future__ import annotations

import re

REQUIRED_DEFAULT = 0.80
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "none": 0, "no": 0}

ABSENT_POWER = re.compile(
    r"(no power (?:analysis|calculation)"
    r"|power (?:analysis )?(?:is|was) not (?:reported|conducted|performed|done)"
    r"|not report(?:ed)? (?:a )?power"
    r"|no power was)", re.I)

# Any phrasing that puts a decimal near the word "power": "Power: 0.77", "power came to .91",
# "a power of 0.72 was reached", "power analysis returned 0.52".
POWER = re.compile(r"power[^.;]{0,30}?(\d?\.\d+)", re.I)
# "0.45 power" names the achieved value before the word; prefer it over a later target.
POWER_BEFORE = re.compile(r"(\d?\.\d+)\s+power\b", re.I)
REQUIRED = re.compile(r"required[^.;]{0,20}?(\d?\.\d+)", re.I)

DECLARED = re.compile(
    r"(shortfall[^.]{0,40}declared"
    r"|declared[^.]{0,40}(?:before|prior)"
    r"|pre-?specified[^.]{0,30}shortfall"
    r"|shortfall[^.]{0,30}(?:was )?(?:stated|specified|announced))", re.I)
NOT_DECLARED = re.compile(
    r"(no shortfall[^.]{0,30}declared"
    r"|shortfall[^.]{0,30}was not declared"
    r"|nobody declared|never declared|not (?:been )?declared|without (?:a )?declaration)", re.I)

PREREG_ABSENT = re.compile(
    r"(no pre-?registration"
    r"|pre-?registration\s*[:=]?\s*(?:absent|none|no)\b"
    r"|not pre-?registered|never pre-?registered)", re.I)
PREREG_PRESENT = re.compile(
    r"(pre-?registration\s*(?:[:=]|was|is)?\s*(?:present|yes|filed|on file)"
    r"|pre-?registered"
    r"|registered (?:design|protocol)"
    r"|with pre-?registration)", re.I)

CONFOUNDERS = re.compile(
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|none)\s+(?:potential\s+|measured\s+)?"
    r"confounders?\b[^.]*?(?:named|identified|listed|measured|included)", re.I)
ADJUSTED = re.compile(
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|none|both|all)\s*"
    r"(?:of\s+(?:the|them|those)\s*)?(?:confounders?\s+)?(?:are|were|is|was)?\s*"
    r"(?:adjusted|controlled|accounted)", re.I)
# "one confounder was named and adjusted" — the count is stated once, the adjustment inherits it.
ADJUSTED_INHERIT = re.compile(r"confounders?\b[^.]{0,30}(?:and|,)\s*adjusted", re.I)


def _span(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def _count(token: str) -> int:
    token = token.lower()
    return NUMBER_WORDS.get(token, int(token) if token.isdigit() else 0)


def _as_float(raw: str) -> float:
    return float(raw if raw.startswith("0") else "0" + raw)


def extract(text: str) -> dict:
    """Fields plus the span each came from, so a reader can check the reading."""
    fields: dict = {"power": None, "power_absent": False, "required": REQUIRED_DEFAULT,
                    "prereg": None, "named": None, "adjusted": None, "declared": None,
                    "spans": {}}

    absent = ABSENT_POWER.search(text)
    if absent:
        fields["power_absent"] = True
        fields["spans"]["power"] = absent.group(0)
    else:
        m = POWER_BEFORE.search(text) or POWER.search(text)
        if m:
            fields["power"] = _as_float(m.group(1))
            fields["spans"]["power"] = m.group(0)

    m = REQUIRED.search(text)
    if m:
        fields["required"] = _as_float(m.group(1))

    if PREREG_ABSENT.search(text):
        fields["prereg"] = False
        fields["spans"]["prereg"] = _span(PREREG_ABSENT, text)
    elif PREREG_PRESENT.search(text):
        fields["prereg"] = True
        fields["spans"]["prereg"] = _span(PREREG_PRESENT, text)

    m = CONFOUNDERS.search(text)
    if m:
        fields["named"] = _count(m.group(1))
        fields["spans"]["named"] = m.group(0)
    m = ADJUSTED.search(text)
    if m:
        token = m.group(1).lower()
        fields["adjusted"] = 2 if token == "both" else fields.get("named") if token == "all"             else _count(token)
        fields["spans"]["adjusted"] = m.group(0)
    elif fields.get("named") is not None and ADJUSTED_INHERIT.search(text):
        fields["adjusted"] = fields["named"]
        fields["spans"]["adjusted"] = ADJUSTED_INHERIT.search(text).group(0)

    if NOT_DECLARED.search(text):
        fields["declared"] = False
        fields["spans"]["declared"] = _span(NOT_DECLARED, text)
    elif DECLARED.search(text):
        fields["declared"] = True
        fields["spans"]["declared"] = _span(DECLARED, text)

    return fields


def verdict(fields: dict) -> str:
    """The rule from tools/probe_s4.py, applied to extracted fields."""
    if fields.get("power") is None:
        return "FAIL"
    if fields.get("named") is not None and fields.get("adjusted") is not None:
        if fields["adjusted"] < fields["named"]:
            return "FAIL"
    required = fields.get("required") or REQUIRED_DEFAULT
    power = fields["power"]
    if power < required - 0.05:
        return "FAIL"
    if power < required:
        return "WEAK_PASS" if fields.get("declared") else "FAIL"
    return "PASS" if fields.get("prereg") is not False else "WEAK_PASS"


def complete(fields: dict) -> bool:
    """Only the fields the verdict turns on have to be readable.

    An unmatched number is not an absent number: `power_absent` is set only when the text says the
    analysis was not done. A case at 0.83 does not need a declaration it never mentions.
    """
    if fields.get("power") is None:
        return bool(fields.get("power_absent"))
    if fields.get("named") is not None and fields.get("adjusted") is None:
        return False
    required = fields.get("required") or REQUIRED_DEFAULT
    power = fields["power"]
    if power < required - 0.05:
        return True
    if power < required:
        return fields.get("declared") is not None
    return fields.get("prereg") is not None
