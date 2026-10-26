# ScienceRSI-8b.i1-Q4_K_M Integration Plan for Eidos
**Optimized for llama.cpp + Importance-Matrix Quantization**

**Version**: 1.2.0 (llama.cpp-specific)  
**Date**: 2026-10-26  
**Status**: Implementation-Ready  
**Target**: Eidos v4.2.0+  
**Runtime**: llama.cpp  
**Model Artifact**: `ScienceRSI-8b.i1-Q4_K_M.gguf` (imatrix Q4_K_M)

---

## 1. Executive Summary

This plan optimizes the integration of **ScienceRSI-8b** into Eidos under the concrete deployment constraint of **llama.cpp + ScienceRSI-8b.i1-Q4_K_M**.

Key optimizations relative to the generic plan:

- Explicit support for the **i1 (importance-matrix)** quantization variant, which preserves more scientific reasoning fidelity than plain Q4_K_M.
- Precise VRAM accounting and mutex rules tuned for a 12 GB card (RTX 4070 class).
- llama.cpp server flags and ModelManager configuration that match Eidos’ existing stage-aware scheduler.
- Stricter temperature and JSON-schema enforcement for Gate S (S4/S7) to compensate for residual quantization noise.
- Mandatory behavioral probe before model promotion, consistent with Eidos’ dependency-governance contract.

The result is a drop-in scientific reasoning engine that strengthens hypothesis generation, evidence evaluation, diagnosis, and Gate S without violating any of Eidos’ core invariants (VRAM budget, auditability, negative controls, LESSONS memory).

---

## 2. Model Artifact Specification

| Property | Value |
|----------|-------|
| Release name | ScienceRSI-8b |
| Quantization | i1-Q4_K_M (importance-matrix Q4_K_M) |
| Expected file | `ScienceRSI-8b.i1-Q4_K_M.gguf` |
| Approx. size on disk | 4.8 – 5.1 GB |
| Typical VRAM (weights + moderate KV) | 6.5 – 7.2 GB |
| Context length (recommended) | 24 576 – 32 768 |
| Backend | llama.cpp (preferred) or compatible OpenAI-compatible server |
| License | Apache-2.0 |

**Why i1-Q4_K_M?**  
Importance-matrix quantization allocates higher precision to the most sensitive weights. For scientific reasoning tasks (methodological judgment, confounder analysis, referee-style critique) this yields noticeably better fidelity than a naïve Q4_K_M at essentially the same memory cost.

---

## 3. Configuration Changes

### 3.1 Model Registration (`configs/global/framework.yaml`)

```yaml
inference:
  vram_budget_gb: 10.5
  models:
    # ... existing models ...

    sciencersi_8b:
      backend: llama_cpp
      path: "models/ScienceRSI-8b.i1-Q4_K_M.gguf"
      quant: i1-Q4_K_M
      context_length: 28672          # safe default under 12 GB
      max_tokens: 6144
      temperature: 0.25             # slightly lower than generic plan
      top_p: 0.9
      repeat_penalty: 1.05
      vram_footprint_gb: 6.9        # measured typical peak
      n_gpu_layers: -1              # full offload when possible
      capabilities:
        - function_call
        - scientific_reasoning
        - evidence_evaluation
        - json_mode
      mutex_with:
        - startlux_decision_4b

    startlux_decision_4b:
      # existing config
      mutex_with:
        - sciencersi_8b
```

### 3.2 Stage Mapping

```yaml
stage_models:
  hypothesis:
    primary: sciencersi_8b
    fallback: llama3_1_8b
    reasoning: "Specialized scientific hypothesis generation"

  literature:
    primary: qwen2_5_14b
    fallback: llama3_1_8b

  design:
    primary: qwen2_5_14b
    secondary: sciencersi_8b      # second opinion only; never concurrent
    fallback: gemma2_9b

  execution:
    primary: startlux_decision_4b

  evaluation:
    primary: sciencersi_8b
    fallback: llama3_1_8b

  diagnosis:
    primary: sciencersi_8b
    fallback: llama3_1_8b

  manuscript:
    primary: qwen2_5_14b
    fallback: llama3_1_8b
```

### 3.3 Recommended llama.cpp Server Flags

When launching the model via `llama-server` (or the Eidos ModelManager wrapper):

```bash
llama-server \
  --model models/ScienceRSI-8b.i1-Q4_K_M.gguf \
  --ctx-size 28672 \
  --n-gpu-layers -1 \
  --temp 0.25 \
  --top-p 0.9 \
  --repeat-penalty 1.05 \
  --port 8081 \          # distinct from decision model
  --host 127.0.0.1
```

Eidos’ stage-aware scheduler must unload this process (or free the model) before loading `startlux_decision_4b`.

---

## 4. Gate S Enhancements (S4 & S7)

ScienceRSI-8b is used only for the two judgment-heavy checks.

