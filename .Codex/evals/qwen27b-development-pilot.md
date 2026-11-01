# Qwen 27B development pilot

Defined 2026-11-01 before model inference. Frozen protocol SHA-256:
`4f425aac287ceef4308c27278205a5b237b3b6b05e5451b3ad15cef386d51d07`.

Purpose: measure availability and exact rule-following on the existing fifteen
structured S4 development cases. This is neither an untouched hold-out nor
qualification for scientific adjudication or autonomous self-improvement.

Candidate: local Hermes `Qwen3.8-27B-UD-Q4_K_M.gguf`, 16,464,440,224 bytes,
SHA-256 `322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482`.
Ollama's `qwen3.8:27b` is a distinct artifact and cannot inherit these results.

- Reuse the existing structured S4 system rule and case fields. Freeze their
  source fingerprints and all expected labels before inference; no prompt tuning.
- Temperature 0, seed 19, 96 generated tokens, thinking off, one attempt per case.
  Exact JSON verdicts are graded against deterministic labels. Malformed output
  counts as incorrect; resource/transport aborts remain separate from model error.
- Use an owned temporary llama.cpp server on an OS-selected loopback port,
  context 4096, four GPU layers, CPU KV and twelve CPU threads. No preset edits,
  production-service stop/restart or model substitution.
- Require at least 4096 MiB free before loading. Poll GPU usage and stop only the
  owned server if free memory falls below 1536 MiB or system-wide usage rises
  more than 1536 MiB. Concurrent activity can cause an abort; changes are not
  attributed solely to this model.
- Require the existing StartLux identity/health before, during and after the run.
  Bound load to 150 seconds, requests to 45 seconds and the experiment to 600
  seconds, with an outer owned process-tree timeout and cleanup margin.
- Account for all fifteen cases, identity, resource telemetry, artifact integrity,
  raw responses and lifetime cleanup. Preserve adverse outcomes and incomplete runs.
  The owned runner's admission outcome is authoritative; a controller result
  alone does not qualify a run. Exclusive ownership prevents result overwrite.

Historical ScienceRSI 13/15 is context, not a matched same-session comparison.
This pilot does not measure long documents, scientific novelty or full research
design, and does not profile isolated peak throughput. No score automatically
promotes a model. Follow-up needs independently prepared held-out research tasks.

The first GPU4 admission observed 9218 MiB used and 2793 MiB free, so no model
was launched and no quality case was attempted. Its RESOURCE_BUSY result is
retained. Before any model inference, a separate GPU1 resource-only profile was
frozen: SHA-256 `f2ae5b8daff5006d90748b8d6f3faaa39a4b0f0163d9ddcea86505ceb72c6c25`.
It uses one GPU layer, requires 2560 MiB initially, aborts below 1792 MiB free or
above a 768 MiB system-wide increment. Weights, prompts, labels, seed and all
scientific-qualification limits are unchanged. It is a separate admission, not
a retry of an incorrect model answer or an isolated-throughput comparison.

GPU1 stopped during loading after the system-wide usage increment reached
1133 MiB, exceeding its 768 MiB budget; it completed zero cases. Its result and
executed controller/runner are retained. Before observing any model answers, a
third, resource-only profile `gpu1-budget1536` was frozen with protocol SHA-256
`b28ba5523b67ccfbb2ded3df91183ff6cb9f01dab171808f7c894647e0689aa1`.
It still uses one GPU layer and CPU KV, requires 3584 MiB free before loading,
retains the 1792 MiB free-memory floor, and allows a 1536 MiB system-wide
increment. All model, task, prompt and inference controls are identical. Both
earlier adverse resource admissions remain separate from model-quality scores.

Final GPU1-budget1536 admission: COMPLETE, 15/15 correct, no invalid formats,
run `ace4436e35e140a881c58ea7d2a5dd08`. The parent runner exited 0, the monitor
stopped, and the temporary server was explicitly terminated after the fifteen
responses. Thirty checks preserved the original StartLux identity and health.
No promotion occurred. See `docs/LOCAL-MODEL-CAPACITY-2026-11-01.json` for the
portable case/response record and raw evidence fingerprints.
