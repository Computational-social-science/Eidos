# Verifiers: citations and statistics before a claim

P0 of `Eidos_ScienceRSI-8b_i1-Q4_K_M_Integration_Plan.md` v1.3.0 says the first two deliverables
are deterministic, not model-driven: prove a citation exists and is not retracted, and recompute the
statistics a paper reports. Both are implemented and gated. Neither loads a model, and neither needs
a GPU.

## What runs

```
literature intake ──► proofpath resolve ──► VERIFIED | BLOCKED | SOURCE_UNAVAILABLE
                                     └──► artifacts/literature/proofpath.json
evaluation        ──► academic-research-kernel ──► p, d, g, power, CI, OR/RR
                                     └──► artifacts/evaluation/stat_recompute.json
```

```bash
python tools/audit_verifiers.py --fixtures                       # every fixture against its expectation
python tools/audit_verifiers.py --citations refs.txt             # network, cached
python tools/audit_verifiers.py --citations refs.txt --offline   # cache only
python tools/audit_verifiers.py --stats spec.json                # recompute and compare
```

Exit 1 is a refusal: a blocked citation or a statistic that does not reproduce. `--fixtures` runs in
the commit hook, so a verifier that stops refusing fails the commit.

## Citations (proofpath)

`proofpath` is a CLI, installed outside the virtualenv:

```bash
uv tool install "git+https://github.com/Yigtwxx/proofpath"
```

Three outcomes, because they need three different actions:

| status | meaning | what a claim may do |
|---|---|---|
| `VERIFIED` | resolved, no retraction notice | cite it |
| `BLOCKED` (retracted) | resolved, retraction found | cannot cite; replace the source |
| `BLOCKED` (unresolved) | no identifier resolves | cannot cite; fix the reference |
| `SOURCE_UNAVAILABLE` | provider down or rate-limited (e.g. Semantic Scholar 429) | cannot cite *yet*; retry, do not rewrite the bibliography |

The last row is the one that matters operationally: a 429 is not a bad citation, and collapsing the
two would make an outage look like misconduct. Responses are cached under
`artifacts/literature/cache/resolve.json`, which is what makes `--offline` and reruns possible.

Measured on this host (2026-10-26), against real providers:

```
10.1038/s41586-020-2649-2         VERIFIED    Array programming with NumPy
10.1016/S0140-6736(97)11096-0     BLOCKED     retracted (retraction-watch, 2010-02-06)
10.9999/does-not-exist-xyz        BLOCKED     unresolved
```

## Statistics (academic-research-kernel)

```bash
pip install academic-research-kernel      # or: pip install -e ".[verifiers]"
```

The kernel supplies deterministic functions (`p_from_t`, `cohens_d`, `achieved_power_ttest`,
`check_ci_consistency`, `check_p_match`, `or_rr_from_2x2`); Eidos binds them to a declarative spec
and compares the result with what the document reported.

```json
{"test": "t",
 "groups": {"m1": 1.2, "sd1": 0.4, "n1": 30, "m2": 1.0, "sd2": 0.5, "n2": 30},
 "reported": {"p": 0.09, "d": 0.44, "power": 0.39, "ci": [0.02, 0.38]}}
```

### Deviation from the plan, and why

The plan fixes a relative tolerance of **1e-3** on p and the effect size. Applied literally that
rejects ordinary rounding: d = 0.44 against a recomputed 0.4417 differs by 0.4 %, and p = 0.09
against 0.0925 by 2.7 % — both would fail, and so would most published tables.

The comparison is therefore made **at the precision the document reports**: half a unit in the last
reported place, with 1e-3 as a floor for values given to many digits. A misstated number still
fails (p = 0.009 against 0.0925, d = 0.75 against 0.4417); a rounded one does not. For p the
kernel's own `check_p_match` is used, which implements exactly this rule.

