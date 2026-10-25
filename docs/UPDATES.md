# Dependencies: sense, try, promote, roll back

Eidos depends on things it does not control: Quarto, DVC, MLflow, the llama.cpp build that serves
the decision model, and the GGUF weights themselves. This document is how those versions move.

The design separates three powers, because the failure mode of a self-updating system is not that
it updates — it is that it updates and cannot say why, on what evidence, or what it replaced.

```
sense  ──►  events (no pin changes)     tools/update_operator.py sense
try    ──►  verdict in a throwaway env  tools/update_operator.py try <dep> <ver>
promote──►  pin moves, evidence cited   tools/update_operator.py promote <dep> <ver>
rollback─►  previous pin restored       tools/update_operator.py rollback <dep>
```

## The lock is the single source of truth

`lock/versions.lock.json` holds one pin per dependency and the full history of every move.

```json
{"pins": {"dvc": {"version": "3.67.1", "pinned_at": "…", "evidence": "…"}},
 "history": [{"ts": "…", "name": "dvc", "from": {"version": "3.67.0"}, "to": "3.67.1"}]}
```

`rollback` reads that history; it does not guess from what happens to be installed.

## Sense

`sense` asks PyPI (`/pypi/<dist>/json`) and GitHub (`/releases/latest`, or the release list when a
project tags builds rather than versions) and writes `docs/status/updates.json`. It never changes
a pin, so it is safe on a timer:

```
*/6 * * * *  python tools/update_operator.py sense
```

Three details this host forced:

* **mlflow** installs as the distribution `mlflow-skinny`; the import name is `mlflow`. Metadata is
  read from the distribution list, not from the import name.
* **llama.cpp** tags builds (`b11876`) but marks a different release as "latest" (`v0.7.0`), so the
  newest build is found by filtering the release list and comparing build numbers.
* **quarto** is not on PATH on this machine; it is resolved from `QUARTO_BIN`, then
  `../tools/quarto/bin/quarto.exe`. No absolute path is written into the code.

## Try

`try` builds a throwaway environment (`uv venv`, then `uv pip install <dist>==<ver>`) and runs a
probe there. Nothing in the production environment is touched.

| dependency | probe |
|---|---|
| dvc | `python -m dvc version` returns 0 and names its version |
| mlflow | logs a metric to a temporary sqlite store and reads it back |
| quarto | candidate binary reports the expected version, then renders a fixture to HTML |
| llama.cpp | candidate binary answers `--version` |
| decision model | compared by sha256; not installed |

The verdict is written to `docs/status/update_tries/<dep>-<ver>.json` together with the time.
A passing try is evidence for **7 days**; after that it must be repeated.

## Promote

`promote` refuses unless both hold:

1. a **passing** try exists for exactly this version, recorded within the TTL;
2. the target is **not older** than the pin.

The second rule exists because a try answers "does it work", not "is it newer". On 2026-10-25 the
loop was demonstrated by promoting an older DVC and rolling it back; the pin was correct at the
end, but the mechanism allowed a downgrade on the strength of a passing try alone. It no longer
does — `--allow-downgrade --note <why>` is required, and the reason is recorded.

## Rollback

`rollback` restores the pin that preceded the last promotion. It is a lock operation, not an
install: rolling back the pin while the installed version stays put is a *divergence*, which the
status table shows as `pinned ≠ installed`. Reinstalling is a separate, deliberate step.

## What is not covered

* **Binary rollback.** Quarto and llama.cpp are installed by other tools; the operator records a
  candidate's verdict but does not manage the installed binary. A rollback returns the pin and
  reports the divergence.
* **Model weights.** The GGUF is compared by hash. An upgrade means a new file, a new hash, and a
  new try; there is no download step here.
* **Dependency-of-dependency drift.** A try installs the candidate into a fresh environment, so it
  proves the candidate works *there*, not that the combination in production stays coherent.
  Coherence is what the chain audit checks after a promotion.

## Commands

```
python tools/update_operator.py status
python tools/update_operator.py sense [--offline]
python tools/update_operator.py try dvc 3.68.0
python tools/update_operator.py promote dvc 3.68.0
python tools/update_operator.py rollback dvc
```

`sense --offline` records what this host runs without asking anyone — the form CI uses.
