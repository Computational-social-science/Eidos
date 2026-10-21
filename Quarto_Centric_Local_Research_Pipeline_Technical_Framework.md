# Global Reusable Research Pipeline Framework (Optimized)
## Quarto + BootLoops + Complementary Quality Gates

**Version:** 4.1
**Date:** October 20, 2026
**Status:** Production-ready global template; v4.1 removes the memory layer and routes decisions to a dedicated operator
**Target Hardware:** NVIDIA RTX 4070 (12 GB VRAM) and above
**Primary Goal:** Theory-driven LLM experimentation → Multi-layered certified results → Multi-format reproducible delivery

**One Source → Journal LaTeX/PDF + Word + Interactive Website + Executable Code**  
**with BootLoops + complementary lightweight quality gates enforced throughout.**

---

## 1. Executive Summary

This Version 4.1 optimizes the previous global framework by:

1. Explicitly addressing remaining logical defects.
2. Integrating complementary lightweight open-source resources that maximize research productivity while remaining local-first and model-agnostic.
3. Establishing a dual quality-gate system:
   - **BootLoops** for quantitative precision and certified numerical claims.
   - **Inspect / DeepEval / Promptfoo / Ragas** for semantic, agentic, RAG, and prompt-level quality.
4. Strengthening human-in-the-loop gates, failure diagnosis, and one-click executable reproducibility.
5. **Removing the framework-owned memory layer.** Knowledge is kept in three explicit places instead: agent skills for procedure, agent memory for facts, and each project's own `LESSONS` file for history. A framework vector store was a fourth place nothing wrote to.
6. **Splitting generation from judgement.** High-frequency decisions (routing, gate triage, hypothesis screening, failure classification) are asked of **StartLux-Decision-4B-Q8_0**, a typed-decision operator that returns calibrated option probabilities in one forward pass, instead of a general 7B–8B generator whose text must then be parsed.

The entire workflow remains a **project-agnostic global skeleton**. New projects inherit all quality gates, publishing capability, and reproducibility machinery automatically.

---

## 2. Identified Logical Defects and Mitigations

| Defect | Description | Mitigation in v4.1 |
|--------|-------------|--------------------|
| Incomplete quality coverage | BootLoops is strong on quantitative precision but weaker on NLP semantic quality, hypothesis novelty, and theoretical consistency | Dual-gate system: BootLoops (quantitative) + Inspect/DeepEval/Promptfoo/Ragas (semantic & agentic) |
| Ambiguous human intervention | Over-automation risk; low-quality but “gate-passed” results may reach the paper | Explicit mandatory human review gates at hypothesis confirmation, critical experiment design, and final manuscript submission |
| Weak interactive exploration | Heavy focus on batch → gate → write; early hypothesis probing is inefficient | Optional interactive mode with AIPOCH-style workbench patterns and live literature feedback |
| Limited executable reproducibility | Provenance exists but reviewers still need manual environment setup | One-click executable package (Quarto + Docker/Binder template + freeze cache) |
| Knowledge had no home | Patterns and lessons were to be kept in a framework vector store that nothing wrote to | Three explicit layers: agent skills (procedure), agent memory (facts), project `LESSONS` file (history). No vector store. |
| Judgement delegated to generators | Routing, gate triage and failure classification were asked of a general 7B–8B model, whose text then had to be parsed; confidence needed separate calibration | **StartLux-Decision-4B-Q8_0** returns typed decisions (choice / yes-no / score) with calibrated probabilities in one forward pass |
| Weak failure diagnosis | Gates mostly block; little structured analysis of why a gate failed | Dedicated failure-diagnosis node, fed the gate's structured `details`, producing actionable reports |
| Resource contention on 4070 | Simultaneous heavy LLM + BootLoops tools can overload VRAM | Explicit stage scheduling and model unloading rules; the 4B decision operator (~4.3 GB Q8) stays resident while larger generators swap |

