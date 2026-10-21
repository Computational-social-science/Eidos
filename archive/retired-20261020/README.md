# Retired 2026-10-20 — `framework/agents`

**Why.** The coupling audit (`tools/audit_coupling.py --symbols`) found that this module
exposed 11 public names and was imported by **nothing** outside itself: not by `tools/`,
not by `tests/`, not by any other framework module. Under the rule that a layer without a
consumer is deleted rather than kept, it had no reason to exist here.

**What replaced it.** Judgement and routing moved to the typed-decision operator
(`framework/decision.py`, StartLux-Decision-4B). Generation stays with whatever the caller
uses; the framework does not wrap it.

**Why archived rather than deleted.** This repository had no commits when the module was
retired, so `git rm` would have destroyed the only copy. It is kept here, out of the
package, as the record of a design that was tried and not wired.

**To restore it** (only with a consumer): move `agents/` back under `framework/`, add
`agents = ["langgraph>=0.2"]` to `pyproject.toml`, and register a chain for it in
`tools/audit_chains.py` so that "it exists" and "it is used" are the same statement.
