# EIDOS reusable-product and feedback delivery plan

Decision date: 2026-11-03. This document is an implementation/acceptance plan,
not a statement that every item has shipped. Stable production remains 0.4.12.

## Product boundary

Provide one versioned core SDK/CLI, a thin Agent adapter, independent project
workers and an optional shared local monitor. Ordinary research projects consume
the core rather than fork it. Domain protocols, data, locks, scientific validators
and manuscripts remain project-owned. Core, model and scientific capabilities
have separate qualification records. The default path needs no Gemini, paid API,
mandatory service account or implicit hosted fallback.

Release-integrity checking currently refuses the candidate because release
history still ends at 0.4.12 while the development source declares 0.5.0. Keep
this as a publication blocker; do not append a fictitious release to silence it.
The versioned release stage must bind the final source/artifacts and actual CI.

The shared-monitor development source now has a completed stable-input audit:
1,309 passing tests, six explicit skips, 77% whole-framework coverage and ten
passing chains with one skip. The local skips include unavailable Torch modules
and platform-specific controls. This is not an all-backend, independent-machine
or RSI certificate. The earlier 61-case/91% scoped module coverage is historical
and must not replace the whole-framework number.

Actual worker qualification includes normal noneditable Windows installations,
different dependency sets, a fresh Unicode/spaced public replay, source-controller
HTTP and desktop/mobile browser checks. A network-disabled same-host Linux
container qualifies two installed workers, source aggregation and a real FIFO
registration rejection. The frozen v2 manifest binds 141 payloads; protocol-v1
retains 47 earlier payloads. Neither archive is rewritten with later results.

## Delivery gates

| Gate | Current checkpoint | Required exit evidence |
|---|---|---|
| P1: install and invoke | CLI and installed replay exist; exact old candidates retained | Coherent distribution/import/console names, immutable versioned artifacts, fresh installation, documented compatibility and exact-final-commit CI |
| P2: share observations | Worker protocol, collector and UI implemented; actual candidate controls passed | Publish reviewed source/evidence; qualify installed controller packaging and safe production migration; retain failure isolation and stale-view controls |
| P3: close one core-defect incident | Metadata-only export exists; complete lifecycle open | Old defect reproduction, failed candidate, independently accepted fix, immutable release, originating-project replay and exercised rollback |
| P4: Agent entry | Thin instruction adapter added; deterministic tools independently qualified | Realistic end-to-end adapter trials, wrong-project/version/unsupported-operation refusals, no gate duplication or hosted fallback |
| P5: measure improvement | Engineering evidence exists | New-machine/adopter qualification and held-out matched-budget research trials; attribute human and external-assistant contributions |

## Naming and packaging migration

PyPI `eidos` is a different project. Do not publish over it or advertise its
index command as ours. Before selecting a new distribution name, check current
availability and repository ownership. Also select a specific import namespace
and console command; changing the distribution alone leaves generic `framework`
and command collisions unresolved. A name check is not a reservation.

Perform the migration on a separate candidate branch. Inventory every supported
import/CLI consumer, change declarations and lock coherently, define any bounded
compatibility period, and retain existing wheels/trials as historical artifacts.
Do not mass-rewrite frozen receipts to a new name. Qualification requires two
fresh environments, coexistence/conflict controls, the old supported entry path
where promised, new entry points, selected-interpreter worker enrollment and
hash-bound reports/feedback. Use a prerelease identifier for a public preview;
the current 0.5.0 development label is not a released product.

Keep the scientific worker light. A controller may use a separate package/extra
and environment, but it must not silently install every model, GPU backend or
tracking service in downstream projects. A verified local/GitHub wheel path
remains useful before a public index listing.

## P3: concrete feedback campaign

Select one real core defect with immutable pre-fix and repaired artifacts. Prefer
the already reproduced stale-verdict binding defect over inventing a synthetic
scientific discovery. Preserve the exact failing configuration, validator, input
versions, expected/actual verdicts and their originating project identity. Obtain
permission for any private reproducer export; local sanitized evidence is enough
and no GitHub account is required.

Use an incident ledger with states:

```text
DETECTED -> TRIAGED -> REPRODUCED -> CANDIDATE -> VALIDATED -> RELEASED
         -> DOWNSTREAM_VERIFIED -> CLOSED
```

Candidate rejection, insufficient evidence, deferred work and rollback are
explicit recorded branches. Classification distinguishes core, environment,
downstream code/data, unsupported scope and genuine scientific negative results.
Uncertain attribution stays open. Every transition cites immutable evidence
hashes and the prior event; a label or freely written PASS is not validation.