This is recorded as a deviation, not a silent weakening: the exit criterion the plan states ("a
fixture that misstates p or d fails") holds, and both fixtures prove it.

## Status against the plan

| Step | State | Evidence |
|---|---|---|
| 1. proofpath (identity, retraction) | **done** | `framework/verifiers/citations.py`, live run above, 4 tests |
| 2. academic-research-kernel (statistics) | **done** | `framework/verifiers/stats.py`, 3 fixtures, 5 tests |
| 3. support verification | **backend not available — contract implemented** | see below |
| 4. Instructor on S4/S7 | **blocked** | needs ScienceRSI-8b; no `ScienceRSI-8b.i1-Q4_K_M.gguf` exists on this host |
| 5. DSPy compile | **blocked** | needs ≥ 15 labelled S4/S7 fixtures, which need step 4 |

The model steps are blocked by a missing artefact, not by a missing decision. `llama.cpp` is
present (build 11671 through the Hermes runtime), the mutex contract is already declared in
`framework/inference`, but the GGUF itself is not on disk. Nothing in the verifiers depends on it.

## What this does not claim

* A `VERIFIED` citation is not a supported claim. Existence and retraction are not entailment;
  that is step 3, and until it runs, support is `SUPPORT_UNCHECKED`.
* A passing recomputation is not a correct analysis. It says the printed statistic follows from the
  printed summary data — not that the test was appropriate, pre-registered, or unconfounded.
* `SOURCE_UNAVAILABLE` is not evidence of anything. It is a retry.


## Step 3: support verification, with no backend assumed

The plan names a support-checking service for this step. On 2026-10-26 no such tool could be
verified as accessible: the name resolves to an unrelated project, and the site linked from the
plan serves no documentation. It is therefore **not** referenced by this framework — a dependency
that exists only in a document is the defect this repository corrected with LangGraph.

What exists is the contract, and it is enforced:

| state | meaning | Gate S |
|---|---|---|
| `SUPPORTED` | a passage with source, offsets and text backs the claim | may pass |
| `NOT_SUPPORTED` | a passage contradicts it | FAIL |
| `UNCLEAR` | the source does not settle it | FAIL |
| `SUPPORT_UNCHECKED` | no backend has run | **BLOCKED**, never PASS |

`framework/verifiers/support.py` writes one record per claim under
`artifacts/literature/support/<claim>.json`. It refuses a `SUPPORTED` verdict that has no passage,
no offsets, or a quote that does not match the source at those offsets — an unchecked "supported"
is worse than an admitted `SUPPORT_UNCHECKED`.

A backend that produces the verdict (BM25 retrieval over a fetched paper plus a bounded entailment
question) is not implemented, and no external service is assumed to provide it.

## Step 4: S4 and S7 are checked, not trusted

`framework/verifiers/pointers.py` resolves every `evidence_pointer` of the form
`/artifacts/…/file.json#/json/pointer` against the artefact on disk and enforces the category rules:
`statistics` must land in `stat_recompute.json`, `support` in a support record, `identification` in
`proofpath.json`. A `PASS` carrying a failed check, a `blocking` entry that did not fail, or a
pointer that escapes the project root are all inadmissible. This runs without a model, so a dangling
pointer fails identically when the server is down.

The model's own output is held to it: `tests/fixtures/s4_real_answer.json` is the verbatim reply
from the deployed ScienceRSI-8b, and one test asserts it is admissible while eight assert that
mutations of it are not.


## S11: the design verdict is arithmetic

A claim may carry an `s4` record — `power`, `required`, `named`, `adjusted`, `prereg`, `declared`,
and the `verdict` being asserted. Gate S recomputes the verdict from the fields and fails a mismatch:

```yaml
- id: C7
  s4: {power: 0.78, required: 0.80, named: 2, adjusted: 2, prereg: true,
       declared: false, verdict: FAIL}
```

A record missing a field the branch needs is BLOCKED, not guessed. Prose is not admissible: extraction
from unseen paraphrases reads 7/10 (docs/S4_VERDICT.md), so a paragraph cannot gate anything. The
model is not consulted — it scored 0.867 on these records and missed precisely the two comparisons
(docs/S4_VERDICT.md).

S7 is a different rule family and a different outcome: 0.750, detecting all eight planted defects but
mislabelling two and inventing one on a clean case (docs/S7_VERDICT.md). It drafts objections for a
human; it does not gate.