---

## 3. High-Level Optimized Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Multi-Format Delivery (Quarto – Single Source)             │
│         Journal LaTeX/PDF  │  Word  │  Interactive HTML  │  Code Artifacts  │
├─────────────────────────────────────────────────────────────────────────────┤
│                  Dual Quality-Gate Layer (Mandatory)                        │
│  BootLoops (quantitative)  +  Inspect/DeepEval/Promptfoo/Ragas (semantic)  │
│  + Explicit Human Review Gates                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                  Analysis, Writing & Critique Layer                         │
│  Local LLM Agents (LangGraph) + Failure Diagnosis Node                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                  Decision Layer (typed, calibrated)                         │
│  StartLux-Decision-4B-Q8_0: choice / yes-no / score → option probabilities  │
├─────────────────────────────────────────────────────────────────────────────┤
│                  Evaluation & Robustness Layer                              │
│  Ragas + DeepEval + Inspect + Custom Scientific Metrics                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                  Experiment Orchestration Layer (Reusable Core)             │
│  Hydra + LangGraph + MLflow + DVC                                           │
│  Knowledge: agent skills (procedure) · agent memory (facts) · project LESSONS│
├─────────────────────────────────────────────────────────────────────────────┤
│                  Retrieval & Knowledge Layer                                │
│  LlamaIndex + Qdrant/Chroma + Hybrid Search                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                  Inference Serving Layer                                    │
│  vLLM (batch) + Ollama (interactive) + StartLux (decisions) + Scheduling     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Dual Quality-Gate System

### 4.1 BootLoops (Quantitative Precision Gate)

- Repository: https://github.com/BootLoops-ai/bootloops + skills
- Role: Certified computational tools + working protocols that define “done”.
- Key protocols enforced:
  - acceptance-gate
  - planted-truth
  - independence-bookkeeping
  - timing-discipline
  - tool-stewardship
  - lit-review / ref-check
  - prose-lint
  - referee-sim (optional)

### 4.2 Complementary Lightweight Gates

| Tool | Primary Strength | Integration Point | License |
|------|------------------|-------------------|---------|
| **Inspect** | Research-grade agent & tool-use evaluation, sandboxed execution | Complex multi-step reasoning and agent evaluation | MIT |
| **DeepEval** | Pytest-style LLM/RAG/Agent unit tests, 50+ metrics, local Judge | Daily experiment regression and CI gates | Apache-2.0 |
| **Promptfoo** | Config-driven prompt comparison, red-teaming, CI gates | Hypothesis generation and writing nodes | MIT |
| **Ragas** | RAG-specific metrics (faithfulness, context precision/recall) | Literature retrieval and knowledge injection | Apache-2.0 |

### 4.3 Gate Placement (Optimized)

| Stage | Quantitative Gate (BootLoops) | Semantic/Agent Gate | Human Gate |
|-------|-------------------------------|---------------------|------------|
| Hypothesis generation | lit-review, planted-truth | Promptfoo + novelty checks | Mandatory review |
| Experiment design | tool-stewardship, timing-discipline | DeepEval design tests | Recommended |
| Experiment execution | acceptance-gate, independence-bookkeeping | — | Optional |
| Evaluation | acceptance-gate | Inspect + DeepEval + Ragas | — |
| Result injection | independence-bookkeeping, prose-lint | DeepEval faithfulness | — |
| Manuscript drafting | prose-lint, ref-check | Promptfoo style checks | Mandatory before final |
| Package generation | Full battery | Full semantic suite | Mandatory final sign-off |

### 4.4 Decision routing: a decision operator, not a small generator

The framework makes many **judgements per run** — which branch to take, whether a
gate's failure is methodological or environmental, whether a hypothesis survives
screening. Asking a general 7B–8B model for these means generating prose and then
parsing it back into a decision, and the confidence in that decision has to be
calibrated separately.

