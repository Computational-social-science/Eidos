# Softmax Cancellation: an optimizer-level before / after comparison

**T1.** The fixed students preserve the teacher parameters in this recorded experiment.

This is a bounded mechanistic comparison, following the local prospective protocol in
`protocol.json`. The claim register was written after observing the results, so it labels
this descriptive claim observational and tentative. It does not present a retrospective
claim register as an external preregistration.

Three modular-addition teachers are trained with seeds 0, 1 and 2. Each student starts
with identical weights and, explicitly, identical represented logits. Standard and fixed
soft-target losses then drive 2,000 full-batch Adam steps at temperature 4. The standard
students' final parameter L2 displacement is approximately 0.172161, 0.150217 and 0.181606;
every fixed student remains at exactly zero. Every seed and checkpoint is retained.

`validate.py` independently checks the registered configuration, actual runtime,
source hashes, full split permutations and all model files. It reads raw float32
storages without executing pickle code, recomputes final displacements from saved
weights, and rejects changed, unfinished or incomplete evidence. `gate.py` records
the validation result and checks this single bounded claim through Gate S.

The teachers have 100% training accuracy but only about 0–0.0712% held-out accuracy.
This demonstrates optimizer stationarity, not useful generalisation, improved test
accuracy or the full training results of the source paper. Float64 KL near roundoff
is descriptive; no confidence intervals or significance tests are claimed.

The first run was rejected: a full-batch teacher cache sliced into the training split
differed from a direct training-batch student forward by about 1.05e-5 due to CUDA GEMM
rounding. Both the failure and model files are preserved in `failed-batch-shape.zip`.
The corrected run uses matched batch dimensions and asserts exact initial logit equality.

Source: [A Fix for Softmax and Cross-Entropy, v3](https://arxiv.org/html/2610.31642v3).
The numerical repairs and scientific discoveries belong to the paper's authors;
this delivery is Eidos's independently checked, adapted mechanistic implementation.
