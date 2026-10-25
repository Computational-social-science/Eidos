"""DEMO · does the operator give the same answer when a question is reworded?

This is the template project. It exists to be copied: every file a new project needs is here,
and nothing else is. It is also a real measurement — twelve states, three wordings each, plus a
verbatim repeat of the first wording as a determinism control.

    python build_evidence.py          # ~40 calls, a few seconds
    exit 0 measured · 3 operator unavailable (the registry maps this to SKIP)

The measurement is intentionally small: an onboarding demo that takes ten minutes to run is a
demo nobody runs. The claims it registers are the claims it can support at this size, and the
report says so.
"""

from __future__ import annotations

import datetime
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def eidos_root(start: Path) -> Path:
    """Find the framework, wherever this project was copied to.

    A fixed ../.. works only while the project sits inside the repository. The template has to
    survive being copied anywhere, so it walks up until it sees framework/decision.py.
    """
    override = os.environ.get("EIDOS_ROOT")
    if override:
        return Path(override).resolve()
    for parent in (start, *start.parents):
        if (parent / "framework" / "decision.py").is_file():
            return parent
    raise SystemExit("cannot locate Eidos: set EIDOS_ROOT to the repository root")


ROOT = eidos_root(HERE)
OUT = HERE / "docs" / "evidence.json"
sys.path.insert(0, str(ROOT))

from framework.decision import DecisionClient, DecisionUnavailable  # noqa: E402

OPTIONS = {"yes": "the state establishes this as true",
           "no": "the state establishes this as false",
           "not_stated": "the state does not say"}

#: (state, canonical question, two rewordings). The three must ask the same thing; if they do
#: not, the measure is about the item set, not about the operator.
ITEMS = [
    ("Trial 7 recorded 412 crates in the east wing.",
     "Did trial 7 record more than 400 crates?",
     "Were more than 400 crates recorded in the east wing for trial 7?",
     "Trial 7: were there over 400 crates in the east wing?"),
    ("The sample was stored at 4 degrees Celsius.",
     "Was the sample stored below 0 degrees Celsius?",
     "Was the storage temperature of the sample under 0 degrees Celsius?",
     "Did the sample see temperatures under 0 degrees Celsius in storage?"),
    ("Nine of the eleven participants completed the second session.",
     "Did all eleven participants complete the second session?",
     "Was the second session completed by every one of the eleven participants?",
     "Did every participant finish session two?"),
    ("The instrument was recalibrated on 3 March 2025.",
     "Was the instrument recalibrated in 2024?",
     "Did the recalibration of the instrument happen during 2024?",
     "Was there a recalibration in the year 2024?"),
    ("The east wing reported 412 crates; the west wing reported 380.",
     "Did the west wing report more crates than the east wing?",
     "Were more crates reported by the west wing than by the east wing?",
     "Which wing reported more crates: did the west exceed the east?"),
    ("Batch B failed the purity threshold on the first pass.",
     "Did batch B pass the purity threshold on the first pass?",
     "On the first pass, did batch B meet the purity threshold?",
     "Was the purity threshold met by batch B the first time?"),
    ("The protocol specifies a 12-hour fasting window.",
     "Does the protocol specify a fasting window longer than 24 hours?",
     "Is the fasting window in the protocol more than 24 hours?",
     "Does the protocol call for fasting beyond 24 hours?"),
    ("The survey ran from June to August 2023.",
     "Did the survey run into September 2023?",
     "Was the survey still running during September 2023?",
     "Did the survey extend past August, into September 2023?"),
    ("Two of the four reactors were offline.",
     "Were all four reactors online?",
     "Was every one of the four reactors online?",
     "Were all four reactors running?"),
    ("The dataset contains 1,204 labelled frames.",
     "Does the dataset contain more than 2,000 labelled frames?",
     "Are there over 2,000 labelled frames in the dataset?",
     "Does the dataset hold more than two thousand labelled frames?"),
    ("The second assay gave the same result as the first.",
     "Did the two assays disagree?",
     "Was there a disagreement between the two assays?",
     "Did assay one and assay two disagree?"),
    ("The control group received a placebo.",
     "Did the control group receive the treatment?",
     "Was the treatment given to the control group?",
     "Did the control group get the treatment rather than a placebo?"),
]


def ask(client: DecisionClient, state: str, question: str) -> str:
    """One choice among the three option labels, with the state as evidence."""
    return str(client.choose(question, OPTIONS, state).choice)


def main() -> int:
    try:
        client = DecisionClient()
    except DecisionUnavailable as exc:
        print(f"operator unavailable: {exc}")
        return 3

    rows = []
    for state, canonical, second, third in ITEMS:
        answers = [ask(client, state, q) for q in (canonical, second, third)]
        repeat = ask(client, state, canonical)
        rows.append({"state": state, "canonical": canonical, "answers": answers,
                     "repeat": repeat, "all_agree": len(set(answers)) == 1,
                     "repeat_agrees": repeat == answers[0]})

    n = len(rows)
    successes = sum(1 for r in rows if r["all_agree"])
    agreement = successes / n
    repeat_agreement = sum(1 for r in rows if r["repeat_agrees"]) / n

    # Wilson interval: with 12/12 the point estimate is 1.0 and says nothing about the rate;
    # the lower bound is the only number here that carries information.
    z = 1.959964
    centre = (successes + z * z / 2) / (n + z * z)
    half = z * math.sqrt(successes * (n - successes) / n + z * z / 4) / (n + z * z)
    ci_low, ci_high = max(0.0, centre - half), min(1.0, centre + half)

    data = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "n_items": n,
        "n_calls": 4 * n,
        "agreement": round(agreement, 3),
        "repeat_agreement": round(repeat_agreement, 3),
        "chance": round(1 / len(OPTIONS), 3),
        "agree_count": successes,
        "ci_low": round(ci_low, 3),
        "ci_high": round(ci_high, 3),
        "items": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{n} items, {4 * n} calls · agreement {successes}/{n} = {agreement:.3f} "
          f"(Wilson 95% [{ci_low:.3f}, {ci_high:.3f}]) · repeat {repeat_agreement:.3f} · "
          f"chance {data['chance']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
