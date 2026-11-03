# Installed availability-probe repair

The [probe-fix-v2 record](recorded_trials/probe-fix-v3/acceptance.json) binds a
published 0.4.12 wheel and an unreleased repaired 0.5.0 wheel in separate normal
Windows and same-host network-disabled Linux prefixes. A private CLI reproduces inherited stdout/stderr handles;
the old arm must time out after the child-start and client-finish witnesses.
The repaired arm must return with its descendant already gone, before the outer
controller can clean up. Missing/nonzero CLI controls remain unavailable.

The driver binds its bytes, the trusted fixture, complete worker SDK sources,
distribution identity/metadata, controller SDK/runtime and generated CLI inputs
before/after. It is not hostile-code attestation or real-model qualification.
The fake Windows Python executable/DLL hashes are recorded; system binaries are
not redistributed. Use a matching local Python runtime to regenerate them.

Prepare `env-old` and `env-new` under a new workspace, install the hash-locked
core dependencies and the corresponding wheels, using `uv pip install --link-mode
copy` for mutable failure-injection trials. Default hardlinks do not provide
file-level independence. Then run with a qualified controller SDK environment:

```text
python reference/inference_probe_acceptance/check.py --workspace <prepared-root> --fixture tests/test_inference_probe_lifetime.py --old-wheel <0.4.12-wheel> --new-wheel <repaired-wheel>
```

Existing `results` is refused. The fixture is trusted executable test code,
not an untrusted upload. No actual Ollama service is contacted or restarted.
The CLI smoke separately verifies init, deliberate scientific refusal, status
and local feedback without altering installed identity.

The first measured driver was withdrawn because it lacked both-arm entry
witnesses. The first metadata negative control was also withdrawn: in-place
mutation propagated through uv hardlinks. Recovery and an atomic isolated v2
control are retained. Only the strengthened final replay and v2 control support
acceptance. Raw withdrawn PASS files are not acceptance evidence.

Initial Linux trials failed on CRLF setup and a noexec scratch mount; the required
entry witnesses correctly prevented acceptance. A fresh network-disabled container
with executable private scratch then passed the full old/new installed probe
controls with hash-locked dependencies, readonly root/input mounts and verified
owned-container removal. Earlier failures remain retained. This is same-host
caller qualification, not shared UI, new-machine, production migration, a released
fix, originating-project closure, rollback or scientific RSI.
