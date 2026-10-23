# What this project borrows from Langfuse

Langfuse (https://github.com/langfuse/langfuse) is an LLM observability server: traces own
spans, spans carry start/end/status/metadata, verdicts ride as scores, and the UI draws a
waterfall per trace. The pipeline page here uses that **data model** because it is the right
one for a pipeline whose units are long-running steps with verdicts.

## Borrowed

| Langfuse concept | Here |
|---|---|
| trace with an id, name, start, end | `docs/traces/latest.json` → `trace` |
| span with `startTime`, `endTime`, `metadata` | one span per chain, with `duration_ms` and the detail string |
| scores attached to an observation | `chain_verdict` score per span, `PASS`/`SKIP`/`FAIL` as a categorical value |
| batch ingestion (`POST /api/public/ingestion`) | `tools/export_langfuse.py` produces the same payload |
| waterfall view | `tools/pipeline_view.py` draws it from the same spans, offline |

## Not borrowed

* **No server on this host.** A Langfuse deployment needs Postgres, ClickHouse, Redis and
  object storage; the pipeline page must work on a laptop with none of that. The page is a
  snapshot from disk and becomes live through `tools/serve_site.py`, not through Langfuse.
* **No data leaves the machine.** The exporter writes a file; `--send` only posts when
  `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, and it says
  "NOT SENT" otherwise rather than failing silently.
* **No sampling of prompts or completions.** Eidos traces its own pipeline, not a model's
  conversations; the one model-facing consumer keeps its evidence in its own directory.

## To enable ingestion

```bash
export LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted instance
export LANGFUSE_PUBLIC_KEY=pk-... LANGFUSE_SECRET_KEY=sk-...
python tools/audit_chains.py --spans docs/traces/latest.json
python tools/export_langfuse.py --send
```

A successful send prints `SENT  accepted N, rejected 0`; anything else names the reason.
The local page does not depend on this working — that is the point of keeping the trace
format the source of truth and the server an optional consumer of it.
