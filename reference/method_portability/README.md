# Offline Linux acceptance for the numerical method tool

This developer acceptance harness runs the sourced formula compiler in a fresh
Linux venv, with network access disabled during execution. It uses a public,
digest-pinned Python image and a NumPy wheel selected from `uv.lock` for the
target environment. No model, provider key, new scheduler or resident service
is involved. The ordinary [numerical tool](../numerical_method_tools/README.md)
also runs without Docker; this harness tests its Linux isolation/reuse path.

The [measured report](../../docs/METHOD-OFFLINE-PORTABILITY-2026-11-02.md) retains
the original saved proposal at 0/23 and the separate external known-method
program at 23/23. These are public development points, not scientific novelty,
new model inference, general transfer or RSI. The harness is a source-checkout
work package and is not part of the published v0.4.10 wheel.

## Prepare public inputs before isolation

Use the EIDOS project environment on the host. The preparer uses the existing
`packaging` marker parser from that environment; the fresh container runtime
has only NumPy and pip. The explicit profile is Linux x86_64, CPython 3.12.16,
NumPy 2.5.4. Other versions/architectures need a separately qualified profile.

```text
python -m reference.method_portability.prepare --wheel-info
```

This prints the exact public wheel URL, filename, SHA-256 and size from the lock.
Download those bytes using your usual HTTPS client, then supply the local file:

```text
python -m reference.method_portability.prepare --wheel /absolute/path/to/numpy-2.5.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl --output .scratch/method-linux-input
```

The destination must be new. This command does not download anything. It checks
the wheel and creates `input.json`, a curated source ZIP, a hash-required
requirements file, the standalone container harness and the checked wheel copy.
Retain the printed input SHA-256. The ZIP contains the compiler's frozen source
closure and one public saved response; it excludes private data, `.git`, host
venvs, credentials and model files. Existing destinations, changed inputs and
unsafe/duplicate/unlisted archive members are refused.

Both NumPy 2.4.6 and 2.5.4 in this lock publish cp312 wheels. Selection therefore
evaluates the target resolution markers before choosing a wheel; matching a
filename alone is insufficient. Catalog method-card identity remains independent
of JSON whitespace/newlines, while each run separately records raw source hashes.

The public image is:

```text
public.ecr.aws/docker/library/python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
```

If it is not cached, explicitly pull it before offline execution. Initial image/
wheel downloads require network access. The acceptance claim starts after those
bootstrap inputs are available; this is not a cold offline installation claim.
No private custom image or paid backend is needed.

## Run the isolated worker

Create a new empty output directory. Replace `ABS_INPUT`, `ABS_OUTPUT` and
`INPUT_SHA256` below with absolute host paths and the preparer's printed hash.
Use the complete command on one line in your shell:

```text
docker run --rm --pull never --platform linux/amd64 --network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 2147483648 --cpus 2 --pids-limit 128 --init --tmpfs /tmp:rw,exec,nosuid,nodev,size=1073741824,mode=1777 --mount type=bind,src=ABS_INPUT,dst=/input,readonly --mount type=bind,src=ABS_OUTPUT,dst=/out public.ecr.aws/docker/library/python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 python -I /input/check.py --input /input --sha256 INPUT_SHA256 --output /out
```

Quote mount arguments if host paths contain spaces. The worker creates a new
venv, installs the provided wheel with no index/dependency resolution and required
hash checking, verifies its distribution inventory, runs an actual wrong-pin
negative control, the method CLI, its CLI reader and a fresh API reader. The
last reader hands verified in-memory artifact identities to the outer checks.
No mutable output is accepted merely because its new hash can be computed.

`linux-result.json` is the terminal receipt; `progress.json` alone is not
acceptance. Failure retains diagnostics. A nonempty output mount is refused.
The worker has a 180-second alarm and per-step deadlines. The recorded parent
also had a separate 240-second wait, checked actual Docker settings before start
and after exit, and removed only its labeled owned container. The command above
replays the worker; it does not independently certify its caller's Docker setup.
For a full external audit, retain the container ID, inspect its actual image,
mounts/isolation/limits and exit status, then remove that owned container.

Do not equate a registry manifest/index digest with a local Docker image ID.
`validate_image` checks the immutable public reference in `RepoDigests` and
captures the local ID separately. `validate_container` binds that ID, command,
owned identity, input/output mounts and required resource/isolation settings.
These are trusted-daemon observations, not hostile-kernel attestation.

## Read the delivered evidence

The recorded archive preserves input metadata/source ZIP/harness, actual command
logs, the fresh tool result, reader binding, sanitized Docker inspections, source
snapshots and cleanup observations. The large NumPy wheel and Python image are
identified by public source and hashes; they are not redistributed. Archived
Python sources use `.snapshot` suffixes, so pytest cannot collect historical
test copies. Prepare a fresh input/output pair for a new replay.

This is same-host Linux container source acceptance. Independent-machine,
installed Eidos-wheel, live-model tool selection, model-service portability,
GPU/vector/AMP/higher-order behavior, new scientific gaps, sealed transfer and
RSI remain separate requirements. Temporary tmpfs does not establish durability.
Run the synthetic preparation/archive/ownership controls without Docker:

```text
python -m pytest reference/method_portability -q
```
