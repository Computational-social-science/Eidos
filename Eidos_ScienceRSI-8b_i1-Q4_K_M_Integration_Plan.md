# Eidos Integration Plan: Deterministic Gates + ScienceRSI-8b.i1-Q4_K_M

**Version**: 1.3.0  
**Date**: 2026-10-26  
**Status**: Implementation-ready  
**Target**: Eidos v4.2.0+  
**Runtime**: llama.cpp  
**Model artifact**: `ScienceRSI-8b.i1-Q4_K_M.gguf` (imatrix Q4_K_M)  
**Supersedes**: 1.2.0 (model-first binding)

---

## 1. Executive summary

Version 1.2.0 bound ScienceRSI-8b as the primary model for hypothesis, evaluation, and diagnosis, and treated Gate S as a model judgment. That over-uses an 8B quantized model for checks that are cheaper and more reliable when done deterministically.

This revision keeps the llama.cpp deployment (mutex, 28k context, temperature 0.25, ~6.9 GB) and **reorders the work**:

1. **proofpath** blocks nonexistent or retracted citations before they enter `CLAIMS`.
2. **academic-research-kernel** recomputes reported statistics; mismatch fails the quantitative gate.
3. **Callimachus** checks source support only for claims that passed (1) and (2), and writes passage pointers.
4. **Instructor** (Pydantic against the local llama-server) constrains S4/S7 JSON. Unresolved pointers are `FAIL`.
5. **DSPy `BootstrapFewShot`** compiles S4/S7 prompts only after at least 15 fixtures exist. No MIPROv2, no weight update.

ScienceRSI-8b.i1-Q4_K_M remains the judgment model for S4, S7, hypothesis, and diagnosis. It does not search the literature, recompute p-values, or share VRAM with StartLux-Decision-4B.

Out of scope for this plan: DiscoveryRSI, SwarmRSI, AI Scientist v3, Lean agent libraries, SemanticCite (extra resident models), LiteLLM, and the full K-Dense skill catalog.

---

## 2. What changed from 1.2.0

| Topic | 1.2.0 | 1.3.0 |
|---|---|---|
| First deliverable | Register and bind the GGUF | proofpath on literature intake |
| Evaluation primary | ScienceRSI-8b | Deterministic recompute; model only interprets residuals |
| Literature primary | Unchanged 14B | Identity and retraction are non-model; entailment is Callimachus |
| Gate S input | Raw stage artefacts | Only claims that survived proofpath, stats, and (when cited) Callimachus |
| JSON | "Force JSON mode" | Instructor + pointer resolution, fail closed |
| RSI | LESSONS injection called a loop | LESSONS records verifier failures; DSPy is a one-shot prompt compile against fixtures |
| Timeline | P0 model smoke | P0 verifiers; model promotion is P3 |

---

## 3. Integration order

Do not start a later step until the previous exit criterion is met.

### Step 1 — proofpath (literature identity)

