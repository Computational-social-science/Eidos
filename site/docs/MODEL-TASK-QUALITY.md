# Model quality and task authority

The [first real C0 program-generation trials](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-C0-MODEL-TRIALS-2026-11-01.md)
completed with preserved services, but both Qwen 27B and ScienceRSI returned
inadmissible responses. Qwen hit the output limit and also generated invalid
operator arity; ScienceRSI emitted duplicate/incomplete fields. Neither reached
numerical grading or earned authority. These are one-task development results,
not general model-accuracy estimates; the short S4 results retain their narrower scope.

In the subsequent [decoder-constrained study](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-C0-DECODER-STUDY-2026-11-02.md),
both models generated admissible programs but failed all 23 joint numerical
development points. Qwen's program has loss/derivative defects; ScienceRSI's
program does not use its input. Runtime acceptance did not confer task authority.
The subsequent intervention was grounded method retrieval and bounded counterexample
feedback under a new protocol. The [component plan](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-COMPONENT-ASSEMBLY-2026-11-02.md)
requires local, keyless operation without Gemini or paid services.

The [configured CPU CLI trial](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-LOCAL-RUNTIME-2026-11-02.md)
then completed one real ScienceRSI proposal with no GPU requirement. Runtime,
service preservation, source/environment bindings and cleanup passed; the new
program again failed all 23 joint points. This is a different execution profile,
not a CPU/GPU throughput or model-ranking experiment. No scientific authority
or recursive-improvement result follows.

The completed [six-proposal retrieval/feedback comparison](https://github.com/Computational-social-science/Eidos/blob/main/docs/RSI-RETRIEVAL-FEEDBACK-2026-11-02.md)
retained zero jointly conforming candidates in either arm. Treatment loss values
passed 23/23 public points, while its derivatives failed all points despite an
externally supplied correct formula. All three baselines repeated the same
answer; treatment proposals two and three also repeated. Fixed seeds and the
earliest-tied-prior rule limit interpretation. This configuration remains
unqualified for numerical research authority; these are not independent tasks
or a general model ranking. Next qualify typed method/derivative tools and a
feedback policy that avoids recycling equivalent failures, using local models
and preserved raw proposals. Known-method tool execution remains distinct from RSI.

EIDOS has no task-qualified autonomous research reasoner. The legacy stage/model
table was a proposed routing list, not an executed capability measurement. Model
presence, endpoint health, general benchmarks and task acceptance are different
claims. This limitation remains even if a larger model is installed.

Live inventory also confirms larger candidates, including `qwen3.8:27b` and
`qwen2.5:32b`. The legacy three-name snapshot below is not a complete host
inventory. Historical ScienceRSI failures cannot be extrapolated to these
models. See the [verified local capacity and pilot record](LOCAL-MODEL-CAPACITY-2026-11-01.md).
The separate Hermes 27B UD-Q4_K_M artifact completed 15/15 known structured
S4 development cases with no invalid formats under partial GPU offload. This
is a bounded execution result, not a scientific qualification or a matched
comparison against historical ScienceRSI scores.

The [scientific self-improvement assessment](RSI-READINESS-2026-11-01.md) records
the development failures, current authority boundary and next acceptance
milestone. Software regression counts do not qualify the scientific mission.

## What was actually measured

| Model | Evidence | Accepted use and limitation |
|---|---|---|
| ScienceRSI-8b.i1-Q4_K_M, Qwen3 architecture | S4 structured design judgement 13/15 (86.7%); S7 held-out support judgement 17/20 (85.0%); see [measured errors](MODEL_VERDICTS.md) | May draft hypotheses/objections. Not promoted to scientific gates. Confounding, statistical misuse and selection bias caused substantive errors. These measurements are not scores for the legacy Llama/Qwen/Gemma candidates. |
| StartLux-Decision-4B-Q8_0 | Constructed calibration and a 50-item hold-out; 23 actions, recorded precision 1.0 with 95% interval [0.857,1.0] | Typed routing and bounded triage. This sample does not establish experiment-design, novel-gap discovery, general scientific judgement or reliable confidence for other option sets. Threshold tau was not identified. |
| llama3.1:8b / qwen2.5:14b | Absent from the host's dated Ollama inventory on 2026-11-01; see [snapshot](MODEL_TASK_READINESS.json) | UNQUALIFIED. An entry in MODEL_REGISTRY is not an installed model. Llama3:8b and Qwen2.5:32b are distinct identities and do not satisfy these names. |
| gemma2:9b | Installed with a recorded digest; no accepted EIDOS task evaluation | UNQUALIFIED. May be evaluated as a draft assistant; installation does not establish scientific capability. |
| Local Qwen3.8 27B Q4_K_M / separate Hermes UD-Q4_K_M, Qwen2.5 32B, BigBang 35.5B, DeepSeek R1 Qwen 14B and NeoHorse 9B | Present in the live local catalog; the separate Hermes 27B file is hashed for a bounded development pilot | Candidate pool for task-specific comparison. Different quantizations and artifacts do not inherit one another's results. No scientific authority is granted. |

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
