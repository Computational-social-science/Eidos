# Loss precision × epsilon: paired reconstruction

All 36 specified training trajectories completed, with independently checked final models and gradient endpoints.

**Observed result:** fixed CE is higher in 5/18 paired endpoints, lower in 12/18, and tied in 1/18. The best final held-out accuracy across all arms is 79.210%. These runs do not reproduce the paper's high-generalization table and do not establish a uniform finite-budget generalization benefit.

At the model interface, the fixed arm's maximum target-zero count is 0 across 918 producer-recorded checkpoints; standard CE reaches 243/480. Final gradient counts are independently reloaded; intermediate counts are recorded by the producer.

Locally registered follow-up; three seeds, float32 model/forward, two supported loss precisions and three epsilon values. Not an exact paper reproduction. bfloat16 remains UNQUALIFIED.

All cells below are retained. Delta is fixed minus standard in percentage points; no population inference or significance test.

| Loss dtype | Epsilon | Seed | Standard test (%) | Fixed test (%) | Delta (pp) |
|---|---:|---:|---:|---:|---:|
| float32 | 1e-08 | 0 | 26.611 | 68.815 | +42.204 |
| float32 | 1e-08 | 1 | 11.435 | 10.603 | -0.832 |
| float32 | 1e-08 | 2 | 4.990 | 4.158 | -0.832 |
| float32 | 1e-12 | 0 | 54.470 | 11.435 | -43.035 |
| float32 | 1e-12 | 1 | 15.800 | 10.811 | -4.990 |
| float32 | 1e-12 | 2 | 6.237 | 3.534 | -2.703 |
| float32 | 1e-16 | 0 | 61.331 | 9.356 | -51.975 |
| float32 | 1e-16 | 1 | 13.721 | 12.058 | -1.663 |
| float32 | 1e-16 | 2 | 6.445 | 4.574 | -1.871 |
| float64 | 1e-08 | 0 | 79.002 | 79.210 | +0.208 |
| float64 | 1e-08 | 1 | 10.603 | 10.395 | -0.208 |
| float64 | 1e-08 | 2 | 3.742 | 3.742 | +0.000 |
| float64 | 1e-12 | 0 | 11.019 | 11.642 | +0.624 |
| float64 | 1e-12 | 1 | 11.019 | 11.227 | +0.208 |
| float64 | 1e-12 | 2 | 4.366 | 4.158 | -0.208 |
| float64 | 1e-16 | 0 | 9.563 | 9.979 | +0.416 |
| float64 | 1e-16 | 1 | 13.306 | 11.642 | -1.663 |
| float64 | 1e-16 | 2 | 4.990 | 4.574 | -0.416 |

## Evidence and limitations

Six float32/epsilon=1e-8 final model hashes exactly replay the parent experiment. All cells reuse that parent's original initial models and splits.

Each trajectory records 51 checkpoints, including actual training-batch target-gradient zero counts before and after the loss-to-model precision boundary. Final counts are independently replayed from all 36 saved models on the recorded CUDA runtime. Intermediate counters remain producer logs, not an independently reloaded trajectory.

Final held-out predictions, margins and float64 cross-entropy are independently recomputed from raw saved tensors by NumPy. Cross-entropy comparisons use relative error with no absolute floor.

The full loss-precision/epsilon grid of supported kernels is covered; the paper's bf16 grid, additional baselines, unspecified architecture/initialization choices and further tasks remain outside this reconstruction. Generalization can depend strongly on seed and implementation choices.

[Source paper, section 6 and Table 1](https://arxiv.org/html/2610.31642v3#S6). The protocol and source hashes define this local study; completed cells are not selected for favorable outcomes.

Downloads: [trajectories](trajectories.csv), [paired endpoints](paired.csv), [protocol](protocol.json), [raw evidence](evidence.json), [final gradient audit](final-gradient-check.json), [source and checkpoints](reproduce.zip).

Publication masters: [editable SVG](accuracy-matrix.svg), [PDF at 183 mm](accuracy-matrix.pdf).

CPU acceptance: `python reference/softmax_matrix/verify.py`. Retraining needs the recorded CUDA runtime and a separately registered output location; the original producer refuses overwrite.

## Methods

### Study design and experimental units

Modular addition modulo 31 uses a 50% training split. Three initialization/split seeds (0, 1, 2) are reused across the loss-precision and epsilon conditions. Both arms in each pair copy identical initial weights. Every run uses 10,000 epochs; checkpoints are logged every 200 epochs. No seeds or cells are excluded and no favorable-outcome stopping rule is applied.

### Architecture, optimizer and precision

A 1-layer, 4-head Transformer of width 64 uses ReLU and no LayerNorm. AdamW uses learning rate 0.001, betas (0.9, 0.98), and weight decay 1. Parameters and model forward remain float32. Only loss-entry logits switch between float32 and float64; the full protocol lists input representation, attention, initialization and decay details that are not specified by the paper.

### Statistical analysis

An experimental unit is a seed-specific training run. The 18 condition-specific pairs share three initialization/split seeds and must not be treated as 18 independent seed replicates. All individual trajectories and final paired differences are reported. There is no significance test, confidence interval or error bar; the study is descriptive and does not estimate a population effect.

### Independent checks and provenance

Raw model tensors and final held-out predictions are checked by an independent NumPy forward path. Final gradients are independently reloaded on the recorded CUDA runtime; intermediate gradient counts remain producer logs. Source, data, protocol, initial state, checkpoint and environment hashes are verified. The original experimental lock is archived unchanged when the local EIDOS release label changes; any dependency/source/marker/hash change still fails that equivalence check.
## Data availability

Original protocols, raw measurements, seed/split identifiers and saved-model
artifacts are available in [the evidence record](evidence.json) and
[the checksummed reproduction bundle](reproduce.zip). Every specified outcome is retained. The repository records code, data
and environment hashes; artifact acceptance can be rerun independently.

## Code availability

Source and tests are included in `reproduce.zip` and in the
[EIDOS repository](https://github.com/Computational-social-science/Eidos).
Follow the bundle README for CPU acceptance and the recorded runtime for retraining.
The original numerical method is attributed to its authors in the references.

## Reporting and submission metadata

This is a technical validation report. Authors, affiliations, funding, author
contributions and competing-interest declarations must be completed by the human
research team before journal submission. No inferred personal or funding metadata
has been supplied. Technical production follows the linked figure and manuscript
guides; scientific suitability and editorial acceptance require separate review.

## References

1. Barron, J. T., Gnanapragasam, D. & Tschannen, M. *A Fix for Softmax and
   Cross-Entropy*, version 3. [arXiv:2610.31642v3](https://arxiv.org/html/2610.31642v3).
2. Nature. [Research figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/).
3. Nature. [Formatting guide](https://www.nature.com/nature/for-authors/formatting-guide).
