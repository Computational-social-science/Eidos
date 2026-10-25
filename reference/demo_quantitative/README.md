# DEMO · quantitative consumer with a planted truth

The second template, and deliberately unlike the first: no model, no prompt, no text. A linear
model whose effect is known by construction, an honest estimator and a corrupted one, a
quantitative acceptance gate, and a rendered result document.

```bash
python build.py            # measure (1 s) + render (Quarto)
python show_vacuous.py     # a gate that exits 0 and writes nothing must be refused
```

| file | what it teaches |
|---|---|
| `build_evidence.py` | planted truth, coverage, bias, and an acceptance gate with explicit directions |
| `render_results.py` | a result document rendered from source, with `QUARTO_BIN` found by walking up |
| `show_vacuous.py` | the registry's `expects` is what turns "no artefact" into a FAIL |
| `analysis/CLAIMS.yaml` | two claims, each with a control that must fail if the measure is blind |

**Why the control matters.** The corrupted estimator shifts the interval by +0.30 and covers the
planted value in 0.432 of runs against the honest 0.927. If both had looked acceptable, the
measurement would have been unable to distinguish a valid estimator from a broken one — and the
gate would have been decoration.

**Why `out_of_scope` appears here.** There is no prompt to vary, so `prompt_shape` is declared out
of scope with a reason instead of being left blank. That is the S5 branch this demo exists to
exercise.
