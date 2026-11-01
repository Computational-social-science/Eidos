# Configured local C0 runtime

This source-checkout CLI runs one public numerical proposal with a trusted local
llama.cpp server and GGUF model. It needs **no provider key, paid API, subscription
or model download**. You supply existing files and their identities. A GPU is not
required by this CPU baseline. The model is not scientifically qualified by
being installed or by completing a request.

The [first actual execution](../../docs/RSI-LOCAL-RUNTIME-2026-11-02.md) completed
its runtime checks but failed all 23 joint numerical development points. This is
same-host Windows evidence, not a new-machine, installed-wheel or Linux model
qualification. The runtime is an additional research work package on `main`,
not a retroactive addition to the immutable v0.4.10 wheel.

## Prerequisites and configuration

Clone the repository and use its project environment with NumPy and psutil
installed from the frozen lock. Work from the repository root. The native
[`llama-server`](https://github.com/ggml-org/llama.cpp) executable must support the recorded CLI options, including
`--device none`, `--no-kv-offload`, `--no-op-offload`, `--reasoning off`,
`--reasoning-budget 0` and the GBNF HTTP request field. Backend incompatibility
is an explicit failure, never a hosted fallback. Do not use an untrusted binary
or weights; hashing a file pins its identity but does not authenticate its origin.
Review code/model/dependency licenses before redistribution.

Create a JSON configuration. Engine/model paths can be absolute or relative to
the configuration file, regardless of the caller's working directory:

```json
{
  "engine": {"path": "../runtime/llama-server", "sha256": "REPLACE_WITH_64_LOWERCASE_HEX_DIGITS"},
  "model": {"path": "../models/model.gguf", "sha256": "REPLACE_WITH_64_LOWERCASE_HEX_DIGITS", "bytes": 5027784544},
  "limits": {
    "load_seconds": 150, "request_seconds": 480, "evaluation_seconds": 30,
    "total_seconds": 900, "threads": 8, "context": 4096, "max_tokens": 768,
    "min_available_memory_mib": 4096, "max_tree_rss_mib": 12288
  },
  "protected_services": []
}
```

The paths, hashes and byte count above are placeholders; use your actual local
files. For example, in the project's Python:

```python
import hashlib
from pathlib import Path

artifact = Path("path/to/your/model.gguf")
with artifact.open("rb") as handle:
    print(hashlib.file_digest(handle, "sha256").hexdigest())
print(artifact.stat().st_size)
```

Choose limits for your actual RAM/CPU. Weights must fit the declared model-tree
RSS budget, and available RAM before launch must cover weights plus the reserve.
The whole deadline must include load, target request, isolated evaluation,
post-target control and cleanup. Memory/log checks are sampled abort controls,
not hard operating-system quotas. The RSS sample covers the model process tree;
the available-RAM check observes system-wide headroom.

If a resident service must be preserved, explicitly declare its observations:

```json
{"url":"http://127.0.0.1:8081/health","expected":{"status":"ok"},"listener_port":8081}
```

Add such objects to `protected_services`. Nonempty expected JSON projections
and listener PID/creation-time/executable identities are checked before, during
and after the trial. Only numeric loopback HTTP URLs with explicit ports are
accepted. Proxies, embedded credentials and redirects are refused. An empty list
does **not** measure protection of other services. This runtime never restarts,
unloads or terminates a protected process.

## Execute once and inspect both outcomes

Here `python` means the activated project interpreter, not an arbitrary system
Python or the host's separate CUDA research environment.

```text
python -m reference.rsi_bootstrap.local_runtime --config local-model.json --output runs/c0-001
```

The output directory must be new. Reusing it is refused; failures are never
overwritten. Each attempt has a fresh owned server, nonce and source/config
protocol. The original C0 prompt, seed 19, temperature 0, top_p 0.9 and thinking
off are fixed. CPU execution is explicit, not an automatic GPU fallback.

Read `outcome.json` and `core.json` together:

| CLI contract | Meaning |
|---|---|
| Exit 0 | Runtime accepted and the candidate conforms on all public development points. No scientific promotion. |
| Exit 2 | Runtime accepted, but the candidate is malformed or numerically nonconforming. This is an experimental failure, not a runtime pass for the candidate. |
| Exit 1 | Prerequisite/configuration or runtime/evidence acceptance failed. |

Shell wrappers can map native exit codes differently. Preserve `$LASTEXITCODE`
explicitly in PowerShell automation, and use the structured outcome to distinguish
runtime failure from mathematical failure. Do not turn a nonzero command into a
successful research result merely because a process completed.

The directory retains protocol, actual provider response, independently executed
core evaluation, controller result, outcome and logs. Inspect the exact recorded
core status and all points; a finite forward value is not a gradient check.
The post-target literal grammar control is only a backend smoke check. It does
not qualify every decoder rule or establish scientific competence.

## Evidence boundary

The SDK outer owner bounds process-tree lifetime; the controller terminates only
its own model handle. Numeric requests use absolute HTTP wall deadlines and
bounded response reads. Protected-service requests close only the client's own
connection on timeout. RAM/log and service watchers are separate so a slow
protected endpoint cannot stop resource sampling.

The evaluator has its own deadline and records its actual Python/NumPy/psutil
identity. Protocol/source/config/response/nonce bindings are checked. The parent
replays the same numerical oracle to reject inconsistent point inventories,
substituted inputs, false counts or contradictory receipts. This replay is a
coherence check, not a second independent scientific authority.

The binary/model and local maintainer environment are trusted. This is not a
hostile-code sandbox, an OS network-egress barrier, a hard memory/disk limit or
remote attestation. Generated candidate Python is never executed; candidates
use the existing closed scalar expression interpreter. Package runtime identity
records do not fingerprint every transitive binary dependency.

The historical [C0 specification](C0-SPEC.md) retains its original profile and
scope. GPU portability, clean-machine installation, sealed-task separation,
method-retrieval/feedback campaigns and improvement of the improver require
separate acceptance. No new scheduler or CRON task is installed.
