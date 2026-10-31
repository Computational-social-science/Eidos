# Releases

A version number is a claim that something changed for whoever uses the framework. It is not a
bookmark for the last edit.

## The rule

**One release per deliverable.** A deliverable is one of:

* a capability a user can newly exercise (a new verifier, a new gate, a new command), or
* a measured result that changes a decision (the model is promotable; it is not), or
* a correction that invalidates something already published (a tag was wrong, a claim was false).

A doc edit, a measurement of the same object, a refactor with no behaviour change, or a test added
beside an existing test **rides the next release**. It does not earn one.

## What went wrong on 2026-10-26

Seven tags in 125 minutes — `v4.3.0` at 21:42 through `v4.3.6` at 00:12 — for one line of work whose
scientific result was a single negative finding (S4 agreement 0.733 against a 0.90 bar). Two of the
earlier tags (`v4.4.0`, `v4.5.0`) were cut with the wrong digit and deleted. That is churn recorded
as progress, and it makes the history unreadable: a reader cannot tell which tag they should care
about.

The honest accounting for that stretch is **two** releases:

| release | contents |
|---|---|
| one patch | proofpath and kernel verifiers, support contract, S10 with BLOCKED, VRAM mutex, config made real, overrides merge |
| one patch | the ScienceRSI measurement campaign: header verified, VRAM at two contexts, probe 0.733, prompt compile null result |

Everything after the first of those was an edit to the same object.

## Cutting one

1. The deliverable exists and its measurement is written down.
2. `python -m pytest` green, `tools/audit_site.py` green.
3. `build_site.py --bump patch` (or `minor` only with the user's explicit agreement).
4. Commit, tag, push — in that order, so the tag never points at an unverified tree.
5. CI green before the tag is announced. A tag that needs a follow-up fix is a tag that was cut
   too early.

Do not tag to mark the end of a work session.
