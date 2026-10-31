# Exact edit-rate repair

This independent-project adapter checks a metric contract found in the existing
HPAF Unicode forensic report engine. HPAF's `README.md`, line 48, promises
"Normalized Levenshtein distance relative to the original length"; the engine's
edit-rate numerator is an opcode-script cost. Python's `SequenceMatcher` does not guarantee
minimum edit sequences. Preserve that matcher for visual alignment; calculate the
quantitative edit metric separately using unit-cost minimum edit distance.

The producer uses a two-row dynamic program. The independent validator uses
RapidFuzz 3.14.6's explicit C++ Levenshtein backend, with no preprocessing and
weights `(1, 1, 1)`. Exhaustive breadth-first edit graphs qualify that backend
on every ordered pair of binary-Unicode strings of length zero through three.
The producer also runs those 225 pairs, plus ten benign Unicode/edge examples.
Legacy-cost and zero-distance controls must be rejected.

## Reproduce

From this directory, use a dedicated environment:

```sh
uv sync --locked --python 3.12
uv run --no-sync python run.py
uv run --no-sync python verify.py
uv run --no-sync python acceptance.py
```

Commands create new files under `results/` and refuse existing outputs, including
aliases to input files. Use a fresh copy or new output paths for another run;
committed records under `docs/` are historical evidence, not overwritten results.
Use `verify.py --check` for repeated validation without publishing a new record.

For a private corpus, supply the same `--corpus FILE` arguments to both scripts,
and choose separate `--output`/`--evidence` paths. JSON rows require string `goal`
and either `perturbation` or `perturbed_text`. Outputs contain row identifiers,
lengths, metrics and input hashes; they contain no original text. Existing HPAF
code/data are not modified. The public fixture and deliverable contain only
new benign examples and exhaustive short strings, never HPAF's private corpora.

The rate is distance divided by `max(len(source), 1)`, preserving HPAF's original
denominator. It is directional and can exceed one. Units are Unicode code points,
not grapheme clusters; no normalization is performed. Visual opcode alignments
and `SequenceMatcher.ratio()` remain separate descriptive outputs.

This is a retrospective deterministic audit, not preregistered inference. It
establishes neither model attack success, new scientific discovery, population
generalization, nor complete EIDOS functional readiness. Exact code/data/config
and lock hashes bind every result; changed inputs require regeneration.

Sources: [Python difflib contract](https://docs.python.org/3.12/library/difflib.html),
[RapidFuzz Levenshtein API](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html).