**StartLux-Decision-4B-Q8_0** is trained for typed decisions and returns them
directly: `choice`, `noul` (yes/no probability) and `score`, with per-option
probabilities and a `none_probability` in one response.

| Dimension | General 7B–8B (Q4/Q8) | StartLux-Decision-4B-Q8 |
|---|---|---|
| Training target | text generation | typed decisions (choice / yes-no / score) |
| Output | prose that must be parsed | option probabilities directly |
| Latency | generation-bound | one forward pass; **measured 182 ms wall clock for 2 questions (n=3) and 253 ms for 3 questions (n=5) over HTTP; the published ~26 ms is the engine read-out, not the round trip** |
| Confidence | needs separate calibration | calibrated probabilities, usable for threshold routing |
| Footprint | 7–8B Q4/Q8 | 4B Q8, ~4.3 GB file, fits beside a resident generator |

**Where it is used.** Stage routing (which branch or model), gate triage (which
action a failure implies), hypothesis screening (keep / drop / escalate), and
failure classification (category). **Where it is not used:** drafting, summarising,
or anything whose output is prose — that stays with a generator.

The division is deliberate: general 7B–8B models are kept for light **generative**
work where output is text, and every **judgement** — which is high-frequency and
needs a calibrated probability rather than a paragraph — goes to the 4B operator.
Nothing that is a decision is routed to a generator, and nothing that is prose is
routed to the operator.

**Threshold policy.** A decision is acted on only when its `none_probability` is
below the model's measured threshold and its top probability clears the project's
threshold; otherwise the case escalates to a human gate. `none_probability ≥ 0.2`
is the authors' calibration point (66.3 % of all-options-wrong questions caught at
2.2 % false flags); it is borrowed and must be re-measured before it enters a
success criterion.

**Failure semantics.** If the operator is unreachable the framework **escalates or
skips** — it never silently substitutes a regex or a general model and calls the
result a decision. This is the same rule the gates follow for a missing tool.

**Licence.** The weights are **CC BY-NC 4.0 (non-commercial)**. Any project that
needs commercial terms must swap the operator, and the framework must not assume
this model is universally redistributable.

---

## 5. Global Reusable Framework Structure

```text
Eidos/                                     # ← Single reusable core
├── framework/
│   ├── gates/                             # BootLoops + Inspect/DeepEval/Promptfoo wrappers
│   ├── diagnosis/                         # Failure diagnosis node (consumes gate details)
│   ├── decision.py                        # Typed-decision client (StartLux operator)
│   ├── project.py                         # Registry: external repositories by pointer
│   ├── tracking/                          # MLflow + DVC
│   ├── quarto_bridge/
│   └── inference/                         # Stage-aware scheduling
├── protocols/                             # BootLoops skills (submodule)
├── tools/                                 # BootLoops toolkit + chain audit
├── templates/
│   ├── project_skeleton/
│   ├── quarto_manuscript/
│   └── executable_package/                # Docker/Binder one-click template
├── configs/global/
└── docs/

projects/                                  # In-tree projects, or pointers to external ones
├── <name>/project.yaml                    # root + gate/test/render commands (pointer)
└── ...                                    # no files are copied into the framework
```

New projects are created via:

```bash
./bootstrap_project.sh <project_name>
```

An existing repository is **registered**, not moved:

```yaml
# projects/<name>/project.yaml
root: ../../../<repo>
gate_command: ["{python}", "scripts/check_handoff.py"]
```

All gates, publishing logic, diagnosis, decision routing and tracking are inherited
automatically; the project keeps its own gate implementation and tests.

---

## 6. Optimized End-to-End Workflow

1. **Project Instantiation**  
   Bootstrap from global template → full inheritance of dual gates and Quarto pipeline.

2. **Hypothesis & Literature**  
   Agents + LlamaIndex → BootLoops lit-review + Promptfoo + mandatory human review.
   StartLux-Decision screens candidates into keep / drop / escalate, with a
   `none_probability` that flags "no listed option fits" instead of forcing a choice.

