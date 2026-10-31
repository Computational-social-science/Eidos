# Declared executable research delivery

Added for v0.4.2. The release record/tag proves publication separately from the
bounded execution qualification in `docs/PACKAGE-ACCEPTANCE.json`.

The former Quarto packager copied guessed directories, omitted the Python project
and lock, installed a missing requirements file and printed nonexistent commands.
It now delegates to `framework/executable_package.py`. A missing declaration is an
error. Generation returns `execution_verified: false`; it does not run research.

```python
from framework.quarto_bridge import QuartoBridge

bridge = QuartoBridge({
    "project_root": "/path/to/study",
    "executable_package": {
        "files": ["pyproject.toml", "uv.lock", "run.py", "check.py", "data/input.csv"],
        "command": ["python", "run.py"],
        "verify_command": ["python", "check.py"],
        "outputs": ["results/evidence.json"],
        "seed": 42,
        "data_version": "input-v1",
        "config_version": "protocol-v1",
        "extras": [],
    },
})
delivery = bridge.build_executable_package("study-delivery")
```

List every required source, data, config and licence file explicitly. Directories,
globs, hidden files, linked inputs, path traversal, Windows aliases, collisions
with generated files and existing output packages are rejected. Add all modules
needed by the project's package build. A seed of `null` requires `seed_reason`.
These values document provenance; the packager cannot enforce seed use inside
arbitrary project code or establish that a validator is scientifically independent.

From the generated directory:

```sh
uv sync --locked --no-dev --python 3.12
uv run --no-sync python eidos-reproduce.py
```

Append declared `--extra NAME` options to the install command. The installed
environment is isolated; dependencies are checked against the copied lock.
Generated Docker and Binder instructions use the same install contract. The Docker
image supplies Python 3.12 and a pinned uv binary. Base image tags are not immutable
digests; capture resolved image identity in container acceptance records.

The runner verifies input hashes, refuses existing declared outputs, runs the two
explicit Python commands without a shell, requires all declared output files,
then verifies that neither inputs nor manifest changed. Only then does it write
`execution-record.json` with Python/interpreter identity, manifest digest, declared
versions/seed and output hashes. Each copy is claimed exclusively before commands
start; a competing process cannot execute it a second time. The claim remains after
success or failure. The completed record is published by atomic replacement.
Use a fresh copy for another run. The manifest is
an accidental-change detector, not signed attestation or a sandbox for untrusted code.

## Verified local and container replay

The acceptance ZIP at `reference/package_delivery_acceptance/package.zip` contains
only declared inputs and generated launch files, without results from earlier runs.
Extract a new copy for each local or Docker replay. Building a container from an
already executed copy carries its old outputs into the image and is deliberately
rejected by the runner.

The recorded same-host tests pass in a new Windows environment and an offline
Linux container: all 12 numerical cases pass, and both broken controls are rejected.
The two-process regression permits exactly one invocation. See
`docs/PACKAGE-ACCEPTANCE.json` for source/archive/manifest/image/output hashes and
the exact installation/runtime scope. This is not a separate new-machine test.

Docker Hub's token endpoint failed on this host. The successful build used the
official Python image in AWS ECR, pinned by digest, through Docker's image-context
override. From a fresh extracted package:

```sh
docker build --build-context python:3.12-slim-bookworm=docker-image://public.ecr.aws/docker/library/python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 -t eidos-research .
docker run --rm --network none eidos-research
```

The recorded build also passed `HTTP_PROXY` and `HTTPS_PROXY` build arguments for
this host's existing `http://host.docker.internal:7890` proxy. Supply your own
working proxy when needed; it is not required by the package's runtime. The
default-registry failure remains recorded separately from the successful override.
The override follows [Docker's named-context contract](https://docs.docker.com/build/concepts/context/).

Quarto/TeX, GPU drivers, external services and undeclared remote data are not bundled.
Do not infer full manuscript rendering, training replication or a remote Binder
launch from this Python delivery contract. A checked output only means the declared
validator accepted it; scientific gate qualification remains a separate requirement.

Sources for the installation mechanism:
[uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/),
[uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/),
[Binder configuration](https://mybinder.readthedocs.io/en/latest/introduction.html).
