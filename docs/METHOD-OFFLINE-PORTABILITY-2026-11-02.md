# Actual offline Linux reuse of the sourced numerical method tool

Status: completed same-host Linux container acceptance, 2 November 2026
(Asia/Shanghai). A fresh venv containing only NumPy and pip completed the actual
recorded-response comparison and fresh readers without runtime network access.
**The original model proposal remains 0/23; the separately compiled external
known method remains 23/23. No new model inference, tool-selection competence,
scientific promotion or RSI is demonstrated.**

The [machine record](METHOD-OFFLINE-PORTABILITY-2026-11-02.json),
[raw evidence](../reference/method_portability/recorded_trials/linux-v1/) and
[reproduction guide](../reference/method_portability/README.md) retain the
method/input identities, exact commands/exit observations, both evaluator outputs,
source snapshots, network/resource configuration and owned-container cleanup.

## What this acceptance adds

The [earlier Windows execution](NUMERICAL-METHOD-COMPILER-2026-11-02.md) established
a source-checkout formula compiler. It did not establish Linux execution,
minimal dependencies or a network-disabled path. This run created a fresh venv
inside a public pinned Linux image, with only the lock-selected NumPy research
dependency plus pip, and ran the same public saved-response/method task there.
The host's installed EIDOS, tracking packages and model services were not mounted.

The [preregistered contract](../.Codex/evals/method-offline-portability.md) preceded
implementation and execution. Input preparation froze 25 source/contract/catalog/
lock/CI files plus the exact previously archived T1 response. The source ZIP is a
curated source subset, not a preinstalled EIDOS wheel. The new Linux receipt has
its own source/runtime identity; historical Windows records retain their original
frozen context and require a new replay when raw source/runtime differs.

## Bootstrap and actual environment

| Input or setting | Observed/pinned value |
|---|---|
| Public base | `public.ecr.aws/docker/library/python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337` |
| Target/runtime | Linux x86_64; CPython 3.12.16 |
| Fresh distributions | NumPy 2.5.4 and pip 25.0.1 only |
| Python isolation | New venv; different base prefix; user site disabled; clean child environment |
| Networking | Docker NetworkMode=none before/after; socket-connect probe returned unreachability, errno 101 |
| Filesystems | Read-only container root and input mount; new owned output mount; private 1 GiB /tmp tmpfs |
| Bounds | 2 CPUs, 2 GiB memory, 128 PIDs, dropped capabilities, no new privileges |
| Deadlines | Per-step limits, 180-second worker alarm, separate 240-second parent wait |

The selected wheel is
`numpy-2.5.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`,
16,727,283 bytes, SHA-256
`fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a`.
Its exact public URL and lock pin are retained in the machine record. The host
download took 13.221 seconds and completed **before** isolation. The image was
already cached and was used with `--pull never`. Bootstrap network access is
separate from the offline execution claim; no cold offline bootstrap is implied.
Image and wheel binaries are identified rather than redistributed.

The installer used `--no-index`, `--no-deps`, `--require-hashes`, no cache and
binary wheels only. These are documented
[pip controls](https://pip.pypa.io/en/stable/cli/pip_install/). The parent inspected
the actual [Docker configuration](https://docs.docker.com/reference/cli/docker/container/run/)
before start and after exit. The unreachable socket probe is supplementary;
it does not independently prove network isolation without those inspections.

## Complete execution outcomes

| Step | Actual exit | Seconds | Interpretation |
|---|---:|---:|---|
| Fresh venv | 0 | 2.836 | Local image's bundled pip bootstrap |
| Hash-required NumPy installation | 0 | 2.092 | Provided wheel only; no package index |
| Environment/source inspection | 0 | 0.349 | NumPy+pip only; frozen curated source closure |
| Deliberately wrong response pin | 1 | 0.279 | Expected refusal; no candidate output published |
| Actual method CLI | 0 | 1.923 | Saved proposal 0/23; separate external tool 23/23 |
| Fresh CLI reader | 0 | 2.411 | Full source/input/program/outcome verification |
| Fresh API reader and memory binding | 0 | 3.021 | Verified identities handed to the parent |

All timings are single observations. The worker measured 14.265 seconds, including
input/extraction/checking overhead. The host controller measured 24.350 seconds
from after input preparation/plan through container cleanup. Initial wheel
download and input preparation are outside that controller duration; preparation
was not separately timed. These are scoped measurements, not throughput claims
or a fair comparison with the earlier LLM generation costs.

The numerical task, 23 represented float32/64 points, Decimal420/520 convergence,
relative tolerances 2e-5/2e-12, joint loss/derivative criterion and sign checks are
unchanged. There is no absolute-gradient floor. The derivative/formulas are
externally supplied known methods, not model discoveries or automatic derivations.
Replaying the old response does not create another independent model trial or
scientific task. No reliability interval or p-value is inferred from these points.

## Portability defects prevented before execution

The lock contains both NumPy 2.4.6 and 2.5.4, with cp312 Linux wheels available for
both. Filename matching alone could select a version that the target lock markers
exclude. Preparation now uses the existing
[packaging marker evaluator](https://packaging.pypa.io/en/stable/markers.html)
with the target environment, then requires one exact wheel/version/hash/size.
No independent dependency resolver or private fallback was added.

Review also rejected an assumption that the registry digest must equal the local
Docker image ID. The implementation now verifies the public digest reference in
`RepoDigests`, captures the local ID separately and binds both container inspections
to it. A positive test explicitly uses different values. This prevents a test
fixture from reinforcing the same incorrect assumption as the implementation.

The suite passed **304 scoped controls before execution**: 180 existing RSI,
68 compiler and 56 new portability controls. Controls cover unsafe/duplicate/
symlink/unlisted ZIP entries, changed wheel/source/harness/requirements, existing
destinations, reader handoff mutations, typed verdicts and altered container
ownership/image/network/mount/resource configurations. Synthetic checks are not
substitutes for the actual container run or new model evidence.

## Provenance, cleanup and scope

Input SHA-256:
`592b231d548d0d103f5aa50c830fc3b891a086b95f4429cb4bc639e95a7597b8`.
Linux execution run: `ebf98abb717545adabcb2fa226de8595`.
Worker receipt SHA-256:
`b8e7ea5989c19fa0613201d73c76875c18fa97829d984b65a7901a503711c55d`.
Controller receipt SHA-256:
`f5b562dc91a7a65295d90830a56725154b30e04e08175c707b4e95f034007d23`.

The parent validates the fresh reader's captured record/file identities rather
than recomputing hashes of changed files and treating them as accepted. It also
checks every command log and complete artifact inventory, frozen input/source
bytes and typed expected outcomes. The archive includes a pinned controller plan
and an explicit, contained qualification-source inventory. Environment values
and unrelated logging configuration are excluded from Docker projections.

The container was created with an attempt-specific ID/name/owner label. Only
that owned ID was removed after its observed exit-zero state; a subsequent
Docker inspection returned an explicit missing-container response. No legacy
model/monitor service was stopped or restarted, and no CRON/Startup task was
added. Release labels/assets and the v0.4.10 wheel are unchanged.

This is a same-physical-host, trusted-Docker-daemon/kernel container observation.
It does not certify an independent machine, an installed EIDOS wheel, cold
offline bootstrap, persistent storage, a hostile OS, live-model selection or
model-service portability, GPU/vector/AMP/higher-order support, novel science,
sealed transfer or RSI. The next steps remain independent-machine/package
acceptance and bounded local tool selection with explicit assistance attribution,
followed by the preregistered feedback-policy and fresh-task improvement tests.
