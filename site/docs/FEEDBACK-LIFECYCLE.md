# EIDOS Agent: local repair lifecycle contract

Status: development source, 2026-11-03. This is a deterministic local software
repair ledger. The published 0.4.12 installation has not acquired this API.
Publication of a new wheel and a real originating-project release replay remain
separate acceptance gates. No autonomous scientific RSI is claimed.

## Entry and ownership

Select the downstream project and its normal installed interpreter explicitly:

```text
<worker-python> -I -m framework.cli incident --help
<worker-python> -I -m framework.cli incident create --project <project> --message <observation> --protocol <sealed-protocol.json> --feedback-bundle <feedback.zip> --json
<worker-python> -I -m framework.cli incident record --project <project> --incident <id> --receipt <receipt.json> --json
<worker-python> -I -m framework.cli incident status --project <project> --incident <id> --json
<worker-python> -I -m framework.cli incident adopt --project <project> --incident <id> --python <candidate-python> --json
<candidate-python> -I -m framework.cli incident close --project <project> --incident <id> --json
<worker-python> -I -m framework.cli incident revert --project <project> --incident <id> --json
```

The new source also declares the `eidos-agent` console alias. Legacy `eidos`
invokes the same implementation. Neither spelling changes the installed
distribution `eidos` or namespace `framework`; see the naming ADR. Use a qualified
wheel containing the API, rather than assuming these commands exist in 0.4.12.

The default feedback export contains only local metadata. Importing that explicit
bundle into an incident preserves its identifier. No operation automatically
uploads evidence, installs packages, restarts services or runs a model. `adopt`
selects an already installed candidate by writing this project's runtime pin;
it does not migrate the resident dashboard or its legacy services.

## Protocol and evidence

Seal the project ID, scope, required check names, regression check, optional
mandatory rejection control, required CI workflows and origin-file hashes before
evaluating candidates. The protocol schema is `eidos.repair-protocol.v1`.
`origin_sha256` hashes UTF-8 canonical JSON of the relative-path-to-raw-SHA256
mapping: sorted keys, separators `(',', ':')`, followed by a newline. The project
configuration and origin files must remain current at record/adopt/replay/close.

Every external receipt has schema `eidos.repair-receipt.v1`, incident/project/
protocol IDs, `kind`, explicit object `details` and an `artifacts` mapping. Each
artifact names a bounded local relative file and its SHA256. Inputs are copied
into content-addressed blobs. Receipts are bounded JSON, not executable plugins.

Execution artifacts use `eidos.repair-check.v1`, a fresh run ID and aware timestamp,
the actual stage, project/protocol/origin/wheel hashes and exactly the sealed
check inventory. Each row states executed=true and PASS or FAIL. A passing check
cannot be a declared fault injection. Reproduction isolates the regression FAIL
from unaffected PASS checks. Post-adoption replay must be a new execution after
the actual pin was written and must bind its SHA256; validation cannot be reused.

Publication requires consistent raw release, exact-head CI and tag receipts in
addition to the wheel and a release summary. Their asset size/digest, version,
tag and delivery commit must agree. The generic ledger checks supplied receipt
consistency offline. A trusted producer must fetch the real remote records and
execute the protected evaluator. Locally fabricated JSON is not authenticated
GitHub proof, even if internally consistent.

## Derived states and refusal

```text
DETECTED -> TRIAGED -> REPRODUCED -> CANDIDATE -> VALIDATED -> RELEASED
                                      |                       |
                                   REJECTED                ADOPTED
                                      |                       |
                                  ROLLED_BACK          REPLAYED -> CLOSED
                                      |                       |
                                  CANDIDATE              REPLAY_FAILED
                                                              |
                                                           REVERTED
                                                              |
                                                           ADOPTED
```

Reversion is also available immediately after adoption. Unknown attribution,
scientific negative results and unsupported scope cannot enter a software repair
campaign. If rejection controls are required, closure requires both an actual
rejected candidate and its baseline rollback evidence.

One project pin lock serializes mutations across incidents; journal locks follow
it. Every append passes the same complete validator used when reading a journal
before atomic publication. Write-ahead adoption/reversion events preserve the
previous pin bytes or its absence. Interrupted operations can retry without
overwriting an unrelated pin or losing the original rollback target. Existing
committed UUID run records are preserved; unpublished atomic staging files are
not mistaken for historical runs.

Closure runs from the actual normal installed pinned worker. Its complete SDK,
distribution version, interpreter, prefix and dependency identity must match.
Changed source/configuration/origin/pin/runtime withdraws currency as STALE while
the historical lifecycle remains visible. All results retain scientific_status
UNRUN: software lifecycle completion does not certify scientific conclusions.

## Qualification checkpoint

The focused lifecycle suite currently has 36 passing checks. An earlier combined
68-check run measured 83% coverage of the new feedback module. Subsequent release
binding controls separately passed 10 checks, including missing/wrong console
aliases and changed Python requirements. These are development checks; use the
new full-source audit for its measured source identity and totals once recorded.

The final stable-input full audit, including the mobile matrix, live IDLE
contrast and document-sync corrections, measured **1,363 passed, six skipped,
77% whole-framework coverage, ten passing chains and one skipped chain**. Its
canonical source SHA256 is
`d02d740d0cde3fc3efe07bafe01be8a651e7a9ef1239ea4e54389d305f224b10`;
installed distribution identity and test inventory were stable before/after.
This full audit and the focused feedback-module coverage have different scopes.

A fresh copy-mode normal Windows installation of candidate wheel SHA256
`56d2fe35b1e5ab552fe001ae675e3af4f095e78522fa8fae682f5ea41cfa301c`
matched all 51 installed SDK modules and exercised both console aliases, project
initialization, cross-alias status, deliberate scientific refusal and local-only
feedback export. This does not qualify a new namespace, another operating system,
an installed controller, or a published release.

Next acceptance is a trusted real campaign using the already reproduced
inherited-pipe inference defect: immutable old/bad/repaired wheels, protected
original evaluator, rejected upgrade rollback, real version/CI/release, originating
project adoption, failed-replay reversion, fresh successful replay and closure.
Keep that campaign open until all links have actual evidence.