- Install: `uv tool install` from [Yigtwxx/proofpath](https://github.com/Yigtwxx/proofpath) (MIT), or vendor the CLI.
- Run on every bibliography artefact before a claim may be written.
- Layers used now: source exists (Crossref, OpenAlex, arXiv, Semantic Scholar); retraction (Retraction Watch via Crossref, OpenAlex).
- Entailment inside proofpath stays **off** until Step 3, so two tools do not double-judge the same sentence.
- Fail closed: missing identifier, unresolved title, or retracted source → citation status `BLOCKED`. Blocked citations cannot be referenced by `CLAIMS`.
- Persist a JSON report next to the bibliography (`artifacts/literature/proofpath.json`) with database, query, and match score. No prose verdicts.

**Exit**: a fixture paper with one fake citation and one retracted DOI is rejected; a known-good DOI is accepted. `make audit` still green.

### Step 2 — academic-research-kernel (quantitative gate)

- Install: `pip install academic-research-kernel`.
- Bind to the evaluation stage, beside BootLoops. It does not replace BootLoops.
- Recompute, from the reported summary statistics, at least: t-test p, Cohen's d or Hedges' g, confidence intervals, odds or risk ratios, and power, using the kernel's deterministic functions.
- Tolerance (project constant, not a model choice): relative error > 1e-3 on p or on the effect size, or a CI that does not contain the reported estimate, → quantitative gate `FAIL`.
- Write `artifacts/evaluation/stat_recompute.json` with inputs, recomputed values, and delta. The model never supplies these numbers.

**Exit**: a fixture that misstates p or d fails; a correctly reported result passes without loading ScienceRSI.

### Step 3 — Callimachus (support, not discovery)

- Use [Callimachus](https://callimachus.science/): the pipeline identifies the source and extracts passages; the model only answers bounded support questions.
- Point it at the existing llama-server (Section 5) **or** skip the model and record `SUPPORT_UNCHECKED` if the 8B is busy. Do not add a second resident model.
- Enable the BM25 extractive path. Do not send full papers into the 28k window.
- Eligible inputs: claims whose citations are `VERIFIED` (Step 1) and whose numeric claims, if any, passed Step 2.
- Persist passage offsets and the question/answer pair on the claim pointer. A claim with no passage pointer cannot receive Gate S `PASS`.

**Exit**: one supported, one contradicted, and one out-of-scope sentence produce `SUPPORTED`, `NOT_SUPPORTED`, and `UNCLEAR` with stored passages. The model process is unloaded afterward.

### Step 4 — Instructor on S4 and S7

- Add `instructor` and validate against the OpenAI-compatible endpoint in Section 5.
- S4 and S7 response models are the schemas in Section 6. Retries: 2. After that, `FAIL` with the raw text stored, not repaired by another model.
- Post-condition, in code: every JSON Pointer (RFC 6901) resolves to an on-disk artefact from Steps 1–3. Dangling pointer → `FAIL`.

**Exit**: malformed JSON and a dangling pointer both fail fixtures without manual inspection.

### Step 5 — DSPy compile, only with fixtures

- Preconditions: ≥ 15 labeled S4/S7 fixtures covering `PASS`, `WEAK_PASS`, and `FAIL`, including the negative controls Eidos already requires.
- Optimizer: `BootstrapFewShot` only. Metric: schema-valid **and** pointer-resolvable **and** verdict match to the fixture.
- Compile offline. Check the compiled prompt into the repo. Do not compile inside a research run.
- Promote with the existing sense → try → promote path. If the behavioral probe drops, revert the prompt file. Do not touch GGUF weights.

**Exit**: compiled prompt beats the hand prompt on the held-out fixtures and does not weaken the negative-control fixture.

---

## 4. Where ScienceRSI is actually used

| Stage | Primary | ScienceRSI-8b role |
|---|---|---|
| literature | proofpath (identity, retraction) | None |
| literature support | Callimachus | Optional entailment backend via llama-server, one claim at a time |
| hypothesis | ScienceRSI-8b | Draft only. Drafts are not evidence |
| design | Existing 14B | Second opinion **after** unload of any other model, never concurrent |
| execution | StartLux-Decision-4B | Mutex. ScienceRSI must be unloaded |
| evaluation numbers | academic-research-kernel | None |
| evaluation narrative | ScienceRSI-8b | May explain a residual only by pointing at `stat_recompute.json` |
| diagnosis | ScienceRSI-8b | Must cite a verifier artefact, not a new fact |
| manuscript | Existing 14B | None |
| Gate S S4 / S7 | ScienceRSI-8b | Judgment only, after Steps 1–3, JSON via Instructor |

Hypothesis text, diagnosis prose, and referee comments are not valid evidence pointers.

---

## 5. llama.cpp configuration (unchanged hardware contract)

| Property | Value |
|---|---|
| File | `models/ScienceRSI-8b.i1-Q4_K_M.gguf` |
| Quantization | i1-Q4_K_M |
| Disk | ~4.8–5.1 GB |
| VRAM weights + moderate KV | 6.5–7.2 GB (budget figure **6.9**) |
| Context | 28672 |
| Temperature | 0.25 general; **0.15** for S4/S7 |
| License | Apache-2.0 |
| Card budget | 10.5 GB of 12 GB |

```yaml
inference:
  vram_budget_gb: 10.5
  models:
    sciencersi_8b:
      backend: llama_cpp
      path: "models/ScienceRSI-8b.i1-Q4_K_M.gguf"
      quant: i1-Q4_K_M
      context_length: 28672
      max_tokens: 4096          # lowered: judgments are short JSON
      temperature: 0.25
      gate_s_temperature: 0.15
      top_p: 0.9
      repeat_penalty: 1.05
      vram_footprint_gb: 6.9
      n_gpu_layers: -1
      capabilities:
        - scientific_reasoning
        - json_mode
      mutex_with:
        - startlux_decision_4b

    startlux_decision_4b:
      mutex_with:
        - sciencersi_8b
```

```bash
llama-server \
  --model models/ScienceRSI-8b.i1-Q4_K_M.gguf \
  --ctx-size 28672 \
  --n-gpu-layers -1 \
  --temp 0.25 \
  --top-p 0.9 \
  --repeat-penalty 1.05 \
  --port 8081 \
  --host 127.0.0.1
```

S4/S7 requests override temperature to 0.15. The scheduler unloads this process before StartLux-Decision-4B. A unit test asserts both footprints cannot be resident together.

Wrong or missing filename is a startup error, not a fallback to another quant.

---

## 6. Gate S after the verifiers

S4 and S7 run only when Steps 1–3 have written their artefacts. If a required artefact is absent, Gate S returns `BLOCKED`, not a model opinion.

### 6.1 S4 — design validity

The model may only judge:

- a pre-registration or design artefact is present and matches the executed analysis
- a negative control exists and is the right one
- power in `stat_recompute.json` is adequate for the claimed effect
- confounders named in the design are actually adjusted

It may not invent a power estimate.

```json
{
  "verdict": "PASS | WEAK_PASS | FAIL",
  "checks": [
    {
      "id": "power",
      "status": "PASS | FAIL | NOT_APPLICABLE",
      "evidence_pointer": "/artifacts/evaluation/stat_recompute.json#/power"
    }
  ],
  "blocking": ["power"]
}
```

### 6.2 S7 — referee simulation

Every objection:

```json
{
  "severity": "minor | major | fatal",
  "category": "identification | statistics | support | design | other",
  "evidence_pointer": "/artifacts/literature/callimachus/claim_014.json#/passage",
  "suggested_revision": "string",
  "resolvable": true
}
```

`PASS` is illegal if any major or fatal objection is unresolved. `category: statistics` must point into `stat_recompute.json`. `category: support` must point into a Callimachus record. `category: identification` must point into `proofpath.json`.

### 6.3 LESSONS

On `FAIL` or `BLOCKED`, append one record: stage, verifier, pointer, and the machine reason. Inject at most the last 8 records into the next S4/S7 system prompt. Do not inject free-text "lessons" the model wrote about itself. This is an audit trail, not a training loop.

---

## 7. Optional skill text (not on the critical path)

If a skill file is added, copy only these three from [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) (MIT), strip domain examples, and keep them as procedure text:

- `statistical-analysis`
- `experimental-design`
- `paper-lookup`

They do not override Steps 1–3. Do not import the rest of the catalog.

---

## 8. Phases

| Phase | Effort | Work | Exit |
|---|---|---|---|
| **P0 Verifiers** | 1–2 days | Steps 1 and 2, fixtures, artefact paths | Fake citation and bad p fail with no GPU |
| **P1 Support** | 1–2 days | Step 3, Callimachus → claim pointers, unload test | Three support classes stored; VRAM released |
| **P2 Model + Gate S** | 2–3 days | Section 5, Instructor, S4/S7 schemas, pointer check | New fixtures pass; negative control still fails |
| **P3 Probe** | 1 day | Behavioral probe, mutex test, sense/try entry | Probe agreement ≥ 0.90 vs reference answers; mutex test green |
| **P4 Prompt compile** | 1 day, gated | Step 5 when ≥ 15 fixtures | Held-out metric up; else keep the hand prompt |

**Total**: 6–9 days. P4 can slip without blocking use.

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Quantization noise on S4/S7 | Medium | Medium | Temperature 0.15, Instructor, pointer check, probe before promote |
| Verifier and model disagree | Medium | Low | Verifier artefact wins. The model cannot override a recompute or a retraction |
| Callimachus pays for a source Eidos cannot fetch | Medium | Medium | Status `UNCLEAR` or `SOURCE_UNAVAILABLE`; never `PASS` |
| VRAM clash | Low | High | Hard mutex; Callimachus uses the same server, not a second GGUF |
| proofpath network dependency | Medium | Medium | Cache responses under `artifacts/literature/cache/`; reruns must work offline from cache |
| Life-science bias of the 8B | Medium | Medium | Use it on methods (design, power, confounders, support). Do not ask it to be a domain oracle for computational social science |
| DSPy overfit on tiny fixtures | Medium | Medium | Hold out at least 5 fixtures; refuse compile below 15; revert on probe regression |

---

## 10. Success metrics

- Existing `make test` and `make audit` stay green.
- 100% of `CLAIMS` entries either cite a `VERIFIED` proofpath record or are explicitly uncited.
- 100% of reported p / d / CI values in evaluation either match `stat_recompute.json` within tolerance or fail the quantitative gate.
- No Gate S `PASS` without resolved pointers into those artefacts.
- Median S4/S7 latency ≤ 7 s on the target 12 GB card, measured after verifiers have already run.
- Peak VRAM during a full stage cycle ≤ 10.5 GB.
- Behavioral probe ≥ 0.90 before the model is promotable.
- ≥ 75% of Gate S failures write a LESSONS record that points at a verifier artefact in the same run.

---

## 11. Immediate next actions

1. Add proofpath to literature intake and the fake-citation fixture.
2. Add academic-research-kernel to evaluation and the mis-stated-p fixture.
3. Only then place `ScienceRSI-8b.i1-Q4_K_M.gguf`, apply Section 5, and record peak VRAM on load and unload.
4. Wire Callimachus to port 8081 with BM25, then Instructor schemas.
5. Do not run DSPy until the fixture count is ≥ 15.

---

## 12. Conclusion

On a 12 GB card the productive move is to stop asking ScienceRSI to discover, identify, or recompute. proofpath, academic-research-kernel, and Callimachus make those checks repeatable. The i1-Q4_K_M model then spends its context on S4/S7 judgments whose evidence pointers already exist. Prompt compilation waits until those judgments have fixtures. Nothing in this plan updates weights or relaxes the negative-control rule.

---

**Document control**  
Author: Eidos integration working note  
Supersedes: `Eidos_ScienceRSI-8b_i1-Q4_K_M_Integration_Plan.md` v1.2.0  
Next review: after P0 verifier fixtures land
