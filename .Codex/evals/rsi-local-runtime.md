# Keyless local C0 runtime acceptance

Declared before implementation, 2026-11-02. This is a new CPU baseline profile,
not a retroactive amendment to C0-SPEC.md or the GPU-assisted v1/v2 trials.

## Capability contract

Provide a source-checkout CLI accepting a JSON configuration and a fresh output
directory. Engine/model paths resolve relative to the configuration, not a drive
letter, user home, current directory or ignored scratch script. No keys, hosted
fallback, weights download, resident process restart or new scheduler is allowed.
Use a trusted, SHA-256-pinned local llama.cpp executable and GGUF model. Existing
llama.cpp CLI flags remain an explicit backend prerequisite.

One fixed C0 prompt, seed 19, temperature 0, top_p 0.9, thinking off and one
proposal. Explicit context/token/thread/deadline/memory limits. Request the
bounded v2 expression grammar, retain actual raw responses, and evaluate the
actual program through the existing independent public oracle in its own
deadline. A literal grammar control follows the target; it is only a backend
smoke check, not mathematical or comprehensive decoder qualification.

Runtime completion, admissible syntax and numerical conformance are separate.
No scientific promotion, sealed result, transfer result or RSI is possible.

## Required controls before acceptance

1. Reject duplicate/unknown/nonfinite/mistyped configuration, external HTTP
   endpoints, redirects, missing/mismatched engine/model files and reused output
   directories. No malformed configuration launches a model.
2. Verify loopback-only, proxy-free HTTP and bounded response reads, including a
   slow response under a separate wall watchdog. No credential is required or
   sent. The backend is trusted code, not an OS network sandbox.
3. Only the owned engine is terminated. Use the existing SDK outer process-tree
   owner so controller failure/timeouts cannot leave the owned server behind.
   Observe declared protected service identities before/during/after execution;
   any changed/unobservable identity prevents runtime acceptance.
4. Check available RAM before/while running and owned-tree RSS/log growth while
   running. These are sampled admission/abort controls, not hard OS memory/disk
   limits. Record failures explicitly and retain all attempts.
5. Freeze configuration/protocol/source identities before launch, bind evaluation
   to the exact response/protocol/run nonce, and check input identities afterward.
   A stale/missing/mismatched child record cannot yield a successful parent receipt.
6. Distinguish synthetic controls from live model evidence. Run the real CLI with
   an actual pinned local model; record its cost, unfavorable mathematical
   outcome if any, cleanup and existing-service continuity. Do not count replay
   or test transports as inference.

## Regression scope

Run the existing 60 C0/grader/interpreter tests plus focused runtime controls.
Preserve prior trial archives byte-for-byte. Keep docs/pipeline.json as runtime
state outside the source commit. Update English usage/limits and the technical
framework when measured results are accepted. Windows source-checkout execution
does not prove installed-wheel/new-machine/Linux model runtime qualification.
