# Windows recovery shell compatibility incident

Status: local monitoring restored; 0.4.12 installed-wheel candidate qualification
completed. Release publication remains pending.

## Observed failure

The monitor at 127.0.0.1:8765 had no listening process. Its prior supervisor
was also absent; the old log records process exit, not enough evidence to
attribute the shutdown to a particular cause. The existing hidden launcher was
started independently of the interactive agent execution lifetime. HTTP and
an installed Edge browser then returned 200 with no page JavaScript errors.
Advancing sample sequence and `stale=false` established continued sampling.

The retained recovery loop restored runtime_18434, but decision_service remained
down. Its recovery log showed WSL Bash rejecting the MSYS path
`/e/2026-AI4S/decision-service/scripts/serve.sh`. A detached Startup process does
not necessarily inherit the development terminal's SHELL or Git PATH. Finding
an executable called bash is not evidence that it accepts the caller's paths.

## Repair and bounded controls

Windows recovery now checks explicit EIDOS_BASH strictly, then considers SHELL,
standard Git installation locations and PATH. Known WSL/System32 aliases are
rejected before execution. A hidden, owned five-second process tests whether the
candidate can actually read the translated path to the recovery module. The
probe requires both exit zero and an exact marker; it does not source BASH_ENV
or ENV. This is a compatibility probe, not binary attestation or an OS sandbox.
POSIX shell selection retains the native path convention.

An initial OSTYPE-based implementation was rejected by actual measurement:
this host's Git Bash reported `cygwin`. The final probe tests the required path
behavior directly. The actual resolver selected
`C:/Program Files/Git/bin/bash.exe` and read the Windows source path successfully.

Missing/incompatible shells are refused before reserving a service start.
Durable state transactions may still publish an empty state file; refusal must
not consume a launch attempt or create an in-flight reservation. Health checks,
port ownership, retry budgets, cooldown and measured terminal verification are
retained. The first explicit actual-service request correctly returned NO_LAUNCH
because the prior failure's cooldown had not elapsed; that is not a recovery
success. No budget or failure history was reset.

The original implementation failed three new shell-selection controls. After
repair, 49 scoped recovery controls passed, including actual installed Git Bash
execution and the no-budget/no-launch refusal check. The completed full source
audit records 1,200 passes, six skips, no failures/errors and 75% framework
coverage, with identical before/after source/distribution fingerprints.
Its initial chain measurement was nine passes and two skips while the decision
service was unavailable. A separate post-recovery chain run measured ten passes,
one explicit optional-project-checker skip and no failures. The earlier result
was retained. This does not qualify a new installed wheel.

Only the new monitor processes created during this incident were refreshed to
load the repair. Their parent relationships, command identity and creation times
were checked before stopping those specific processes. Existing model/runtime
processes were retained. No external CRON or new Startup entry was installed.

## Publication and remaining acceptance

At 16:42:36 Asia/Shanghai the retained monitor initiated the next permitted
decision-service attempt using the corrected source. The service became ready
at 16:43:19, and recovery recorded a verified terminal outcome at 16:43:25.
Independent HTTP reads then returned 200 from both 8081/health and 8090/health.
The latter identified the local StartLux GGUF model and llama.cpp backend.
The monitor returned overall OK, stale=false and an advancing sequence. This
was an actual automatic recovery after cooldown, not the earlier NO_LAUNCH call.
No Gemini or paid model API was used.

The published v0.4.11 wheel and its evidence remain historical immutable
artifacts. This source change requires fresh self-audit and recovery acceptance,
then a new package version, installed-wheel replay and publication checks.
Four additional controls exposed relative/expanded override paths that failed
or changed meaning when the service working directory changed. Configuration is
now expanded and resolved before probing, and the same absolute executable is
returned for launch. Windows/POSIX relative and expanded paths all pass; the
scoped suite reached 53 passes. Two further POSIX fallback controls closed
relative PATH discovery and missing-Bash launch reservation; the final scoped
suite has 55 passes. The final source audit measured 1,206 passes, six skips,
75% coverage and 10 PASS / 1 SKIP chains. The 0.4.12 candidate then completed
the installed Windows/Linux replay described in the
[candidate checkpoint](RELEASE-CANDIDATE-0.4.12.md). Release metadata and publication
remain pending; this does not change the published 0.4.11 tag or assets.
Do not update old source hashes simply to preserve a PASS label. Actual local
decision-service restoration is distinct from generic disposable-service tests;
neither alone proves the entire research or RSI pipeline.

Operational observations are recorded in
`docs/status/monitor-restoration-2026-11-02.json`. Development logs, the failed
OSTYPE experiment and guarded startup observation are retained under
`.scratch/quality/`; they are not a portable published acceptance archive yet.

## Live browser recheck at 18:26 Asia/Shanghai

An independent installed Microsoft Edge headless session returned HTTP 200 from
both `/` and `/dashboard.html`, with no page JavaScript errors. Across a
22-second observation the sample sequence advanced from 18,334 to 18,336;
the final observation was 2.8 seconds old, `overall=OK` and `stale=false`.
The rendered dashboard displayed `Live sample`. The API reported 17 services
up, none down, ten passing chains and one explicit optional-checker skip.

The existing supervisor and listener remained running during this recheck;
no restart, new CRON, recovery-budget reset or model-service interruption was
needed. This is operational verification, not a scientific or release claim.
The compact evidence is in
`docs/status/monitor-recheck-2026-11-02.json`.
