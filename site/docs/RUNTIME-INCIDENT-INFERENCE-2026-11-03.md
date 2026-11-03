# Inference availability-probe incident, 2026-11-03

State: **REPRODUCED; candidate repaired; release/downstream closure open**.

The production dashboard had fresh advancing samples but reported ALARM from
scheduler_failures. The recorded inference check timed out after 900 seconds.
This check verifies model routing/budget declarations; it does not run a research
LLM. Independent owned NVMe and exFAT status-store probes passed quickly, so those
results alone did not identify the intermittent production failure.

A read-only py-spy dump of the actual stalled chain identified
ModelManager._check_ollama -> subprocess.run -> communicate -> reader-thread join.
The raw root-process timeout did not own all inherited pipe lifetimes. A separate
owned page-build helper showed the chain caller waiting in communicate as well.
Only that newly created helper tree was stopped after identity/ancestry checks;
no existing Ollama, monitor, scheduler or other service was stopped/restarted.

A private CLI reproducer starts a descendant holding stdout/stderr, records its
PID and root-exit witness, then exits. The old source fails its bounded caller.
The repaired probe uses the SDK-owned process lifetime and exposes programming
errors while mapping operational launch/timeout/containment failures to unavailable.
The descendant-exit check runs inside the worker before outer cleanup can mask it.

The strengthened reproducer independently rejects immutable 0.4.12 source
(2 failed, 2 passed). The repaired source passed eight scoped private tests,
including nonzero/missing CLI and operational failure controls. Separate Python
and code reviews approved the fix after correcting the cleanup proof, POSIX path
quoting and process-disappearance race. Initial 28-case inference regression and
45-case worker/probe integration passed. The renewed full candidate audit completed: 1,317 passed, six skipped,
77% framework coverage, ten passing chains and one skip, with stable identities.

The strengthened normal Windows installed old/new replay passed. Linux attempts
did not establish the required counterfactual and are not accepted. A separate
metadata negative-control mistake exposed uv hardlink aliasing; the original
control was withdrawn, affected own metadata aliases restored, and an atomic
isolated control passed. Production later returned OK naturally; the new source
was not deployed and this does not prove repair recovery.
Production remains a separate loaded runtime: this document does not clear the
alarm or claim recovery. Preserve actual release publication, selected-version
originating-project replay, a failed candidate and exercised rollback before
closing the incident. No scientific RSI or autonomous repair claim is made.

Raw local evidence is retained under .scratch/quality and in the isolated
shared-monitor development campaign. Publish sanitized receipts with the candidate;
do not upload unrelated runtime logs or private project data automatically.


### Subsequent Linux caller qualification

The missing Linux entry witnesses were traced to a noexec scratch mount. With
explicit executable private scratch, a fresh network-disabled/read-only-root
container passed the actual installed old/new probe campaign with unchanged
input/wheelhouse/SDK/metadata identities and verified owned-container cleanup.
The final `reference/inference_probe_acceptance/recorded_trials/probe-fix-v3`
profile supersedes v2 as this caller acceptance; failed attempts and withdrawn
controls remain preserved. This closes only the availability-probe Linux gap,
not current-wheel shared UI, new-machine, release/rollback or scientific RSI.
