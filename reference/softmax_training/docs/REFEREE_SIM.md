# Internal implementation and scientific-scope review

This is an internal review record, not journal peer review.

## O1. Training stationarity is not generalisation
[RESOLVED] Report includes the very low held-out teacher accuracy, limits its claim
to observed parameter stationarity, and does not claim the paper's training outcomes.

## O2. Evidence could pass with changed protocols or missing models
[RESOLVED] Independent review found the original gate too weak. Mutation tests now
reject changed protocol/runtime, missing data/state identities, missing artifacts,
invalid metric ranges and duplicated backend cases. A positive control validates
the actual completed run; final displacement is independently recomputed from weights.

## O3. Equal weights did not guarantee equal logits
[RESOLVED] Failed batch-shape run and checkpoints are retained. Teacher cache now
matches student batch dimensions and exact initial logit equality is checked before optimization.