3. **Experiment Design & Execution**  
   Hydra + vLLM/Ollama → MLflow/DVC → BootLoops acceptance-gate + timing-discipline.
   Design choices that are judgements (which control, which baseline) are asked as
   typed decisions and recorded with their probabilities.

4. **Evaluation**  
   Dual suite: BootLoops quantitative batteries + Inspect/DeepEval/Ragas semantic metrics.

5. **Failure Diagnosis**  
   If any gate fails, the diagnosis node receives the gate's structured `details`
   (which metric, which threshold, which observed value) and asks StartLux to
   classify the cause; the report carries both the classification and its
   probability. Below threshold, the case escalates to a human gate.

6. **Result Certification & Injection**  
   Only certified results enter the Quarto source. Prose-lint and faithfulness checks applied.

7. **Manuscript Drafting**  
   Local LLM agents refine sections under dual gates + mandatory human sign-off.

8. **Multi-Format Rendering + Executable Package**  
   Quarto produces LaTeX/PDF, Word, interactive HTML, and code.  
   One-click executable package (Docker/Binder + freeze + full provenance) is generated only after final human gate.

9. **Lessons Recorded, Not Stored in a Vector Database**  
   A failure that cost time is written to the **project's own `LESSONS` file**, and a
   procedure that generalises is written as an **agent skill**. There is no shared
   memory service: the lesson travels with the code or with the agent, not in a store
   nobody queries.

---

## 7. Quarto Multi-Format Configuration (Inherited)

```yaml
project:
  type: manuscript

format:
  pdf:
    documentclass: article          # or journal-specific template
    number-sections: true
  docx: default
  html:
    theme: cosmo
    toc: true
    code-fold: true

execute:
  freeze: auto
  cache: true
```

---

## 8. Reproducibility & Audit Chain (Strengthened)

Every delivered package contains:

- Git commit of framework + project
- DVC data/model hashes
- MLflow run ID(s)
- BootLoops self-test and acceptance-gate logs
- Inspect / DeepEval / Promptfoo / Ragas evaluation reports
- Quarto `_freeze` cache
- Environment lockfile
- One-click executable environment (Docker/Binder)
- Explicit record of all applied gates and human review signatures

---

## 9. Hardware & Scheduling Notes (RTX 4070)

- **Decisions** (routing, gate triage, hypothesis screening, failure classification) → **StartLux-Decision-4B-Q8_0**, ~4.3 GB, resident; one forward pass per question set
- Interactive writing / drafting → Ollama (8B–14B Q4), loaded on demand
- Batch experiments → vLLM (quantized)
- BootLoops pure-Python tools → CPU preferred
- Explicit model unloading between heavy stages; only one large **generator** resident at a time (the 4B decision operator may stay)
- The decision operator is reached over HTTP (`DECISION_SERVICE_URL`, default `http://127.0.0.1:8090`); if it is down the caller escalates or skips, never silently substitutes

---

## 10. Core Dependencies

```text
# Core framework
langgraph
llama-index
mlflow
dvc
hydra-core
vllm
ollama
qdrant-client
litellm

# Dual quality gates
# BootLoops (git submodule)
inspect-ai
deepeval
promptfoo
ragas

# Publishing
quarto

# Optional workbench patterns
# AIPOCH Open-Science concepts for interactive exploration

# Decision operator (shared, outside any project)
# startlux-decide  (upstream: github.com/StartLuxLabs/StartLux-Decision)
# weights: StartLux-Decision-v1.1-4B-AutoThink-GGUF, Q8_0, ~4.3 GB
# licence: code Apache-2.0; weights CC BY-NC 4.0 (NON-COMMERCIAL)
# the Eidos client is stdlib-only (framework/decision.py); no SDK is vendored
```

---

## 11. Conclusion

