"""Typed decisions from the shared StartLux operator.

WHY THIS MODULE EXISTS
    The framework asks many yes/no and choice questions per run: which branch to
    take, whether a gate failure is methodological or environmental, whether a
    hypothesis survives screening. A general 7B-8B generator answers by writing
    prose, which is then parsed back into a decision, and its confidence has to be
    calibrated separately.

    StartLux-Decision is trained for the decision itself and returns the answer
    typed: `choice`, `noul` (yes/no probability) or `score`, with per-option
    probabilities and a `none_probability` in one response. One forward pass, no
    parsing.

NO SILENT FALLBACK
    If the service is unreachable this raises `DecisionUnavailable`. A caller may
    escalate to a human gate or skip the decision, but it must say so. Returning a
    regex or a general model's guess under the name "decision" is the defect this
    module exists to prevent.

LICENCE
    The weights are CC BY-NC 4.0 (non-commercial). This client is stdlib-only and
    carries no model; the operator is deployed once, outside any project, at
    $DECISION_SERVICE_URL (default http://127.0.0.1:8090).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

DEFAULT_URL = os.environ.get("DECISION_SERVICE_URL", "http://127.0.0.1:8090")
DEFAULT_TIMEOUT = float(os.environ.get("DECISION_SERVICE_TIMEOUT", "120"))

#: The authors' calibration: at none_probability >= 0.2, 66.3 % of questions whose
#: listed options are all wrong are caught, at 2.2 % false flags. Borrowed -- a
#: project that uses it in a success criterion must re-measure it on its own cases.
#:
#: Re-measured here (2026-10-20, n=20): in a closed 7-way option set with no fitting
#: option it fired (none=0.464); with an explicit "not stated" option it never
#: exceeded 0.033, including on the items the operator declined. It is therefore a
#: closed-set guard, not a general abstention signal -- see Decision.accepted.
NONE_THRESHOLD = 0.2


class DecisionUnavailable(RuntimeError):
    """The operator could not be reached or returned an unusable response."""


@dataclass(frozen=True)
class Decision:
    """One typed answer, with the model's uncertainty kept intact."""

    question: str
    type: str
    choice: Optional[str] = None
    confidence: Optional[float] = None
    probabilities: Dict[str, float] = field(default_factory=dict)
    none_probability: Optional[float] = None
    score: Optional[float] = None
    elapsed_ms: Optional[float] = None
    model: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def is_none_likely(self, threshold: float = NONE_THRESHOLD) -> bool:
        """True when no listed option probably fits.

        A caller that ignores this treats a forced choice as a free one.
        """
        return self.none_probability is not None and self.none_probability >= threshold

    def choice_or_none(self, threshold: float = NONE_THRESHOLD) -> Optional[str]:
        return None if self.is_none_likely(threshold) else self.choice

    @property
    def probability(self) -> Optional[float]:
        """The answer's own probability: `noul` for yes/no, else confidence/score."""
        noul = self.raw.get("noul")
        if self.type == "noul" and isinstance(noul, (int, float)):
            return float(noul)
        if self.confidence is not None:
            return self.confidence
        return self.score

    def is_abstention(self, option: str = "not_stated") -> bool:
        """True when the operator took the caller's own abstention option."""
        return self.choice == option

    def accepted(self, min_confidence: float = 0.6,
                 none_threshold: Optional[float] = NONE_THRESHOLD,
                 abstention_option: Optional[str] = None) -> bool:
        """Whether this answer may be acted on. Two modes, chosen by the caller.

        Mode A -- closed option set (no explicit abstention option). `none_threshold`
        guards against a forced choice: measured on this deployment, a 7-way category
        question with no fitting option returned none=0.464 while still naming a
        category at p=0.78, and acting on that name would have been wrong.

        Mode B -- the option set contains its own abstention option (e.g.
        "not_stated"). Pass `abstention_option="not_stated"` and `none_threshold=None`:
        abstention is then observable as the choice itself. In a 20-item probe where
        such an option was offered, `none_probability` never exceeded 0.033 even on the
        items the operator declined, so keeping the none test in this mode can only
        produce false rejections. A missing `none_probability` is not a measured zero.

        Confidence always applies. For `noul`, confidence is the distance from 0.5, so
        a confident "no" (p(yes) near 0) is not read as low confidence.
        """
        if abstention_option is not None and self.is_abstention(abstention_option):
            return False
        if none_threshold is not None and self.is_none_likely(none_threshold):
            return False
        value = self.probability
        if value is None:
            return False
        if self.type == "noul":
            # A confident "no" is p(yes) near 0; confidence is the distance from 0.5.
            value = max(value, 1.0 - value)
        return value >= min_confidence


class DecisionClient:
    """Thin HTTP client for `POST /v1/systemone`."""

    def __init__(self, url: Optional[str] = None, timeout: Optional[float] = None):
        self.url = (url or DEFAULT_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    # ------------------------------------------------------------------ health
    def health(self) -> Dict[str, Any]:
        """Structured status; never raises. A gate can SKIP on `up: False`."""
        for path in ("/health", "/v1/models", "/"):
            try:
                with urllib.request.urlopen(self.url + path, timeout=5) as response:
                    return {"up": True, "url": self.url, "path": path,
                            "status": response.status}
            except Exception:  # noqa: BLE001 - health must not raise
                continue
        return {"up": False, "url": self.url}

    # ------------------------------------------------------------------ decide
    def decide(self, state: str | Mapping[str, Any],
               questions: Dict[str, Dict[str, Any]]) -> Dict[str, Decision]:
        if isinstance(state, str):
            state = {"text": state}
        payload = {"state": dict(state), "questions": questions}
        target = self.url + "/v1/systemone"
        started = time.perf_counter()
        try:
            request = urllib.request.Request(
                target,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DecisionUnavailable(
                f"decision service unreachable at {target}: {type(exc).__name__}: {exc}. "
                f"Start it with decision-service/scripts/serve.ps1, or set DECISION_SERVICE_URL."
            ) from exc
        except json.JSONDecodeError as exc:
            raise DecisionUnavailable(
                f"decision service at {target} returned non-JSON: {exc}") from exc

        answers = raw.get("answers")
        if not isinstance(answers, dict):
            raise DecisionUnavailable(
                f"response has no 'answers' object: {str(raw)[:200]}")

        elapsed = round((time.perf_counter() - started) * 1000, 1)
        model = raw.get("model")
        return {
            name: Decision(
                question=name,
                type=str(answer.get("type", questions.get(name, {}).get("type", "?"))),
                choice=answer.get("choice"),
                confidence=answer.get("confidence"),
                probabilities=dict(answer.get("probabilities") or {}),
                none_probability=answer.get("none_probability"),
                score=answer.get("score"),
                elapsed_ms=elapsed,
                model=model,
                raw=dict(answer),
            )
            for name, answer in answers.items()
        }

    # ------------------------------------------------------------ convenience
    def yes_no(self, statement: str, evidence: str | Mapping[str, Any],
               **controls: Any) -> Decision:
        """One yes/no question, answered as a probability of 'yes'."""
        answers = self.decide(
            evidence,
            {"answer": {"type": "noul", "instructions": statement}},
        )
        return answers["answer"]

    def choose(self, instructions: str, options: Mapping[str, str],
               evidence: str | Mapping[str, Any], **controls: Any) -> Decision:
        """One choice among named options, with per-option probabilities."""
        answers = self.decide(
            evidence,
            {"answer": {"type": "choice", "instructions": instructions,
                        "criteria": dict(options)}},
        )
        return answers["answer"]
