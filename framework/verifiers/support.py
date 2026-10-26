"""Support verification: a claim passes only if a passage backs it.

The integration plan's Step 3 asks for a support-checking service. None could be verified as
accessible (the name resolves to an unrelated project, and the linked site serves no
documentation), so no such dependency is referenced here: a tool that exists only in a plan is the
defect this repository corrected with LangGraph. What follows is the contract a backend must
satisfy, without assuming one.

So this module implements the *contract* the plan needs, without inventing the backend:

* a support record has a verdict (`SUPPORTED` / `NOT_SUPPORTED` / `UNCLEAR`), the question asked,
  and — when the verdict is `SUPPORTED` — a passage with source, offsets and text;
* a `SUPPORTED` record whose passage does not resolve against the cited source is rejected, because
  an unchecked "supported" is worse than an admitted `SUPPORT_UNCHECKED`;
* a claim with no record is `SUPPORT_UNCHECKED`, and Gate S treats that as `BLOCKED`, never `PASS`.

A backend (BM25 over a fetched paper, a bounded entailment call to a local model, a human) produces
the record; this module refuses to produce one it cannot justify.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "artifacts" / "literature" / "support"

SUPPORTED = "SUPPORTED"
NOT_SUPPORTED = "NOT_SUPPORTED"
UNCLEAR = "UNCLEAR"
UNCHECKED = "SUPPORT_UNCHECKED"

VERDICTS = (SUPPORTED, NOT_SUPPORTED, UNCLEAR)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _path(claim_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in claim_id)
    return STORE / f"{safe}.json"


def record(claim_id: str, verdict: str, question: str, passage: dict | None = None,
           answer: str | None = None, backend: str = "unspecified",
           source_text: str | None = None, store: Path | None = None) -> dict:
    """Store one support verdict, refusing a `SUPPORTED` that cannot show where it came from."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, not {verdict!r}")
    if verdict == SUPPORTED:
        if not passage or "source" not in passage:
            raise ValueError("a SUPPORTED verdict needs a passage with a source")
        has_offsets = "start" in passage and "end" in passage
        if not has_offsets:
            raise ValueError("a SUPPORTED verdict needs passage offsets (start, end)")
        if source_text is not None:
            start, end = int(passage["start"]), int(passage["end"])
            if not (0 <= start < end <= len(source_text)):
                raise ValueError(f"passage offsets {start}:{end} fall outside the source "
                                 f"({len(source_text)} chars)")
            quoted = passage.get("text")
            if quoted is not None and source_text[start:end].strip() != str(quoted).strip():
                raise ValueError("the quoted passage does not match the source at those offsets")

    row = {"claim": claim_id, "verdict": verdict, "question": question, "answer": answer,
           "passage": passage, "backend": backend, "ts": _now()}
    target = (store or STORE) / _path(claim_id).name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def load(claim_id: str, store: Path | None = None) -> dict:
    path = (store or STORE) / _path(claim_id).name
    if not path.is_file():
        return {"claim": claim_id, "verdict": UNCHECKED,
                "reason": "no support record; run a support backend or the claim stays unchecked"}
    return json.loads(path.read_text(encoding="utf-8"))


def passable(claim_id: str, store: Path | None = None) -> tuple[bool, str]:
    """Can this claim receive Gate S PASS on support grounds? Returns (allowed, reason)."""
    row = load(claim_id, store)
    verdict = row.get("verdict")
    if verdict == SUPPORTED and row.get("passage"):
        return True, "passage recorded"
    if verdict in (NOT_SUPPORTED, UNCLEAR):
        return False, f"support verdict {verdict}"
    return False, "support unchecked"


def summary(claim_ids: list[str], store: Path | None = None) -> dict:
    rows = {cid: load(cid, store) for cid in claim_ids}
    counts = {}
    for row in rows.values():
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return {"ts": _now(), "counts": counts, "claims": {k: v.get("verdict") for k, v in rows.items()},
            "blocked": [cid for cid in rows if not passable(cid, store)[0]]}