Version 4.1 transforms the framework into a more robust, production-grade global research system by:

- Closing the most important logical gaps identified in reflection.
- Establishing a complementary dual quality-gate architecture (BootLoops + Inspect/DeepEval/Promptfoo/Ragas).
- Separating **judgement** from **generation**: typed, calibrated decisions come from a dedicated 4B operator; prose comes from generators.
- Keeping knowledge in three explicit layers (skills, agent memory, project `LESSONS`) instead of a framework vector store nothing wrote to.
- Making human review, failure diagnosis, and one-click executable reproducibility first-class citizens.
- Preserving full local-first operation and deep customizability.

Researchers clone the global framework once and bootstrap any number of projects, obtaining consistent quality enforcement, multi-format delivery, and strong reproducibility guarantees across all work.

---

## 12. Changelog

### v4.1 — 2026-10-20

**Removed the memory layer.** `framework/memory` (JSON + ChromaDB backends, six
tests) was built, exercised, and deleted: no project ever wrote to it. Knowledge now
has three explicit homes — agent skills for procedure, agent memory for facts, and
each project's `LESSONS` file for history. The removal is recorded in
`docs/CHAIN_AUDIT.md`, with the host's `chromadb` + `sentence-transformers` segfault
as supporting evidence in `docs/KNOWN_ISSUES.md` §1.

**Added the decision operator.** `framework/decision.py` is a stdlib-only client for
the shared **StartLux-Decision-4B-Q8_0** service (`POST /v1/systemone`), returning
typed `choice` / `noul` / `score` answers with calibrated probabilities and a
`none_probability`. `framework/inference` registers the model and routes decision
stages to it; generative stages keep their generators.

**Evidence and limits, stated once.** The Decision Index 68.21 and DecisionPivot
59.9 are the model authors' published figures. The operator was deployed on
2026-10-20 (GGUF Q8_0 behind llama.cpp, `startlux-decide` on :8090) and probed with
known-answer questions: p(17 prime)=0.963, p(15 prime)=0.0076, and 0.9 chosen over
0.11 at p=0.995. **Measured wall clock: 182 ms median for 2 questions (n=3), 253 ms
for 3 questions (n=5)** — the published ~26 ms is the engine's read-out, not the
HTTP round trip, and a framework must quote the number its callers experience. Three
upstream deployment defects were found and are recorded in
`docs/CHAIN_AUDIT.md`; the working commands are in
`decision-service/docs/DEPLOYMENT_VERIFIED.md`. The weights remain **CC BY-NC 4.0
(non-commercial)**.

**Calibration, measured here (n=100).** Fifty items answerable from a short state and
fifty asking about a dimension the state never mentions, offered as a three-way choice
(`yes`/`no`/`not_stated`): accuracy 50/50, abstention 0/50 vs 50/50, Fisher exact
p = 2e-29. `none_probability` was returned on every choice answer and **never
exceeded 0.033**, including on the items the operator declined. So the 0.2 threshold
is inert in practice: abstention is produced by *offering* a "not stated" option, not
by that field, and a bare yes/no question is answered rather than declined (p(yes)
0.21–0.64 on unanswerable items). The confidence floor is **not identified** by this
data — nothing was answered wrongly, so precision stayed 1.000 at every floor from 0.50
to 0.99; the lowest confidence on a correct answer was 0.540. Gates must therefore rest
on an explicit option set and on a floor no higher than that bound until items the
operator sometimes gets wrong exist; `none_probability >= 0.2` must not be written as a
success criterion.

---

**Global Optimized Framework Template — Ready for Instantiation**  
**All components are open-source and designed for local, offline operation.**  
**BootLoops:** https://github.com/BootLoops-ai/bootloops  
**Complementary gates:** Inspect, DeepEval, Promptfoo, Ragas  
**Decision operator:** StartLux-Decision (weights CC BY-NC 4.0, non-commercial)
