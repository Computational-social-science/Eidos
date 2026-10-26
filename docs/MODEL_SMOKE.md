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

## Not measured

* **GPU latency.** The plan's target is ≤7 s median on the card. Measuring it needs the resident
  7 GB runtime unloaded first; that eviction is a deliberate act, not a side effect of a test.
* **Peak VRAM on load.** Same reason.
* **Quantization effect on verdicts.** One prompt is an anecdote; the plan's answer is a behavioural
  probe over at least 15 fixtures, and those do not exist yet.
