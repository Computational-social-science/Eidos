# Installed project CLI development

Status: **UNRELEASED** on `feature/installed-cli`, prospective version 0.5.0.
The stable release remains 0.4.12 at delivery commit
`7a3d35e85736e3d245f4d9d83f10627a27a4d3d5`. Its ten remote jobs and 21 assets were
verified, with the 0.4.11 and 0.4.10 tags/assets unchanged. This worktree has an
independent environment; the running monitor and release checkout are retained.

## User-facing operations being qualified

```sh
eidos init --project /path/to/study --name my_study
eidos check --project /path/to/study --json
eidos status --project /path/to/study --json
eidos report --project /path/to/study --format html --json
eidos feedback --project /path/to/study --message "Observed failure" --out feedback.zip --json
```

Initialization writes a project-local `.eidos` workspace without moving research
files. Its validator deliberately returns REFUSED until a real validator is
configured. A default scientific check combines the declared command with the
existing Gate S implementation. An explicit `--execution-only` result retains
scientific UNRUN. Gate S checks registered evidence contracts; it is not a
universal scientific-truth oracle.

Report generation delegates to the installed Quarto SDK and needs an actual
manuscript and tools. It establishes technical delivery, not scientific validity.
Feedback exports local metadata and a checksum manifest; it does not include
data, environment variables or logs, and does not upload anything. This is the
incident-capture foundation, not a completed repair/release/replay loop.

## Defects exposed before integration

The first twelve user-journey tests reproduced the missing installed CLI. An
initial green run exposed an adapter compatibility regression, which was fixed.
Review then found an execution-binding defect and cross-project support reuse:
results computed before a declared input changed could bind to the new inputs;
two projects sharing a claim ID could read the same global support verdict.
Three actual failing controls established these defects before repair.

The prototype now binds immutable inputs before and after execution, distinguishes
explicit outputs, and brackets scientific checking. Validator/configuration and
explicit inputs take precedence over an output declaration. Gate S and snapshot
collection use the same project-local support store. No global support fallback
is used for project validation.

Four more failing controls covered a changed runtime distribution, status errors
returning success, malformed cache pointers and an edited execution-only record
being displayed as scientific PASS. Runtime metadata identity and byte-bound run
references now withdraw or refuse those results. Runtime identity is metadata
binding, not full dependency-file attestation or hostile-code containment.

The focused CLI/snapshot/support suite now has 70 passes, including the Python
agent entry. A measured run before those last two tests gave 91% CLI coverage,
96% snapshot coverage and 93% across these two modules, combining real CLI child
process coverage. These are scoped module figures, not whole-framework coverage.

A fresh normal noneditable Windows environment outside both worktrees passed
eight actual entry/identity flows, including the unchanged numerical checker,
47-module wheel/installed identity, initial refusal, configured execution,
cached status, metadata-only feedback, missing-output rejection and real HTML
delivery. The first prototype wheel SHA-256 is
`510f7c45026bc1c1edd07922518f973ba1fbf2f1ab8ab793031d23804428358b`.
This does not qualify Linux, all three report formats, central enrollment or
the complete feedback loop. A complete source audit then measured 1,229 passing
tests, six skips, 76% framework coverage and ten passing chains with one explicit
skip. That audit belongs to the baseline before the following configuration fix.

An independent installed probe found a gap that those tests had not covered:
the execution phase bound raw workspace YAML, while status bound only its parsed
ProjectSpec fields. Seed, delivery and comment-only changes could retain PASS.
All three new controls failed before repair. The first candidate added its own
configuration to `validity_inputs` and passed 73 focused checks. Subsequent
independent review found a regression: implicit configuration incorrectly
satisfied module mode's requirement for explicitly declared code inputs. An
actual installed probe obtained scientific PASS with an empty declaration, then
retained PASS after changing the unbound module.

The exact old and new wheels were retained and replayed in separate noneditable
environments. Each arm used the same prefix for its own check and status query:
the old wheel retained PASS after a configuration change; the repaired wheel
withdrew it as STALE. The new wheel SHA-256 is
`316a47a0af75b668d2a40fe4e73a715f800243d6c81387c616bf7d76b4ff5d4e`.
Its 47-module identity, normal dependencies and existing numerical controls also
pass. This wheel repairs configuration invalidation but has the module-input
regression above; it is not an accepted release. A subsequent full audit measured
1,232 passes, six skips and 76% framework coverage, but did not expose that gap.

