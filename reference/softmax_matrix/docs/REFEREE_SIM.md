# Matrix review scope

## O1. [RESOLVED] Which precision changes?
Only loss-entry logits change precision. Model parameters and forward stay float32; both gradient interfaces are recorded.

## O2. [RESOLVED] Is this the full paper result?
No. Three fixed seeds and supported float32/float64 cover a bounded reconstruction. bf16 is UNQUALIFIED; unspecified architecture choices and all unfavorable results are retained.

## O3. [RESOLVED] Does completion prove superiority or every historical gradient?
No. Acceptance checks inventory, provenance and independent final models/endpoints. Intermediate counters remain producer logs; no population inference or independent trajectory verification is claimed.