The core-defect trial must demonstrate:

1. The old installed wheel fails the original acceptance criterion in a fresh
   trial prefix, with source/runtime/config/input identity recorded before/after.
2. A negative patch still fails and cannot reach validated/released/closed.
3. A corrected candidate passes the independently fixed regression and unaffected
   controls, without modifying the protected acceptance rule.
4. A new immutable version is built and published through normal checks. The
   release digest, source commit, lock and actual CI run refer to that version.
5. The originating project explicitly trials that release in an isolated prefix
   and replays the original reproducer; unrelated project pins remain unchanged.
6. A rejected upgrade can return to the prior pinned environment without losing
   run history. Retain its actual outcome; do not infer rollback from a plan.
7. Closure verifies the complete incident/regression/patch/release/replay links.
   Missing, stale, mismatched or failed replay prevents closure.

Start with a local deterministic ledger and artifact verification. Agent proposals
can drive the same operations later. Receipt hashes establish integrity against
accidental changes, not trust in arbitrary hostile producers or a scientific
oracle. Keep the independent evaluator and acceptance policy outside the
candidate's writable scope during qualification.

## Agent contract

The packaged instruction adapter selects an explicit project and installed
interpreter, checks supported operations, calls the existing CLI and reports its
structured receipt. It cannot replace a domain validator, rename FAIL to PASS,
weaken acceptance, upload feedback, apply updates or restart the monitor without
authorization. First-use inference does not establish new scientific competence.
An optional MCP can expose the same contract once versioning is stable.

## Production and sustained operation

Keep on-demand research, the resident read-only worker observer and existing
bounded operational self-check/recovery. No external CRON or automatic global
dependency upgrade is needed. The currently loaded production monitor remains a
separate runtime; source changes alone do not migrate it. Prepare an owned,
reversible migration with listener/single-writer ownership, startup persistence,
sample sequence and freshness, failure recovery and rollback acceptance. Preserve
the existing service until that migration is separately authorized and qualified.

Track reproducible incidents, downstream-verified closures, false acceptance,
regression/recurrence, rejected candidates, rollback success and time/compute to
verification. Publish unresolved denominators. Separately evaluate research
quality on held-out tasks under preregistered matched budgets. Engineering repair,
external component reuse and package upgrades alone do not establish scientific
RSI or recursive improvement of the improvement procedure.

Update README, project integration, completeness ledger, technical framework,
site document copies and release history from these same acceptance boundaries.
Do not mark a feature delivered solely because documentation describes its target.


## Renewed probe-repair checkpoint, 2026-11-03

The earlier 1,309-pass source audit is historical. After the real inherited-pipe
availability defect and README reorganization, the renewed stable-input audit
measured **1,317 passed, six skipped, 77% whole-framework coverage, ten passing
chains and one skip**. Source identity is
`76db9d342993a8da3dc97ff564ca6a1ff3d52eb221249ef89928ff322fdd5ed1`.
The current unreleased installed wheel SHA256 is
`57f7e6481aa7f706420e3a45ba3052a10c43da58050435167dadfce99cc94b2c`.

Actual normal Windows old/new wheel controls reproduce the old defect and verify
inner cleanup before outer-owner termination. Current-wheel CLI init/refusal/
status/local-feedback and a new shared-controller desktop/mobile replay pass.
The initial harness result and a hardlink-contaminated metadata control are
withdrawn; exact restoration and an isolated atomic v2 control are retained.
Distinct prefixes do not by themselves establish mutable-file independence; use
copy mode for fault injection. The existing stable environment remains 0.4.12.

Current-repair Linux qualification remains open after two failed container
attempts; no valid counterfactual was accepted there. Production later recovered
OK naturally without deployment or state edits, so it is not evidence that this
patch was applied. Versioned publication/CI, installed-controller packaging,
protected production migration and the full feedback release/replay/rollback
lifecycle remain open. See `RUNTIME-INCIDENT-INFERENCE-2026-11-03.md` and the
`reference/inference_probe_acceptance` records in the development branch.


### Subsequent Linux caller qualification

The missing Linux entry witnesses were traced to a noexec scratch mount. With
explicit executable private scratch, a fresh network-disabled/read-only-root
container passed the actual installed old/new probe campaign with unchanged
input/wheelhouse/SDK/metadata identities and verified owned-container cleanup.
The final `reference/inference_probe_acceptance/recorded_trials/probe-fix-v3`
profile supersedes v2 as this caller acceptance; failed attempts and withdrawn
controls remain preserved. This closes only the availability-probe Linux gap,
not current-wheel shared UI, new-machine, release/rollback or scientific RSI.
