# Recorded local C0 trials

These exact source copies and protocols describe real local model trials, not a
portable runtime installation. `executed-*.py` files have host-specific paths
and single-use ownership. Audit the code and hashes; these archived entry points
are not the public SDK.

The [trial report](../../../docs/RSI-C0-MODEL-TRIALS-2026-11-01.md) and JSON retain
raw responses and rejection outcomes. Models/binaries are identified by hash but
not distributed. Parent-work-package numerical checks remain runnable separately.

The [decoder follow-up](../../../docs/RSI-C0-DECODER-STUDY-2026-11-02.md) adds
`c0-qwen27b-v2/` and `c0-sciencersi-v2/`: both runtimes completed, both programs
were admissible, and both failed all 23 joint numerical points. The
`c0-decoder-probe-v1/` and `c0-decoder-probe-v2/` directories preserve the failed
2/3 and successful 3/3 structural controls respectively. Control probes do not
qualify numerical correctness. None of these records establishes RSI.

The [configured CPU runtime record](../../../docs/RSI-LOCAL-RUNTIME-2026-11-02.md)
adds `c0-local-cpu-v1/`. Unlike the historical single-use scripts, its new public
runner accepts configured engine/model paths. The archived configuration still
describes this particular host: use the [guide](../LOCAL-RUNTIME.md) for a fresh
configuration. Its runtime passed but its program failed all 23 joint points.
The `source/` tree preserves 20 bound inputs using `.snapshot` filenames to keep
historical tests out of pytest collection; raw bytes and hashes are unchanged.
`test-only/` contains an auxiliary
synthetic server fixture that was not the real model provider. The archived
snapshot is execution evidence, not a standalone installer or a redistributed model.
