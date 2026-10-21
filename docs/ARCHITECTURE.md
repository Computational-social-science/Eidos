# Eidos architecture

This document states what each layer is responsible for, and — more usefully —
what it deliberately does not do.

## 1. Design constraints

1. **One source of truth per fact.** Global defaults live in
   `configs/global/framework.yaml`; a project states only its overrides in
   `configs/project.yaml`. Duplicating the global file into a project is
   forbidden because the two copies then drift.
2. **A gate that cannot fail is not a gate.** Every gate is tested in both
   directions (`tests/test_gates.py`). The acceptance gate originally treated
   every threshold as ">=" and silently passed an error rate of 0.12 against a
   0.05 ceiling; direction is now explicit.
3. **Optional dependencies stay optional.** The core (gates, diagnosis) imports
   with stdlib + pyyaml. mlflow/dvc/chromadb/langgraph are extras
   (`pip install -e '.[tracking]'`), and a missing extra raises a clear error
   only when the capability is used.
4. **Failures are reported, never swallowed.** A missing tool makes its gate
   fail with an explanation; it does not become a pass.

## 2. Layers

| Layer | Module | Responsibility | Explicit non-goal |
|---|---|---|---|
| Decision | `framework/decision.py` | Typed choices with calibrated probabilities (StartLux) | Does not generate text; does not decide validity |
| Gates | `framework/gates` | Quantitative + semantic checks | Does not fix the work it rejects |
| Diagnosis | `framework/diagnosis` | Turns a failure into severity, cause, actions | Does not auto-apply fixes |
| Tracking | `framework/tracking` | MLflow runs + DVC data versions | Does not choose metrics |
| Publishing | `framework/quarto_bridge` | Quarto render + Docker/Binder package | Does not write prose |
| Inference | `framework/inference` | VRAM-aware, stage-aware model scheduling | Does not train models |

## 3. The research loop

```
hypothesis → [human gate] → literature → design → [human gate]
   → execution → quantitative gates → semantic gates
   → diagnosis (on failure) → manuscript → prose/ref gates
   → [human gate] → render + package → lessons recorded (project file)
```

Human gates are mandatory at hypothesis confirmation, critical experiment
design, and final submission. The pipeline records the requirement; it does not
pretend to satisfy it.

## 4. Gate semantics

A gate returns `GateResult(passed, score, details, human_review_required)`.

- `passed` is the only field a pipeline may branch on.
- `score` exists for dashboards, not for thresholds; do not average it into a
  pass decision.
- `details` must let a reader reproduce the verdict (values, thresholds,
  directions, missing inputs).

## 5. Hardware model

`framework/inference` assumes a 12 GB card and a hard VRAM budget (10.5 GB by
default). It loads one large model at a time, unloads between stages, and maps
stages to models. The mapping is data, not code: override
`inference.stages` in a project config.

## 6. What the framework cannot do

- It cannot make an under-powered experiment significant.
- It cannot verify a claim whose reference does not exist in the data; it can
  only report the absence (as the keystroke project does with `AVG_KEYPRESS`).
- It cannot replace a human gate. A green dashboard is not a peer review.
