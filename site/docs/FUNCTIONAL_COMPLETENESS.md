# Functional completeness ledger

Baseline audit: 2026-10-31; executable-delivery update: 2026-11-01. Eidos remains pre-release. A successful case or self-audit
does not establish completeness. Acceptance means an executed, reproducible
lifecycle: onboard → register falsifiable claims → run → independently check →
reject unsupported claims → deliver → detect changes and revalidate.

| Capability | Current evidence | Remaining acceptance |
|---|---|---|
| Environment | Project Python 3.12, frozen lock, Linux CI 3.11/3.12; `AGENTS.md` | Complete new-machine installation with external Quarto/TeX and optional GPU backend. Inventory alone is insufficient. |
| Onboarding and registry | Safe bootstrap, isolated shell/registry tests; required-output checks | A new independent project must execute the entire lifecycle, including deliberate wrong evidence and missing outputs. |
| Scientific gates | `framework/validity/`, fixtures, mutations, `docs/SELF_AUDIT.json` | Structured evidence checks do not establish scientific truth or novelty. Evaluate unseen false acceptances and independent adopters. |
| Numerical capability | Decimal reference, actual CUDA tests, broken controls; `docs/CASE-SOFTMAX.md` | AMP/bfloat16, higher-order backward and other backends remain unqualified. Each needs independent references and broken controls. |
| Research execution | Three-seed paired reconstruction, source/lock/data hashes and models; `docs/SOFTMAX-TRAINING-FOLLOWUP.md` | Full paper training results are not reproduced. Align input representation, initialization and architecture before attributing differences to the repair. |
| Experimental acceptance | NumPy final inference and reloaded CUDA final gradients for all 36 matrix runs | Intermediate gradients remain producer-recorded; parent extension optimizer moments were not separately archived. No universal benefit or novel discovery established. |
| Consumer observation | Input-bound snapshots, atomic publication, single background recheck; `tests/test_consumer_snapshot.py` | Scope is registry, framework sources and declared Gate S file inputs. Underlying undeclared models/data require consumer validators. Formal toolchain snapshot binding is explicitly unqualified. |
| Scheduler and recovery | Heartbeat, lifetime lock, watchdog, transactional reload, attempt/verification separation; real Hermes watchdog dispatches after project-interpreter isolation | Multiple real watchdog dispatches pass with no console window; the daily contracts branch is bootstrap-tested but its scheduled dispatch remains unobserved. Reboot/logon and a clean 24-hour observation remain required. Past failures are retained. See [scheduler isolation](CRON-ISOLATION.md). Rechecking Gate S does not regenerate research evidence. |
| Inference and decisions | Local contracts, GPU budget tests, typed operator calibration | Calibration is bounded. Model scientific judgements missed acceptance thresholds and remain outside scientific gates. See `docs/MODEL_VERDICTS.md`. |
| Tracking and provenance | Optional DVC/MLflow chains and case-specific metadata | General deliveries need explicit required code/data/config/seed/checkpoint/run records, and must reject missing required provenance. Not every project uses both services. |
| Reporting and visualization | Shared manuscript policy, Quarto HTML/PDF/DOCX, physical font/dimension/PDF/Word audits and artifact fingerprints; `docs/PUBLICATION-QUALITY.md` | Every changed layout requires complete PDF/Word page inspection. Human metadata and journal-specific scientific review remain necessary. |
| Executable delivery | Explicit-manifest export, fresh Windows installation and offline Linux container replay; 12 numerical cases pass and 2 broken controls are rejected; exclusive execution ownership and atomic records | Same-host CPU acceptance uses an official ECR image override with pinned digest; default Docker Hub connectivity remains failed. Remote Binder, new-machine/Quarto/TeX/GPU qualification and lifecycle integration remain separate. See [delivery contract](EXECUTABLE-DELIVERY.md) and `docs/PACKAGE-ACCEPTANCE.json`. |
| Knowledge transfer | Existing Paper2Agent/MCP, filed failures/findings and reusable numerical checks | Demonstrate transfer to a second independent research problem and detection of a newly introduced error. Autonomous scientific self-improvement is not established. |
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

Negative controls keep their old artifacts and age by real Gate S verification
time. Positive consumers continue to age by research-evidence generation time;
rechecking does not make old positive evidence new. Hourly refresh selection uses
the same rule so an old negative fixture cannot monopolize refreshes.

## Work order and exit conditions

1. Close stale observation and schema defects with mutation/failure-path checks;
   verify advancing live samples and retain prior soak failures.
2. Repair generic packaging: bounded file manifest, lock-based installation,
   explicit reproduction command and required provenance, then a clean build/run.
   External Binder availability must be assessed separately.
3. Run an independently onboarded project end to end and reject injected wrong
   evidence, missing output and stale snapshots.
4. Align the paper reconstruction before extending precision/tasks; register
   criteria before execution and retain unfavorable outcomes.
5. Reassess every row against artifacts before declaring functional completeness.

This is an evidence map and work queue, not a machine-produced PASS certificate.
