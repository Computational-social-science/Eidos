"""Operational verification age is separate from the original measurement age.

Callers must withdraw a cached verdict when its input binding changes. A recent
check does not recreate an experiment or prove that time-dependent data is new.
"""

from datetime import datetime, timezone
import math
from numbers import Real

from framework.project import evidence_age_hours


def verification_freshness(root, expected, checked_at, max_age_h=24.0, *, now=None):
    if (
        isinstance(max_age_h, bool)
        or not isinstance(max_age_h, Real)
        or not math.isfinite(max_age_h)
        or max_age_h <= 0
    ):
        raise ValueError("verification age limit must be finite and positive")
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("verification clock must be timezone-aware")
    age = None
    if expected in {"PASS", "FAIL"} and isinstance(checked_at, str):
        try:
            when = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
            if when.tzinfo is None:
                raise ValueError("ambiguous verification time")
            measured = (current - when).total_seconds() / 3600.0
            # Preserve the existing tolerance for at most 60 seconds of clock skew.
            if measured >= -1 / 60:
                age = max(0.0, measured)
        except ValueError:
            pass
    try:
        artifact_age = evidence_age_hours(root)
    except OSError:
        artifact_age = None
    return {
        "age_h": age,
        "artifact_age_h": artifact_age,
        "source": "verification",
        "stale": age is None or age > max_age_h,
    }
