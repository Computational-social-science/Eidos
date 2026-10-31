# Softmax training follow-up: reconstruction and exploratory extension

These studies are not an exact reproduction or a novel discovery. The 50,000-epoch extension was designed after inspecting the 10,000-epoch reconstruction. All three seeds and both arms are retained.

The frozen producer files and protocols record initialization, split, optimizer, device and dtype. `verify.py` independently binds the full artifact inventory, raw model tensors, source hashes, initial pairing, final metrics, conditional distillation and parent replay. No desired superiority is required for completion.

## softmax_grokking

paper-aligned reconstruction of one fp32 epsilon setting, followed by conditional distillation; not the full precision/epsilon table

| Seed | Standard test accuracy | Fixed test accuracy | Standard distillation L2 drift | Fixed distillation L2 drift |
|---|---:|---:|---:|---:|
| 0 | 26.611227% | 68.814969% | SKIP: teacher below 95% | SKIP: teacher below 95% |
| 1 | 11.434511% | 10.602911% | SKIP: teacher below 95% | SKIP: teacher below 95% |
| 2 | 4.989605% | 4.158004% | SKIP: teacher below 95% | SKIP: teacher below 95% |

Final-checkpoint gradient endpoint (standard / fixed evaluation at the **same fixed-trained model**):

| Seed | Standard target-gradient zeros | Fixed target-gradient zeros |
|---|---:|---:|
| 0 | 359/480 | 0/480 |
| 1 | 313/480 | 0/480 |
| 2 | 321/480 | 0/480 |

CPU acceptance: `python reference/softmax_grokking/verify.py`. Endpoint provenance: `reference/softmax_grokking/docs/gradient-endpoints.json`.

## softmax_grokking_extension

exploratory 50000-epoch extension; not the paper 10000-epoch protocol

| Seed | Standard test accuracy | Fixed test accuracy | Standard distillation L2 drift | Fixed distillation L2 drift |
|---|---:|---:|---:|---:|
| 0 | 97.297297% | 100.000000% | 1.75510953 | 0 |
| 1 | 18.295218% | 98.544699% | 2.8241244 | 0 |
| 2 | 93.139293% | 97.713098% | 2.62529717 | 0 |

Final-checkpoint gradient endpoint (standard / fixed evaluation at the **same fixed-trained model**):

| Seed | Standard target-gradient zeros | Fixed target-gradient zeros |
|---|---:|---:|
| 0 | 454/480 | 0/480 |
| 1 | 404/480 | 0/480 |
| 2 | 410/480 | 0/480 |

CPU acceptance: `python reference/softmax_grokking_extension/verify.py`. Endpoint provenance: `reference/softmax_grokking_extension/docs/gradient-endpoints.json`.

## Interpretation and limits

The 10,000-epoch reconstruction does not yield a qualified generalizing teacher. The exploratory extension yields three fixed teachers above the prespecified 95% threshold; the standard arm also generalizes strongly for some seeds. This is a small, paired, three-seed result with disclosed reconstruction choices; it supports no universal superiority or paper-wide MATCH claim.

At those three exact initial teachers, the standard distillation path moves the model while the fixed path preserves exact stationarity. This tests an optimizer-level numerical mechanism; it is not a guarantee of better downstream generalization. The endpoint analysis measures target gradients only at final checkpoints and cannot establish a gradient trajectory.

The extension replays all six parent trajectories to epoch 10,000 with exactly matching model state hashes, then continues with the same optimizer in the producer. Original optimizer moments were not separately saved or independently verified.

The homepage Figure 2 remains the independently qualified MLP stationarity case; these follow-up studies are archived separately and are not silently substituted into its curves. Publication and broader claims require a separate review of the paper reconstruction choices.

## Supported precision/epsilon matrix

The separately registered 36-run follow-up is now available in [the complete matrix report](../site/reports/softmax-matrix/report.html). All 18 paired endpoints are retained: fixed CE is higher in 5, lower in 12, tied in 1. Six baseline states exactly replay this parent study. The numerical repair is supported in the measured gradient diagnostics; this reconstruction does not establish a uniform finite-budget generalization benefit or reproduce the paper table. Inspect the disclosed implementation choices before attributing the discrepancy to a scientific mechanism.