Two new controls then failed for the intended defects: the CLI executed module
mode without explicit code inputs, and direct SDK observation missed implicit
workspace YAML changes. The repaired SDK observes `.eidos/project.yaml`
implicitly without changing `validity_inputs`; empty module declarations are
refused before execution. A positive module control passes and source mutation
withdraws its verdict. The focused CLI/snapshot/support suite has **76 passes**.
Review found no new reproducible blockers. Configuration and code-declaration
contracts remain separate and are shared by CLI and source adapters.

The third candidate was rebuilt and replayed in a new noneditable environment
outside both worktrees. Wheel SHA-256:
`0d8ca60088be1366f90889ddba686e32c28b15d458a7a5033470a26d683d78cf`.
Actual console comparison reproduced the second candidate's false PASS and
confirmed the third candidate's pre-execution REFUSED. Explicit module source
changes and seed/delivery/comment configuration changes each produce STALE.
The installed 47-module identity and unchanged numerical controls pass. Each
arm used its own unchanged interpreter prefix for check and status. The first
attempt's driver invocation missed its required `-I`; that harness error and
its workspace were retained, then a separate fresh attempt passed.

This is software feedback repair, not scientific RSI. At that checkpoint the
final-source full audit, Linux, monitor enrollment and the complete
release-to-originating-project loop still required separate acceptance.
The RED evidence was captured before code
changes. No deliberately failing commit bypassed the repository's green hooks.

## Final source and installed-profile checkpoint

The next full audit retained stable source identities but found one failure
(1,234 passed, six skips): without inherited UTF-8 settings, the Windows release
rehearsal could not print scientific Unicode. The audit refused publication.
The rehearsal now sets its own child stdio encoding; missing and latin-1 parent
encoding controls both failed before repair. A public-guide link test also
exposed missing static-site copies; the publisher now includes the two exact
referenced documents. The combined focused suite has 95 passes, and both fixes
were independently reviewed. The subsequent frozen full audit passed **1,237
tests, six skips, 76% framework coverage, ten passing chains and one skip**. Source
and distribution identities remained stable; no failed audit was promoted.

The final portable console profile passed **26 actual cases per platform** on
native Windows and same-host network-disabled Linux. It excludes editable
installs, owns console process trees and binds driver/fixture/wheel inputs plus
complete installed SDK identities before and after all cases. Independent review
closed the earlier harness gaps. Old PASS records from withdrawn harnesses and
the namespace-origin setup failure remain archived. A controlled SDK mutation in
two fresh prefixes exposes v4's stale provenance acceptance and v5's final
identity rejection. The positive qualified prefixes were left unchanged.

[Frozen profile and raw evidence](https://github.com/Computational-social-science/Eidos/tree/feature/installed-cli/reference/installed_cli_acceptance)
retain 419 payload files plus a checksum manifest. These are synthetic installed
controls, not outside-adopter, new-machine, generic Agent, complete-project or
scientific RSI acceptance. The development preview uses two finite read-only
observations with operational recovery disabled; it is not the deployed monitor.

## Still required

1. Preserve the final-source installed replay and its negative controls; prior
   wheels remain immutable failed/intermediate candidates. Extend acceptance
   when further source changes occur.
2. Preserve the final Windows/Linux profile and installed identities; new-machine
   acceptance remains open.
3. Preserve actual HTML delivery and failed/stale-output controls; qualify
   additional formats explicitly rather than inferring them from HTML success.
4. Complete version-specific publication evidence, documentation, delivery
   artifacts, normal commits and exact-final-commit CI before release. The scoped
   source audit above is complete; source changes require renewed verification.
5. Add explicit central-monitor enrollment and project-worker identity without
   sharing environments or starting competing 8765 servers.
6. Extend incident capture into reproduced regression, independent patch
   validation, versioned promotion and originating-project replay. Preserve
   rejected candidates and rollback outcomes.

General Agent/MCP entry points must call this same tested core. Local/free
operation, no hosted fallback, no external CRON and no automatic global upgrades
remain requirements. Scientific RSI still needs separate held-out evidence.
