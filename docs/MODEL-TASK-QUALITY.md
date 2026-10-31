# Model quality and task authority

EIDOS has no task-qualified autonomous research reasoner. The legacy stage/model
table was a proposed routing list, not an executed capability measurement. Model
presence, endpoint health, general benchmarks and task acceptance are different
claims. This limitation remains even if a larger model is installed.

## What was actually measured

| Model | Evidence | Accepted use and limitation |
|---|---|---|
| ScienceRSI-8b.i1-Q4_K_M, Qwen3 architecture | S4 structured design judgement 13/15 (86.7%); S7 held-out support judgement 17/20 (85.0%); see [measured errors](MODEL_VERDICTS.md) | May draft hypotheses/objections. Not promoted to scientific gates. Confounding, statistical misuse and selection bias caused substantive errors. These measurements are not scores for the legacy Llama/Qwen/Gemma candidates. |
| StartLux-Decision-4B-Q8_0 | Constructed calibration and a 50-item hold-out; 23 actions, recorded precision 1.0 with 95% interval [0.857,1.0] | Typed routing and bounded triage. This sample does not establish experiment-design, novel-gap discovery, general scientific judgement or reliable confidence for other option sets. Threshold tau was not identified. |
| llama3.1:8b / qwen2.5:14b | Absent from the host's dated Ollama inventory on 2026-11-01; see [snapshot](MODEL_TASK_READINESS.json) | UNQUALIFIED. An entry in MODEL_REGISTRY is not an installed model. Llama3:8b and Qwen2.5:32b are distinct identities and do not satisfy these names. |
| gemma2:9b | Installed with a recorded digest; no accepted EIDOS task evaluation | UNQUALIFIED. May be evaluated as a draft assistant; installation does not establish scientific capability. |
| Larger local or external candidates | No matched EIDOS task qualification in the current record | Candidates for a future comparison; no automatic promotion or performance claim. |

The ScienceRSI probes are historical measurements recorded on 2026-10-27, not a
new benchmark run on 2026-11-01. The inventory command checks presence without
loading models. Long-context behaviour, quantisation effects and scientific
transfer beyond the recorded short prompts remain unmeasured.

Primary model cards for context: [Llama 3.1](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct),
[Qwen2.5 14B](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct),
[Gemma 2 9B](https://huggingface.co/google/gemma-2-9b-it).
Their general benchmarks are not EIDOS qualification evidence.

## Current execution contract

Scientific-generation stages default to unqualified. `prepare_stage(stage)`
returns false before loading a model. A caller may explicitly request
`allow_unqualified_draft=True`; that permits a draft, never scientific authority.
Candidates are alternatives: preparation stops after one successful load rather
than attempting to load all of them. Unknown stage names are rejected.

`experiment_execution` and `evaluation_gates` load no LLM. Registered commands
execute research; independent verifiers and project evidence decide acceptance.
StartLux remains a routing/triage operator. A successful inference-chain audit
checks budget/routing contracts; it does not qualify scientific model quality.

Hypothesis confirmation, critical experimental design and final submission keep
their existing human gates. Multiple agents using one model do not constitute
independent scientific verification.

## Qualification work still required

Freeze task sets, sources, answers/rubrics and decision thresholds before testing
candidates. Use a development split and an untouched held-out split with source
retrieval, long documents, code execution and failure controls. Include novel
Softmax-like numerical traps, teacher/student equality, dtype boundaries,
selection bias, invalid statistics, missing sources and unsupported novelty.

Measure false acceptance of invalid claims, missed defects, source fidelity,
abstention/coverage, executable results, uncertainty and cost/latency. Aggregate
accuracy and model-reported confidence alone are insufficient. Report all seeds,
prompts, model/quantisation hashes, context settings and unfavourable outcomes.
Independent reviewers must inspect design and novelty. A candidate earns one
bounded task capability at a time; no tested model is currently promoted to the
role of autonomous scientific principal investigator.
