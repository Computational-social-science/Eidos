# Offline Linux replay of the sourced numerical method tool

Declared 2026-11-02 before implementation/execution. Prior source checkpoint:
2aed9ed. Continue the free local reuse requirement, without rewriting historical
Windows records or claiming new model inference/RSI.

## Target

Qualify an actual before/after recorded-response CLI run and fresh reader inside
an isolated Linux container, with a fresh venv containing only the locked NumPy
research dependency and packaging support. Preserve the same public T1 input,
known method and unchanged 23-point oracle/relative tolerances/sign checks.
This is same-host Linux source replay, not independent-machine, model, installed
Eidos-wheel, autonomous tool-selection or scientific-transfer acceptance.

## Inputs and bootstrap

- Use the public Python3.12 slim-bookworm image through an explicit immutable
  public ECR digest; record local image identity and actual Docker configuration.
  Do not equate registry manifest/index digests with local image/config IDs:
  verify the exact RepoDigests reference, then bind the resolved local ID separately.
  Missing image is an unmet prerequisite, never a silent private-image fallback.
- Select the CPython3.12 Linux x86_64 manylinux NumPy wheel from uv.lock, including
  exact URL/SHA/size/version. Accept only that provided wheel. Bootstrap download
  may use the public pinned URL before isolation; disclose it separately.
- Prepare a new, explicit input directory containing a bounded manifest/source
  ZIP, the checked wheel, a hash-required requirements file and the container
  harness. Curate the compiler's source closure plus the pinned public response.
  No .git, private data, host credentials, venv or model artifact is mounted.
- Bind all source/archive/requirements/wheel/harness bytes. Refuse unsafe/duplicate
  ZIP paths, symlinks/nonregular entries, unlisted/missing files, extra sources,
  hash/size mismatch, existing destinations and source drift.

## Execution

Run only a new owned container, network mode none, read-only root filesystem,
private tmpfs /tmp, bounded CPU/memory/PID limits, dropped capabilities and no
new privileges. Mount input read-only and a fresh owned output directory writable.
Never stop/reconfigure legacy services or add CRON/Startup work.
The output bind mount must be newly allocated and empty; existing per-execution
directories and nonempty output mounts are refused. The declared limits are
2 CPUs, 2 GiB memory, 128 PIDs and 1 GiB private /tmp, with a 180-second worker
alarm and a separate 240-second outer wait. The fresh CLI reader is followed by
a fresh API reader that hands its verified in-memory artifact identities to the
outer validator; mutable files cannot be absorbed as newly accepted hashes.

Inside it: verify every input; extract only the checked source files; create a
new venv; install the wheel with --no-index/--no-deps/--require-hashes; inspect
the actual installed distribution set; run the real method CLI and a separate
fresh reader with clean explicit environments and absolute per-step deadlines.
Use an independent whole-container timeout and preserve failure observations.
Runtime networking must be inspected as none and a non-data socket-connect probe
must observe unreachability; this is scoped container isolation, not a hostile
kernel/daemon attestation. Bootstrap itself is not claimed network-disabled.

Retain the raw response, both actual evaluator results, source/runtime records,
pip/CLI/reader logs, exact commands/exit outcomes and observed container state.
Producer and parent recompute file hashes and compare all expected source,
response, method, conformance and authority identities; incomplete/changed data
cannot be labeled accepted. Retain failed attempts, unknowns and cleanup state.

## Required controls

1. Lock wheel selection is explicit/unambiguous and never uses host Windows wheels.
2. Wrong wheel bytes, wrong raw response hash, changed/extra source, archive path
   traversal/symlink/duplicates and existing output refuse before acceptance.
3. Strict input/terminal schema, actual command/exit and artifact linkage are checked;
   fabricated scores and stale receipts refuse. Cleanup targets only owned IDs.
4. The actual isolated replay must retain original joint0/23 and separate external
   tool23/23, with all sign and Decimal checks; do not promote the original model.
5. Run the preparation/harness controls and existing scoped controls, then archive
   raw receipts/snapshots with immutable bytes. Publish English report/usage/limits,
   update technical framework and synchronize GitHub. Prior release assets stay intact.