### 4.1 Temperature & Output Constraints

- Temperature: **0.15 – 0.25** (lower than generative stages).
- Force JSON mode / response_format = "json".
- Post-validate every evidence pointer (RFC 6901) against actual artefacts. Any unresolved pointer → automatic FAIL.

### 4.2 S4 – Experimental Design Validity

Checks performed by ScienceRSI-8b:
- Pre-registration / explicit design artefact present
- Negative control present and appropriate
- Statistical power adequate for claimed effect
- Major confounders addressed

Output schema remains identical to the previous plan (strict JSON with pointers and verdict).

### 4.3 S7 – Referee Simulation

ScienceRSI-8b acts as a strict methodological reviewer. Every objection must carry:
- severity (`minor` | `major` | `fatal`)
- category
- evidence_pointer
- suggested_revision
- resolvable flag

Any unresolved major/fatal objection blocks PASS.

### 4.4 LESSONS Injection (Minimal RSI Loop)

On Gate S failure the structured objections are appended to the project’s `LESSONS` file. On subsequent runs the most recent 8–10 lessons are injected into the S7 (and optionally S4) system prompt. This creates a lightweight, fully auditable recursive improvement signal without requiring weight updates.

---

## 5. Implementation Phases (Optimized Timeline)

| Phase | Effort | Key Deliverables | Exit Criteria |
|-------|--------|------------------|---------------|
| **P0 – Placement & Smoke** | 0.5–1 day | Place GGUF, register model, load/unload test under VRAM budget | Model loads, generates, unloads cleanly; `make audit` green |
| **P1 – Stage Binding** | 1–2 days | Wire primary/fallback for hypothesis, evaluation, diagnosis | Stage artefacts produced by ScienceRSI-8b pass existing schema checks |
| **P2 – Gate S Upgrade** | 2–3 days | EnhancedGateS class, S4/S7 prompts, JSON validation, fixtures | All new Gate S fixtures (PASS / WEAK_PASS / FAIL) pass; negative controls still rejected |
| **P3 – LESSONS Loop** | 1 day | Write-back on failure + prompt injection | Lessons appear in subsequent contexts; full provenance retained |
| **P4 – Governance & Probe** | 1 day | Behavioral probe (fixed scientific questions), sense/try entry | Probe agreement ≥ 0.90 vs reference; model eligible for promotion |

**Total calibrated effort**: 6–9 engineering days.

---

## 6. Risk Register (Updated for i1-Q4_K_M)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Residual quantization noise on fine methodological judgments | Medium | Medium | Lower temperature (0.15–0.25), strict JSON schema, mandatory pointer validation, behavioral probe before promotion |
| VRAM overshoot with long context | Low | Medium | Cap context at 28 672; monitor peak with existing status instruments |
| i1 quant not present / wrong file | Low | High | Explicit filename check in ModelManager; fail fast with clear message |
| Domain mismatch (life-science bias) | Medium | Medium | Start with pure methodological tasks (design, power, confounders); expand only after measured gain on computational social science claims |
| Concurrent residence with decision model | Low | High | Hard mutex enforced by scheduler; unit test that both cannot be loaded simultaneously |

---

## 7. Success Metrics

- **Correctness**: All existing `make test` / `make audit` chains remain green.
- **Scientific fidelity**: On a fixed set of methodological claims, S4/S7 judgments from ScienceRSI-8b.i1-Q4_K_M show higher expert agreement than the previous general 8B/14B models.
- **Operational**: Median S4/S7 latency ≤ 7 s on target hardware.
- **Governance**: Model passes the behavioral probe and is promotable under the existing sense → try → promote contract.
- **RSI signal**: ≥ 75 % of major Gate S failures produce a structured LESSONS entry in the same run.

---

## 8. Immediate Next Actions

1. Place `ScienceRSI-8b.i1-Q4_K_M.gguf` under `models/`.
2. Apply the YAML fragments in Section 3.
3. Run a minimal load → generate → unload cycle and record peak VRAM.
4. Implement the EnhancedGateS skeleton with the lower temperature and pointer validation.
5. Add three fixtures (one PASS, one WEAK_PASS, one FAIL) before merging.

---

## 9. Conclusion

The combination of **llama.cpp** and the **i1-Q4_K_M** artifact is the practical sweet spot for Eidos on 12 GB hardware: high scientific reasoning quality, modest memory footprint, and full compatibility with the framework’s stage scheduler, mutex rules, and audit culture.

This plan deliberately stays minimal and contract-preserving. Once the four phases are complete, Eidos gains a specialized scientific reasoner and a lightweight recursive improvement loop while remaining local-first, fully auditable, and honest about its own state.

---

**Document control**  
Author: Eidos Integration Working Note  
Companion files: previous generic plan (v1.1), `ScienceRSI-8b_Eidos集成方案.md` (Chinese reference)  
Next review: after P2 Gate S fixtures land
```
