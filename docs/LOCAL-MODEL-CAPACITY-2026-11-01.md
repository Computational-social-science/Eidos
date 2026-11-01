# Local model capacity and bounded development pilot

Observed on 2026-11-01. This corrects an assessment that focused too narrowly
on historical 8B/14B candidates. Larger locally installed models must be tested
on their own merits; historical ScienceRSI failures do not establish their
inability. No candidate currently has accepted autonomous scientific authority.

## Verified local resources

The read-only Ollama-compatible `/api/tags` inventory includes the following
local catalog identities. Parameter counts and quantization labels are reported
metadata, not independently verified upstream provenance or task measurements.

| Local catalog identity | Reported parameters | Quantization | Stored bytes |
|---|---:|---|---:|
| qwen3.8:27b | 27.3B | Q4_K_M | 17,741,872,154 |
| qwen2.5:32b | 32.8B | Q4_K_M | 19,851,349,669 |
| smtek/BigBang-v1:latest | 35.5B | Q4_K_M | 21,864,082,353 |
| deepseek-r1-qwen-14b:Q4_K_M | 14.8B | Q4_K_M | 8,988,110,250 |
| neohorse-1-9b:latest | 9.0B | Q4_K_M | 5,629,109,282 |

A separate Hermes artifact, `Qwen3.8-27B-UD-Q4_K_M.gguf`, has
16,464,440,224 bytes and SHA-256
`322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482`.
Its GGUF header reports architecture `qwen35`. It is the pilot target, and is
distinct from the Ollama Q4_K_M artifact. The latter's catalog manifest digest
`22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`
is not the Hermes weight-file hash. Results cannot be pooled or transferred.

The host has an Intel Core i9-13900K, approximately 128 GiB RAM and an NVIDIA
RTX 4070 reporting 12282 MiB total VRAM. Existing StartLux inference and desktop
activity share that GPU. A 15.33 GiB weight file alone exceeds total VRAM;
CPU/GPU partitioning is needed for this artifact on this card. KV caches,
compute buffers and context length add resource costs. A 262144-token catalog
context is not a verified deployment capacity.

The selected local llama.cpp build supports partial GPU offload. Available
devices, GPU layers and CPU KV are explicit configuration choices; see the
[upstream server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
The pilot uses the installed build and hashes it rather than assuming that
current upstream defaults describe this machine.

## Protocol and interpretation

The development protocol was frozen before inference. It reuses fifteen
existing structured S4 rule-following cases, deterministic labels and exact
JSON grading. Temperature is 0, seed 19, maximum output 96 tokens, thinking off,
one attempt per case and context 4096. The cases are known development examples,
not an untouched scientific hold-out. The historical ScienceRSI 13/15 score
used a different configuration and is not a matched causal comparison.

The owned temporary server is bound to loopback, with twelve CPU threads,
CPU KV and resource monitoring. Both the existing StartLux front door and real
engine/process/model identity are checked before, during and after execution.
Only the temporary server is stopped on a resource breach or deadline. Existing
production model services and presets are not replaced.

Three resource profiles were declared sequentially before any model answers:

| Profile | Initial free VRAM required | Free VRAM floor | Maximum system-wide increment | GPU layers | Admission result |
|---|---:|---:|---:|---:|---|
| GPU4 | 4096 MiB | 1536 MiB | 1536 MiB | 4 | RESOURCE_BUSY; zero cases, no model loaded |
| GPU1 | 2560 MiB | 1792 MiB | 768 MiB | 1 | ABORTED_RESOURCE during loading; zero cases |
| GPU1-budget1536 | 3584 MiB | 1792 MiB | 1536 MiB | 1 | COMPLETE; 15/15 correct, no invalid formats |

The first admission had 2793 MiB free. The second observed a system-wide
increment of 1133 MiB during loading. Concurrent activity prevents attributing
this whole increment to the pilot. Both adverse outcomes are retained as
resource results; neither is a zero-accuracy model result. The third profile
keeps a free-memory floor and changes no model, task, prompt or scoring inputs.

The final owned run `ace4436e35e140a881c58ea7d2a5dd08` finished at
2026-11-01 11:27:40 UTC. Its protocol SHA-256 is
`b28ba5523b67ccfbb2ded3df91183ff6cb9f01dab171808f7c894647e0689aa1`.
All fifteen responses were graded once: **15 correct, zero incorrect, zero
invalid formats**. This demonstrates completion of this bounded development
exercise; it does not establish superiority over the historical 8B run.

Loading took 5.69 seconds. Per-case request latency ranged from 7.17 to 17.92
seconds, with median 9.95 seconds. Server generation-only timing ranged from
2.31 to 2.67 tokens/second; those rates exclude prompt processing. System-wide
GPU usage was 7907 MiB at admission and peaked at 9120 MiB; minimum observed
free memory was 2891 MiB. These are shared-system observations, not isolated
model memory or maximum achievable throughput.

Thirty continuity checks preserved the existing StartLux engine identity and
health. Model hashes matched before/after, the monitor stopped, and the owned
temporary server was explicitly terminated after all responses. Its termination
exit code is recorded; a normal server exit is not claimed. The runner exited
successfully. Full case inputs, labels, raw responses, timings, artifact
identities and retained resource admissions are in the [machine-readable record](LOCAL-MODEL-CAPACITY-2026-11-01.json).

## Deployment and qualification decision

Use this larger candidate pool for a locked task comparison before changing
scientific roles. Qwen 27B can be evaluated for source-grounded drafting,
experimental design and code repair; ScienceRSI can supply additional objections;
StartLux retains bounded routing. These are proposed evaluation roles, not new
permissions. Registered tools and independent verifiers still execute and check
research. Similar model families or multiple role prompts are not independent
ground truth.

For performance tuning, measure time to first token, generation rate, task
latency, memory and correctness under explicit context and concurrency settings.
Prefer a queue for heavy local inference; avoid uncontrolled parallel model
loads. GPU-heavy experiments and inference need a shared resource budget.
This partial-offload pilot does not establish an optimal profile. Higher GPU
residency requires a separately admitted resource window and measurement.

The decisive next evaluation needs independently prepared held-out research
tasks: numerical defect discovery and executable repair, confounder/selection
bias detection, source fidelity, invalid-claim rejection and a complete
supervised research lifecycle. Preserve all adverse results and quantify false
acceptance, abstention and uncertainty. Fifteen short cases cannot establish
novel scientific discovery, long-context reliability or autonomous RSI.
