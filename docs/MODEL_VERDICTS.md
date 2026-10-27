# Model verdicts: ScienceRSI-8b.i1-Q4_K_M

One file, because the same conclusion written in four places drifts in four directions. Everything
below was measured on this host (RTX 4070 12 GB) with the commands named.

## 1. The artefact

| Property | Measured |
|---|---|
| Path | `%LOCALAPPDATA%\hermes\models\ScienceRSI-8b.i1-Q4_K_M.gguf` |
| Size | 5.03 GB |
| SHA-256 | `a7e1cdab380e52ef55dfe249f634262052c171bdd4b606b7530637398852b7ad` |
| Container | GGUF v3, 399 tensors, 45 metadata keys |
| Architecture | `qwen3`, `name = "ScienceRSI 8b"`, `size_label = 8B` |
| Quantization | `general.file_type = 15` → `q4_k_m` |
| License in the file | `apache-2.0` |

`framework/inference/gguf.py` reads those keys from the header without loading weights, so a
mislabelled file fails at registration rather than after a 6 GB allocation.

## 2. What it costs

| ctx | KV | resident | incremental | note |
|---|---|---|---|---|
| 28672 | f16 | 10351 MiB | 8.56 GiB | over the 10.5 GB budget by 336 MiB |
| 16384 | f16 | 9211 MiB | 7.0 GiB | the alternative nobody ran |
| 40960 | q8_0 | 10251 MiB | 8.1 GiB | the preset as shipped |
| **16384** | **q8_0** | **8151 MiB** | **6.2 GiB** | current deployment |

Reducing the preset from 40960 to 16384 returned **2.05 GiB**, twice the ~1 GiB predicted: the 40960
KV cache was larger than the weights alone implied. Two facts about the preset file: an edit does
nothing until the router restarts (the running process has cached its arguments), and the edit
survives a restart — but nothing watches the file, so the restart is manual. `serve_model.py status`
now compares preset, registry and loaded arguments so this cannot be discovered by accident again.

Loading through the router takes **1.9–3.7 s** end to end (budget check, unload, autoload, identity).

Latency for judgements (GPU, S4 prompt, thinking off):

| input | median | notes |
|---|---|---|
| structured fields | 128 ms | 7 output tokens |
| prose, zero-shot | 620 ms | 35 tokens |
| prose, rules + 3 examples | ~1.0 s | 350-token prompt |
| S7 objection list | 0.29–2.28 s | cost tracks the number of objections |

## 3. S4 — design validity

| condition | result |
|---|---|
| prose, zero-shot | **11/15 = 0.733**; 9/9 on cases decided by the power number, 2/6 on cases decided by a qualification |
| prompt rewritten with 5 clauses + greedy demonstrations | train 7→8, **holdout 4/5 → 4/5** |
| **fields handed over as JSON** | **13/15 = 0.867** |

The two misses that survive structured input are the confounder comparison (3 named, 1 adjusted →
`PASS`) and the 0.75 floor (0.74 with a declaration → `WEAK_PASS`). Those are inequalities, and the
model gets them wrong with the numbers in front of it.

Extraction from prose is not a way around it: on ten paraphrases written after tuning, the
deterministic extractor scores **7/10**, and its saving property is that it is **never confidently
wrong** — an unreadable case returns `INCOMPLETE` rather than a guess.

**Verdict: not promoted.** S4's rule-shaped checks are deterministic (`framework/verifiers/extract_s4.py`
over a structured record, enforced as Gate S **S11**). A claim carrying a `s4` record whose verdict
does not follow from its fields fails, whoever wrote the verdict.

## 4. S7 — support and objections

| condition | result | Wilson 95% |
|---|---|---|
| open-ended: model picks the category, 12 cases | 9/12 = 0.750 | [0.468, 0.911] |
| category fixed by the artefact, 12 cases | 11/12 = 0.917 | [0.646, 0.985] |
| **category fixed by the artefact, 40 cases** | **38/40 = 0.950** | **[0.835, 0.986]** |

The architecture that raised the score: resolve the artefact first, let its type fix the category,
and ask one question — does this evidence support the claim? The model never names a category, so it
cannot mislabel one, which was two of the three failures in the open-ended run.

The two remaining misses are informative rather than random:

* **X-23** (design, 31% vs 4% attrition): the model *described* the differential attrition correctly
  and still answered "supports". A reasoning slip after a correct reading.
* **X-33** (clean, generalisation to adults, evidence lists two adult samples and one adolescent): the
  model read it as "only one adolescent sample". A reading error on a clean case.

**Verdict: not established.** 0.95 as a point estimate, 0.835 as a lower bound. At this accuracy the
interval reaches 0.90 only at n ≈ 200; perfect accuracy on the existing 40 would give [0.912, 1.0].
So the cheapest path to a decision is to fix the two failure modes and re-run 40, not to add cases
blindly. Until then: `do not gate on S7`; the model may draft objections for a human.

## 5. What this means for the gate

No model is a gate component. Gate S is deterministic: verifier artefacts (S10), a recomputed design
verdict (S11), and pointer admissibility for S4/S7. The model drafts prose and nothing else, and that
is a measured position rather than a preference — two rule families, four probes, and intervals that
do not support a stronger claim.

## 6. Not measured

* Long-context behaviour: every call was under ~400 prompt tokens.
* Quantisation effect on verdicts: one file, one quantisation.
* Whether fixing X-23 and X-33 generalises, or was two lucky cases.
