# Eidos 0.4.12 candidate qualification checkpoint

Status: **CANDIDATE_TESTS_PASS_RELEASE_PENDING**. This document is not a release
announcement and does not replace the current published 0.4.11 evidence.

The candidate repairs Windows recovery selecting WSL for MSYS drive paths, binds
relative/expanded shell configuration to an absolute executable before changing
service cwd, and refuses missing Bash before reserving a service start. The
retained monitor already recovered the actual local decision service after its
unchanged cooldown. Both service endpoints and the live monitor then reported
healthy state. No retry budget was reset or external CRON installed.

## Executed measurements

Wheel: `reference/sdk_process_acceptance/eidos-0.4.12-py3-none-any.whl`.
SHA-256: `8afe9a670c5cf83b750d220b7f6f0a9e4a24233374be3da1a1d1a3282965b3d7`.
All 45 framework modules match candidate source and executed installed bytes.
METADATA/RECORD, dependency origins and normal dependency completeness were
checked in independent environments outside the checkout.

| Qualification | Native Windows | Network-disabled Linux |
|---|---:|---:|
| Installed shell/path controls | 4 | 4 |
| Installed process lifetime controls | 6 | 6 |
| Installed numerical controls | 23 log1mexp + 16 softplus | same |
| Installed numerical refusal inventory | 12 | 12 |
| Installed reproduction controls | 18 + 512 Decimal comparisons | same |
| Installed delivery controls | 16, including actual Quarto/TeX | 15, controlled CLI + actual Matplotlib/Poppler |
| Installed tracking protocol | 49 | 49 |
| Source disposable-service recovery | 13 | 13 |
| Source recovery failure/optimization controls | 6 | 6 |

The source self-audit measured **1,206 passes, six skips, no failures/errors,
75% framework coverage and 10 PASS / 1 SKIP chains**. Before/after source and
distribution identities were identical. The optional project-checker skip stays
explicit. Fifty-five scoped shell/recovery tests include the new failures before
their repair and actual Git Bash execution.

Installed negative checks reject optimized qualification, leaked host
distributions, a changed identity-helper pin, an extra installed framework module,
failed tracking execution and a same-code wheel with forged METADATA. Controlled
mutations were confined to the new candidate environment; restoration was checked.

## Provenance and failures retained

The [machine checkpoint](RELEASE-CANDIDATE-0.4.12.json) cross-checks case inventories,
wheel/source identities and the raw archive manifest. The
[645-payload archive](../reference/numerical_programs_acceptance/recorded_trials/v0.4.12/manifest.json)
includes successful and failed controller observations, input snapshots,
qualification drivers, dependency requirements and negative fixtures.
The candidate wheel is referenced once from its versioned artifact path; public
dependency wheels are referenced by hashes in the frozen requirement files.

The first Linux tracking/recovery launches could not bind the E: source volume.
An exact C: code/protocol snapshot allowed read-only source mounting. The first
tracking snapshot was missing its driver/payload; a complete 249-file snapshot
then passed. Every consumed snapshot member was checked against the original
source. Failed containers were absent or explicitly removed with ownership
verification. A cached-dependency-only Windows install also refused a missing
cffi artifact; the subsequent public bootstrap used the same hash-locked pins.
These are recorded failures, not passed experiments.

Linux core used a public digest-pinned Python image and a fresh normal venv.
Additional delivery/tracking profiles used qualified immutable dependency images;
their image identities, actual read-only mounts and owned cleanup are recorded.
They are same-host offline qualifications, not clean installation on arbitrary
new hardware. Initial public dependency/image acquisition is outside the offline
execution claim. Tracking SQLite tests used private tmpfs and establish no disk
performance or durability result.

No Gemini, paid model API or mandatory service credentials were needed. The
installed-wheel fixtures use no research model; the source chain audit also
performs smoke calls to the resident local decision model. No new research
proposal, model training or scientific-improvement campaign was generated.
Trusted fixture execution, source
integrity checks and bounded cleanup do not constitute hostile-code containment,
binary attestation, scientific novelty or RSI evidence.

## Receipt-assembly follow-up

Eight previous current records were archived from Git before any alias refresh.
The new assembler then verified and refreshed seven current acceptance records
from the actual 0.4.12 measurements. Its complete controller/input/source checks
distinguish the public Python image, cached delivery image and owned tracking
image; historical failure and review fields are explicitly historical.

Review also exposed an omission defect in checkpoint aggregation: an empty source
hash map bypassed the original per-item loop. The defect was reproduced, then
closed by requiring the exact thirteen-source inventory. Five actual checkpoint
mutations now reject wrong platforms, stale source, empty/missing source entries
and input changes during aggregation; the prior checkpoint is preserved and a
restored positive replay passes. Source bytes for the generator and control are
captured before execution and rechecked afterward.

The alias assembler separately rejects five mutated inputs and was interrupted
on its third actual publication write. The first two writes rolled back, leaving
all seven original records unchanged; the restored dry run passed. These controls
and failed early harness attempts are retained under the versioned audit folder,
separate from the immutable 645-payload execution archive. Read-only review found
no remaining blockers within the reviewed aggregation/control scope.

The fifth refusal binds the installed-shell checkpoint to its actual archived
Windows/Linux receipt bytes. Final publication also checks the exact platform,
wheel, 45-module inventory, four declared controls and driver/helper identities;
wrong receipt hashes, platforms, drivers and duplicated cases are refused by
actual publisher-fragment controls. These are local guard controls, not remote
CI or publication evidence.

The machine checkpoint's pending list describes its earlier capture stage; it is
kept unchanged because the current recovery record binds its exact bytes. Receipt
refresh is now done. This still does not establish release publication or CI.

## Required before publication

1. Completed: archive 0.4.11 current-record aliases and assemble new aliases from
   executed 0.4.12 results with current source/wheel/driver/archive bindings.
2. Completed: regenerate versioned site/reports and inspect changed publication pages.
3. Source committed as `208b12a`; final metadata must pass the normal repository hooks.
4. Require CI on the exact final commit, then publish a new tag and verified
   GitHub assets. Keep old release tags/assets unchanged.

The broader functional-completeness and scientific RSI objectives remain open.

The actual onboarding rehearsal passed all six checks, including a deliberate
false claim and a vacuous gate. Version history now records the real source
commit `208b12a`; it is not evidence of a pushed tag or published release.
