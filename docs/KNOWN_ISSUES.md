# Known issues (host-specific, measured)

These are recorded with the evidence that produced them, not as folklore. Each
entry states what was observed, how to reproduce it, and the design decision it
forced.

---

## 1. chromadb + sentence-transformers segfaults this Python 3.14 install

**Observed:** `python -c "import chromadb; from sentence_transformers import SentenceTransformer"`
prints `c ok` and then dies with `Segmentation fault` (exit 139). The reverse
order (`sentence_transformers` first) also dies at the chromadb import. Each
package imports cleanly on its own.

**Why it matters:** a segfault cannot be caught by `try/except`. Any library that
imports both at module scope takes the whole pipeline down, and the failure
looks like a crash rather than a gate failure.

**What it decided:** the framework carries **no vector store**. A memory layer
(`framework/memory`) was built with two backends, exercised, and deleted because
no project wrote to it; cross-project knowledge lives in agent skills and
project-local history lives in each project's own `LESSONS` file. The backend
split below is recorded because it is the design that survives this host if a
vector store is ever needed again:

| `backend` | Store | Embeddings |
|---|---|---|
| `json` | local JSON file | optional sentence-transformers, else a deterministic hash |
| `chromadb` | Chroma persistent client | Chroma's own embedding function; sentence-transformers is never imported |

**Reproduce the observation:** run the two-line command above; it segfaults. The
tests that covered the memory backends were deleted with the module.

**If a future Python/chromadb build fixes the clash:** the split can be relaxed,
but only after `import chromadb; import sentence_transformers` is re-tested in a
single process on the target interpreter.

---

## 2. opentelemetry version conflict after installing chromadb

> chromadb is no longer a framework dependency (the memory layer was removed), so
> this conflict only matters if a project installs it for its own purposes.

**Observed:** `pip install chromadb` upgraded
`opentelemetry-semantic-conventions` to `0.66b1`, while
`opentelemetry-instrumentation-asgi/fastapi/sqlalchemy 0.61b0` require
`==0.61b0`. pip reports the conflict but installs anyway.

**Impact:** none observed for the framework's own paths. It matters if a project
enables OpenTelemetry instrumentation for FastAPI/SQLAlchemy.

**Mitigation:** pin `opentelemetry-semantic-conventions==0.61b0` in a project
that needs those instrumentations, or avoid installing chromadb in that
environment.

---

## 3. PyPI resolution backtracks instead of failing fast on a large tree

**Observed:** `pip install mlflow dvc inspect-ai deepeval ragas chromadb` ran for
>15 minutes without installing anything (3 GB RSS, 14 s CPU). The resolver log
shows it walking opentelemetry versions one at a time:

```
Collecting opentelemetry-sdk<3,>=1.9.0 (from mlflow-skinny==3.17.1->mlflow)
  Downloading opentelemetry_sdk-1.42.1 ... 1.42.0 ... 1.41.1 ...
INFO: pip is still looking at multiple versions of opentelemetry-sdk
```

**Root cause:** `mlflow-skinny` accepts a wide `opentelemetry-sdk` range, while
`chromadb`'s OTLP exporter pins an exact `opentelemetry-exporter-otlp-proto-common`
version. Each pin invalidates the previous candidate, so pip re-solves the whole
tree for every version instead of reporting the conflict.

**Design decision:** install extras **one at a time**, and prefer
`mlflow-skinny` (tracking API without the UI stack) when only run logging is
needed. Individually, each install completed in seconds to a couple of minutes.

```
pip install mlflow-skinny
pip install dvc
pip install chromadb
pip install inspect-ai
```

`deepeval` and `ragas` are intentionally left out of the default setup; their
gates fail loudly with a missing-tool message until a project installs them.

---

## 4. Scripts directory not on PATH (Windows, user installs)

`pip install` places `mlflow.exe`, `dvc.exe`, `inspect.exe` in
`%APPDATA%\Python\Python314\Scripts`, which is not on PATH. Either add it or
invoke the tools as modules (`python -m dvc ...`).

---

## 5. A bulk install silently rebinds shared packages

**Observed:** installing `mlflow dvc chromadb inspect-ai` in one command
completed, but also replaced packages the rest of the environment shares:

| package | before | after |
|---|---|---|
| `pydantic` | 2.12.5 | 2.14.1 |
| `anyio` | 4.12.1 | 4.15.1 |
| `cryptography` | 46.0.6 | 50.0.2 |
| `fsspec` | 2026.7.0 | **2026.6.0** (downgraded) |

**Why it matters:** this is a user-site Python (`C:\Python314`) shared by
figpipe, keystroke-observatory and the framework. A dependency bound decided by
one project silently changes the interpreter for all of them, and `fsspec` moved
*backwards*.

**Verified after the change:** Eidos 25/25 tests pass; `figpipe 0.5.0` imports;
pandas/numpy/matplotlib import. No breakage was observed *this time* — which is
luck, not a guarantee.

**Rule:** install into a project virtualenv (`uv venv`) when the project has its
own dependency set; keep the shared interpreter for tools that must be global.
Record the versions a project was validated against.

