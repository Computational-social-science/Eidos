# DEMO · onboarding template

Ten minutes from an empty directory to a project the framework can check. Nothing here is
specific to this measurement; the items and the claims are placeholders you replace.

## 1. Copy

```bash
python tools/bootstrap_project.py --name my_study --dest ../../my_study
```

That copies this directory, rewrites the project name, and registers it under `projects/`.
It refuses to overwrite an existing project.

## 2. Replace three things

| file | what changes |
|---|---|
| `build_evidence.py` | the items and the measurement; write `docs/evidence.json` |
| `analysis/CLAIMS.yaml` | one claim per sentence the report will state, each with an evidence pointer |
| `docs/REPORT.md` | the sentences themselves; every number must already exist in the evidence |

The rule that makes this work: **the register points at a number, and the sentence states the same
number.** Change one without the other and Gate S fails — that is the point, not an obstacle.

## 3. Run

```bash
cd ../my_study
python build_evidence.py          # writes docs/evidence.json
cd ../Eidos && python -m framework.project check my_study
python tools/audit_validity.py --project my_study
```

## 4. What the gate will tell you

| finding | meaning |
|---|---|
| S1 no claims | the register parsed but declared nothing |
| S2 span not in the document | the paper says something else, or the wording drifted |
| S3 pointer does not resolve | the evidence file changed shape, or the path is wrong |
| S4 supported without preregistration or control | the strength is not earned |
| S5 scope axis missing | a reader cannot tell where the claim applies |
| S6 power / multiplicity undeclared | the sample size has no stated justification |
| S7 referee count | the simulation is missing, or it under-reports an open objection |
| S8 formal claim without proof | the claim says "machine-checked" and nothing checks it |
| S9 prose number ≠ evidence number | the sentence states a number the artefact does not hold |

## 5. What this template deliberately leaves out

No training, no corpus, no model download: a demo that needs a GPU is a demo nobody runs. The
measurement takes about thirty seconds against the local operator and returns SKIP (exit 3) when
the operator is unavailable — a SKIP is recorded as SKIP, never as a pass.
