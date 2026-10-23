"""Export the chain trace in the shape Langfuse ingests.

Langfuse's advantage is not its storage — it is the *model*: a trace owns spans, a span has
a start, an end, a status and free attributes, and everything is identified by stable ids.
Eidos already records exactly that (`tools/audit_chains.py --spans`), so this tool is a
translation, not an integration:

    python tools/export_langfuse.py                 # write docs/traces/langfuse_batch.json
    python tools/export_langfuse.py --send          # POST it, if LANGFUSE_* is configured

Credentials are read from the environment only (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY,
LANGFUSE_HOST). Nothing is written to disk and no default endpoint is assumed: an
unconfigured run writes the batch and says so, instead of failing.

The ingestion API is Langfuse's batch endpoint (`POST /api/public/ingestion`), the same one
the SDKs use; a trace created this way appears in their UI with the same waterfall the
page draws locally.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "docs" / "traces" / "latest.json"
OUT = ROOT / "docs" / "traces" / "langfuse_batch.json"


def to_iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="milliseconds")


def build(trace_doc: dict) -> dict:
    trace = trace_doc["trace"]
    trace_id = trace["id"]
    batch = [{
        "id": f"trace-{trace_id}",
        "type": "trace-create",
        "timestamp": to_iso(trace["start_ts"]),
        "body": {
            "id": trace_id,
            "name": trace["name"],
            "timestamp": to_iso(trace["start_ts"]),
            "metadata": {"duration_ms": trace["duration_ms"], **trace.get("attributes", {})},
            "tags": ["eidos", "chain-audit"],
        },
    }]
    for span in trace_doc["spans"]:
        batch.append({
            "id": f"span-{span['id']}",
            "type": "span-create",
            "timestamp": to_iso(span["start_ts"]),
            "body": {
                "id": span["id"],
                "traceId": trace_id,
                "name": span["name"],
                "startTime": to_iso(span["start_ts"]),
                "endTime": to_iso(span["end_ts"]),
                "metadata": {"duration_ms": span["duration_ms"], **span.get("attributes", {})},
            },
        })
        # Langfuse scores are how a verdict travels with the span; "PASS" is not a status
        # it knows, so it is attached as a categorical score rather than dropped.
        batch.append({
            "id": f"score-{span['id']}",
            "type": "score-create",
            "timestamp": to_iso(span["end_ts"]),
            "body": {
                "id": f"score-{span['id']}",
                "traceId": trace_id,
                "observationId": span["id"],
                "name": "chain_verdict",
                "value": span["status"],
                "dataType": "CATEGORICAL",
            },
        })
    return {"batch": batch}


def send(payload: dict) -> tuple[bool, str]:
    host = os.environ.get("LANGFUSE_HOST", "").rstrip("/")
    public = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not (host and public and secret):
        return False, "LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set"
    token = base64.b64encode(f"{public}:{secret}".encode()).decode()
    request = urllib.request.Request(
        f"{host}/api/public/ingestion",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    errors = [e for e in body.get("errors", []) if e]
    return (not errors), f"accepted {len(body.get('successes', []))}, rejected {len(errors)}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args(argv)

    if not TRACE.exists():
        print(f"no trace at {TRACE}; run tools/audit_chains.py --spans docs/traces/latest.json")
        return 1
    payload = build(json.loads(TRACE.read_text(encoding="utf-8")))
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(payload['batch'])} events "
          f"({sum(1 for b in payload['batch'] if b['type'] == 'trace-create')} trace, "
          f"{sum(1 for b in payload['batch'] if b['type'] == 'span-create')} spans, "
          f"{sum(1 for b in payload['batch'] if b['type'] == 'score-create')} scores)")

    if args.send:
        ok, detail = send(payload)
        print(f"{'SENT' if ok else 'NOT SENT'}  {detail}")
        return 0 if ok else 0  # a missing server is a statement, not a failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
