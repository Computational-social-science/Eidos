# ScienceRSI-8b, this host

Measured 2026-10-26 on the 12 GB card. Every number here came from a command in this repository's
shell, not from the model card.

## The artefact

| Property | Measured |
|---|---|
| Path | `%LOCALAPPDATA%\hermes\models\ScienceRSI-8b.i1-Q4_K_M.gguf` |
| Size | 5.03 GB (4.7 GiB on disk) |
| SHA-256 | `a7e1cdab380e52ef55dfe249f634262052c171bdd4b606b7530637398852b7ad` |
| Container | GGUF v3, 399 tensors, 45 metadata keys |
| Architecture | `qwen3`, `general.name = "ScienceRSI 8b"`, `size_label = 8B` |
| Quantization | `general.file_type = 15` → `q4_k_m` |
| License (declared in the file) | `apache-2.0` |
| Context (declared in config) | 28672 |

`framework/inference/gguf.py` reads those keys from the header without loading weights, so a
mislabelled file fails at registration rather than after a 6.9 GB allocation.

## Can it be resident with anything else?

| Quantity | Value |
|---|---|
| Card | 12282 MiB |
| Resident when measured | 7018 MiB (the Hermes runtime's own llama.cpp) |
| Free | ~5.2 GB |
| ScienceRSI footprint, plan §5 | 6.9 GB |

It cannot co-reside with the runtime that was already loaded. `ModelManager.can_load` now refuses on
the mutex alone, before the budget arithmetic, and `validate_registry()` rejects a one-sided
declaration — ScienceRSI and StartLux-Decision exclude each other in both directions.

## What the model actually did (CPU, `-ngl 0`)

Served with `llama-server -m <gguf> -ngl 0 -c 4096 --port 8091`, **no GPU layers**, to exercise the
file without evicting the resident runtime.

| Run | Request | Result |
|---|---|---|
| Thinking on (default for this template) | 118-token prompt, 140 max tokens, `response_format: json_object` | 17.9 s, 7.8 tok/s, **`content` empty** — the whole budget went to reasoning, and the JSON body never started |
| Thinking off (`chat_template_kwargs: {"enable_thinking": false}`) | same prompt, 160 max tokens | **4.4 s, 35 tokens**, valid JSON, verdict `FAIL` with `blocking: ["power"]` |

The answer was right: the artefact showed achieved power 0.41 against a required 0.80, and the
vertex is `FAIL`. That verbatim reply is the fixture `tests/fixtures/s4_real_answer.json`, so the
admissibility check is tested against a real model output.

### The finding

`response_format: json_object` does **not** suppress this model's reasoning. At temperature 0.15 the
reply is 140 reasoning tokens and an empty `content` string — a silent failure that a client reading
only `content` would record as an empty verdict. Plan §5 does not mention it. Any S4/S7 call must set
`enable_thinking: false`; the value is not a preference, it is what makes JSON mode mean anything.

## On the GPU, with the card to itself

Measured by `tools/measure_sciencersi_load.py`: `-ngl 99 -c 28672 --jinja`, the plan's flags, after
stopping the decision service and the monitor (both restarted afterwards and verified).

| Quantity | Plan §5 | Measured |
|---|---|---|
| Load time | — | **4.56 s** |
| Total card usage after load | budget 10.5 GB | **10351 MiB (10.11 GiB; 10.86 GB decimal)** |
| Incremental VRAM (this model) | 6.9 GB | **8760 MiB (8.56 GiB)** |
| of which KV cache at 28672 | ~1.4 GB (implied) | **3.53 GB** |

The estimate in the plan is 24% low. At 28k context the model needs 8.6 GB of the card, not 6.9:
weights are 5.03 GB and the KV cache is 3.53 GB. Adding the 1.6 GiB the desktop already held gives
10351 MiB, i.e. 10.86 GB in decimal units — **above the plan's 10.5 GB budget** (10015 MiB), by
336 MiB. Units matter here: the same 10351 MiB is 10.11 GiB, which would slip under a 10.5 GiB
budget. Read as written (GB), §10's "peak VRAM ≤ 10.5 GB" fails at 28672. Judgements are short JSON; at `-c 16384` the KV cache halves to ~2.0 GB and the
total lands near 7.2 GB, inside the budget. That is a configuration change, not a hardware limit.

### Latency

Five S4 judgements through `framework/inference/llama_cpp.py` (thinking off, JSON mode), one prompt
each, no batching:

| case | verdict | s |
|---|---|---|
| power 0.41 vs required 0.80 | FAIL | 0.84 |
| power 0.93 | PASS | 0.59 |
| power 0.78, shortfall pre-declared | WEAK_PASS | 0.64 |
| no power analysis reported | FAIL | 0.62 |
| power 0.86, confounders adjusted | PASS | 0.58 |

**Median 0.62 s**, max 0.84 s — against a plan target of ≤7 s. Four of the five verdicts are
unambiguous; the `WEAK_PASS` is defensible (0.78 against 0.80 with the shortfall declared in
advance) and shows the third verdict class is reachable rather than decorative.

All five answers were **inadmissible** as evidence: each pointed at
`/artifacts/evaluation/stat_recompute.json`, which this repository does not have. The pointer check
refused them for that reason alone — which is the designed behaviour, and the reason a model answer
alone is never a Gate S pass.

## Behavioural probe: 11/15, and the misses are all the same mistake

`tools/probe_s4.py` asks fifteen labelled design cases, each decided by a rule stated in the file
(required power 0.80; 0.75–0.80 is `WEAK_PASS` only if the shortfall was declared before data
collection; unadjusted confounders or no power analysis are `FAIL`). The labels are computed from
the case fields, not assigned by hand.

**Agreement 11/15 = 0.733.** The plan's promotion bar is 0.90. The model is not promotable.

The decomposition is the interesting part:

| cases | what decides them | agreement |
|---|---|---|
| 9 | the headline power number alone | **9/9** |
| 6 | a qualification — declaration, pre-registration, confounders, the 0.75 floor | **2/6** |

Every miss is the same failure: the model reads the number and discards the fields that qualify it.

| case | expected | got | what it ignored |
|---|---|---|---|
| s4-04 | FAIL | PASS | 0.78 with **no** declared shortfall |
| s4-06 | FAIL | PASS | 3 confounders named, **1** adjusted |
| s4-07 | WEAK_PASS | PASS | **no** pre-registration |
| s4-08 | FAIL | WEAK_PASS | 0.74 — below the floor, where a declaration does not apply |

This is the failure mode the plan warns about when it says the model "may not invent a power
estimate": it did not invent one, it ignored the sentence next to it. A prompt can be compiled to fix
this — and because the fix is a prompt, it must be measured on these fifteen cases rather than
assumed. That is exactly what P4's fixture gate is for, and it is why the gate is a gate.

### At 16384, the configuration that fits

Re-measured with `-c 16384`, idle card at 2099 MiB: **9211 MiB total**, i.e. ≈7.0 GB incremental
against the 8.56 GB at 28672. The registry and `framework.yaml` now declare 16384 / 7.0 GB, and the
budget check accepts it. The probe reproduces **11/15** at this context — verdicts do not depend on
the window, so the smaller context costs nothing measured.

## The prompt that was supposed to fix it, and did not

`tools/compile_s4_prompt.py` does what the plan's P4 describes without the DSPy dependency: state
the five clauses explicitly, then add up to three worked examples chosen greedily on ten train cases,
and judge on five held-out cases that include the rule types the model missed.

| prompt | train (10) | holdout (5) |
|---|---|---|
| baseline, zero-shot | 7/10 | **4/5** |
| rules stated + greedy demos | 8/10 | **4/5** |

**Do not promote.** The holdout did not move, and the one case the candidate still misses is `s4-06`
— three confounders named, one adjusted — with clause (2) sitting in the system prompt in plain
English. The greedy search selected no demonstration that improved train over the rules alone, so
the candidate is the rules-only prompt.

The finding is narrower and more useful than the headline: the model can follow a rule it is given
*when the rule is about the number* (clauses 3–5 all worked), and still ignores a rule about a
*different field in the same sentence* (clause 2). Instructions are not the lever for that; a
structured pre-pass that extracts the fields, or a model that reads them, is. That is a design
change, not a prompt change — and it is worth saying before anyone spends a day on DSPy.

## Not measured

* **Long-context behaviour.** All calls were ~120–200 prompt tokens; nothing here says how the model
  behaves at 10k.
* **Whether a structured pre-pass fixes clause 2.** It is the next experiment, not a result.
