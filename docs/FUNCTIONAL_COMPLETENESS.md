# Functional completeness ledger

Baseline audit: 2026-10-31; executable-delivery update: 2026-11-01; configured CPU research-runtime checkpoint: 2026-11-02. Eidos remains pre-release. A successful case or self-audit
does not establish completeness. Acceptance means an executed, reproducible
lifecycle: onboard → register falsifiable claims → run → independently check →
reject unsupported claims → deliver → detect changes and revalidate.

| Capability | Current evidence | Remaining acceptance |
|---|---|---|
| Environment | Project Python 3.12, frozen lock, Linux CI 3.11/3.12; `AGENTS.md` | Complete new-machine installation with external Quarto/TeX and optional GPU backend. Inventory alone is insufficient. |
| Onboarding and registry | Safe bootstrap, isolated shell/registry tests; gate-stage required outputs; real independent HPAF intake and negative controls | The HPAF metric-repair lifecycle now rejects wrong evidence, missing outputs and changed sources/data, with separate fresh Windows replays for 1,033 private and 235 public pairs. Unseen projects and outside adopters remain unqualified; see `docs/INDEPENDENT-LIFECYCLE-ACCEPTANCE.json`. |
| Scientific gates | `framework/validity/`, fixtures, mutations, `docs/SELF_AUDIT.json` | Structured evidence checks do not establish scientific truth or novelty. Evaluate unseen false acceptances and independent adopters. |
| Installed project CLI (0.5.0 compatibility preview) | Published immutable wheel; both console aliases; normal local Windows/offline Linux controls and independent remote installed-core CI; [current quickstart](DOWNSTREAM-QUICKSTART.md) | Complete new-machine research setup, outside adopters, installed controller and live Agent reasoning remain separate |
| Software incident repair | Actual Eidos origin CLOSED with fifteen linked events, rejected candidate, real release/CI/asset, failed-replay reversion and fresh replay; explicit identity supplement retained; guarded v2 rehearsal also passes | One known defect under supervised deterministic execution; scientific_status UNRUN. Distinct defects, generic hostile-code isolation and scientific RSI are not established |
| Numerical capability | Decimal reference, actual CUDA tests, broken controls; `docs/CASE-SOFTMAX.md` | AMP/bfloat16, higher-order backward and other backends remain unqualified. Each needs independent references and broken controls. |
| Project execution lifetime | SDK-owned Windows Job and Linux owner-pipe guardian; independent installed-wheel controls for normal, timeout, nested and cleanup handoff behavior; `docs/SDK-PROCESS-ACCEPTANCE.json` | Direct reproduction now has installed-wheel numeric/execution/receipt controls; tracking/update/formal/citation/inference paths still need caller-specific migration. This is not a hostile-process sandbox, hard real-time/output-memory bound or running-service migration. |
| Direct manuscript/figure SDK | Fresh staging, bounded Quarto/Matplotlib workers, file/asset validation, declared-input checks, locked publication and rollback; [contract](QUARTO-DELIVERY.md) | Controlled CLI and actual Quarto qualification are separate. Poppler/TeX are external prerequisites; receipt readers must verify hashes. Transitive undeclared resources, scientific content and journal acceptance remain outside these file-production checks. |
| Installed numerical-program API | `framework.numerical_programs` compiles/parses supplied formulas into immutable typed scalar programs; fresh Windows/public-image offline Linux controls check 23 log1mexp and 16 softplus points, wrong-gradient rejection and strict execution boundaries; [contract](NUMERICAL-PROGRAMS.md) | Known external methods and explicitly supplied derivatives. No automatic differentiation, vector/GPU, whole-domain mathematical certificate, autonomous discovery or RSI claim. Caller projects must retain independent scientific checks. |
| Free symbolic derivative reference | Isolated SymPy tool uses the immutable installed 0.4.11 SDK. Actual Windows/offline Linux preserve the saved forward and improve joint public controls from 0/23 to 23/23; 16 softplus + 8 square points, 20 tests and nine integrity/timeout controls pass per platform. [Report](https://github.com/Computational-social-science/Eidos/blob/main/docs/SYMBOLIC-GRADIENT-TOOL-2026-11-02.md) | External assistance on known cases; adapter is not installed in the released wheel. Literal thresholds only; no whole-domain/finite-precision proof, vector/GPU/higher-order AD, live-model tool selection, sealed transfer, novelty or RSI qualification. |
| Research execution | Three-seed paired reconstruction, source/lock/data hashes and models; `docs/SOFTMAX-TRAINING-FOLLOWUP.md` | Full paper training results are not reproduced. Align input representation, initialization and architecture before attributing differences to the repair. |
| Experimental acceptance | NumPy final inference and reloaded CUDA final gradients for all 36 matrix runs | Intermediate gradients remain producer-recorded; parent extension optimizer moments were not separately archived. No universal benefit or novel discovery established. |
| Consumer observation | Input-bound snapshots, Python gate-entry and explicit validator/data/config binding, atomic publication, single background recheck; `tests/test_consumer_snapshot.py` | Scope includes registry, framework sources, direct Python gate entry, explicit validity_inputs and Gate S file handles; it is not an import/dependency closure. Underlying undeclared models/data require consumer validators. Formal toolchain snapshot binding is explicitly unqualified. |
| Scheduler and recovery | Resident checks, lifetime ownership, stall watchdog, durable reservations and idempotent terminal events. External CRON retired with history preserved. Native Windows and offline Linux execute a real disposable-service crash/restart comparison against c12acdd; missing routes, redirects, visible Windows consoles and unattributed listener defects are repaired; [method and record](RECOVERY-ACCEPTANCE.md); positive/negative consumer operational freshness now uses actual Gate S verification, with original measurement age retained and separate [live observation evidence](CONSUMER-OBSERVATION-ACCEPTANCE.json) | Disposable-service source checks do not qualify model-service or installed-recovery restarts. Existing monitor and two old chain loops still require migration after automatic approval rejected restart. Reboot/logon, default-duration retry timing and a clean 24-hour observation remain required; past failures are retained. Earlier Hermes evidence is historical. HTTP authentication presence is not successful inference. Rechecking Gate S does not regenerate research evidence. |
| Inference and decisions | Local contracts, GPU budget tests, typed operator calibration | Calibration is bounded. Model scientific judgements missed acceptance thresholds and remain outside scientific gates. See `docs/MODEL_VERDICTS.md`. |
| Configured local research runtime | New source-checkout CPU CLI, 124 scoped tests and one actual ScienceRSI execution with bound inputs/environments, declared-service continuity and owned cleanup; [record](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-LOCAL-RUNTIME-2026-11-02.md) | The candidate achieved 0/23 joint numerical conformance points. Clean-machine, installed-wheel, Linux model execution and portable GPU qualification remain open. No paid provider or silent hosted fallback is required. |
| Local method retrieval and feedback | Preregistered six-proposal CPU comparison, deterministic sourced cards, own-arm public feedback, source/context/token/time reconstruction; 180 scoped tests; [complete record](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-RETRIEVAL-FEEDBACK-2026-11-02.md) | Both arms achieved 0/23 joint conformance. Treatment loss passed 23/23, but derivatives failed all points; identical answers and earliest-tie feedback reuse were retained. One known task, no independently network-denied/new-machine model acceptance or full OpenScholar/ERA reproduction. |
| Sourced formula-to-program tool | Deterministic compiler reuses typed execution and the public oracle; original T1 remains 0/23, separate external known-method program passes 23/23 and sign checks. Windows CLI and actual offline Linux source replay with fresh NumPy+pip venv, negative pin control, fresh readers, inspected isolation and owned cleanup pass; 304 combined controls; [Linux record](https://github.com/Computational-social-science/Eidos/blob/main/docs/METHOD-OFFLINE-PORTABILITY-2026-11-02.md) | Source-checkout prototype with one known method. Bootstrap downloads precede runtime isolation. No general derivation/full-domain correctness, live-model tool selection, independent installed/new-machine qualification or RSI. Wheel/API promotion and feedback-policy improvement remain separate. |
| Scientific self-improvement | Public C0 oracle, closed expression execution, preserved real malformed/nonconforming proposals, local retrieval/feedback execution and controlled runtime evidence | No EIDOS-generated improver has demonstrated matched-budget superiority on fresh sealed tasks. Typed method/derivative tools, improved feedback policy, independent sealed stewardship and recursive/transfer acceptance remain open. Component assembly and self-healing do not establish RSI. |
| Tracking and provenance | Explicit run/store identity, uncached DVC content verification and isolated model roundtrips; 49 installed cases pass on Windows and offline Linux tmpfs, with paired v0.4.9 failure controls; [contract and limits](TRACKING-INTEGRITY.md) | Complete exact-release CI and assets; ordinary-overlay SQLite performance remains unresolved. General deliveries still need explicit code/data/config/seed/checkpoint/run records and rejection of missing provenance. Not every project uses both services. |
| Reporting and visualization | Shared manuscript policy, Quarto HTML/PDF/DOCX, physical font/dimension/PDF/Word audits and artifact fingerprints; `docs/PUBLICATION-QUALITY.md` | Every changed layout requires complete PDF/Word page inspection. Human metadata and journal-specific scientific review remain necessary. |
| Executable delivery | Explicit-manifest export, fresh Windows installation and offline Linux container replay; 12 numerical cases pass and 2 broken controls are rejected; exclusive execution ownership and atomic records | Same-host CPU acceptance uses an official ECR image override with pinned digest; default Docker Hub connectivity remains failed. Independent HPAF lifecycle delivery now has same-host Windows replay; that case has no Linux/Binder qualification. Remote Binder and new-machine/Quarto/TeX/GPU qualification remain separate. See [delivery contract](EXECUTABLE-DELIVERY.md) and `docs/PACKAGE-ACCEPTANCE.json`. |
| Knowledge transfer | Existing Paper2Agent/MCP, filed failures/findings and reusable numerical checks | Independent HPAF metric repair detects a real contract defect, validates the correction against C++ and exhaustive graphs, and delivers separately replayed public/private packages. This bounded transfer does not establish generality, novel discovery or autonomous scientific self-improvement. |
| Release | Windows local suite, Linux CI, fixture/mutation/site hooks, versioned evidence | Validate source-archive installation and generic packaging; keep docs, exports, screenshots and CI tied to the release. |

Report exporters now hold directory ownership through export and rendering;
release snapshot/rollback shares that ownership. Nested writes by the same owner
are permitted, competing processes are excluded, and ZIP replacement is atomic.
This does not make the entire multi-file directory atomic for readers. Continue
to run export-producing checks sequentially, then audit the final delivered bytes.

## Consumer snapshot contract

The builder captures inputs before and after Gate S. An input change during the
check yields ERROR without a bound digest. The saved snapshot includes a registry
fingerprint and per-consumer hashes for configuration, framework Python sources,
Gate S entry/helper, claim register, deliverables, expected outputs, referenced
claim files and implicit verifier records. Missing files are explicit; unreadable
or out-of-project references prevent the audit from running. Claim file mtimes
are bound because Gate S can use them in preregistration checks. Deliberately
shared outside-project evidence requires an exact-file `validity_external_inputs`
allowlist in the project registry; the negative `null_study` control declares its
shared operator evidence this way.

The monitor withdraws mismatched cached verdicts. Unknown inputs produce an
UNOBSERVABLE instrument and a STALE card with an explanation; a known failure in
another unchanged consumer remains an alarm. Removed consumers cannot retain a
green card. The server queues one background check with a five-minute retry
cooldown and a 300-second timeout. Sampling continues. The timeout owns the tool's
process tree: a Windows kill-on-close Job or a POSIX process group. Windows Job
semantics follow the [Microsoft documentation](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
Atomic replacement prevents partial JSON reads. Manual and automatic server builds
share a lock. Independently invoked builders may finish out of order; input hashes
expose an outdated result on the next sample. This is local change detection, not
remote attestation or a new model-training run.

Positive consumers and negative controls both age operationally by actual Gate S
verification time. Research-evidence generation age is retained separately;
rechecking does not regenerate that evidence. Changed inputs still withdraw the
cached verdict. Age-only automatic arbitrary consumer execution was removed;
time-dependent research-data freshness needs its own declared contract.

## Work order and exit conditions

1. Close stale observation and schema defects with mutation/failure-path checks;
   verify advancing live samples and retain prior soak failures.
2. Repair generic packaging: bounded file manifest, lock-based installation,
   explicit reproduction command and required provenance, then a clean build/run.
   External Binder availability must be assessed separately.
3. Extend the completed same-host HPAF metric lifecycle to unseen independent
   adopters and new-machine replay; preserve wrong-evidence, missing-output and
   stale-snapshot controls.
4. Align the paper reconstruction before extending precision/tasks; register
   criteria before execution and retain unfavorable outcomes.
5. Reassess every row against artifacts before declaring functional completeness.

This is an evidence map and work queue, not a machine-produced PASS certificate.

## Direct-reproduction defect and development repair (2026-11-01)

Controlled calls to `framework.reproduction.compare` reproduced three false
`MATCH` verdicts: expected positive infinity with a finite observation and relative
comparison; an infinite tolerance; and integers 9007199254740992 versus
9007199254740993 at zero tolerance (both were first converted to the same float).
The exact integer distance is one. These defects remain in the immutable 0.4.7
wheel and are repaired in 0.4.8 with typed finite inputs and exact represented
arithmetic. The comparator is still not an unrestricted scientific oracle. These are controlled API defect probes; they do not establish a
failure of the separately qualified finite Softmax kernel/gradient cases.

Repair acceptance: finite typed expectations/observations and finite
nonnegative tolerances; preserve represented integer/float differences; reject
invalid specs before launching work; bind records to commands/inputs and retain
explicit unavailable/error states. Independent installed-wheel controls now include deliberate false-MATCH probes,
valid positive comparisons and owned direct-reproduction lifetimes. Tracking,
formal/citation and update subprocess callers also retain their separate work.


Version 0.4.8 repairs these numeric cases and binds schema-2 receipts
through source files, complete bundle inventories, exact recomputation and
consumer-cache invalidation. The legacy source-free MATCH shortcut is blocked.
Controlled stubs are actually executed in disposable audit/fuzz copies. This
is not a retroactive correction to the published 0.4.7 wheel. Independent Windows
and network-disabled Linux installed-wheel controls are recorded in
[the acceptance receipt](REPRODUCTION-ACCEPTANCE.json). See
[reproduction integrity](REPRODUCTION-INTEGRITY.md).

Scheduling consolidation, applied Hermes configuration and remaining duplicate
writers are tracked in [the scheduling policy](SCHEDULING-POLICY.md). Source
changes remove age-only automatic consumer execution, serialize manual and
background refresh, and reuse matching recent verdicts without renewing their
check time. Existing old service processes have not been migrated.


## Reusable-product checkpoint, 2026-11-03

Stable remains 0.4.12. The unreleased shared-monitor candidate now includes
project-local CLI, independent worker enrollment, asynchronous read-only
aggregation and inert desktop/mobile cards. Normal installed Windows workers
with different dependencies and same-host offline Linux workers have separate
raw qualification records. The source audit measured 1,309 passes, six skips,
77% framework coverage, ten passing chains and one skip with stable identities.
This supersedes the earlier absence of candidate aggregation, not the pending
production migration or installed-controller qualification.

The thin project Agent skill and English quickstart are available in the
development branch. They do not establish a general reasoning Agent, new-machine
installation or scientific RSI. Public package/import/command naming, final
publication/CI, a fully closed incident-to-release-to-originating-project replay
with failed-candidate/rollback controls, and held-out research evaluation remain
open. See the [delivery plan](https://github.com/Computational-social-science/Eidos/blob/feature/shared-monitor/docs/REUSE-DELIVERY-PLAN.md).


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

## EIDOS Agent development checkpoint, 2026-11-04

The product name and additional `eidos-agent` console entry are implemented in
development. A normal Windows installation matches all 51 SDK modules and both
console entries. Distribution/import namespace migration remains open. The local
incident ledger has reviewed source-level rejection, rollback, adoption, replay
and stale-closure guards; the real published originating-project campaign is
still open. Unit publication fixtures do not close that campaign.

After the host reboot, Startup selected project Python 3.12 for the existing
monitor/scheduler. A targeted local source probe fix resolved a real recurrence
without restarting those services; the old timeout and cumulative failures are
retained. This supersedes older current-runtime observations about global Python
loops, but does not deploy the unreleased shared-worker/controller protocol.
See [the incident](RUNTIME-INCIDENT-INFERENCE-2026-11-03.md),
[naming ADR](ADR-EIDOS-AGENT-NAMING.md) and
[feedback contract](FEEDBACK-LIFECYCLE.md).


## Accepted software delivery, 2026-11-04

The 0.5.0 compatibility preview is actually published and the original Eidos
software incident closes through fifteen linked events. The first remote-CI and
publication-identity refusals remain preserved; current preparation and identity
guards pass their separate controls and fresh rehearsal. The current table above
supersedes earlier development checkpoints for these software capabilities. The
resident controller remains 0.4.12, and scientific RSI remains unqualified. See
[the actual delivery record](RELEASE-PUBLICATION-0.5.0.json) and
[local deployment boundaries](LOCAL-DEPLOYMENT-STATUS-2026-11-04.md).
